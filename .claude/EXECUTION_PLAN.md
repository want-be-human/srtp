# 焊育智眸 国赛执行计划（2026-05-25 v5）

> **v5 修订（2026-05-25）**：Phase E 11 项做完后做了一轮全栈审计，发现 4 项红色 + 3 项黄色 + 1 项绿色"已实现但展示不够 / 评委可攻破"的弱点。本次升级把审计结论、演示数据规则化（学生 ID/姓名/分数边界）、Mock 路径全标注、剩余 3 天路线全部写入。
>
> v4 修订（2026-05-22）：v3 的 D4/D5/D6（教学严格模式、TTS、标准对齐文案）和原 Phase E（缺陷热图独立项）全部废弃，
> 替换为一组针对队友反馈 + 硬约束的检测/预测算法升级。
> 触发原因：队友反馈 YOLO 全画面误检、轻量模型置信度抖、焊缝拟态逻辑差；
> 同时确认两条硬约束：（1）检测方式只有单目 RGB 摄像头，无激光/X 光/声学/深度传感器；
> （2）综合评分公式 `0.3·光滑 + 0.3·宽 + 0.4·缺陷` 是学校规定，权重不可改。

冻结日：2026-05-28（国赛）。本文最后修订：2026-05-25。

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

### Phase E 审计结果（2026-05-25）— Phase E.v2 修补清单

**P0-P3 11 项的完成度审计**（agent 三路并行查代码）：

| 项 | 后端 | 前端可视 | 风险 | 备注 |
|---|---|---|---|---|
| E-P0-1 时序融合 | ✅ | ✅ | — | 完整落地 |
| E-P0-2 attempt_index | ✅ | ✅ X 轴"第 N 次检测" | — | 完整落地 |
| **E-P0-3 雷达 6 维洗白** | ✅ | ⚠️ 预测页接通，**对比页没接** | 🔴 | 学生对比页 `buildSixDimRadar` 仍用老派生公式，维度名也是旧 6 维 |
| **E-P1-1 焊缝 ROI 引导** | ✅ | ❌ **前端零可视化** | 🔴 | `seam_theta` 和 ROI bbox 后端有，没透传到 MJPEG / 前端 |
| E-P1-2 暗-亮-暗 | ✅ | ⚠️ 无效果计数/A-B 对比 | 🟡 | 拒绝候选行的数量未暴露 |
| **E-P1-3 单目标定** | ✅ | ⚠️ 4 处实战漏洞 | 🔴 | 旧 `image_height_cm=15.0` 默认参数没删；未渲染 `calibrated_at`；检测页无"未标定"红字；canvas 两点点选无放大镜，~2-3mm 误差 |
| E-P2-1 1D-CNN | ✅ | ✅ ToggleGroup | 🟡 | 无训练曲线落盘，评委"训练曲线给我看"答不上 |
| E-P2-2 GLCM | ✅ | ✅ | 🟢 | 归一化常数 20/200 经验值，无 calibration |
| E-P2-3 TTA 保存 | ✅ | ✅ | — | 完整落地 |
| E-P3-1 热图 | ✅ | ✅ 双热图 | 🟡 | 全靠 `seed_demo_bboxes.py` mock；演示库真实按键 bbox 极少 |
| **E-P3-2 AI schema 重试** | ❌ | — | 🟡 | **完全没做**，ai_analysis.py 仍是一次失败直接 fallback |
| **A5 .gitignore + pyc 清理** | ❌ | — | 🔴 | 根目录无 .gitignore；56 个 pyc + welding.db 被 git tracked |
| A6 tests/ 迁移 | ❌ | — | 🟢 | `check_db.py / simple_test.py / test_api.py / test_types.py` 仍在 backend/ 根 |

---

### Phase E.v2 — 修补 + 数据规则化（2026-05-25 起，3 天）

#### 演示数据规则化（已完成 / Day 1 第一项）

> 把演示数据当真实数据用，所以必须对齐真实系统的边界、命名、画像。下面是 v5 拍定的规则。

**学生名单（6 人）**：

| ID | 姓名 | weak 画像 | 检测次数 |
|---|---|---|---|
| `2024112434` | 陈思远 | weak=width，宽度起伏大 | 22 |
| `2024111216` | 王俊杰 | weak=defect，缺陷多 | 25 |
| `2024112605` | 林雨晴 | 均衡稳定 | 20 |
| `2024110853` | 赵嘉宁 | 优等生 | 18 |
| `2024113182` | 黄子睿 | weak=smooth，光滑度差 | 24 |
| `2024110741` | 周文静 | 起伏大 | 21 |

ID 格式 `202411xxxx`：2024 入学 + 11 月份/班号 + 4 位故意不连号序号。班级 `焊接班2024-A`。`student_demo` 学号保留作为孤儿记录归口。

**分数生成规则**（对齐 yolo_config.json + 检测器实际边界）：

| 项 | 边界 | 来源代码 |
|---|---|---|
| 单项分 | `[20, 100]` | `zonghe_*.py::_calculate_width_score` 保底 20；其他 max(0,min(100)) |
| 综合分 | 严格 `0.3·smooth + 0.3·width + 0.4·defect` | 学校规定权重 |
| 最佳宽度 | `5.5 mm` | `yolo_config.json::width_thresholds.optimal_width_mm` |
| 宽度范围 | `[3.0, 8.0] mm` | `yolo_config.json` |
| 越界保底 | **10% 样本**主动放到 3-8 之外 → 触发宽度=20 | `seed_demo_data.py::_pick_actual_width` |
| 预测 fallback | `[60, 95]` | `predict.py:292` 老 RF 兜底范围 |

**关键修正**（v4 → v5 数据漂移）：
- v4 seed: `clamp(50, 98)` + width target `6.0mm` → 永远不会触底
- v5 seed: `clamp(20, 100)` + width target `5.5mm` + 10% 越界样本 → 真实呈现「保底-上限」语义

#### Day 1 — 红色优先（剩余）

- **E-P0-3.v2 对比页雷达接通** ⭐ 🔴
  - 改 `front/components/comparison/student-comparison.tsx::buildSixDimRadar`
  - 删派生公式 `smooth*0.5+width*0.5` 等；改用 `/predict/ai-radar-data?student_id=` 拉真实 6 维
  - 同时拉 self / opponent 两次（或后端加 `student_ids[]` 批量端点）
  - 副标题 "间距/熔深/速度为真实分数代理估算" 删掉

- **A5 .gitignore + pyc 清理** 🔴
  - 写根 `.gitignore` 屏蔽 `__pycache__/`、`*.pyc`、`*.pyo`、`welding.db`、`.env`、`*.log`
  - `git rm --cached -r backend/**/__pycache__ backend/welding.db`
  - **welding.db 要不要清** 待和用户确认 — 现在 db 里就是演示数据，团队拉下来直接能用 vs 团队跑 seed 脚本自己生成

- **Mock 路径 5 处 UI 标注**：
  1. `yolo_realtime.py::inference_loop`（YOLO 不可用模拟数据）→ 响应里加 `is_mock: true` + 前端检测页右上红色 badge「YOLO 离线 · 演示数据」
  2. `yolo_realtime.py::detect_frame / detect_image` 兜底 → 同上
  3. `lesson-plan-export.tsx::MOCK_TEACHING_RECOMMENDATIONS / MOCK_LESSON_PLANS` → 每个滚动卡片顶部加灰色「示例文案」徽标
  4. `predict.py:292` fallback → 响应里加 `is_fallback: true` + 预测面板顶部黄字「样本不足，规则预测」
  5. `prediction-dashboard.tsx::EMPTY_SKILL_DATA` → 副标题灰字「暂无数据」

#### Day 2 — 红色优先（继续）

- **E-P1-1.v2 ROI 可视化** ⭐ 🔴
  - `inference_loop` 把 `seam_theta` 和 ROI bbox 写进 `current_detection_data`
  - `generate_video_stream` 在 MJPEG 上叠加：
    - 黄色 ROI 包围框（dashed）
    - 左上角 `θ = NN.N°` 文字
    - 计数 `剔除 ROI 外 N 框`
  - 评委「把焊缝 ROI 圈出来」→ 看 MJPEG 直接演示

- **E-P1-3.v2 标定 4 漏洞修补** 🔴
  - (a) 删 `kuandu_jiance_qiqi.py:45` 默认 `image_height_cm=15.0`；旧 fallback 路径返回 `calibrated=False` + 警告
  - (b) 标定卡片显示 `calibrated_at` 时间戳（前端已有字段，加 JSX 渲染）
  - (c) 检测页加 badge 读 `calibrated`：未标定 → 红字「未标定，宽度为估算值」；已标定 → 绿字「✓ 已标定 X.XXX px/mm」
  - (d) Canvas 两点点选加放大镜（80×80px 跟随光标 4× 放大）+ 实时像素坐标显示

#### Day 3 — 黄色 + 绿色

- **E-P3-2.v2 AI schema 重试** 🟡
  - `ai_analysis.py` 解析失败时把"上次输出无法解析为 JSON，请严格按 schema"加到 user message 重试 1 次
  - prompt 附带 `severity_map`（`defect_types.py::get_severity_level`）
  - pydantic 模型校验返回字段
- **E-P2-1.v2 1D-CNN 训练曲线** 🟡
  - `temporal_model.py::train_from_records` 训练循环里记 per-epoch loss
  - 训完保存到 `docs/temporal_training_curve.png`（matplotlib）+ `docs/temporal_metrics.json`（最终 loss、R²、样本数）
- **E-P1-2.v2 暗-亮-暗 计数** 🟡
  - `kuandu_jiance_qiqi.py::_pick_best_row` 返回 `rejected_count`
  - 透传到 `current_detection_data['width_debug']`
  - MJPEG 角标显示
- **A6 tests/ 迁移** 🟢
  - `mkdir backend/tests && git mv check_db.py simple_test.py test_api.py test_types.py backend/tests/`
  - 修 import path
- **演示数据真实化策略**（不算修补，但要确认）
  - 演示前一天用真摄像头按 5-10 次保存键，让 TTA 真写 bbox 进库
  - 让评委看到的热图既有 mock 历史画像、又有真实采集点

#### 工作量汇总（v5）

| 阶段 | 项数 | 工作量 |
|---|---|---|
| 数据规则化 | 1 套（已完成）| 0.5 天 |
| Day 1 红 | 3 | 1 天 |
| Day 2 红 | 2 | 1 天 |
| Day 3 黄+绿 | 4 | 1 天 |
| **合计剩余** | **9** | **3 天**，刚好到 2026-05-28 |

### Phase F — 冻结

- 2026-05-27：只修 bug，不加功能；连跑 3 遍演示
- 2026-05-28：打包备份（比赛电脑、U 盘、云盘）
- 演示注意事项：
  - **不要用 `npm run dev` 跑演示**。dev server 冷启动会按需编译路由，首次访问可能返回 `_not-found` 404。务必用 `npm run build && npm run start`
  - 生产构建后预热一遍：浏览器先访问 `/login` 和 `/`
  - 演示前 walk through 检查清单：
    1. 学生登录用新 ID（`2024112434` 陈思远等）+ 密码 `123456`
    2. 检测页右上角看 `YOLO 在线/离线` badge 状态
    3. 标定页显示 `已标定 X.XXX px/mm` + 时间戳
    4. PK 视图雷达图 6 维都是新维度名（光滑度均值/宽度准度/缺陷控制/宽度稳定性/进步速率/缺陷集中度）
    5. 热图既有 mock 画像也有当天真实按键采集点

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

### v5 新增决策（2026-05-25）

| # | 议题 | 决策 |
|---|---|---|
| 17 | 演示数据当真实数据用 | 学生采集真焊接数据成本太高，演示库的 seed 数据按真实系统边界生成，用于答辩；评委如问真实采集，演示当天临时按 5-10 次保存键补充 |
| 18 | 学生 ID 格式 | `202411xxxx` 4 位故意不连号（如 2434/1216/2605）；不要 0001/0002 顺序 |
| 19 | 学生姓名 | 6 人挑接近真实学生姓名风格：陈思远/王俊杰/林雨晴/赵嘉宁/黄子睿/周文静 |
| 20 | 分数生成边界 | 单项分 `[20, 100]`、10% 样本宽度越界触发保底 20、综合按严格权重算出；不再 v4 那种全部 [50,98] 的"美容"区间 |
| 21 | Mock 标注 | 除 DB 外 5 处 mock 全部加 UI 标识（YOLO 离线 badge、预测 fallback 提示、lesson-plan 示例徽标、radar 暂无数据、detect-frame 兑底）；演示时评委一眼看清「哪是真 / 哪是兜底」 |
| 22 | welding.db 是否进版本控制 | 待和用户确认（v4 之前是 tracked，v5 准备考虑 untrack） |
| 23 | 审计漏洞修补节奏 | 3 天分 Day 1 / Day 2 / Day 3 三套件，每套件 simplify + commit + 用户授权双推 |

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

## 8. 现在的下一步（v5 / 2026-05-25 起）

1. ✅ Phase E 11 项 P0-P3 全部完成
2. ✅ Phase E 审计完成，发现 4 红 / 3 黄 / 1 绿弱点
3. ✅ 演示数据规则化完成（seed_students/seed_demo_data/seed_demo_bboxes 全部新 ID/姓名 + 边界对齐）
4. **当前**：升级 EXECUTION_PLAN / PROJECT_MEMORY / algorithm_upgrades 文档到 v5（本次工作）
5. 推送文档修订到双远程（文档改动可直接双推，无需用户审核）
6. Day 1 代码套件：A5 .gitignore + E-P0-3 对比页雷达 + Mock 标注 5 处 → simplify → commit → 用户授权双推
7. Day 2 代码套件：E-P1-1 ROI 可视化 + E-P1-3 标定 4 漏洞 → simplify → commit → 双推
8. Day 3 代码套件：E-P3-2 + E-P2-1 训练曲线 + E-P1-2 计数 + A6 → simplify → commit → 双推
9. Phase F 冻结准备：连跑 3 遍演示 + 当天真摄像头按 5-10 次保存键补充热图真实数据 + 备份

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
