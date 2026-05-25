# 智能问答语义过滤模块设计

> 模块定位：在 `POST /api/v1/teacher/chat` 调用远端 LLM 之前，在本地（云下）
> 做一道语义过滤——拦截无关 / 异常 / 滥用类问题，并对正常问题做实体抽取以
> 增强 prompt。
>
> 状态：设计阶段。本文负责把方案、可行性、依赖、论文支撑落到纸上；脚本和
> 实测指标在落地阶段补。

## 1. 为什么需要本地过滤

当前 `backend/api/teacher.py` 直接把学生输入转发给 deepseek，存在三个问题：

1. **off-topic 请求白白消耗 token**：学生输入“今天天气怎么样”也会被打到
   LLM，对教学没有帮助
2. **滥用风险**：没有任何内容校验层，恶意 prompt 注入直接进入云端
3. **prompt 缺乏结构化上下文**：LLM 拿到的是原始文本，没有任何项目领域
   先验（识别出的工艺、缺陷、参数等）

“云下过滤”做的就是在本地 CPU 跑一道前置流水线，把不该上云的拦住，
把该上云的喂得更准。

## 2. 提议架构：三级级联过滤

```
学生输入  →  Stage 1: FastText 领域分类（焊接 / 非焊接）        延迟 < 5 ms
              ├─ 非焊接 → 直接拒绝（前端显示“请提交焊接相关问题”）
              └─ 焊接 → 进下一级
              ▼
            Stage 2: BERT embedding + One-Class SVM 异常检测     延迟 ~150 ms
              ├─ 远离正常分布 → 标记 suspicious，给 LLM 额外 system prompt 警告
              └─ 在分布内 → 进下一级
              ▼
            Stage 3: BERT-BiLSTM-CRF 焊接领域 NER                延迟 ~200 ms
              ├─ 抽取工艺 / 缺陷 / 参数实体
              └─ 拼到 LLM prompt：
                  "用户输入：{原文}\n识别到的关键实体：{工艺=TIG, 缺陷=气孔}"
              ▼
            转发 deepseek
```

总延迟预算 < 400 ms（CPU），加上 deepseek 远端往返 1-2 s，对“一问一答”
教学场景可接受。

## 3. 各组件可行性分析

### 3.1 FastText 领域分类（Stage 1）

**作用**：二分类“焊接相关 / 无关”，作为最廉价的快速拦截层。

**为什么是它**：
- subword embedding 对 OOV 鲁棒，学生打错字也能识别
- CPU 单条推理 < 5 ms，是流水线里最便宜的一级
- 训练数据需求低：正负样本各几百条就能起步
- 模型小（< 10 MB），打包进发行版无压力

**论文支撑**：
- Joulin, A., Grave, E., Bojanowski, P., Mikolov, T. (2016). *Bag of Tricks for
  Efficient Text Classification.* arXiv:1607.01759. <https://arxiv.org/abs/1607.01759>
  ——FastText 的 text classification 主文献，给出了 CPU 高速 + 精度持平
  深层模型的实验依据。
- Bojanowski, P., Grave, E., Joulin, A., Mikolov, T. (2017). *Enriching Word
  Vectors with Subword Information.* arXiv:1607.04606. <https://arxiv.org/abs/1607.04606>
  ——subword n-gram 的设计依据，解释 OOV 鲁棒性来源。

**项目落地路径**：
- 训练语料：
  - 正样本（焊接相关）：从 `defect_types.py` 的 17 个缺陷类别 + `teacher.py`
    历史对话（如果有持久化）+ 焊接百科 + 教材语料中采样 1000 条
  - 负样本（无关）：从中文通用问答（如 LCCC、中文维基百句）采样 1000 条
- 训练命令：`fasttext supervised -input train.txt -output filter`
- 推理：`fasttext.load_model("filter.bin")` 模块级单例 + `predict(text)`

**风险与降级**：
- 历史对话语料可能不足。降级方案：用关键词命中（焊接 / 焊缝 / 焊条 / 工艺 /
  缺陷 / TIG / MIG 等）当 baseline，FastText 训出来后再切

### 3.2 One-Class SVM 异常检测（Stage 2）

**作用**：用 BERT embedding 在 R^768 空间里训一个“焊接正常问题”的分布支撑域，
把偏离支撑域的输入标 suspicious。

**为什么是它**：
- 异常检测视角更稳：只需要“正常”样本就能训，不用收集“异常”样本
- 解决 FastText 二分类的边界模糊问题——边缘 case（“焊接好学吗”）
  FastText 可能分对也可能分错，但 OC-SVM 在 embedding 距离上是连续的
- 训练样本 500 条就够。`sklearn.svm.OneClassSVM` 现成

**论文支撑**：
- Schölkopf, B., Platt, J. C., Shawe-Taylor, J., Smola, A. J., Williamson, R. C.
  (2001). *Estimating the Support of a High-Dimensional Distribution.* Neural
  Computation 13(7), 1443–1471.
  <https://direct.mit.edu/neco/article/13/7/1443/6488>
  ——OC-SVM 原始论文，给出 ν-parameter 的几何解释。
- Devlin, J., Chang, M.-W., Lee, K., Toutanova, K. (2018). *BERT: Pre-training of
  Deep Bidirectional Transformers for Language Understanding.* arXiv:1810.04805.
  <https://arxiv.org/abs/1810.04805>
  ——embedding 来源。本项目用 `bert-base-chinese` 抽 `[CLS]` 768 维向量。

**项目落地路径**：
- 训练阶段：把 FastText 训练集中的“正样本”灌进 `bert-base-chinese` 抽
  `[CLS]` embedding，丢给 `OneClassSVM(nu=0.05, kernel="rbf", gamma="scale")` 拟合
- 推理阶段：拿到 embedding 算 `clf.decision_function(x)`，结果小于 0 即 suspicious
- ν 参数对应允许的 outlier 比例，初始取 0.05（5% 的训练集会被判为 anomaly），
  做 sweep 选最稳的值

**风险与降级**：
- BERT 推理 100-300 ms（CPU）会拉高总延迟，是流水线最重的一级
- 若性能不达标，降级方案：
  - 用 `sentence-transformers` 的轻量蒸馏模型（如 `paraphrase-MiniLM-L6-v2`，
    22 MB，CPU 推理 < 30 ms）替代 BERT base
  - 或干脆放弃 Stage 2，只保留 Stage 1 + Stage 3

### 3.3 BERT-BiLSTM-CRF 焊接领域 NER（Stage 3）

**作用**：从学生问题里抽出焊接工艺（TIG/MIG/手工电弧）、缺陷（裂纹/气孔/
未熔合等 17 类）、参数（电流/电压/温度）等实体，拼进 LLM prompt 做结构化
上下文增强。

**为什么是这套架构**：
- BERT 提供上下文相关的 token embedding，比纯 word2vec 强很多
- BiLSTM 捕捉序列双向依赖
- CRF 头做标签转移约束（保证 B-X 后面不会跟 I-Y），输出序列合法
- 是 NER 任务的标准工业实现，2018-2022 业内主流

**论文支撑**：
- Huang, Z., Xu, W., Yu, K. (2015). *Bidirectional LSTM-CRF Models for Sequence
  Tagging.* arXiv:1508.01991. <https://arxiv.org/abs/1508.01991>
  ——BiLSTM-CRF 序列标注的奠基论文。
- Devlin et al. (2018) BERT, arXiv:1810.04805（同上）
- Souza, F., Nogueira, R., Lotufo, R. (2019). *Portuguese Named Entity Recognition
  using BERT-CRF.* arXiv:1909.10649. <https://arxiv.org/abs/1909.10649>
  ——BERT 直接接 CRF 在小语料 NER 任务上表现优于纯 BiLSTM-CRF 的实证。
- Lample, G., Ballesteros, M., Subramanian, S., Kawakami, K., Dyer, C. (2016).
  *Neural Architectures for Named Entity Recognition.* arXiv:1603.01360.
  <https://arxiv.org/abs/1603.01360>
  ——BiLSTM-CRF 在 NER 上 SOTA 的早期论文之一。

**项目落地的关键瓶颈：训练数据**

这一级是整套方案最不确定的环节，**必须坦诚标注**：

- 焊接领域中文 NER 数据集**公开可用的几乎没有**，需要自己造
- 标注 500 条 sentence-level NER 训练样本，按 BIO 格式打标，需要 1-2 天人工
- 量小时 CRF 头可能不收敛，得用半监督方法引导

**项目落地路径**（分两阶段）：

阶段 A — 词典 + 规则的 baseline（最快可上线）：
- `defect_types.py` 已经有 17 个缺陷类别的中英文映射，是天然的实体词典
- 工艺词典（TIG/MIG/MAG/手工电弧/CO2/SAW…）+ 参数关键词（电流/电压/速度）手写
- 直接正则 + 词典匹配出实体，覆盖项目 80% 常见问句

阶段 B — BERT-BiLSTM-CRF 微调（数据准备好后再上）：
- 用阶段 A 的输出做弱标注，再人工修正出 200-500 条精标语料
- backbone：`bert-base-chinese`（HuggingFace 上免费）
- LSTM hidden=128 双向 + CRF
- 训练：transformers `Trainer` + `seqeval` 评估，dev F1 达到 0.7 以上才切

**降级方案**：如果数据筹备超时，直接保留阶段 A 词典 NER，stage 3 退化为
关键词增强，但 stage 1/2 仍然有效。

## 3.4 三级各自的数据集要求与获取方案（最关键的一节）

简短答案：**全要数据集，每一级都要**。下面分级列出"需要多少 / 怎么搞到 / 兜底方案"。

### 3.4.1 Stage 1 FastText：领域分类正负样本

**目标量**：每类 800-1500 条，二分类共 ~2000 条

**获取路径**：

| 来源                                 | 估算量    | 成本                                                                |
|--------------------------------------|-----------|---------------------------------------------------------------------|
| `defect_types.py` 17 类缺陷 + `yolo_config.json` 工艺关键词扩问 | 200       | 0，已有词典 + 模板套出来                                            |
| 焊接教材 / 国标 GB/T 19867 等公开标准里的 Q&A | 300       | 半天 PDF 扒一扒                                                     |
| 现有 `teacher.py` 历史日志（如果有持久化）         | 0-500     | 看实际是否持久化，没有就跳过                                        |
| **LLM 自合成**（deepseek/gpt-4 生成）  | 1000+     | 给一个 prompt "你是焊接老师，生成 100 条学生可能问的焊接问题"，分批跑 |
| 中文通用问答负样本（LCCC / 中文 Wiki 句段）      | 1000      | 直接拉公开数据集随机采样                                            |

**风险与解决**：
- LLM 自合成会带语料偏置（措辞偏书面），训出来的模型在真实学生口语化输入上可能掉点。
  缓解：合成时让 LLM 模仿"00 后职校生口语"，多几个 prompt 风格
- 负样本如果都是高质量百科句，模型可能学到"短句焊接 / 长句无关"的伪相关。缓解：负样本
  控制长度分布跟正样本对齐

**兜底**：哪怕只有 200 条正样本，FastText 也能跑起来。先用规则关键词
（焊接 / 焊缝 / 工艺 / TIG / MIG / 缺陷词典命中）做 baseline，FastText 训出来再切。

### 3.4.2 Stage 2 One-Class SVM：单类正常样本

**目标量**：500-1000 条"正常焊接问题"，**不需要负样本**

**获取路径**：直接复用 3.4.1 里的正样本，不需要额外标注。这是 OC-SVM 相比二分类的
最大便宜。

**调参流程**：
1. 把全部正样本切 80/20 train/dev
2. ν ∈ {0.01, 0.05, 0.1, 0.2} sweep，每个 ν 算 dev 集的拒绝率
3. 选拒绝率最接近 ν 的（说明模型 well-calibrated）
4. 用 dev 集 + 200 条人工挑的"边界 case"（"焊机能修电脑吗"这种）看 separability

**兜底**：500 条正样本能拟合的 OC-SVM 比较保守，可能过度拒绝。如果 dev 集错杀率
超 15%，先关掉 Stage 2，只跑 Stage 1 + Stage 3。

### 3.4.3 Stage 3 BERT-BiLSTM-CRF NER：序列标注

**这是整个方案最贵的一级，所以分阶段 A / B 落地**：

**阶段 A（词典 + 规则，0 标注成本）**：
- 工艺词典：`{TIG, MIG, MAG, MMA, 手工电弧, CO2, SAW, FCAW}` + 中英对照
- 缺陷词典：直接用 `defect_types.py` 已有的 17 类
- 参数模式：正则匹配 `\d+\s*(A|安|V|伏|mm|毫米|℃|度)` 抽数值 + 单位
- 这套规则 NER 在项目已知问句上覆盖率应在 70-85%

**阶段 B（BERT-BiLSTM-CRF 微调，需要数据）**：
- 目标量：200-500 条 BIO 格式 sentence-level 标注
- 获取路径（按优先级）：
  1. **半自动标注**：跑阶段 A 在 1500 条问句上自动打 BIO，再人工修正——
     不是从零标，而是改错。1 个人 1 天可处理 300 条
  2. **公开数据集迁移**：CLUENER（清华，2020）是中文通用 NER 数据集，10 个实体类型，
     可以 fine-tune `bert-base-chinese` 出一个"通用 NER 底座"，再在焊接小数据上继续微调
  3. **众包标注**：1 元一条找标注平台，500 条 = 500 元
- 训练：`transformers` Trainer + `seqeval` 评估，目标 dev entity-F1 > 0.7
- 失败标准：如果 entity-F1 < 0.5，回退阶段 A，不切阶段 B

**关键风险**：焊接领域中文 NER **没有公开数据集**，这是核心瓶颈。三条数据获取路径
里只有第 1 条不依赖外部资源，但人工标注是硬成本。如果项目预算 / 时间不够，
就停在阶段 A 词典 NER。

### 3.4.4 端到端测试集（独立，不参与训练）

**目标量**：200-400 条混合样本，确保跟训练集**完全隔离**

**组成**：
- 150 条真实学生问题（如果项目有日志就用，没有就教师手写）
- 30 条边界 case（半相关：焊工待遇、焊接安全规范）
- 20 条 off-topic 注入（明显无关：今天天气、推荐电影）
- 标签：是否应通过 + 期望识别的实体集

**用途**：跑端到端 pipeline，记录拦截率、错杀率、entity 抽取覆盖率。这套数据集
**绝不参与任何阶段的训练**，避免指标虚高。

### 3.4.5 数据筹备的时间成本估算

| 任务                           | 人天 | 关键依赖                |
|--------------------------------|------|-------------------------|
| Stage 1 正负各 1500 条         | 1    | LLM api 可用            |
| Stage 2 调参 sweep             | 0.5  | 数据集准备好后立刻可做  |
| Stage 3 阶段 A 词典 + 正则     | 0.5  | 0 数据成本              |
| Stage 3 阶段 B 半自动标注 500 条 | 2  | 阶段 A 跑过、人工时间    |
| 端到端测试集 400 条            | 1    | 教师参与手写            |
| **合计**                       | 5 人天 | —                       |

如果 5 人天预算不够，**砍法**：跳过阶段 B（NER 退回阶段 A），从 5 人天降到 2.5 人天。
精度上 entity-F1 大概从 0.75 掉到 0.6，但 stage 1/2 不受影响。

## 4. 项目集成方案

### 4.1 后端新增模块

```
backend/services/filter/
├── __init__.py
├── fasttext_classifier.py     # Stage 1
├── ood_detector.py             # Stage 2: BERT embedding + OC-SVM
├── ner_extractor.py            # Stage 3: 词典匹配（A）或 BERT-BiLSTM-CRF（B）
├── pipeline.py                 # 三级串联 + 早停 + 错误兜底
└── artifacts/
    ├── filter.bin              # FastText 模型
    ├── ocsvm.pkl               # OneClassSVM 模型
    └── ner_model.pt            # 阶段 B：微调过的 BERT-BiLSTM-CRF
```

### 4.2 API 接入点

`backend/api/teacher.py::chat`：

```python
@router.post("/teacher/chat")
async def chat(req: ChatRequest):
    pipeline_result = filter_pipeline.run(req.message)
    if pipeline_result.rejected:
        return ChatResponse(
            reply="您的问题似乎与焊接学习无关，请提交焊接相关问题。",
            filtered=True,
            reason=pipeline_result.reason,
        )
    enriched_prompt = build_prompt(
        original=req.message,
        entities=pipeline_result.entities,
        suspicious=pipeline_result.suspicious,
    )
    reply = await deepseek_client.chat(enriched_prompt)
    return ChatResponse(reply=reply, entities=pipeline_result.entities)
```

### 4.3 启动加载

`backend/main.py` 加 startup hook：

```python
@app.on_event("startup")
async def _warm_load_filter_pipeline():
    from services.filter.pipeline import filter_pipeline
    filter_pipeline.warm_up()   # 加载 FastText / OC-SVM / NER 到模块级单例
```

跟 1D-CNN 一样冷启动加载，第一次请求 0 等待。

### 4.4 模型大小估算

| 组件                       | 大小          | 加载时间（CPU）   |
|----------------------------|---------------|-------------------|
| FastText                   | ~10 MB        | < 1 s             |
| `bert-base-chinese`        | ~400 MB       | 3-5 s             |
| OneClassSVM (500 样本)     | < 1 MB        | < 0.1 s           |
| BERT-BiLSTM-CRF NER head   | ~5 MB（fine-tuned 头部）| 复用 bert backbone |

BERT 400 MB 是主要负担——发行版分发要考虑 HuggingFace cache。可以预先把模型
打到 `backend/services/filter/artifacts/bert-base-chinese/` 让安装即可用。

### 4.5 性能预算

| 流水线步骤            | CPU 单条延迟（目标） |
|-----------------------|----------------------|
| FastText 分类         | < 5 ms               |
| BERT embedding        | 100-300 ms           |
| One-Class SVM         | < 10 ms              |
| BERT-BiLSTM-CRF NER   | 100-300 ms           |
| **本地流水线合计**    | **< 500 ms**         |
| deepseek 远端往返     | 1000-2000 ms         |
| **端到端**            | **< 2.5 s**          |

## 5. 待测指标（落地后补脚本）

下面列出落地阶段需要写脚本测量的指标，结果回填到本节：

### 5.1 Stage 1 — FastText 分类

- 数据集：1000 正 + 1000 负，5-fold CV
- 指标：
  - precision / recall / F1（class=焊接 / class=非焊接 分别记录）
  - 单条 CPU 推理延迟 p50 / p95 / p99
  - 模型大小（MB）
- 脚本：`backend/scripts/evaluate_filter_stage1.py`（待写）

### 5.2 Stage 2 — One-Class SVM 异常检测

- 数据集：500 正常 + 200 异常（合成 + 真实负样本）
- 指标：
  - FRR（False Rejection Rate）：正常问题被判为 suspicious 的比例
  - FAR（False Acceptance Rate）：异常问题没被识别的比例
  - ν 参数 sweep：[0.01, 0.05, 0.1, 0.2]
  - 决策函数分布直方图（正常 vs 异常的 separability）
- 脚本：`backend/scripts/evaluate_filter_stage2.py`（待写）

### 5.3 Stage 3 — NER（阶段 A 词典 / 阶段 B 模型）

- 数据集：200 条人工标注的焊接 QA，BIO 格式
- 指标：
  - entity-level precision / recall / F1（按 entity type 分别记录）
  - 工艺 / 缺陷 / 参数三类各自的覆盖率
  - 阶段 A vs 阶段 B 对比表
- 脚本：`backend/scripts/evaluate_filter_stage3.py`（待写）

### 5.4 端到端

- 200 条真实学生问题 + 50 条 off-topic 注入
- 指标：
  - 总流水线延迟 p50 / p95
  - 拦截率（off-topic 被拒绝的比例）+ 错杀率（正常被拒绝的比例）
  - 实体抽取覆盖率（最终 prompt 含 entity 字段的比例）
- 脚本：`backend/scripts/evaluate_filter_pipeline.py`（待写）

## 6. 风险与未决项

1. **BERT 400 MB 体积**：教学场景部署机器一般 100 GB+ 硬盘没问题，但首次启动
   3-5 s 冷加载会被用户感知。已在 startup hook warm-load，运行时无感
2. **NER 训练数据筹备**：核心风险。阶段 A 词典方案是兜底，阶段 B 是“锦上添花”
3. **deepseek 远端不可用时**：filter pipeline 跑通了也没意义。需要在调用前
   先做 health check，远端挂掉时本地返回 fallback 教学建议（标“离线模式”）
4. **One-Class SVM 在小数据集上的鲁棒性**：500 样本可能 ν=0.05 的支撑域过窄，
   需要做 sweep + cross-validation 选参数
5. **本地 CPU 推理跟 deepseek 远端串行**：总延迟 < 2.5 s 对人机交互可接受，
   但如果 deepseek 那边偶尔 timeout 到 5+ s，整体体验会差

## 7. 不做 / 不在本期范围

- **不做强毒性内容审核**：那是另一类问题（NSFW / 违法内容），需要专门数据集
  和模型，本期只做“焊接相关性”过滤
- **不做多轮对话上下文管理**：当前 chat 是无状态单轮，filter 也按单轮处理
- **不做 LLM 输出端过滤**：先做输入端，输出端等 v2

## 8. 论文与可靠数据来源汇总

| 主题                    | 文献                                                                   |
|-------------------------|------------------------------------------------------------------------|
| FastText 分类           | Joulin et al. 2016, arXiv:1607.01759                                   |
| FastText subword        | Bojanowski et al. 2017, arXiv:1607.04606                               |
| BERT                    | Devlin et al. 2018, arXiv:1810.04805                                   |
| BiLSTM-CRF              | Huang et al. 2015, arXiv:1508.01991                                    |
| Neural NER 综述         | Lample et al. 2016, arXiv:1603.01360                                   |
| BERT-CRF NER            | Souza et al. 2019, arXiv:1909.10649                                    |
| One-Class SVM           | Schölkopf et al. 2001, Neural Comp. 13(7):1443                         |
| 蒸馏 sentence encoder   | Reimers & Gurevych 2019, arXiv:1908.10084（sentence-BERT，蒸馏备选）   |
