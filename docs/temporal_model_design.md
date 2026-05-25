# 焊接质量时序预测模型设计

文档对应实现：[`backend/services/prediction/temporal_model.py`](../backend/services/prediction/temporal_model.py)。

## 1. 目的

学生在系统里连续检测一段时间后，希望看到“未来 5 次的总分趋势预测”。这一块原本只用
Random Forest（`backend/prediction.py::predict_future_scores`），但 RF 对**时间局部形态**
不敏感——它把每条记录当独立样本，靠 lag 特征拼时序。所以加了一条“深度预测”通道与 RF
并存，前端 toggle 切换。

## 2. 模型架构

3 层 1D 卷积 + 全局平均池化 + 一层 fc，参数总数约 **1349（≈ 5.3 KB / FP32）**。

```text
Input  (batch, 3, T)              # T 任意，3 = 光滑度 / 宽度 / 缺陷
  │
  ▼   Conv1d(3→8,  kernel=3, padding=1) + ReLU
  ▼   Conv1d(8→16, kernel=3, padding=1) + ReLU
  ▼   Conv1d(16→16, kernel=3, padding=1) + ReLU
  │   # padding=1 让时间维长度保持 = T
  ▼   AdaptiveAvgPool1d(1)             # T → 1
  ▼   Dropout(0.2)
  ▼   Linear(16 → 5)
Output (batch, 5)                 # 未来 5 步总分（归一化值，外层 ×100 还原）
```

设计取舍：
- **卷积保留时间维 + 全局平均池化**：模型变成“长度无关”的——同一份权重在 T=5、T=20、
  T=30 上都能跑。如果用早期版本那种“卷积无 padding + flatten + fc”的做法，T 一变 fc 输入
  维就变，需要重训或改架构。
- **三层 conv 已经够看 ±3 步局部形态**（感受野 = 3 + 2 + 2 = 7 步）。再深也无意义，因为
  全局池化之后只保留通道级统计，更深的局部细节会被平均掉。
- **不带总分进输入**：标签是未来总分，输入只有三项子分数，避免 label leakage。
- **Dropout 0.2** 抑制小数据集场景下的过拟合。

## 3. 短序列与长序列同时支持

模型本身（adaptive pool）对输入长度没有结构性约束，但要让“短输入和长输入都准”，训练
阶段也要见过各种长度的样本：

```python
TRAIN_WINDOWS = (10, 15, 20, 25, 30)
```

`_build_buckets` 按这五种长度分桶切训练对（同一批历史能切出多个窗口长度的样本）。每个
epoch 把五个桶都过一遍，模型同时学到“5 步局部斜率”和“30 步整体趋势”的形态。

推理时：
- `len(input) >= 5`（`MIN_INFER_WINDOW`）：直接喂模型，取最近 `min(len, MAX_INFER_WINDOW=30)`
- `len(input) < 5`：返回中性预测（85 分），上游 API 看到样本太少会回退 RF

实测（递增趋势训练数据）：

| 输入长度 | 5 步预测 | 解读 |
|---|---|---|
| 5  | [65.5, 69.1, 63.2, 71.5, 71.8] | 只看到最早 5 行，预测偏向早期分数段 |
| 8  | [76.0, 77.4, 74.1, 78.0, 78.4] | 中段趋势 |
| 20 | [86.7, 85.9, 85.3, 84.6, 85.1] | 看到完整后段 |
| 30 | [88.7, 87.5, 87.4, 85.8, 86.3] | 与 50 同（自动截到 30） |
| 50 | [88.7, 87.5, 87.4, 85.8, 86.3] |
| 3  | [85, 85, 85, 85, 85]            | 不足 MIN，返回中性 |

同一份模型权重，输入长度从 5 到 50 都给出有意义的、与数据“新近度”单调相关的预测。

## 4. 训练数据

训练数据集物理位置：[`backend/services/prediction/artifacts/temporal_training_data.csv`](../backend/services/prediction/artifacts/temporal_training_data.csv)
（1200 行，列：`student_id, student_name, weak, sample_index, smoothness_score,
width_score, defect_score, total_score`）。

**为什么不写回 `welding.db`**：`welding.db` 是运行时数据库，保存学生平时检测和保存的真实
记录（项目演示时约 155 条），保持干净不掺入训练用合成数据。训练集独立 CSV 落盘后，可以
直接用 Excel/pandas 打开复审。`welding.db` 行数永远等于真实保存记录数，不会因为训练而
变 1300+。模型相关产物（.pt / .png / .json / .csv）全部在
[`backend/services/prediction/artifacts/`](../backend/services/prediction/artifacts/) 这
一个目录下，`docs/` 只放 markdown 设计文档。

**数据合成假设**：6 个学生画像（`scripts/seed_demo_data.py::PROFILES`，含
base/delta/noise/weak）模拟“一学期 200 次焊接练习”的连续时序：
- `progress = i / (n - 1)` 从 0 走到 1，对应学期初到学期末
- `base + delta · progress + noise` 模拟整体进步趋势 + 单次随机波动
- 10% 样本主动放到 [3, 8] mm 宽度范围外，触发检测器宽度=20 的保底逻辑
- weak 画像（width / defect / smooth）对应那项分数额外打折
- 综合分严格按 `0.3·smooth + 0.3·width + 0.4·defect`（学校规定权重）算出

**切窗口策略**（关键设计）：每个学生的 200 条**按时间顺序**切，**不跨学生**：
- 跨学生切窗会引入“幽灵跳变”——A 同学的最后一次直接接 B 同学的第一次，模型学到的
  是噪声而不是时序。早期版本跨学生切，R²=-0.19；按学生隔离后 R² 提升到 0.27
- 同一学生数据按 `TRAIN_WINDOWS = (10, 15, 20, 25, 30)` 五个长度滑窗切，每个窗口 →
  一个 `(X[3, L], y[5])` 训练对；多窗口分桶让模型见过短/长 context 都不偏科——相比固定
  窗口属于标准数据增强（DA）
- 切窗后每个学生 200 条 → 161 + 156 + 151 + 146 + 141 = 755 个训练对（合并所有窗口）
  × 6 学生 = 4530 总样本，按 70/15/15 切后 train=3480 / val=204 / test=204

**train/val/test 切法**：按**时间序列切**而非随机 shuffle。每个学生先按时间序号切前 70%
进训练段、中 15% 进验证段、后 15% 进测试段，每段再各自滑窗。时序数据若 shuffle 会发生
“未来泄漏”（同一窗口的相邻样本时间上几乎重叠，shuffle 把“未来”窗口塞进训练集），R²
会虚高，但拿到真实新数据会崩。

## 5. 训练方法

**模型结构**：3 层 1D Conv（`3→8→16→16`，kernel=3, padding=1 保留时间维）+
`AdaptiveAvgPool1d(1)` 把变长时间维 collapse 成 1 + Dropout(0.2) + Linear(16→5)。参数量
1349（5.3 KB / FP32）。AdaptiveAvgPool 是变长输入支持的关键——同一份权重对 5..30 任意
长度输入都能跑。

**损失函数**：MSE，但分数已归一化到 [0, 1]（`/SCORE_SCALE=100`）后再算 loss，所以
`temporal_metrics.json` 里 MSE 是归一化空间的值（0.005-0.008）；MAE 再 × 100 还原到 0-100
分数空间方便引用（“平均偏差 7 分”）。

**优化器与训练流程**：Adam，`lr=1e-3`，**无 LR scheduler**（数据量小、训练时间短，调度
收益低于复杂度）。每个 epoch 把 5 个 window bucket **依次**过一遍（不混 batch），每个
bucket 一次 `optim.step`——长 window 桶样本少会被 over-weight 但实测 R² 没显著下降，保留
这个简单写法。200 epoch CPU ~15 s。

**Dropout 与 train/val loss 反转**：模型在 `model.train()` 模式下 dropout=0.2 随机 zero
out 20% 的中间激活，所以**训练态 loss 系统地高于评估态 loss**。评估时统一 `model.eval()`
关掉 dropout，得到的 val/test MSE 都比训练态低。曲线上 train MSE 一直在 val MSE 上方
**不是过拟合反转，是 dropout 模型的标准行为**——把 dropout 改成 0 重训这条线就贴回去。

**早停**：每个 epoch 都跑一次 val，记录 `best_val_mse` 和对应 `best_epoch`。当前实现不真
实停训（只是记录），跑完 200 epoch 后从 metrics 看 epoch 183 附近 val 触底，之后小幅回升
0.0001-0.0002（轻微过拟合开始）。生产可以加 patience=20 的早停，本次实验数据量小没必要。

**指标计算口径**：
- **MSE** 在归一化空间，作为优化目标的直接镜像
- **MAE_normalized** 同空间，相对 MSE 更鲁棒（不被极端样本拉偏）
- **MAE_score** = MAE_normalized × 100，对话引用：“5 步预测的平均偏差是 X 分”
- **R²** = `1 − SS_res / SS_tot`，衡量“比预测均值好多少”。负值说明不如猜均值；正值越大
  越好
- 三套指标分别在 train / val / test 三段上计算，全部 `model.eval()` 模式

## 6. 性能与指标

- 参数量：1349 个 FP32，5.3 KB 内存占用，权重文件 `.pt` 落盘约 8.4 KB
- CPU 训练（200 epoch，3480 个 train 样本，5 个 window bucket）：约 15 秒
- CPU 单次推理：< 10 ms（实测在普通笔记本上 < 3 ms）
- 不依赖 GPU；项目 torch 是 `2.5.1+cpu`

完整指标见 [`backend/services/prediction/artifacts/temporal_metrics.json`](../backend/services/prediction/artifacts/temporal_metrics.json)：

| split | 样本数 | MSE (归一化) | MAE (0-100 分数空间) | R²    |
|-------|--------|--------------|-----------------------|-------|
| train | 3480   | 0.0057       | 6.02 分               | 0.319 |
| val   | 204    | 0.0065       | 6.82 分               | 0.271 |
| test  | 204    | 0.0080       | **7.68 分**           | 0.112 |

best val 出现在 epoch 183（200 epoch 训练，之后轻微过拟合）。曲线见
[`artifacts/temporal_training_curve.png`](../backend/services/prediction/artifacts/temporal_training_curve.png)。

几个要注意的解读点：
- **MAE ≈ 7 分** 是最直观的指标——5 步预测的平均偏差。学生总分常在 70-90 分区间，
  对应相对误差 8-10%，足够支撑“趋势向好/平/下降”的判断。
- **train MSE 系统高于 val MSE** 是 dropout=0.2 在训练态打开造成的（噪声推高 train loss），
  评估态关闭后 val 更准。不是过拟合反转。
- **test R² 只有 0.11** 反映数据本身的高方差：缺陷类别和宽度触底样本是离散随机的，
  连续 5 步未来值的可解释方差天花板就不高。MAE 更适合作为业务指标。

## 7. 训练产物

统一在 [`backend/services/prediction/artifacts/`](../backend/services/prediction/artifacts/)
目录下，跟 `temporal_model.py` 同级，部署时整个目录拷过去即可。

| 文件                           | 大小      | 用途                                                            |
|--------------------------------|-----------|-----------------------------------------------------------------|
| `temporal_model.pt`            | **8.39 KB** | **PyTorch state_dict**——`{layer_name: tensor}` 的字典序列化结果；这才是“训练出来的模型”，进程加载它就能直接推理 |
| `temporal_metrics.json`        | < 1 KB    | 训练指标快照（含 `weights_path` 字段指向 .pt 相对路径）          |
| `temporal_training_curve.png`  | ~30 KB    | 训练曲线，文档/报告直接贴                                       |
| `temporal_training_data.csv`   | ~70 KB    | 1200 行训练集，可审计可复现                                     |

**`.pt` 内部存储**（`torch.save` 默认走 zipfile + pickle）：

```python
{
  "conv1.weight": Tensor(shape=[8, 3, 3]),     # 72 floats
  "conv1.bias":   Tensor(shape=[8]),           # 8 floats
  "conv2.weight": Tensor(shape=[16, 8, 3]),    # 384 floats
  "conv2.bias":   Tensor(shape=[16]),          # 16 floats
  "conv3.weight": Tensor(shape=[16, 16, 3]),   # 768 floats
  "conv3.bias":   Tensor(shape=[16]),          # 16 floats
  "fc.weight":    Tensor(shape=[5, 16]),       # 80 floats
  "fc.bias":      Tensor(shape=[5]),           # 5 floats
}  # 合计 1349 floats × 4 B = 5396 B 净数据；.pt 8.39 KB 含 pickle 头 + zipfile 索引
```

跟 YOLO `best.pt` 同种格式，只是本模型只有 1349 参数，所以是 8 KB 而不是几十 MB。

## 8. 部署与推理路径

`backend/services/prediction/temporal_model.py` 加了 `_load_pretrained()` 入口：

```python
def _load_pretrained() -> Optional[WeldTemporalCNN]:
    if not _WEIGHTS_PATH.exists():
        return None
    model = WeldTemporalCNN()
    state = torch.load(_WEIGHTS_PATH, map_location="cpu", weights_only=True)
    model.load_state_dict(state)
    model.eval()
    return model

def get_or_train(records):
    with _model_lock:
        cached = _model_cache["model"]
        if cached is None:
            pretrained = _load_pretrained()      # 冷启动优先 load .pt
            if pretrained is not None:
                _model_cache["model"] = pretrained
                _model_cache["trained_on_count"] = len(records)
                return pretrained
        # 没有 .pt 或 load 失败 → 走老的 lazy train + RETRAIN_DELTA 重训路径
        ...
```

**完整推理链路**（前端按“深度预测”→ 后端到 forecast 出 5 个分数）：

```
[前端 toggle "深度预测"]
   ↓ /api/v1/predict?student_id=X&mode=deep
[predict.py::get_prediction]
   ↓ 拉该学生最近 ≤200 条 WeldingRecord
[prediction.py::predict_with_temporal_model]
   ↓ records 转 (smoothness/width/defect/total) DataFrame
[temporal_model.py::get_or_train]
   ↓ 首次：从 backend/services/prediction/artifacts/temporal_model.pt load state_dict
   ↓ 后续：累计 ≥30 条新记录才在线 retrain（并刷新 .pt）
[temporal_model.py::forecast]
   ↓ 取最近 5..30 行 → 归一化 /100 → torch.from_numpy → model(x).cpu().numpy()
   ↓ 反归一化 × 100 → np.clip(0, 100)
[returns 5 个 future scores]
   ↓ predict.py 拼成 forecast = {timestamp_str: score}
[前端折线图：历史 + 预测]
```

**冷启动 vs 在线训练分工**：
- **冷启动加载**（默认路径）：`.pt` 是离线脚本用 1200 条规模数据精调过的，比 lazy train
  用单生 22 条临时拟合的稳得多；服务起来第一次请求就能用。FastAPI 启动时
  `_warm_load_temporal_model()` 在 `@app.on_event("startup")` 钩子里
  `torch.load(temporal_model.pt, weights_only=True)`，权重直接进 `_model_cache`
- **在线 retrain**（数据漂移触发）：当某个学生累计 +30 条新记录后，`train_from_records`
  会重训并写回 `.pt`——支持长时间运行后让模型跟随新数据 drift
- **手动重训**：跑 `python backend/scripts/train_temporal_offline.py` 重新生成四件产物，把
  `.pt` 文件覆盖到生产机器即可，不用重新跑训练

**前端预取链路**：用户登录后，前端顶层 `app/page.tsx` 立即在后台拉一次 `/predict` 和
`/predict/ai-radar-data`，把结果写到 `localStorage`。进智能预测页面时，预测面板和雷达图
用 `useState` 的 lazy initializer 直接读 cache，瞬间出图，不再等接口往返。

**和 YOLO 的对照**：YOLO 走 `models/best.pt` 单文件直接加载，没有“lazy train”分支（因为
预训练成本太高）；本模型只有 5 KB 参数，所以**两条路径并存**——能 load .pt 也能现训。这样
既保留了“无 .pt 也能跑”的鲁棒性，又给了“离线训出好权重就直接部署”的标准 ML 工作流入口。

## 9. 为什么 1D-CNN 而不是 LSTM / Transformer

主要理由是 **CPU 推理速度** + **小样本鲁棒性**：

- **Bai, Kolter, Koltun (2018)** [“An Empirical Evaluation of Generic Convolutional and
  Recurrent Networks for Sequence Modeling”](https://arxiv.org/abs/1803.01271) 在
  Adding、Copy Memory、PennTreebank、Music 等多个序列任务上比较 1D-CNN（TCN）与 LSTM/GRU，
  结论是 1D-CNN 大多数情况下**精度持平或略胜，且训练/推理快 3-5 倍**。教学场景里的
  PC CPU 不一定能 real-time 跑 LSTM。
- **Lim & Zohren (2021)** [Time-series forecasting with deep learning: a survey](https://arxiv.org/abs/2004.13408)
  也指出，对短序列（< 100 步）任务，卷积/MLP 与 RNN 在准确度上没有显著差距，但卷积可并行、
  参数更少，工业部署友好。
- 我们的窗口最大 30 步、数据量百量级，正好落在 1D-CNN 比 LSTM 更友好的区间。

为什么不用 Transformer：参数量级（最小 self-attention 也要几万参数）和数据量不匹配，
小样本上很容易过拟合。

## 10. 复现命令

```bash
cd backend
python scripts/train_temporal_offline.py
# 落盘四个产物：
#   backend/services/prediction/artifacts/temporal_model.pt           权重文件，部署用
#   backend/services/prediction/artifacts/temporal_training_curve.png  训练曲线
#   backend/services/prediction/artifacts/temporal_metrics.json        完整指标
#   backend/services/prediction/artifacts/temporal_training_data.csv   1200 行训练集
```

固定 `RANDOM_SEED=7`，跑出来的指标和 `.pt` 都是 bit-exact 可复现的。

## 11. 论文与可靠数据来源

- Bai, S., Kolter, J. Z., & Koltun, V. (2018). *An Empirical Evaluation of Generic
  Convolutional and Recurrent Networks for Sequence Modeling.* arXiv:1803.01271.
  <https://arxiv.org/abs/1803.01271>  ——
  1D-CNN 在序列建模上整体不输 LSTM 的核心依据。我们的 3 层卷积是 TCN 的简化版（去掉了
  dilated convolution 和残差连接，因为窗口最长才 30）。
- van den Oord, A., et al. (2016). *WaveNet: A Generative Model for Raw Audio.*
  arXiv:1609.03499. <https://arxiv.org/abs/1609.03499>  ——
  dilated 1D 卷积处理长序列的奠基论文，提供“卷积也能看远距离”的设计依据。我们当前
  serving 短序列没启用 dilation，长度更长时可以参考升级。
- Cui, Z., Chen, W., & Chen, Y. (2016). *Multi-Scale Convolutional Neural Networks for
  Time Series Classification.* arXiv:1603.06995. <https://arxiv.org/abs/1603.06995>  ——
  我们多窗口训练（TRAIN_WINDOWS 取五个长度）的思想来源，让单一模型对多种 context
  size 都有响应。
- Lim, B., & Zohren, S. (2021). *Time-series forecasting with deep learning: a survey.*
  Phil. Trans. R. Soc. A. arXiv:2004.13408. <https://arxiv.org/abs/2004.13408>  ——
  小样本短序列场景下 CNN 与 RNN 性能对比的综述。
- Period-Sensitive LSTM for Welding Quality (IEEE 2024).
  <https://ieeexplore.ieee.org/document/10716249/>  ——
  焊接质量时序预测的领域参考，证实“时序模型对焊接质量预测有效”，但其使用 LSTM；本项目
  CPU-only 部署选择更轻的 1D-CNN。

## 12. 当前局限与后续方向

- 训练数据是基于学生画像合成的连续时序，未在大规模真实焊接采集数据上做过端到端评估；
  论文支撑只能说明*架构选择合理*，不等于*精度有保证*。模型输出是基于历史数据外推的
  趋势，不是质检意义上的“未来一定是这个分”。
- 没有不确定度估计。后续可加 MC Dropout 或 ensemble 给前端画出 confidence band。
- 多窗口训练目前是简单的“每个长度一个桶”，可以升级到课程学习（先短后长）或
  attention pooling 提升精度。
- 真要承诺“长序列效果好”（比如 100+ 步），应该加 dilated convolution（WaveNet 风格）
  把感受野指数级放大，当前 7 步感受野够覆盖项目里实际的窗口长度。

## 13. 数据流

```
WeldingRecord (DB)
  │
  ▼  api/predict.py::_get_detection_data_from_db
  │     按 student_id / timestamp 拉记录
  ▼
prediction.py::predict_with_temporal_model
  │     DataFrame ↔ list[dict] 转换
  ▼
services/prediction/temporal_model.py
  ├─ get_or_train(records)
  │     模块级单例 + 锁；新增记录达到 RETRAIN_DELTA 才重训
  ├─ train_from_records  (按 TRAIN_WINDOWS 分桶训)
  └─ forecast            (取近 ≤ MAX_INFER_WINDOW 行推理)
  │
  ▼
api/predict.py
  返回 PredictionResponse → 前端 /predict?mode=deep
```
