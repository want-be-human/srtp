# 项目结构重新规划（已批准的方向）

> 用户 2026-05-19 批准「逐步按本提案拆分 `app/page.tsx` 与 `api/yolo_realtime.py`」（决策 #11）。  
> 本文档是「结构重组」的**方向参考**，不是「立即一次性执行」的清单。**配合 [EXECUTION_PLAN.md](./EXECUTION_PLAN.md) 的 Phase A-D 节奏渐进式拆。**  
> 任何条目执行前，必须保证整链路（前后端启动 + 检测 + 入库 + 预测 + PDF + AI）跑通。

---

## 1. 改造原则

1. **稳定优先**：所有重构必须能在改完当晚跑通完整演示链路。
2. **小步多 commit**：每一次结构性改动单独一个 commit，便于回滚。
3. **代码改动等用户审核再推**（见 [PROJECT_MEMORY.md §8](./PROJECT_MEMORY.md)）。
4. **不引入新硬编码**：URL、阈值、模型路径、摄像头地址一律走配置。
5. **保持运行入口不变**：`start_all.bat`、前端 `npm run dev`、后端 `uvicorn main:app` 三个入口的命令本身不变。
6. **不一次性大改大文件**：`page.tsx`、`yolo_realtime.py`、`predict.py` 都要分多个 PR 拆分。

---

## 2. 后端重组建议

### 2.1 当前结构问题

- `api/yolo_realtime.py` ~940 行：把「线程管理 + 视频流 + 检测调度 + 入库 + 学生对比」糅在一起。
- `api/predict.py` ~890 行：预测 + AI 分析 + 雷达 mock + YOLO 数据接收四件事在一个文件。
- `api/lesson_plan.py` ~1000 行：报告聚合 + PDF 异步任务在一个文件。
- `yolo_config.json` 与 `services/yolo/zonghe_*` 默认值不一致，并指向不存在的 `../YOLO/models/best.pt`。
- 无 `schemas/` 目录，Pydantic 模型散落在各 api 文件内。
- 无统一日志，多处 `print(...)` 与 `traceback.print_exc()` 混用。
- `.env` 在仓库里（理论上含真实 key）。
- 几个一次性 test 脚本 `simple_test.py / test_api.py / test_types.py / check_db.py` 留在 backend 根目录。

### 2.2 建议结构（不强制一次到位）

```
backend/
├── main.py                      # 仅启动 + lifespan，移走业务
├── core/                        # 新增
│   ├── config.py                # 现有 config.py 迁入；新增 ROI/相机/AI 超时配置
│   ├── logging.py               # 统一 logger 工厂（formatter + level）
│   └── lifespan.py              # FastAPI startup/shutdown：detector 加载/释放、线程清理
├── db/
│   ├── database.py              # 现有 database.py
│   └── models.py                # 现有 models.py（保留 spacing_score 字段，但加 alias）
├── schemas/                     # Pydantic 数据契约集中
│   ├── detection.py             # ScoreData / YOLODetectionData / DetectionResult
│   ├── prediction.py            # PredictionResponse / RadarData
│   ├── lesson.py                # LessonPlanData 等
│   └── auth.py                  # 新增：演示登录用 SchoolStudent / LoginRequest
├── api/
│   ├── deps.py                  # 公共依赖：get_db, get_detector
│   ├── yolo_realtime.py         # 拆为：endpoint 路由 + 调用 services.detection.runtime
│   ├── predict.py               # 仅路由；预测逻辑迁 services/prediction.py
│   ├── teacher.py               # 加超时 + 单例 client
│   ├── dashboard.py             # 维持
│   ├── lesson_plan.py           # 路由 + PDF 任务；规则建议迁 services/rules.py
│   └── auth.py                  # 新增：演示登录端点
├── services/
│   ├── yolo/                    # 综合检测器，保留现状
│   ├── pdf_generator/           # 现有，加文件清理策略
│   ├── detection/runtime.py     # 新增：把 capture_loop/inference_loop/全局状态封一类
│   ├── prediction.py            # 从 api/predict.py 抽
│   ├── ai.py                    # 集中 OpenAI client（单例 + Timeout），现有 ai_analysis.py 改造
│   └── rules/                   # 新增：规则建议库（缺陷 → 建议；分数区间 → 建议）
├── llm_output_filter/           # 当前为空，决定要不要做（决定不做就删）
├── tests/                       # 把 simple_test / test_api 等迁入
├── welding.db                   # 保持
├── requirements.txt
└── .env.example                 # 真 .env 必须从仓库历史里清除（git filter-repo）
```

### 2.3 立即可做、风险极低（建议在 /simplify 阶段顺手）

- 删除空目录 `backend/llm_output_filter/` 或加 `.gitkeep` 并写明用途。
- 修正 `yolo_config.json:2` 的 `yolo_model_path` 为 `services/yolo/models/best.pt`。
- `yolo_config.json` 与 `zonghe_*.py` 的 `confidence_threshold` 统一为 `0.5`（评委友好阈值）。
- 把 `test_*.py / simple_test.py / check_db.py` 移到 `backend/tests/`。
- 给 `defect_types.py` 加一个 `get_defect_name_safe(class_id) -> str` 包装，未知 ID 返回「未匹配类别 ID: {x}」。

---

## 3. 前端重组建议

### 3.1 当前结构问题

- `app/page.tsx` 940 行，把 7 个模块的 `*Content` 全部内联。
- `app/page.tsx` 内仍有 3 处硬编码 `http://127.0.0.1:8000`（应走 `API_ENDPOINTS`）。
- 数据树 Context 无持久化、无按学生过滤入口。
- mock 数据散落（`prediction-dashboard.tsx` 的 DEFAULT_MOCK_*、`lesson-plan-export.tsx` 的 175 条 mock 文案）。
- `next.config.mjs` 同时关闭 TS 与 ESLint 报错。
- 同时存在 `package-lock.json` 与 `pnpm-lock.yaml`，需要选一个。
- `front/lib/api.ts` 只有 URL，没有 `fetcher`，导致每个组件自己写 try/catch。

### 3.2 建议结构（标注谁负责）

```
front/
├── app/
│   ├── layout.tsx
│   ├── page.tsx                 # 仅留导航壳 + 模块切换；模块内容外移
│   └── login/page.tsx           # 由用户 P2 任务负责，Claude 不预先建
├── components/
│   ├── modules/                 # 新增：把内联的 *Content 拆成独立模块组件
│   │   ├── DashboardModule.tsx
│   │   ├── DetectionModule.tsx
│   │   ├── TeacherModule.tsx
│   │   ├── PredictionModule.tsx
│   │   ├── DataTreeModule.tsx
│   │   ├── LessonPlanModule.tsx
│   │   ├── ThreeDModule.tsx     # Claude 留空壳，3D 资产由团队其他成员补
│   │   └── SettingsModule.tsx   # 含教学/严格模式切换、演示降级开关、TTS 静音
│   ├── detection/yolo-realtime-detector.tsx
│   ├── data-tree/...
│   ├── prediction/...
│   ├── lesson-plan/...
│   ├── ai-teacher/...
│   └── ui/
├── lib/
│   ├── api.ts                   # 端点 URL 常量（已存在）
│   ├── fetcher.ts               # 新增：统一 fetch（timeout、错误归一、`?t=` cache buster）
│   ├── tts.ts                   # 新增：speechSynthesis 封装 + 静音开关
│   ├── storage.ts               # 新增：localStorage key 命名空间统一（srtp: 前缀）
│   └── auth.ts                  # 由用户 P2 负责，Claude 留空壳供对接
├── contexts/
│   ├── AuthContext.tsx          # 由用户 P2 负责
│   └── DataTreeContext.tsx      # 现有；持久化和按学生过滤由用户 P2 扩
├── hooks/
│   ├── useDashboardStats.ts     # 把 page.tsx 里的 fetch 迁入
│   └── useYoloData.ts           # 把 YOLO 轮询逻辑封装
├── types/
│   └── domain.ts                # YOLODetectionResult / DetectionResult / TreeData 集中
├── public/
│   └── demo/                    # 演示降级模式用：weld.mp4 + cached_result.json
├── next.config.mjs              # 国赛前打开一次 TS 检查并修
├── package.json
└── .env.local.example           # 新增；同时把 .env.local 加进 .gitignore
```

### 3.3 立即可做、风险极低（建议在 /simplify 阶段顺手）

- 删除 `front/pnpm-lock.yaml`（已确定以 npm 为主），或反之删掉 `package-lock.json`。
- 把 `page.tsx` 里 3 处硬编码 URL 替换为 `API_ENDPOINTS` 常量。
- `components/data-tree/data-adapter.ts` 中的 `generateMockTreeData()` 未在生产使用，可以删。
- 给所有 `localStorage` key 加 `srtp:` 前缀，避免多实例污染。
- 检查并删除明显的占位 mock（保留 1-2 条「无数据时的 placeholder」即可）。

---

## 4. 配置与密钥

- `backend/.env` 应 **从仓库历史中清除**（用 `git filter-repo --path backend/.env --invert-paths`）。这一步要在所有团队成员同步后做一次。
- 提交 `backend/.env.example`（已有）+ `front/.env.local.example`（新增）。
- `start_all.bat` 顶部加一段「如未发现 `.env` 则提示并退出」的检查。
- 新增 `config/camera.json`（或 .env），用于运行时切换摄像头 URL，**禁止把账号密码写进 git**。

---

## 5. 与升级计划的对接

| 升级方向 | 涉及结构变动 | 负责人 |
|---|---|---|
| ROI 可配置 | `services/detection/runtime.py` 暴露 `roi`；前端 SettingsModule 加 ROI 设置面板 | Claude |
| 缺陷名兜底 | `defect_types.get_defect_name_safe()`（已建） | Claude |
| AI 超时兜底 | `services/ai.py` 单例 client + `httpx.Timeout`（teacher.py 已示范）；规则库放 `services/rules/` | Claude |
| PDF 本地规则化 | `services/rules/` 提供 `recommend(skill_stats, defect_stats)`；`api/lesson_plan.py` 调用 | Claude |
| 教学/严格模式切换 | `services/detection/runtime.py` 暴露 confidence 阈值可写；SettingsModule 加开关 | Claude |
| 演示降级模式 | `front/public/demo/`+ SettingsModule 开关 + 前端拦截 fetch 改读本地 | Claude |
| TTS 重要事件播报 | `front/lib/tts.ts` + DetectionModule 在分数变化时调用 | Claude |
| 删 mock 雷达 | 删 `api/predict.py` 的 `_MOCK_RADAR_DATA`，改从 DB 聚合 | Claude |
| 演示数据预播种 | `backend/scripts/seed_demo_data.py` | Claude |
| 标准对齐文案 | PDF 模板加页脚、`docs/` 加讲稿大纲（不进 README） | Claude |
| 缺陷热图（最低优先级） | DB 加 `defect_bboxes` JSON 列 + 历史记录可视化 | Claude |
| 有线摄像头接入 | 后端 camera_url 配置化（Claude）+ 硬件连通性（用户） | Claude + 用户 |
| 演示登录 | `api/auth.py` + 前端 `app/login` + `AuthContext` | **用户** |
| 学生数据归属 | `lib/auth.ts` 在保存检测时塞 `student_id` | **用户** |
| 数据树 PK | `DataTreeContext` 按 `student_id` 分组；`DataTreeModule` 加双树视图 | **用户** |
| 3D 重构入口 | `components/modules/ThreeDModule.tsx` + 静态资产放 `front/public/3d/` | **团队其他成员**（Claude 留空壳） |

---

## 6. /simplify 不会涉及的部分（避免误改）

- `yolo_realtime.py` 的线程协作逻辑（capture + inference + lock）— 改动需要专门的稳定性测试。
- `data-tree-viewer.tsx` 的 29000 粒子着色逻辑 — 视觉效果非常脆弱。
- 任何 SQL 字段名修改 — 涉及 `spacing_score ↔ width_score` 错位，需专门迁移。
- AI prompt 文案 — 已经被业务测试过的文案保留。

---

## 7. 验收清单（结构调整后必须通过）

- `start_all.bat` 一键启动，前后端都起来。
- 浏览器打开 `http://localhost:3000` 看到 7 个导航项目，全部能切换无报错。
- 启动检测，能看到 MJPEG 流（即使没相机也要降级到「Camera not started」黑屏）。
- 上传一张图片能拿到检测结果。
- 「保存分数」能落库，预测页 5 秒内出图。
- 「报告导出」按钮能完成一次 PDF 下载。
- AI 教师页能发出 1 条消息（即使 API key 不通，前端有兜底提示）。

---

*第一轮 /simplify 已完成（commit `a62332d`），实际改动清单见 [PROJECT_MEMORY.md §10](./PROJECT_MEMORY.md)。后续阶段按 [EXECUTION_PLAN.md](./EXECUTION_PLAN.md) 推进。*
