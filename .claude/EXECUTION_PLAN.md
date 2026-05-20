# 焊育智眸 国赛执行计划（2026-05-19 v3）

> v3 修正：v1/v2 把「我负责」错读为「用户亲自实现」，又把 P0/P1（除 3D）误塞给 Claude。  
> **实际上用户是项目负责人，把 4 块任务交给 Claude，其余（P0/P1 除 3D）由团队其他成员负责。**

冻结日：2026-05-28（国赛）。本文最后修订：2026-05-19。

---

## 1. 责任分工

| 工作项 | 实际负责人 |
|---|---|
| 决策、验收、对接需求 | 用户 |
| 实物硬件（接线、调光、装相机） | 用户 |
| 3D 重构展示（建模 + 资产） | 团队其他成员 |
| **原规划 P0**（系统稳定性兜底，除 3D 外的硬件配置化、ROI、缺陷名兜底 sweep、PDF 本地规则化、AI 兜底巡查等） | **团队其他成员**（不是 Claude） |
| **原规划 P1 除 3D 部分** | **团队其他成员**（不是 Claude） |
| **有线摄像头接入（代码侧 + 联调）** | **Claude** |
| **原规划 P2 = 演示登录 + 学生数据归属 + 数据树 PK + 学生对比页** | **Claude** |
| **提案新增非 P2 部分 = TTS / 教学严格模式 / 演示降级模式 / mock 清理 / 演示数据预播种 / 标准对齐文案** | **Claude**（能在 P2 中顺带完成则顺带） |
| 提案中的缺陷热图 | **Claude**，最后做 |

> Claude 不主动接 P0/P1 工作。如果在做自己范围内的代码时发现 P0/P1 的明显问题（例如某个端点必崩），告知用户、由用户分配，不擅自修。  
> 已经在 simplify 阶段顺带做掉的 P0/P1 局部（`teacher.py` 单例 + timeout + fallback、`defect_name_safe()` 工具函数、`yolo_config.json` 接通、YOLO 加载链修复）属于历史既成事实，已推送、不回滚。后续不再继续 P0/P1 工作。

---

## 2. 阶段排序

### Phase A — 深度 /simplify（进行中）

**已完成并双推**：

| commit | 内容 |
|---|---|
| `a62332d` | 第一轮 simplify：teacher.py 单例 + timeout + fallback；defect_name_safe；score 夹取；删 mock；URL 统一 |
| `08e796f / 87cafc9 / 1877d50 / 421cdab` | 文档：PROJECT_MEMORY / STRUCTURE_REPLAN / EXECUTION_PLAN（即 UPGRADE_PROPOSAL 改名） |
| `d8299f0` | Batch 1：删 pnpm 锁文件、雷达 mock 兜底加示例数据角标、lesson mock 瘦身 |
| `1946aa5` | YOLO 加载链：torch.load monkey-patch + dill 依赖 |
| `57ca65c` | yolo_config.json 真正接通到 IntegratedWeldDetector |

**Phase A 还剩**（保留为后续 simplify 小批量）：

- A5 `.gitignore` 补 `__pycache__/`、`*.pyc`、`welding.db`；`git rm --cached` 把这些从追踪里清掉
- A6 后端测试脚本 `simple_test.py / test_api.py / test_types.py / check_db.py` 迁到 `backend/tests/` 并修 import

A5/A6 是与代码功能无关的清理，可以在 B/C 推进过程中穿插完成。

### Phase B — 有线摄像头接入（代码侧）

**只有一项**：

- **B1 摄像头来源配置化**
  - 删 `front/components/detection/yolo-realtime-detector.tsx:51` 的硬编码 `http://cc:12345@10.94.91.17:8080/`
  - 新增 `NEXT_PUBLIC_CAMERA_URL` 环境变量 + `srtp:camera_url` localStorage 覆盖
  - 加一个齿轮按钮，运行时切 URL；空值时不传 `camera_url`，后端 fallback 到 `camera_id=0`（本地 USB / 有线相机）
  - 前端新建 `front/lib/storage.ts` 做 `srtp:` 前缀命名空间（顺带 D 阶段的 demo-safe-mode 也走它）
  - 联调：等用户接上有线相机后告知，按上面的 UI 切一遍走通完整流程

### Phase C — 原规划 P2（登录 + 归属 + PK + 对比）

依赖 B1 完成（演示链路稳了再加身份层），按依赖顺序：

- **C1 学号 + 密码登录**（真实场景，非 demo 账号选择器）
  - 数据库：新增 `students` 表（`student_id` 唯一、`password_hash` bcrypt、`batch_id`、`created_at`）
  - 后端：`backend/api/auth.py` 暴露 `POST /api/v1/auth/login`（学号+密码，bcrypt 校验，错误统一「学号或密码错误」）
  - 预播种脚本：`backend/scripts/seed_students.py` 写入班级名单，初始密码统一 `123456`；学校官网接入后改写本脚本即可
  - 前端：独立 `/login` 路由（`front/app/login/page.tsx`），表单 = 学号 + 密码；`front/contexts/AuthContext.tsx` 暴露 `login()` / `logout()` / `currentUser`
  - 路由 gate：根路由 `/`（`front/app/page.tsx`）未登录时 `router.replace("/login")`；登录后顶部右上角显示学号、姓名、班级与登出按钮
  - 不在侧边栏放「登录」入口（登录是 gate，不是模块）
  - 没有 token / session / 强制鉴权后端其它端点：演示阶段够用，后续要真鉴权再补 JWT，不破坏接口契约

- **C2 学生数据归属**
  - 前端 save_score 调用链统一从 AuthContext 取 `student_id / student_name`
  - `WeldingRecord` 表字段 `student_id / student_name / batch_id` 已经存在且 nullable，**无需迁移**
  - 旧记录的 `student_id IS NULL` 问题留给 D3 脚本批量改为 `student_demo`
  - 验证：保存后能从 `/student-comparison` 看到分组

- **C3 数据树用户隔离**
  - `DataTreeContext` 加按 `student_id` 过滤
  - 持久化数据树到 localStorage（解决之前内存丢失问题）
  - 切换账号时清空 / 重加载该学生历史

- **C4 学生对比页 / PK 视图**
  - 左侧导航新建「学生对比 / PK」
  - 调 `/student-comparison` + `/batch-list`，同屏对比平均分、技能雷达、检测次数、最近趋势
  - 加分项：双数据树并排渲染

- **C5 检测态跨模块保活**（C3 复核期暴露的预存在 bug）
  - 现象：`焊缝检测` → 点「咨询 AI 教师」（`setActiveModule("teacher")`）→ 切回 `焊缝检测` 时 `currentScores / videoStreamUrl / isDetecting` 全部归零，无法继续「发送到预测系统」
  - 根因：`front/app/page.tsx` `renderMainContent()` 用 switch 渲染，切换 `activeModule` 时上一个模块整体卸载，`YOLORealtimeDetector` 的本地 React state 跟着丢
  - 修法（首选）：把 `currentScores`（甚至 `isDetecting / videoStreamUrl`）状态上提到 `WeldingDetectionSystem`，作为 props 下传给 detector，使其变受控组件——切回来时 props 还原。改动量约 30 行
  - 备选：模块卸载改为 `display: none` 切换（不推荐，会带累积内存）

- **C6 预测端点按学生过滤 + 取消 30 条上限**（C3 复核期发现）
  - 现象：登录不同学生看到的预测/技能雷达完全一样；折线图永远只有最近 30 条
  - 根因 1：`backend/api/predict.py::get_prediction` 不接受 `student_id` 参数，`_get_detection_data_from_db` 也不过滤；C2 把 `student_id` 入库了但消费端没接通
  - 根因 2：[predict.py:221](backend/api/predict.py) 硬编码 `recent_data = detection_data[-30:]`
  - 修法：
    - `/predict` 加可选 query 参数 `student_id`；`_get_detection_data_from_db` 多一个 `student_id` 过滤条件
    - 前端预测面板 fetch 时从 `AuthContext.currentUser.student_id` 取并拼到 URL
    - 删 `[-30:]` 切片，改用一个稍大的上限常量（如 200）做防御性截断
    - 预测缓存 key 要加 `student_id` 维度，否则缓存命中会跨学生串味
  - 验证：A 学生存 10 条都是 70-80 分的数据，B 学生存 10 条都是 90+ 的数据；切换登录应能看到不同的折线、雷达、forecast

### Phase D — 提案新增项（Phase B/C 之外）

按优先级：

- **D1 演示降级模式**（最重要的现场安全网）
  - 新建 `front/public/demo/weld.mp4`（占位或现有焊缝图序列）、`front/public/demo/cached_result.json`
  - 设置模块加开关：开启后摄像头流改读本地文件、YOLO 数据改读 cached_result.json
  - localStorage 键 `srtp:demo_safe_mode`

- **D2 删 `/predict/ai-radar-data` mock**
  - 后端：删 `_MOCK_RADAR_DATA` 7 套轮换，改为从 DB 按缺陷类型计数 + 技能维度求平均
  - 前端：拿到真数据时不再显示「示例数据」角标

- **D3 演示数据预播种**
  - 新建 `backend/scripts/seed_demo_data.py`：3-4 个学生 × 各 15-30 条历史检测，分数曲线合理（有上升 + 波动），不同学生有不同短板（A 偏宽度差、B 偏缺陷多）
  - 顺带：脚本里加一条 `UPDATE welding_records SET student_id='student_demo' WHERE student_id IS NULL`，把 C2 上线前的孤立旧记录归到 `student_demo`，避免 PK / 对比页出现「未指定学生」分组

- **D4 教学/严格模式切换**
  - 后端 detection runtime 暴露 confidence 可写状态（GET/POST `/api/v1/runtime/confidence`）
  - 前端设置面板加二档开关：教学 0.3 / 严格 0.6

- **D5 TTS 重要事件播报**
  - 新建 `front/lib/tts.ts`（speechSynthesis 封装 + 静音开关 + 显式 voice 选择）
  - DetectionModule 在 3 类事件触发播报：`总分 < 60` / `严重缺陷出现` / `保存成功`
  - 设置面板加全局静音开关；首次触发时给浏览器策略提示
  - 离线兜底：录 1-2 段关键 MP3 放 `front/public/demo/voice/`

- **D6 标准对齐文案**
  - PDF 报告页脚加「评分参考 GB/T 19418-2003 缺陷分级」
  - 新建 `docs/讲稿大纲.md`：把 GB/T 19418、GB/T 32259、1+X 三项叙事写进去
  - 不进 README（决策 #5）

### Phase E — 缺陷热图

- 数据库 `WeldingRecord` 加 `defect_bboxes` JSON 列（非破坏性迁移）
- 后端 save_score 多存 bbox 数据
- 前端历史记录页面单条点击 → 在原图上画 bbox；批次累积 → 热图

### Phase F — 冻结

- 2026-05-27：只修 bug，不加功能；连跑 3 遍演示
- 2026-05-28：打包备份（比赛电脑、U 盘、云盘）
- 演示注意事项：
  - **不要用 `npm run dev` 跑演示**。dev server 冷启动会按需编译路由（首次访问 `/` 因为编译未完成而返回 `_not-found` 404，刷新一次才正常）；务必用 `npm run build && npm run start` 跑生产模式
  - 生产构建后预热一遍：启动后浏览器先访问一次 `/login` 和 `/`，让 Next.js 完成首次响应

---

## 3. 决策摘要（2026-05-19 用户答复）

| # | 议题 | 决策 |
|---|---|---|
| 1 | 3D 路线 | 不由 Claude 负责（团队其他成员处理） |
| 2 | TTS 播报 | 做，仅重要事件（<60 分 / 严重缺陷 / 保存成功） |
| 3 | 教学模式 / 严格模式切换 | 做 |
| 4 | 演示降级模式 | 做 |
| 5 | 标准对齐叙事 GB/T 19418 + 1+X | 做，仅 PDF 和讲稿，不进 README |
| 6 | 演示数据预播种 | 做 |
| 7 | `/predict/ai-radar-data` mock | 删 |
| 8 | 缺陷空间标注 / 热图 | 列为最低优先级，最后做 |
| 9 | 中英切换 | 不做 |
| 10 | 演示登录放哪里 | 新建导航 |
| 11 | 是否按 STRUCTURE_REPLAN 拆分 page.tsx / yolo_realtime.py | 同意，逐步拆 |
| 12 | 任务流 | 先深度 /simplify → 完成原规划（不是 Claude 做的部分以外） → 完成提案剩余项 → 缺陷热图；代码改动等用户审核后再推 |

---

## 4. 推/审流程

- **文档改动**（`.claude/*.md`、`docs/*.md`、`README.md`）：commit 后立即双推。
- **代码改动**：commit 后**先不 push**，commit message 写清动机和影响范围、告知用户「待审」；用户授权后双推。
- 双推命令固定：
  ```bash
  git push srtp main
  git push gitee main:dev-upgrade
  ```

---

## 5. 完成阶段后必做：更新 [PROJECT_MEMORY.md](./PROJECT_MEMORY.md)

每个 Phase（A 完成 / B / C / D / E）结束都要追加修订条目到 §10：
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
- 后端：如果 P2 工作中发现某个端点需要 P0/P1 团队配合调整接口契约，告知用户、由用户协调

---

## 7. 关于硬件部分

- "有线摄像头接入" 的**代码侧**（环境变量、UI、参数下发、状态显示）由 Claude 做。
- 物理操作（插线、调光、对焦、装支架）由用户做。
- 联调时机：B1 完成 + 用户实物到位 → 用户告知 → Claude 协助一起走 start-yolo + 视频流验证。

---

## 8. 现在的下一步

1. ✅ 本文档 v3 修订完毕
2. PROJECT_MEMORY.md / STRUCTURE_REPLAN.md 同步修订（去掉 Claude 拥有 P0/P1 的错误描述）
3. 推送本次文档修订到双远程
4. 进入 Phase B：B1 摄像头配置化（此前已部分开始，会重新对齐这个新边界）
5. B1 → C1 → C2 → C3 → C4 → D1 → D2 → D3 → D4 → D5 → D6 → E → F
