# 焊育智眸 项目记忆文档

> 本文档面向「未来会话中的 Claude」与「人类协作者」共同阅读。  
> 目标是不打开代码也能掌握：项目是什么、长什么样、为什么这么写、哪里脆弱、改哪里要小心。  
> 初版基于 2026-05-19 commit `3df9e9e`，**已经过 simplify 修订**，最新 commit `a62332d`。
> 修订历史见文末 §10。

---

## 0. 速查总览

- **产品定位**：面向焊接实训教学的「检测 + 反馈 + 分析 + 报告 + 成长记录」一体化系统，已进入计算机设计大赛**国赛阶段**。
- **演示主线**：摄像头/上传图片 → YOLO 综合评分（光滑度 0.3 + 宽度 0.3 + 缺陷 0.4） → 入库 → 数据树可视化 → 智能预测 → AI 教师答疑 → 一键 PDF 报告。
- **代码总规模**：后端 ~50 个 Python 文件、前端 Next.js 单页（`page.tsx` 940 行为最大文件）、19000+ 行前端代码（含 shadcn UI）。
- **当前阶段**：国赛 11 天窗口期升级中（截止日 2026-05-28），方向见 [`docs/国赛11天升级规划与代码梳理.md`](../docs/国赛11天升级规划与代码梳理.md)。
- **版本号不一致**：后端 `2.1.0`，前端 `v3.0.1`，封包前需统一。
- **远程仓库**：
  - GitHub `srtp` (https://github.com/want-be-human/srtp.git) — 主推送目标，`main` 分支
  - Gitee `gitee` (https://gitee.com/shollorak/srtp-main.git) — `main` 来源、`dev-upgrade` 为后续工作分支

---

## 1. 仓库结构

```
srtp-main/
├── .claude/                    # 本文档所在位置
├── .venv/                      # Python 虚拟环境（已 gitignore）
├── backend/                    # FastAPI 后端
│   ├── api/                    # 路由层
│   │   ├── yolo_realtime.py    # 实时检测/视频流/分数保存（~940 行，核心）
│   │   ├── predict.py          # 预测、AI 分析、雷达图、YOLO 数据接收（~890 行）
│   │   ├── teacher.py          # AI 教师对话
│   │   ├── dashboard.py        # 仪表板系统状态
│   │   └── lesson_plan.py      # 报告聚合 + PDF 异步任务
│   ├── services/
│   │   ├── yolo/               # 综合检测器（光滑度 + 宽度 + YOLOv8 缺陷）
│   │   │   ├── zonghe_hanjie_zhiliang_jiance_xitong.py  # 集成入口
│   │   │   ├── guanghuadu_jiance_qiqi.py                # 光滑度（亮度法）
│   │   │   ├── kuandu_jiance_qiqi.py                    # 宽度（梯度法）
│   │   │   └── models/best.pt                           # YOLO 权重
│   │   └── pdf_generator/      # ReportLab + Matplotlib 生成报告
│   │       └── standalone_pdf_generator.py              # 主入口（31KB）
│   ├── llm_output_filter/      # 占位目录，当前为空（计划未实施）
│   ├── charts/                 # line_chart.py + radar_chart.py（matplotlib）
│   ├── main.py                 # 应用入口，/api/v1 前缀
│   ├── config.py               # 环境变量集中
│   ├── database.py             # SQLAlchemy 引擎
│   ├── models.py               # WeldingRecord 表
│   ├── defect_types.py         # 17 类缺陷中英映射 + 严重等级
│   ├── ai_analysis.py          # AIAnalysisService（OpenAI 兼容）
│   ├── prediction.py           # RandomForest 趋势预测
│   ├── data_generator.py       # 演示用合成数据
│   ├── welding.db              # SQLite 实际数据库（已入库）
│   ├── yolo_config.json        # 检测器配置（注意：路径 `../YOLO/models/best.pt` 与 services/yolo 重复）
│   ├── .env / .env.example     # API Key 配置（**.env 不应入仓**）
│   ├── requirements.txt        # 版本锁定，含 ultralytics 8.0.196、fastapi 0.109.0
│   └── test_*.py / simple_test.py / check_db.py   # 测试脚本（非系统化）
├── front/                      # Next.js 15 + React 19 前端
│   ├── app/
│   │   ├── layout.tsx          # DataTreeProvider 包裹根
│   │   └── page.tsx            # 单页总入口（**940 行，7 个模块全部内联**）
│   ├── components/
│   │   ├── detection/yolo-realtime-detector.tsx   # MJPEG 流 + 检测 + 上传（300+ 行）
│   │   ├── data-tree/                             # 3D 粒子树（29000 粒子）
│   │   ├── prediction/prediction-dashboard.tsx    # 预测/雷达/AI 分析（400+ 行）
│   │   ├── lesson-plan/lesson-plan-export.tsx     # 报告 + PDF 轮询（700+ 行）
│   │   ├── ai-teacher/ai-teacher-chat.tsx         # 对话
│   │   └── ui/                                    # shadcn 风格组件 ~50 个
│   ├── lib/api.ts              # **44 个端点统一定义**（但 page.tsx 仍有硬编码 URL）
│   ├── next.config.mjs         # **忽略 TS + ESLint 构建错误**
│   ├── package.json            # next 15.2.4 / react 19 / three 0.183 / recharts 2.15
│   ├── .env.local              # NEXT_PUBLIC_API_URL=http://localhost:8000
│   └── pnpm-lock.yaml / package-lock.json         # 两套锁文件并存（以 npm 为准）
├── lizi/                       # Vite + React 19 粒子实验项目（独立 Gemini API 模板，无明显业务集成）
├── docs/国赛11天升级规划与代码梳理.md   # 11 天升级蓝图（已读，见第 7 节摘要）
├── README.md
└── start_all.bat               # Windows 一键启动后端 + 前端
```

---

## 2. 后端架构与关键风险

### 2.1 启动栈

`main.py` 加载 `.env` → 初始化 SQLite → 挂载 5 个 router 到 `/api/v1` → CORS 全开（`allow_origins=["*"]`）→ uvicorn 启动。  
风险：CORS 通配、访问日志禁用、无 graceful shutdown（线程不会被回收）。

### 2.2 数据模型 `models.py` → `WeldingRecord`

字段：`id, timestamp, student_id (idx), student_name, batch_id (idx), smoothness_score, spacing_score, defect_type_score, total_score, actual_width, defect_type_name, notes`。

**关键命名错位**：
- 数据库列名为 `spacing_score`（间距分）。
- 但前端 / API 上下文里这个字段实际是「焊缝宽度分 `width_score`」。
- 入库时手工映射（`yolo_realtime.py:436` 行 `spacing_score=item.width_score`）。
- **改字段名时务必同步前后端**，否则会出现「保存成功但预测页拿不到分」的奇怪 bug。

**已支持的登录/PK 字段**：`student_id`、`student_name`、`batch_id` 都已经在表里，不需要再迁移数据库即可承接「演示登录 + 学生归属 + PK」。

### 2.3 YOLO 实时检测 `api/yolo_realtime.py`

线程模型：

```
capture_loop（60FPS 目标）  →  共享 latest_frame (frame_lock)
inference_loop（6FPS）      →  共享 current_detection_data (data_lock)
FastAPI workers             →  读取这两个共享变量 + 写 /save-score 入库
```

全局可变状态：`is_detecting`、`detector`、`latest_frame`、`camera_cap`、`current_detection_data`。  
**关键问题**：
- `is_detecting` 没有锁保护，存在数据竞争。
- 守护线程退出时不一定释放摄像头（仅在 finally 中调用 `release()`）。
- 采集帧默认中心裁剪 1/3 区域再放大 → 这是「ROI 雏形」，但不可配置，仅 `capture_loop` 内硬编码（约 161-166 行）。
- MJPEG 默认 `640×360`、JPEG 质量 70、推理 6FPS，均硬编码。
- 摄像头未通过环境变量传入；前端 `yolo-realtime-detector.tsx:51` 中硬编码 `http://cc:12345@10.94.91.17:8080/`（**含明文密码，国赛上演前必须改**）。

关键端点：

| 端点 | 用途 | 备注 |
|---|---|---|
| POST `/start-yolo` | 启动两个守护线程 | 接受 `camera_id` 或 `camera_url` |
| POST `/stop-yolo` | 关闭检测，join 线程 3s 超时 | 可能 stuck |
| GET `/yolo-data` | 返回最新一帧检测结果 | 前端 1.5s 轮询 |
| GET `/video-stream` | MJPEG | 多 worker 同时拉流时无 FPS 上限 |
| POST `/detect-image` `/detect-frame` | 单张图片/单帧 | base64 |
| POST `/save-score` | 入库 | **不校验分数是否在 [0,100]** |
| GET `/student-comparison` | 学生聚合 | PK 数据来源 |
| GET `/recent-scores` `/batch-list` | 列表查询 | 配套数据树 |

### 2.4 综合检测器 `services/yolo/zonghe_hanjie_zhiliang_jiance_xitong.py`

- 三模块串联：`WeldingQualityScorer`（光滑度）→ `PreciseWeldDetector`（宽度）→ YOLO（缺陷）。
- 配置默认值：`confidence_threshold=0.3`（代码默认，偏低、容易吃噪声）、`iou_threshold=0.45`、`optimal_width_mm=5.5`。
- 缺陷扣分粒度：严重(0,1,4,6,7,8,9)-35；中等(2,5,10..14)-20；轻微(15,16)-8；class 3=良好+10。
- 风险：confidence 0.3 在评委面前会出现「乱框」，建议演示前调 0.45+ 或允许运行期可调。
- **双源配置仍存在但已收敛**：
  - ✅ simplify 已修复：`backend/yolo_config.json:2` 的 `yolo_model_path` 改为正确的 `services/yolo/models/best.pt`
  - 但代码默认 0.3 vs json 0.5 的不一致**未动**——需要确认 json 实际是否被 zonghe 加载，否则改 json 没有效果。这部分留给后续 PR。

### 2.5 AI 服务 `ai_analysis.py` + `api/teacher.py`

- 默认接 DeepSeek 兼容接口（`AI_API_BASE_URL=https://api.deepseek.com`, `AI_MODEL=deepseek-chat`）。
- `ai_analysis.py` 已有规则 fallback。
- ✅ **simplify 已修复**：`teacher.py` 改为 **模块级 lazy singleton OpenAI client + httpx.Timeout(connect=3s, read=12s)**；AI 失败时不再抛 500，而是返回 `{response: fallback_text, fallback: true}`，UI 不会显示「通信中断」。
- 三种最大 tokens 仍硬编码：800（分数解读）/1500（预测）/2000（教案）。
- temperature 全部 0.7。

### 2.6 预测层 `api/predict.py` + `prediction.py`

- 缓存：60 秒 TTL + 累积 ≥1 条新检测才重算，存在 `_prediction_cache` 全局字典。
- 模型：`RandomForestRegressor(n_estimators=100, max_depth=10)`，加 lag-2、ma-3 特征。
- 雷达图：`/predict/ai-radar-data` 返回 7 套硬编码 mock，每 5 分钟轮换一次（`_MOCK_RADAR_DATA`），**这是评委追问的高风险点**，建议改成从真实库统计。
- 「数字焊枪」相关技能维度在前端文案标了「待接入」，演示时必须讲清。

### 2.7 报告 `api/lesson_plan.py` + `services/pdf_generator/`

- 异步任务：`ThreadPoolExecutor(max_workers=2)` + 字典存任务状态，前端轮询。
- PDF 文件名带秒级时间戳，**无清理策略**，长期跑会塞满磁盘。
- 当前真正生成 PDF 主要靠后端规则 + 数据，前端 `lesson-plan-export.tsx` 里却有 **150+ 条硬编码 mock 教学建议** 和 25 条 mock 课程计划用于「降级展示」。

---

## 3. 前端架构与关键风险

### 3.1 顶层入口 `front/app/page.tsx`（940 行）

- 单页驱动 7 个模块（dashboard / detection / teacher / prediction / data-tree / lesson-plan / settings）。
- 模块组件全部内联在该文件中（`DashboardContent`、`DetectionContent` 等），**未做 React.memo**，切模块就全 rerender。
- 含硬编码 URL：
  - 行 231：`http://10.94.91.182:3000/`（学校 IP）
  - 行 431 / 495 / 551：`http://127.0.0.1:8000/api/v1/...`（绕开 `lib/api.ts` 的统一配置）
- `realTimeData` 每 10 秒轮询 `DASHBOARD_QUICK_STATS`。
- 类型安全：状态、回调多处用 `any`，加上 `next.config.mjs` 关闭 TS 检查，TS 安全网基本失效。

### 3.2 API 集中 `front/lib/api.ts`

- 44 个端点常量集中定义；`API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'`。
- PDF 状态 / 下载用动态函数 `PDF_STATUS(taskId)`。
- **未来要改后端地址只改 `.env.local`，但要先把 page.tsx 里的硬编码 URL 全部替换掉**。

### 3.3 检测组件 `components/detection/yolo-realtime-detector.tsx`

- 启动 → 轮询 `YOLO_DATA`（1.5s）→ 拿到分数后调 `addTreeData()` 写入数据树 Context → 调 `PREDICT_YOLO_DATA` 持久化。
- 写入数据库的同时**手动清掉** `prediction_cache` localStorage，让预测页强制刷新。
- 摄像头地址硬编码（见 2.3）。MJPEG 流不会自动重试。

### 3.4 数据树 `components/data-tree/`

- `DataTreeContext`：`Map<number, TreeData>`，**只在内存**，刷新页面就丢。
- `data-tree-viewer.tsx`：Three.js + React Three Fiber，**29000 粒子**（7000 树干 + 22000 树叶），无 LOD、无 frustum culling、`useFrame` 没节流。
- `data-adapter.ts`：分数加权（total*0.7 + 三项*0.1）转换为 TreeData。注释声明「与 data-tree-receiver 同权」但未必同步。
- **没有按学生筛选 / PK 视图入口**，PK 升级要在这里扩。

### 3.5 预测页 `components/prediction/prediction-dashboard.tsx`

- localStorage 双缓存：`prediction_cache` / `prediction_cache_time` / `shared_total_detections`。
- mock 兜底：`DEFAULT_MOCK_DEFECT_DATA` / `DEFAULT_MOCK_SKILL_DATA` 在拿不到雷达数据时显示 → **可能让评委以为是真数据**。
- 文案 `（待接入数字焊枪）` 现场必须有话术解释。

### 3.6 报告页 `components/lesson-plan/lesson-plan-export.tsx`

- 自动滚动展示 mock 推荐 + mock 课程计划（合计 175 条）。
- PDF：发起 → 轮询 `PDF_STATUS(taskId)` 最多 120 次（2 分钟超时）→ 拿到下载链接生成 `<a>` 触发下载。
- **mock 文本量是重灾区**，必须替换为真实后端数据。

### 3.7 next.config.mjs

```js
eslint:    { ignoreDuringBuilds: true },
typescript:{ ignoreBuildErrors: true },
images:    { unoptimized: true },
```

——构建期不报错≠没问题。生产前应至少打开一次 TS 检查跑一遍。

### 3.8 lizi/

独立 Vite + React 19 项目，来源于 AI Studio 模板（`README.md` 指向 ai.studio app 链接），依赖 `GEMINI_API_KEY`，与主项目**没有集成**。当前用途疑似粒子效果实验/参考，不参与国赛主线，可视作沙盒。

---

## 4. 硬编码值与配置一览（**重要：演示前都要确认**）

| 类别 | 值 | 位置 | 备注 |
|---|---|---|---|
| 摄像头 URL | `http://cc:12345@10.94.91.17:8080/` | `yolo-realtime-detector.tsx:51` | 含明文账密 |
| 学校 IP | `http://10.94.91.182:3000/` | `app/page.tsx:231` | 不应进国赛包 |
| API 主机 | `http://127.0.0.1:8000` | `app/page.tsx:431/495/551` | 应使用 `API_ENDPOINTS` |
| CORS | `*` | `backend/main.py:30` | 演示可，发布前收紧 |
| YOLO 置信度 | `0.3` (代码) / `0.5` (yolo_config.json) | `zonghe...py` / `yolo_config.json:3` | 双源不一致（待确认 json 是否实际加载） |
| YOLO IoU | `0.45` | 同上 | |
| 推理 FPS | `INFERENCE_FPS=6` | `yolo_realtime.py:79` | |
| 视频 FPS | `60` 目标 | `yolo_realtime.py:70` | 实际受相机限制 |
| 流分辨率 | `640×360` | `yolo_realtime.py:72/73` | |
| JPEG 质量 | `70` | `yolo_realtime.py:74` | |
| 中心裁剪 | `1/3` 区域放大 | `yolo_realtime.py:161-166` | ROI 不可配置 |
| 检测权重 | 光滑 0.3 + 宽 0.3 + 缺 0.4 | `yolo_config.json` | |
| 宽度阈值 | min 3.0 / max 8.0 / optimal 5.5 mm | `yolo_config.json` | |
| 预测缓存 TTL | `60s` + 1 条新数据触发 | `predict.py:48` | |
| AI max_tokens | 800 / 1500 / 2000 | `ai_analysis.py:104/184/271` | |
| AI temperature | `0.7` | `ai_analysis.py:51` | |
| PDF 轮询超时 | `120` 次 ×1s | `lesson-plan-export.tsx:302` | |
| 粒子总数 | `29000` | `data-tree-viewer.tsx` | |

---

## 5. 关键问题清单（优先级排序，演示视角）

### P0 — 演示稳定性必须修

1. **摄像头硬编码 + 含明文密码** → 走环境变量或运行时配置面板（未修，**最高优先级**）
2. **YOLO 置信度双源（0.3 vs 0.5）** → 路径已统一；阈值未统一，需先确认 json 是否真的被加载
3. ✅ **AI 调用无超时 + 无兜底** → `teacher.py` 已加 timeout + fallback；`ai_analysis.py` 已有 fallback；其它 AI 调用点（如 lesson_plan）待巡查
4. **MJPEG / 检测线程异常恢复** → start-yolo 失败时前端要复位（未修）
5. ✅ **`/save-score` 不校验分数范围** → 已在 `save_score` 内加 `_clamp_score` 夹取 [0,100]

### P1 — 国赛核心增量（来自规划文档）

1. **ROI 可配置 + 前端可视化检测框** → 替换硬编码 1/3 中心裁剪
2. **缺陷名兜底（未知 → "未匹配类别 ID: x"）**
3. **PDF 报告本地规则化**（已经在做，主要剩去掉前端 mock 文案 + 收紧 AI 依赖）
4. **雷达图改成真实数据** → 删 `/predict/ai-radar-data` 的 mock 数据，从 DB 重新聚合
5. **3D 重构展示入口**（预生成模型为主，不强行实时高斯）
6. **演示登录 + 学生数据归属 + 数据树 PK**

### P2 — 可加分项

1. 把 `app/page.tsx` 拆分模块（按 7 个 module 各自一个文件）
2. 给数据树加 localStorage 持久化（**最容易加且评委肉眼可见**）
3. 给数据树加按学生过滤 + 双树 PK 视图
4. AI 教师对话历史持久化
5. PDF 文件清理策略

### P3 — 长期但不在 11 天范围

- 用户体系（注册/角色权限/token）
- 现场高斯实时重建
- YOLO 模型重训
- Docker / CI

---

## 6. 数据流图（实际版本）

```
[ 摄像头 / 上传图片 ]
        ↓
[ backend/api/yolo_realtime.py ]
   ├─ capture_loop  → 中心裁剪 → latest_frame
   └─ inference_loop → 综合检测器 → current_detection_data
        ↓                            ↓
[ /yolo-data 轮询 ]          [ /video-stream MJPEG ]
        ↓
前端 detection 模块 ──┐
        │             └→ POST /save-score → SQLite welding_records
        ├→ addTreeData() (Context, 内存)
        └→ POST /predict/yolo-data （冗余写库 + 清前端缓存）
                ↓
SQLite ─→ /predict → RandomForest → 历史+预测折线
        ─→ /predict/ai-radar-data → ⚠️ 当前是 mock 轮换
        ─→ /lesson-plan → 报告聚合 → /lesson-plan/generate-pdf → 异步 PDF
        ─→ /dashboard/* → 系统状态卡片
        ─→ /student-comparison /batch-list → PK 数据源（待前端使用）
                ↓
[ AI 教师 /teacher/chat ] ← 接受 detection context
```

---

## 7. 升级规划摘要（[`docs/国赛11天升级规划与代码梳理.md`](../docs/国赛11天升级规划与代码梳理.md)）

11 天窗口（2026-05-18 ~ 05-28），目标是把作品从「开放式检测 Demo」升级到「面向焊接教学的闭环平台」。核心 4 件事：

1. **3D 重构补强检测可信度**（建议：环绕采集 → 预生成模型 → 前端稳定展示；不承诺实时高斯）
2. **ROI + 缺陷标签兜底 提高稳定性**
3. **PDF / AI 本地规则化** 降低对网络/API 的依赖
4. **登录 + 数据归属 + 数据树 PK** 形成教学闭环

明天必须拍板的 10 个问题（详见原文 §11），其中关键的 3 个：
- 3D 放检测页内还是新建导航？
- 现场只展示预生成模型，还是允许现场重建？
- 登录做多深？（演示账号 vs. 账密体系）

风险清单（原文 §12）：实时 3D 高斯过重、YOLO 准确率短期难提升、完整登录会拖慢、AI API 不可控、`page.tsx` 等大文件继续膨胀。

最小可交付（原文 §14）：检测稳定 + ROI 中文化 + 3D 入口 + PDF 不依赖 AI + 演示账号切换 + 数据树 PK。

---

## 8. 开发协作约定（基于本文档的工作流）

1. **双远程同步**：
   - GitHub `srtp/main` 和 Gitee `gitee/dev-upgrade` 必须保持一致。
   - 推送命令固定为：`git push srtp main && git push gitee main:dev-upgrade`。
2. **审核流程**（用户 2026-05-19 决策）：
   - **文档改动**（`.claude/*.md`、`docs/*.md`、`README.md`）：commit 后立即双推，无需审核。
   - **代码改动**：commit 后**先不 push**；在 commit message 写清动机/影响，告知用户「待审」；用户 OK 后再双推。
3. **稳定性优先**：所有改动必须能在改完当晚跑通完整演示链路。
4. **三大文件谨慎触碰**：`yolo_realtime.py`（线程协作）、`data-tree-viewer.tsx`（粒子着色）、`app/page.tsx`（940 行单页）。改之前先告知人。
5. **mock 数据需打标**：前端任何 `MOCK_*` 常量都加 `// TODO:replace-with-backend` 注释。
6. **.env 永不入仓**：`backend/.env` 已含真实 key 风险；如确认入库需 `git filter-repo` 清除。
7. **不要再添加新的硬编码 URL / IP**：必须经 `front/lib/api.ts` 或环境变量。

详细执行计划见 [EXECUTION_PLAN.md](./EXECUTION_PLAN.md)，结构重组方向见 [STRUCTURE_REPLAN.md](./STRUCTURE_REPLAN.md)。

---

## 9. 给未来 Claude 的提示

- **打开仓库第一件事**：读 [EXECUTION_PLAN.md](./EXECUTION_PLAN.md) 拿到当前阶段任务清单和责任分工。
- **Claude 实际工作范围只有 4 块**：有线摄像头接入（代码侧）、原规划 P2（登录/归属/PK/对比）、提案新增非 P2 项（TTS/严格模式/降级模式/mock 清理/数据预播种/标准对齐文案）、缺陷热图（最后做）。**原规划 P0/P1 除 3D 外**由团队其他成员负责，**Claude 不主动做**；如果在 P2 相关代码里遇到 P0/P1 的问题，告知用户、由用户分配，不擅自修。
- **代码改动后默认不推送**：commit 后等用户审核，用户授权再 `git push srtp main && git push gitee main:dev-upgrade`。文档改动可直接双推。
- 改字段时请记得「`spacing_score` ↔ `width_score`」错位的历史包袱。
- `app/page.tsx` 940 行不要再追加新模块；要新增模块就拆文件。
- AI 改动一律走「先 fallback、再 AI」的模式，禁止把 AI 调用做成阻塞主流程的必要条件。
- 数据树相关改动如果不是「按学生分树/双树 PK」级别的需求，不要动 `data-tree-viewer.tsx` 的粒子逻辑，那是非常容易破坏视觉的高复杂度代码。
- 3D 模块不由 Claude / 用户负责，由团队其他成员处理；Claude 只留好导航位和静态资产目录。
- 国赛冻结日 2026-05-27 起，只修 bug、不加功能。

---

## 10. 修订历史

### v5 — 2026-05-25 起 Phase E 审计 + 演示数据规则化

Phase E P0-P3 11 项全部完成后做了一轮全栈审计（3 路 agent 并行查代码 vs 计划），结论：4 项红色 + 3 项黄色 + 1 项绿色「已实现但展示不到位 / 评委可攻破」的弱点。同时把演示数据规则化（学生 ID/姓名/分数边界都对齐真实系统）。详见 [EXECUTION_PLAN.md](./EXECUTION_PLAN.md) v5 章节。

**关键发现**：

| 弱点 | 类别 | 影响 |
|---|---|---|
| 学生对比页 `buildSixDimRadar` 还在用 v3 老派生公式（`smooth*0.5+width*0.5` 等），E-P0-3 后端洗白白做了 | 🔴 | 评委对比两页雷达发现维度名/算法两套 → 抓 0.5/0.4 系数追问 |
| E-P1-1 焊缝 ROI 引导后端跑、前端零可视化（seam_theta + ROI bbox 没透传） | 🔴 | 「把焊缝 ROI 圈出来」答辩翻不到 |
| E-P1-3 标定 4 漏洞：旧 `image_height_cm=15.0` 默认参数没删 / `calibrated_at` 没渲染 / 检测页无未标定红字 / canvas 两点点选无放大镜（~2-3mm 误差） | 🔴 | 评委「假装的 mm」硬伤的修补本身又成新硬伤 |
| 根目录无 `.gitignore`，56 个 pyc + welding.db 被 tracked | 🔴 | 演示 git status 一堆"修改"；团队拉代码冲突 |
| E-P3-2 AI schema 重试**完全没做**，ai_analysis.py 仍是一次失败直接 fallback | 🟡 | 演示 AI 教师栏目无算法层创新 |
| E-P2-1 1D-CNN 无训练曲线落盘、无 R²/loss 指标 | 🟡 | 「训练曲线给我看」答辩翻不到 |
| E-P3-1 热图全靠 mock，真实采集数据极少 | 🟡 | 评委追真实采集 → 答辩硬扛 |
| E-P1-2 暗-亮-暗过滤计数没暴露到 UI | 🟡 | 创新点无法演示 |
| E-P2-2 GLCM 归一化常数 20/200 经验值，无 calibration 数据支撑 | 🟢 | 经验值可答，扣分项不大 |
| backend 根目录还有 4 个 test scratch script 没迁 | 🟢 | 整理项 |

**演示数据规则化**（v4 → v5 完成的迁移）：

| 项 | v4 | v5 |
|---|---|---|
| 学生 ID 格式 | `2024001..006` 顺序 | `2024112434 / 2024111216 / 2024112605 / 2024110853 / 2024113182 / 2024110741` 故意不连号 |
| 学生姓名 | 张三 李四 王五 赵六 钱七 孙八（明显假） | 陈思远 王俊杰 林雨晴 赵嘉宁 黄子睿 周文静 |
| 单项分边界 | `clamp(50, 98)` 永远不触底 | `clamp(20, 100)`，对齐 `zonghe_*.py::_calculate_width_score` 保底 20 |
| 最佳宽度 | `6.0mm`（写死） | `5.5mm`，对齐 `yolo_config.json::optimal_width_mm` |
| 越界样本比例 | 0% | 10%（让宽度=20 真实出现） |
| 综合分计算 | 自己 noise | 严格按 `0.3·smooth + 0.3·width + 0.4·defect` |
| `seed_students.py` | 仅"跳过已存在" | 加 `--purge` 模式：先清不在 ROSTER 里的学生 |

**Mock 路径标注规则**（除 DB 外 5 处全部要 UI 标识）：
1. `yolo_realtime.py::inference_loop` YOLO 不可用兜底 → 响应 `is_mock: true` + 前端红色 badge「YOLO 离线 · 演示数据」
2. `yolo_realtime.py::detect_frame / detect_image` 兜底 → 同上
3. `lesson-plan-export.tsx::MOCK_TEACHING_RECOMMENDATIONS / MOCK_LESSON_PLANS` → 滚动卡片顶部加灰色「示例文案」徽标
4. `predict.py:292` 预测 fallback → 响应 `is_fallback: true` + 预测面板顶部黄字「样本不足，规则预测」
5. `prediction-dashboard.tsx::EMPTY_SKILL_DATA` → 副标题灰字「暂无数据」

**Phase E.v2 修补节奏**（3 天到冻结日 2026-05-28）：
- **Day 1**（红色第一批）：A5 .gitignore + E-P0-3 对比页雷达接通 + Mock 标注 5 处
- **Day 2**（红色第二批）：E-P1-1 ROI MJPEG 可视化 + E-P1-3 标定 4 漏洞
- **Day 3**（黄+绿）：E-P3-2 AI 重试 + E-P2-1 训练曲线 + E-P1-2 计数 + A6 tests/ 迁移

### v4 — 2026-05-22 起 国赛 Phase E 算法升级

EXECUTION_PLAN 进入 v4：旧 D4-D6 + 旧 Phase E 缺陷热图全部废弃，替换为 11 项检测/预测算法升级。触发是队友反馈三大痛点 + 两条硬约束（单目 RGB 摄像头、综合评分权重 0.3/0.3/0.4 是学校规定）。完整清单见 [EXECUTION_PLAN.md](./EXECUTION_PLAN.md)。

**E-P3-1 完成（commit 待提交）**：

| 文件 | 改动 |
|---|---|
| `backend/models.py` | `WeldingRecord` 加 `defect_bboxes` JSON 列（nullable）存归一化坐标列表 |
| `backend/main.py::_ensure_welding_records_columns` | 幂等 ALTER TABLE 给老库补 `defect_bboxes` 列；`SQLAlchemyError` 时只打告警不阻塞启动 |
| `backend/api/yolo_realtime.py::_normalize_bboxes` | TTA detections → `cx/cy/w/h ∈ [0,1]`；三重过滤：良品标签 / 越界 / <1px 退化框 |
| `backend/api/yolo_realtime.py::save_score` | TTA 之后把 `tta_def["detections"]` 喂给 `_normalize_bboxes`，写入 `record.defect_bboxes` |
| `backend/api/yolo_realtime.py::get_detection_heatmap` (新) | `GET /detection-heatmap?student_id&limit=200`，只投影 `defect_bboxes`，按 `timestamp DESC` 取，铺平成点列表 + 按 label 计数 |
| `front/components/comparison/defect-heatmap.tsx` (新) | canvas KDE：σ=14px、半径 3σ 高斯叠加、6 段色阶 ramp、散点叠层、按 label 图例 |
| `front/components/comparison/student-comparison.tsx` | 雷达图下方新增双热图（自己 + 对手） |
| `front/lib/api.ts` | 加 `DETECTION_HEATMAP` 端点 |
| `docs/algorithm_upgrades.md` | 新增 §10 缺陷分布热图（问题/方案/指标/性能/创新/论文/局限）+ 节序号调整为 1-13 |

P3-1 关键事项：
- 老库历史记录 `defect_bboxes = NULL`，热图只反映升级后的新数据
- 用归一化坐标，分辨率变了历史数据仍可用
- KDE 单次渲染 30-60ms，仅 `studentId` 切换时重绘
- _ensure_welding_records_columns 在 SQLite 上 `ALTER ADD COLUMN ... JSON` 取 NUMERIC 类型亲和性，SQLAlchemy JSON 类型层透明序列化

**E-P2 完成（commits `e06fe0b` + `a550058` + `7fad52b`）**：

| 文件 | 改动 |
|---|---|
| `backend/services/prediction/temporal_model.py` (新建) | `WeldTemporalCNN`：3 层 1D-CNN + `AdaptiveAvgPool1d(1)` + fc，参数 ~1349（5.3 KB）。卷积带 `padding=1` 不改时间维长度，所以任意 ≥ 5 行的输入都能跑。训练分桶 `TRAIN_WINDOWS=(10,15,20,25,30)`，每 epoch 各桶过一遍。`get_or_train` 单例 + threading.Lock 缓存，新增 ≥30 条记录才重训。详见 [temporal_model_design.md](../docs/temporal_model_design.md) |
| `backend/prediction.py::predict_with_temporal_model` | RF 同构 wrapper：DataFrame → list[dict]，调 `temporal_model.get_or_train + forecast`，样本不足/训练失败透明回退 RF |
| `backend/api/predict.py::get_prediction` | 加 `mode=fast\|deep` 查询参数，缓存键改 `(student_id, mode)` 元组让两路独立缓存 |
| `front/components/prediction/prediction-dashboard.tsx` | 加快速预测 / 深度预测 `ToggleGroup`；localStorage 缓存键带 `:deep` 后缀避免串数据 |
| `backend/services/yolo/guanghuadu_jiance_qiqi.py` | `_glcm_contrast` (`np.bincount` 实现，3.5× 加速)、`_local_variance_mean` (`cv2.boxFilter`)；`_analyze_brightness` 先调 `weld_roi.suppress_highlight` 再分析；新公式 `0.4·适中亮度 + 0.4·(1-GLCM/20) + 0.2·(1-方差/200)`；删失效的 `white/gray/black_weight`，换 `brightness/smoothness/uniformity` 三键 |
| `backend/services/yolo/weld_roi.py` | `_suppress_highlight` → `suppress_highlight` 公开化让 guanghuadu 复用 |
| `backend/services/yolo/zonghe_*.py` | `detect_defects(use_tta=False)` 把 `augment=use_tta` 透传给 ultralytics；`detect_defects_with_tta` 收成一行 wrapper（删 90 行手写 TTA + cv2.dnn.NMSBoxes）；抽 `_apply_defect_score(current, cls)` 消除两处扣分重复 |
| `backend/api/yolo_realtime.py::save_score` | TTA 重算 4 项分数 override 前端瞬时值；整段包在 `detector_lock` 里防止与 `inference_loop` 抢 ROI 状态；`asyncio.to_thread` 不阻塞事件循环；失败静默回退原值 |
| `docs/algorithm_upgrades.md` (新建) | P0-P2 9 项升级的总览技术文档：问题/方案/指标/性能/创新/论文/局限 |
| `docs/temporal_model_design.md` | E-P2-1 模型架构专文（已在 P2-1 commit 中加） |

P2 关键指标：
- 1D-CNN：1349 参数 / 5.3 KB；CPU 80 epoch 3-5s 训完；推理 < 10ms；变长 5..30 行输入同一份权重
- GLCM 公式：过曝白板 score 从 100→60（bug 修），平滑 98 / 粗糙 77 / 欠曝 60
- TTA：YOLO 调用从手写 4 路减到 ultralytics 内置 1 路，~700-1200ms / 保存
- 整体实时路径开销 < 15 ms / 帧

**E-P1 完成（commit `f22461a`）**：

| 文件 | 改动 |
|---|---|
| `backend/services/yolo/weld_roi.py` (新建) | `WeldRoiTracker`：HSV V 通道 clip 压过曝 + Otsu+21×3 闭运算挑最大连通域 + 上帧 bbox 膨胀 15px 收窄搜索带；YOLO 输入用 convertScaleAbs 把 ROI 外像素衰减到 0.3 倍 |
| `backend/services/yolo/zonghe_*.py` | `detect_defects` 接入 ROI tracker + 按中心点过滤；`detect_width` 把 tracker.last_bbox 传给宽度检测；构造器加 `pixels_per_mm` 透传 |
| `backend/services/yolo/kuandu_jiance_qiqi.py` | `_pick_best_row` 暗-亮-暗连续性筛选（两侧 [10,20] 像素带均值要比候选行至少暗 25）；`enhanced_weld_detection` 接 `roi_bbox`、构造器接 `pixels_per_mm` 直接换算 mm、结果带 `calibrated` |
| `backend/models.py` | 新增 `CameraCalibration` 表 |
| `backend/api/calibration.py` (新建) | POST `/calibration/save`、GET `/calibration/current`、DELETE `/calibration/{camera_id}`，加 `load_calibration_pixels_per_mm` helper 给 inference_loop 启动时调 |
| `backend/api/yolo_realtime.py` | 加 `/snapshot` 端点给前端标定面板抓画面用；`inference_loop` 启动时读 DB 标定值传给 detector |
| `backend/main.py` | 注册 calibration router |
| `front/components/settings/camera-calibration.tsx` (新建) | 抓画面 + canvas 两点点选 + 输入真实长度 + 提交标定 |
| `front/lib/api.ts` | 加 `CALIBRATION_SAVE` / `CALIBRATION_CURRENT` / `SNAPSHOT` 端点 |
| `front/components/detection/yolo-realtime-detector.tsx` | 修连接泄漏：`startYOLODetection` 开头先清 `videoStreamUrl` + await microtask 再设新 URL；`<img>` 加 `key={videoStreamUrl}` |
| `front/app/page.tsx` | `<CameraCalibrationCard />` 接进 SystemSettingsContent |

P1 期间踩过的坑（演示时注意）：
- IP 摄像头 URL 必须带 `http://` 前缀，否则 OpenCV 走裸 TCP 会 ETIMEDOUT
- 反复 start/stop 不 stop 会撞 Chromium 同 host 6 连接上限，现已修复但要 stress test
- 标定时存了 `image_width/height`，但 detector 加载时还没校验当前帧分辨率是否一致 → P2/P3 余力可补

**E-P0 完成（commit `d1262c5`）**：

| 文件 | 改动 |
|---|---|
| `backend/api/yolo_realtime.py` | 新增 `DetectionStabilizer`：5 帧滑动窗口 + IoU 关联 + 多帧确认（≥3 次才认）；track confidence 取窗口中位数；四项分数 EMA（α=0.4）+ 返回 round(2)，UI 不再出长尾 |
| `backend/prediction.py` | 删 day_of_year/day_of_week/hour 三个时间特征（一节课里都是常数，对模型只是噪声）；模型时间维度只剩 attempt_index，外推 last + 1..5 |
| `backend/api/predict.py::_aggregate_radar` | skill 雷达 6 维洗白：光滑度均值 / 宽度准度（vs OPTIMAL_WELD_WIDTH_MM）/ 缺陷控制均值 / 宽度稳定性（std）/ 进步速率（前 N vs 后 N）/ 缺陷集中度（distinct/7）；丢掉 (smooth+width)/2、defect·0.6+smooth·0.4、total·0.92 等派生公式 |
| `backend/defect_types.py` | 新增 `NON_DEFECT_LABELS` frozenset，从 `DEFECT_EN_TO_CN['Good Weld']` 派生 + 加 DB 历史占位值 |
| `backend/config.py` | 启动时读 `yolo_config.json::width_thresholds`，暴露 `OPTIMAL_WELD_WIDTH_MM=5.5`、`MIN_WELD_WIDTH_MM`、`MAX_WELD_WIDTH_MM`，下游不再硬编码 |
| `front/components/prediction/prediction-dashboard.tsx` | `EMPTY_SKILL_DATA` 换成新 6 维名字；删掉「（待接入数字焊枪）」disclaimer（雷达现在是真数据） |

仍未做但已识别的延期项：
- `backend/api/lesson_plan.py:271` 还有第三份硬编码的 non-defect 标签集合 → 应改用 `NON_DEFECT_LABELS`
- `front/components/comparison/student-comparison.tsx` 还在用旧的派生公式本地拼 6 维 → 应消费后端真实雷达数据

下一步：E-P1（焊缝 ROI 引导 + 宽度复用 + 单目宽度标定），3 天。

### v3 — 2026-05-19 责任分工修正

EXECUTION_PLAN 进入 v3：明确 Claude 实际只负责 4 块（有线摄像头代码侧、原规划 P2、提案非 P2 项、缺陷热图）；原规划 P0/P1 除 3D 外**不是** Claude 的工作。v1/v2 误把这些塞给了 Claude。

已经在 simplify 期间顺带做掉的 P0/P1 局部（`teacher.py` AI 超时与兜底、`defect_name_safe()`、`yolo_config.json` 接通、YOLO 加载链修复）属于既成事实，已推送、不回滚。后续不再继续 P0/P1 工作。

涉及 commit：`57ca65c`、`1946aa5`、`d8299f0`、`a62332d` 之上的所有未来 commit 都只在 Claude 实际范围内。

### v2 — 2026-05-19 (commit `a62332d`) simplify 后

应用的修复（详见 commit message）：

| 文件 | 改动 |
|---|---|
| `backend/api/teacher.py` | 模块级 lazy singleton OpenAI client + `httpx.Timeout`；失败返回 fallback 文案而非 500；删去全 payload print |
| `backend/api/yolo_realtime.py::save_score` | 入库前 `_clamp_score` 把 4 个分数夹取到 [0,100] |
| `backend/defect_types.py` | 新增 `get_defect_name_safe(class_id)` 返回「未匹配类别 ID: x」 |
| `backend/yolo_config.json` | `yolo_model_path` 修正为 `services/yolo/models/best.pt` |
| `backend/llm_output_filter/` | 删空目录 |
| `front/lib/api.ts` | 新增 `DETECT` 和 `PREDICT_AI_ANALYSIS_CUSTOM` 端点常量 |
| `front/app/page.tsx` | 3 处硬编码 `http://127.0.0.1:8000/api/v1/*` 全部改用 `API_ENDPOINTS` |
| `front/components/data-tree/data-adapter.ts` | 删除从未被引用的 `generateMockTreeData` |

刻意未动（避免破坏稳定性）：
- `yolo_realtime.py` 的线程协作（capture / inference / locks）
- `data-tree-viewer.tsx` 的 29000 粒子着色
- 数据库字段 `spacing_score ↔ width_score` 错位
- `app/page.tsx` 模块拆分
- mock 数据清理（仍保留在 prediction-dashboard / lesson-plan-export）

### v1 — 2026-05-19 (commit `08e796f`)

首版生成，基于 gitee 同步过来的 `3df9e9e`。

---

*本文档由 Claude 生成与维护。如代码已经发生重大变动，请重新阅读 `git log` 与本文件对照。*
