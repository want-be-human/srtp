# 焊育智眸 国赛执行计划（2026-05-22 v4）

> v4 修订：v3 列出的 D4/D5/D6（教学严格模式、TTS、标准对齐文案）和原 Phase E（缺陷热图独立项）全部废弃，
> 替换为一组针对队友反馈 + 硬约束的检测/预测算法升级。
> 触发原因：队友反馈 YOLO 全画面误检、轻量模型置信度抖、焊缝拟态逻辑差；
> 同时确认两条硬约束：（1）检测方式只有单目 RGB 摄像头，无激光/X 光/声学/深度传感器；
> （2）综合评分公式 `0.3·光滑 + 0.3·宽 + 0.4·缺陷` 是学校规定，权重不可改。

冻结日：2026-05-28（国赛）。本文最后修订：2026-05-22。

---

## 1. 责任分工

| 工作项 | 实际负责人 |
|---|---|
| 决策、验收、对接需求 | 用户 |
| 实物硬件（接线、调光、装相机） | 用户 |
| 3D 重构展示（建模 + 资产） | 团队其他成员 |
| 原规划 P0/P1（除 3D 外） | 团队其他成员 |
| 有线摄像头接入（代码侧 + 联调） | Claude |
| 原规划 P2（演示登录 + 学生归属 + 数据树 PK + 学生对比页） | Claude |
| Phase D 演示侧增强（D1-D3） | Claude（已完成） |
| **Phase E 检测/预测算法升级（v4 新增）** | **Claude** |

> Claude 不主动接 P0/P1 工作。如果在做自己范围内的代码时发现 P0/P1 的明显问题，告知用户、由用户分配。
> 之前 simplify 阶段顺带做掉的局部修复属于既成事实，已推送、不回滚。

---

## 2. 阶段排序

### Phase A — 深度 /simplify（已完成大部分）

**已完成并双推**：

| commit | 内容 |
|---|---|
| `a62332d` | teacher.py 单例 + timeout + fallback；defect_name_safe；score 夹取；删 mock；URL 统一 |
| `08e796f / 87cafc9 / 1877d50 / 421cdab` | 文档：PROJECT_MEMORY / STRUCTURE_REPLAN / EXECUTION_PLAN |
| `d8299f0` | Batch 1：删 pnpm 锁文件、雷达 mock 兜底加示例数据角标、lesson mock 瘦身 |
| `1946aa5` | YOLO 加载链：torch.load monkey-patch + dill 依赖 |
| `57ca65c` | yolo_config.json 真正接通到 IntegratedWeldDetector |

**Phase A 还剩**（穿插完成即可）：
- A5 `.gitignore` 补 `__pycache__/`、`*.pyc`、`welding.db`；`git rm --cached` 把这些从追踪里清掉
- A6 后端测试脚本 `simple_test.py / test_api.py / test_types.py / check_db.py` 迁到 `backend/tests/` 并修 import

### Phase B — 有线摄像头接入（已完成）

- ✅ B1 摄像头来源配置化：`NEXT_PUBLIC_CAMERA_URL` + `srtp:camera_url` + 齿轮按钮、`storage.ts` 命名空间

### Phase C — 原规划 P2（已完成）

- ✅ C1 学号+密码登录（bcrypt、`/login` 路由、AuthContext）
- ✅ C2 学生数据归属（save_score 接通 AuthContext）
- ✅ C3 数据树用户隔离（按 student_id 过滤 + localStorage 持久化）
- ✅ C4 学生对比页 / PK 视图（含双数据树并排）
- ✅ C5 检测态跨模块保活（state 上提到 WeldingDetectionSystem）
- ✅ C5.1 后端 AI 调用异步化（`await asyncio.to_thread`）
- ✅ C6 预测端点按学生过滤 + 取消 30 条上限

### Phase D — 演示侧增强（D1-D3 已完成；D4/D5/D6 v4 废弃）

**已完成**：
- ✅ D1 演示降级模式（`srtp:demo_safe_mode` + 本地视频/缓存数据）
- ✅ D2 删 `/predict/ai-radar-data` mock，改为 DB 真实聚合
- ✅ D3 演示数据预播种（`seed_demo_data.py`：6 个学生 × 18-25 条历史、不同短板画像）

**已废弃（v4 删除）**：
- ~~D4 教学/严格模式切换~~ — 涉及综合评分权重，与学校规定冲突，撤掉
- ~~D5 TTS 重要事件播报~~ — 不属于算法层面创新，国赛 7 天内优先把精力放算法升级
- ~~D6 标准对齐文案~~ — 由用户自行在 PDF/讲稿中加，不需要代码改动

### Phase E — 检测/预测算法升级（v4 新增，替代旧 D4-D6 + 旧 Phase E）

**触发**：队友反馈检测模块三大痛点 + 两条硬约束（单目 RGB / 固定权重）。
**通则**：综合评分公式 `0.3·光滑 + 0.3·宽 + 0.4·缺陷` 不动；只改单项分数的"内部计算公式"、检测推理侧、雷达图维度定义、预测算法。

#### P0 — 必修，预计 1.5 天（修语义 bug + 立刻消除"分数抖"投诉）

- **E-P0-1 时序融合 + EMA + IoU 跟踪**（替代 v3 中"立刻改善置信度"诉求）
  - 文件：`backend/api/yolo_realtime.py::inference_loop`
  - 维护近 5 帧 detections 滑动窗口，**同类缺陷在窗口内 ≥ 3 次才算"确认缺陷"**，瞬时单帧噪声丢弃
  - 总分 EMA 平滑：`smoothed = 0.4·new + 0.6·smoothed`，前端折线不再跳
  - 前后帧检测框 IoU > 0.3 关联为一个 track，按 track 维度取 confidence 中位数
  - 依据：[Lightweight Multi-Frame Integration arxiv 2506.20550](https://arxiv.org/html/2506.20550v1)、[MR2-ByteTrack arxiv 2404.11488](https://arxiv.org/pdf/2404.11488)

- **E-P0-2 修预测时间轴语义（time → attempt_index）**
  - 文件：`backend/prediction.py::predict_future_scores`、`backend/api/predict.py::get_prediction`
  - 现状把 `day_of_year/hour` 当特征、按"天"外推 5 天，但实际数据是按"检测次数"采样的（一节课能采 20+ 次）
  - 改成把 `t` 换成 `attempt_index` 整数序号，外推时直接 `last_index + 1..5`
  - 前端折线 X 轴标签换成"第 N 次检测"
  - 文件：[front/components/prediction/prediction-dashboard.tsx](front/components/prediction/prediction-dashboard.tsx)

- **E-P0-3 雷达 6 维洗白**（去派生公式）
  - 文件：`backend/api/predict.py::_aggregate_radar`
  - 现状 6 维中 3 维是 `(smooth+width)/2`、`defect·0.6+smooth·0.4`、`total·0.92` 这种凑数公式，评审一眼看出
  - 改成 6 维真实可观测：
    | 维度 | 计算方式 |
    |---|---|
    | 光滑度均值 | `avg(smoothness_score)` |
    | 宽度准度 | `100 - avg(|actual_width - 6.0|) * 10` |
    | 缺陷控制 | `avg(defect_type_score)` |
    | 宽度稳定性 | `100 - std(spacing_score) * 2`，钳到 [0,100] |
    | 进步速率 | `avg(后 10 次) - avg(前 10 次)` 归一化 |
    | 缺陷集中度 | `100 - (distinct_defect_types / 7) * 100` |
  - 注意：这是雷达图，不是综合评分权重，不冲突学校规定

#### P1 — 主创新，预计 3 天（解决队友三大投诉）

- **E-P1-1 焊缝 ROI 引导（HSV 高光抑制 + 形态学带状 + 动态 ROI）** ⭐ 主创新点 1
  - 文件：新建 `backend/services/yolo/weld_roi.py`，`zonghe_hanjie_zhiliang_jiance_xitong.py::detect_defects` 调用
  - 三段式：
    1. HSV 高光抑制：V 通道 `clip(V, V_thresh)`，把过曝白斑压回中亮度，消除"焊渣反光被当成焊缝"的拟态根因
    2. 形态学带状提取：Otsu 二值化 → 闭运算（kernel 21×3 长条）→ 最大连通域 → PCA 算主方向 θ
    3. 动态 ROI：上一帧 ROI 膨胀 15 像素作为本帧 search region，第一帧用全图
  - YOLO 推理：ROI 外像素乘 0.3 衰减（不置黑，避免人为强边缘），检测后丢弃中心点落在 ROI 外的框
  - 副产物：焊缝主方向 θ 可作为"焊接走向稳定性"指标
  - 依据：[Dynamic ROI Seam Extraction MDPI Sensors 2025 PMC12157130](https://pmc.ncbi.nlm.nih.gov/articles/PMC12157130/)、[Passive Vision Weld ROI MDPI Sensors PMC12736899](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12736899/)、[Specular Highlight Removal MDPI Mathematics 2024](https://www.mdpi.com/2227-7390/12/16/2578)

- **E-P1-2 宽度检测复用 ROI + 拟态过滤** ⭐ 解决"焊缝拟态" bug
  - 文件：`backend/services/yolo/kuandu_jiance_qiqi.py::PreciseWeldDetector`
  - 现状 `enhanced_weld_detection` 只在全图中心 1/3 找最亮行 + 5% 银白色扩边，焊渣反光带就会被当成焊缝
  - 改为：
    1. 走 E-P1-1 同一个 ROI mask，宽度只在 ROI 内找
    2. 候选行加"连续性验证"：检测行两侧 ±20 像素必须有连续的暗-亮-暗梯度（焊缝两侧应该是基板），过滤孤立亮斑

- **E-P1-3 单目宽度的「参考物一次性标定」** ⭐ 解决"15cm 写死"硬伤
  - 文件：新建 `backend/api/calibration.py`、新建 `front/components/settings/camera-calibration.tsx`、`backend/models.py` 加 `CameraCalibration` 表
  - 现状 `image_height_cm=15.0` 硬编码在 `PreciseWeldDetector` 构造函数，`pixels_per_cm = height / 15.0` 等于完全没标定，宽度 mm 值是"假装的 mm"
  - 流程：
    1. 设置页加"摄像头标定"按钮，要求拍一张含已知长度参考物（标定卡 / 钢直尺）的图
    2. 前端 canvas 上点击参考物两端、输入真实长度（如 50mm）
    3. 后端算 `pixels_per_mm = pixel_distance / real_distance`，存到 SQLite `camera_calibration(camera_id, pixels_per_mm, calibrated_at)`
    4. `PreciseWeldDetector` 启动时优先读 DB 标定值，未标定走旧 fallback + 前端提示"未标定，宽度为估算值"
  - 评审会问的硬伤，必修
  - 依据：[Measuring Planar Objects with Calibrated Camera (MathWorks)](https://www.mathworks.com/help/vision/ug/measuring-planar-objects-with-a-calibrated-camera.html)、[NIST IR 7197 Camera Calibration](https://nvlpubs.nist.gov/nistpubs/Legacy/IR/nistir7197.pdf)、[GMAW Real-Time Weld Bead Width PMC5038773](https://pmc.ncbi.nlm.nih.gov/articles/PMC5038773/)

#### P2 — 增强，预计 2.5 天

- **E-P2-1 1D-CNN 时序预测**（创新点 2）
  - 文件：新建 `backend/services/prediction/temporal_model.py`、`backend/prediction.py` 增加 `predict_with_temporal_model`
  - 在 RandomForest 之外加 1D-CNN：3 个 conv1d + 1 个 fc，参数 < 50KB，输入近 30 次 `[smooth, width, defect]` 序列，输出未来 5 次
  - 训练数据：`seed_demo_data` 已有的 130 条 + 真实采集（启动脚本里增量训练）
  - 前端 toggle"快速预测 / 深度预测"切换两条曲线
  - 为什么不用 LSTM：教学场景 PC CPU 推理优先，1D-CNN 比 LSTM 快 3-5×，短序列效果几乎相同
  - 依据：[Period-Sensitive LSTM IEEE 2024](https://ieeexplore.ieee.org/document/10716249/)

- **E-P2-2 光滑度 GLCM 纹理 + 高光抑制** ⭐ 修过曝白板满分 bug
  - 文件：`backend/services/yolo/guanghuadu_jiance_qiqi.py::WeldingQualityScorer`
  - 现状只看 white/gray/black 比例，过曝白板直接 90+
  - 改为：
    1. 先做 HSV 高光抑制（复用 E-P1-1）
    2. 在抑制后灰度图上算 GLCM 对比度 + 局部 5×5 方差
    3. `score = 0.4·brightness + 0.4·(1 - normalized_GLCM_contrast) + 0.2·(1 - normalized_variance)`
  - 只改"光滑度子分数"算出方式，最外层 0.3 综合权重不动

- **E-P2-3 TTA 仅在按键保存时启用**
  - 文件：`backend/api/yolo_realtime.py::save_score`、`backend/services/yolo/zonghe_hanjie_zhiliang_jiance_xitong.py` 加 `detect_defects_with_tta`
  - 实时流保持单次推理 6 FPS；用户按键保存时对当前帧做 3 路 TTA（原图 + 水平翻转 + 多尺度 0.83/1.0/1.2），NMS 合并
  - 入库分数比实时显示分数更稳
  - 依据：[Ultralytics TTA Tutorial](https://docs.ultralytics.com/yolov5/tutorials/test_time_augmentation)

#### P3 — 余力做（教学侧亮点 + 体验优化）

- **E-P3-1 缺陷热图**（原 Phase E 单独项整合进来）
  - 文件：`backend/models.py` 加 `WeldingRecord.defect_bboxes` JSON 列（非破坏性迁移）
  - `save_score` 多存 `[[x,y,w,h,cls,conf], ...]`
  - 前端学生页新增「缺陷热点图」：把该学生历次检测的 bbox 中心点叠在一张焊缝示意图上画 KDE 热图

- **E-P3-2 AI 分析 schema 重试**
  - 文件：`backend/ai_analysis.py`
  - 现状一次失败就直接 fallback，演示体验差
  - 改为：第一次失败时把"上次输出无法解析为 JSON，请严格按 schema"加到 user message，重试 1 次；2 次都失败再 fallback
  - prompt 里附带 `severity_map`（`defect_types.py::get_severity_level`），AI 知道严重缺陷类别，建议会更具体
  - pydantic 模型校验返回字段齐全度

#### 工作量汇总

| 优先级 | 任务数 | 累计工作量 |
|---|---|---|
| P0 | 3 | 1.5 天 |
| P1 | 3 | 3 天 |
| P2 | 3 | 2.5 天 |
| P3 | 2 | 2 天 |
| **合计** | **11** | **9 天** |

7 天到冻结日：P0 + P1 + P2 必修（共 7 天），P3 视余力。

### Phase F — 冻结

- 2026-05-27：只修 bug，不加功能；连跑 3 遍演示
- 2026-05-28：打包备份（比赛电脑、U 盘、云盘）
- 演示注意事项：
  - **不要用 `npm run dev` 跑演示**。dev server 冷启动会按需编译路由，首次访问可能返回 `_not-found` 404。务必用 `npm run build && npm run start`
  - 生产构建后预热一遍：浏览器先访问 `/login` 和 `/`

---

## 3. 决策摘要

### v3 决策（2026-05-19，部分被 v4 覆盖）

| # | 议题 | 决策 | v4 状态 |
|---|---|---|---|
| 1 | 3D 路线 | 不由 Claude 负责 | 保留 |
| 2 | TTS 播报 | 做 | **v4 撤销**（不属于算法创新） |
| 3 | 教学/严格模式切换 | 做 | **v4 撤销**（涉及综合评分权重，与学校规定冲突） |
| 4 | 演示降级模式 | 做 | 保留（D1 已完成） |
| 5 | 标准对齐叙事 | PDF + 讲稿 | **v4 撤销**（用户自行写，不需代码改动） |
| 6 | 演示数据预播种 | 做 | 保留（D3 已完成） |
| 7 | `/predict/ai-radar-data` mock | 删 | 保留（D2 已完成） |
| 8 | 缺陷空间标注 / 热图 | 最低优先级 | **v4 整合进 E-P3-1** |
| 9 | 中英切换 | 不做 | 保留 |
| 10 | 演示登录 | 新建导航 | 保留（C1 已完成） |
| 11 | STRUCTURE_REPLAN 拆分 | 同意 | 保留 |
| 12 | 任务流 | simplify → 原 P2 → 提案剩余 → 热图 | **v4 调整**：simplify → 原 P2（C 完成）→ 演示侧（D1-D3 完成）→ 算法升级（Phase E P0/P1/P2/P3） |

### v4 新增决策（2026-05-22）

| # | 议题 | 决策 |
|---|---|---|
| 13 | 综合评分权重 0.3/0.3/0.4 | **学校规定，不可改**；所有改进只改单项分数内部算法、检测推理侧、雷达图维度、预测算法 |
| 14 | 检测硬件 | **只有单目 RGB 摄像头**，排除依赖激光/X 光/声学/深度相机的方案 |
| 15 | 算法升级排序 | 按 P0（修语义+稳态）→ P1（ROI 引导 + 拟态过滤 + 标定）→ P2（深度模型 + 高光抑制 + TTA）→ P3（热图 + AI schema） |
| 16 | 命名 | 旧 D4-D6 + 旧 Phase E 全部废弃；新算法升级清单挂在新 Phase E 下 |

---

## 4. 推/审流程

- **文档改动**（`.claude/*.md`、`docs/*.md`、`README.md`）：commit 后立即双推。
- **代码改动**：commit 后**先不 push**，commit message 写清动机和影响范围、告知用户「待审」；用户授权后双推。
- 双推命令固定：
  ```bash
  git push srtp main
  git push gitee main:dev-upgrade
  ```
- **每次代码改动收尾时主动跑 `/simplify` 审一轮再请用户复核**（memory: feedback_simplify_after_changes）
- **代码和注释不能露 AI 痕迹**：无 emoji、无 Args/Returns 模板、不写 phase 标签（如「E-P1-1 改造」）；写完前用 humanize 风格收一遍（memory: feedback_humanize_code_style）

---

## 5. 完成阶段后必做：更新 [PROJECT_MEMORY.md](./PROJECT_MEMORY.md)

每个 Phase（E-P0 / E-P1 / E-P2 / E-P3 / F）结束都要追加修订条目到 §10：
- 列出本阶段实际改动的文件
- 标注是否仍有未完成项需要延期
- 如有重大决策变更，回写到本文第 3 节

---

## 6. 关于其他成员的工作

Claude 不写、不接、不调通联：
- 3D 模型生成与展示（团队其他成员）
- 原规划 P0/P1 除 3D 部分（团队其他成员）

但 Claude 会留好接口供他们填：
- 前端：`front/components/modules/ThreeDModule.tsx` 空壳 + `front/public/3d/` 目录
- 后端：如果 Phase E 工作中发现某个端点需要 P0/P1 团队配合调整接口契约，告知用户、由用户协调

---

## 7. 关于硬件部分

- "有线摄像头接入" 的**代码侧**已在 B1 完成。
- 物理操作（插线、调光、对焦、装支架）由用户做。
- Phase E 标定（E-P1-3）依赖一把已知长度的钢直尺或标定卡——请用户提前准备并告知参考物的真实长度。

---

## 8. 现在的下一步

1. ✅ 本文档 v4 修订完毕
2. 推送本次文档修订到双远程（文档改动可直接双推，无需用户审核）
3. 进入 Phase E：从 P0 开始
   - E-P0-1 时序融合 + EMA + IoU
   - E-P0-2 修预测时间轴语义
   - E-P0-3 雷达 6 维洗白
4. 每完成一个 P-级别（P0/P1/P2/P3）跑 `/simplify` + 等用户复核 → commit → 用户授权后双推
5. P0 → P1 → P2 → P3 → F

### 参考资料

- [Real-Time Seam Extraction with Dynamic ROI (MDPI Sensors 2025)](https://pmc.ncbi.nlm.nih.gov/articles/PMC12157130/)
- [Passive Vision Weld Seam ROI Detection (MDPI Sensors PMC12736899)](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12736899/)
- [Lightweight Multi-Frame Integration for YOLO (arxiv 2506.20550, 2025)](https://arxiv.org/html/2506.20550v1)
- [MR2-ByteTrack for Video Object Detection (arxiv 2404.11488, 2024)](https://arxiv.org/pdf/2404.11488)
- [Two-Stage Detection-Tracking Framework (arxiv 2602.19278)](https://arxiv.org/pdf/2602.19278)
- [Weakly Supervised Specular Highlight Removal (MDPI Mathematics 2024)](https://www.mdpi.com/2227-7390/12/16/2578)
- [Real-Time Weld Bead Width Measurement in GMAW (PMC5038773)](https://pmc.ncbi.nlm.nih.gov/articles/PMC5038773/)
- [Measuring Planar Objects with Calibrated Camera (MathWorks)](https://www.mathworks.com/help/vision/ug/measuring-planar-objects-with-a-calibrated-camera.html)
- [Camera Calibration for Manufacturing Inspection (NIST IR 7197)](https://nvlpubs.nist.gov/nistpubs/Legacy/IR/nistir7197.pdf)
- [Period-Sensitive LSTM for Welding Quality (IEEE 2024)](https://ieeexplore.ieee.org/document/10716249/)
- [Ultralytics Test-Time Augmentation Tutorial](https://docs.ultralytics.com/yolov5/tutorials/test_time_augmentation)
