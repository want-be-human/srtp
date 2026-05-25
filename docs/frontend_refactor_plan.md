# 前端重构与功能调整规划

> 来源：`前端重构.md`（本地任务清单，未入仓）+ 合并队友 3DGS 分支后的整合工作
>
> 目标：5 月 30 日前出可演示版本，先把样式和交互搭起来，后端逻辑次要项之后补。

## 0. 合并 3DGS 后的现状盘点

- 已并入：`3dgs/`（gaussian-splatting 上游 + 数据 + 训练脚本，1700+ 文件）、
  `front/components/detection/gaussian-splat-viewer.tsx`（新组件，632 行）
- `front/lib/api.ts` 已合：保留本端的 `CALIBRATION_SAVE/CURRENT`、`SNAPSHOT`、
  `LIST_CAMERAS`、`DETECTION_HEATMAP`，并叠加队友的 `UPLOAD_VIDEO`、`MODEL_3DGS`
- `front/components/detection/yolo-realtime-detector.tsx` 已合：保留本端的
  `CameraSelector`、`calibration` 状态、`isMock` 与 `已标定/未标定` 徽标，
  并叠加队友的 `viewMode` toggle（“实时检测 / 3D 重构视图”）
- 队友只新加了 1 个 commit（`1afd1d2`），除了 3DGS 没有其他超过本端进度的改动，
  不需要做功能取舍

## 1. 主界面（控制中心）— P0

- [ ] 删除控制中心三张统计卡：检测统计 / 平均分数 / 系统状态
  - 涉及：`front/app/page.tsx` 或 `front/components/dashboard/*` 中对应卡片块
- [ ] 把“焊缝检测 / 智能问答 / 智能预测”三个入口往下移
- [ ] 三张卡腾出来的位置：放一个高斯泼溅迷你预览框（自动播放、loop、无控件）
  - 复用 `GaussianSplatViewer`，加 `mini` 模式：禁用 OrbitControls、固定相机轨道
- [ ] 排查横向滚动条闪烁
  - 嫌疑点：根 `layout` 或 `page` 在加载时短暂 `overflow-x: visible`
  - 暂用 `html, body { overflow-x: hidden }` 收敛；后续定位真实溢出元素

## 2. WeldNet 检测页 — P1

- [ ] 页头标题：`焊缝检测` 改成 `WeldNet 智能检测系统`
- [ ] 当前已经在 `YOLORealtimeDetector` 内做了 `realtime / 3dgs` toggle，
      但 3DGS 视图是“替换主画面”形态。**调整为：实时检测主区在上，3DGS 区在下**
      （独立 Card，纵向排布），去掉 toggle
- [ ] 修“3DGS 加载到一半切走再回来从头重来”的问题
  - 当前 `GaussianSplatViewer` 挂在被切走时会 unmount，three.js scene 被销毁
  - 方案：把 viewer 实例提到父级（`page.tsx` 或 detection layout）保活，
    或者在父级用 `useRef` 缓存已加载的 `.ply` blob，重新 mount 时直接复用

## 3. 高斯泼溅交付形态 — P1

队友默认形态是“用户上传视频，后端训练再显示”。教学场景里没法等训练，改成预设。

- [ ] 移除前端上传视频入口（`UPLOAD_VIDEO` endpoint 保留但 UI 隐藏）
- [ ] 后端预生成 1 个示范 `.ply`（焊缝样本），放到 `backend/static/3dgs/model_light.ply`
- [ ] 渐进式显示：分轮加载点云，第一帧只渲染 20% 高斯点，之后逐步追加到 30%、60%、100%
  - 实现：把 `.ply` 切成 3-4 个分块文件，按序拉取并 merge 到 BufferGeometry
  - 或者用 LOD：单文件按 opacity 阈值排序后切片
- [ ] 首屏时间预算：30 秒内出可辨识形态，剩余精细化在背景继续
- [ ] 不追求极致渲染质量，重点是用户进页面立刻有内容可看

## 4. 智能预测 + 报告导出合并 — P1

- [ ] 把 `lesson-plan` 路由的页面合到 `prediction` 路由下，做成单一长页可下滑
  - 上半屏：现有 `PredictionDashboard`
  - 下半屏：报告导出 + PDF 预览 + 下载按钮
- [ ] 报告改为只导出当前登录学生的数据
  - 后端 `lesson_plan.py` 现在按全班聚合，要加 `student_id` 过滤参数
  - 前端调用时把 `currentUser.student_id` 透传
- [ ] 报告生成改用“静态数据库匹配 + 模板填充”出 PDF
  - 当前 PDF 生成调用了 LLM 做教学建议文本，慢且不稳
  - 退化方案：按总分区间（<70 / 70-85 / >85）匹配预设建议模板，纯查表
- [ ] AI 分析 API 配置修复
  - 排查：`AI_API_BASE_URL` / `AI_MODEL` 是否在 `.env` 里、`teacher.py`
    的 client 初始化是否拿到了非空 key
  - 加错误回显：API 调用失败时前端显示具体原因（key 未配 / 超时 / 401）

## 5. 数据树与学生对比合并 — P2

- [ ] 顶部 `数据树` 页面加 `PK 对比` 按钮，点击在页内切到对比视图
  - 实现：用 `useState` 的 mode 切换，复用同一路由，不做整页跳转
- [ ] 删独立 `student-comparison` 路由的入口（或保留路由但不挂导航）

## 6. AI 教师 — P2

- [ ] 加“历史对话记录”入口，列出当前学生的过往 Q&A
  - 后端已有 `TEACHER_HISTORY` endpoint，前端做对应列表 UI
- [ ] 确认 `chat` endpoint 真实拿到 LLM 返回
  - 失败场景检查：API key 缺 / API 超时 / response 解析失败
  - 失败时给具体提示，不要静默 fallback 到 mock
- [ ] 报告导出和 AI 教师共用同一 deepseek client，避免重复初始化

## 7. PDF 模板细节 — P3

- [ ] 修排版：表格对齐、中英文混排间距、长字段截断
- [ ] 头部加学生信息（学号 / 姓名 / 班级 / 报告日期）
- [ ] 评分趋势图嵌入：用 matplotlib 把 `temporal_metrics` 那张折线渲成 PNG 嵌入

## 8. 接入时机与依赖关系

- P0 控制中心：独立可并行
- P1 检测页：依赖 GaussianSplatViewer 形态调整
- P1 3DGS 渐进：需要先有切片好的 .ply（后端或离线脚本）
- P1 预测 + 报告合并：独立
- P2 数据树 + PK：独立
- P2 AI 教师：独立
- P3 PDF 模板：依赖 P1 报告导出合并

建议执行顺序：P0 控制中心，然后 P1 检测页样式、P1 预测+报告合并、
P1 3DGS 渐进形态，然后 P2 一组，最后 P3。

## 9. 合并后立刻暴露出来的几个新问题（明天一起改）

### 9.1 `/static/3dgs/model_light.ply` 404（必修）

队友前端写了 `API_ENDPOINTS.MODEL_3DGS = ${API_BASE_URL}/static/3dgs/model_light.ply`，
但后端 `main.py` 完全没挂 `StaticFiles`，`backend/static/` 目录也不存在，所以浏览器直接
404，前端 GaussianSplatViewer 拉模型失败，进 error 状态。

修法：
- `backend/main.py` 增加：
  ```python
  from fastapi.staticfiles import StaticFiles
  static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
  os.makedirs(static_dir, exist_ok=True)
  app.mount("/static", StaticFiles(directory=static_dir), name="static")
  ```
- 在 `backend/static/3dgs/` 放一个示范 `.ply`（先用队友 3dgs/data 里的演示模型）
- `.ply` 大的话考虑 gitignore，单独走百度网盘 / 自动下载脚本

### 9.2 摄像头标定每次启动都得重做（持久化失效）

排查结论：标定写库是好的（`calibration.py::save_calibration` 写 `CameraCalibration`
表，`load_calibration_pixels_per_mm` 启动时读）。**问题在于 `backend/welding.db`
本身被 git 追踪**，pull/merge 任何分支都会用仓库版本覆盖本地标定数据。

修法：
- `git rm --cached backend/welding.db` 把数据库从版本追踪里摘出去
- `.gitignore` 加 `backend/welding.db`
- 同时保留一份 `backend/welding.db.seed`（演示数据快照）供新机器初始化用，`main.py`
  启动时若发现 `welding.db` 不存在就从 `welding.db.seed` 复制一份
- 这是 destructive 操作（标定数据放在不入仓的 db 文件里），明天动手前先备份本地 db

### 9.3 高斯泼溅“摄像头采集”是 UI 假动画，不调摄像头（决策已定）

经查 `gaussian-splat-viewer.tsx`：
- 没有 `getUserMedia` / `<video>` / `navigator.mediaDevices` 调用
- `PIPELINE_STAGES` 数组里“从 3DGS 摄像头采集环绕视频 / COLMAP 重建 / 迭代 7000”
  全部是 `setInterval` 假进度，整个 `viewState === 'processing'` 期间只是按预设时长
  画进度条
- 实际只做一件事：从 `modelUrl` 拉预生成的 `.ply` 文件，Three.js 渲染点云

所以学生进检测页看到“正在采集”不会真的开摄像头，**全黑跟室内光线无关**，全黑的真正
原因就是 9.1 那个 404 让点云压根没下下来。

**当前决策（2026-05-26 敲定）**：

实际相机轨道（机械臂 / 转台）还没建好，COLMAP + 3DGS 实时训练管线也没接通，**保留假
动画 + 预生成 `.ply` 这套现状**。但前端能先准备的接入工作要做好，等硬件就绪能直接替换：

- 假动画 + 现成 `.ply` 渲染保留，作为现阶段对外展示的全部
- `PIPELINE_STAGES` 文案不改（"从摄像头采集"先继续讲，UI 层面不区分真假）
- 摄像头选择器 / 预留的本地缓存 / `getUserMedia` 调用点都把代码先写好，但**接口
  默认关闭**——等硬件 + 后端管线一通就 flip 开关切活路径

加速到能现场跑的可行性分析（COLMAP + 3DGS < 1 min 端到端）单独写到
[`docs/3dgs_acceleration_analysis.md`](./3dgs_acceleration_analysis.md)。

### 9.4 前端预留的硬件接入工作（明天做）

按 9.3 的"先把前端能做的做好"决策，明天落地这些代码骨架：

- **摄像头选择器**：在 `GaussianSplatViewer` 顶部加 `<Settings />` 按钮打开 selector
  dialog
  - 复用 `front/components/detection/camera-selector.tsx` + `lib/camera-config.ts`
  - localStorage key 用 `splat_camera_choice`，不复用检测页那把
- **采集帧抓取（写代码但默认禁用）**：用户点"开始三维重建"时，逻辑分支由开关决定：
  - `SPLAT_CAPTURE_ENABLED = false`（当前默认）：直接走假动画 + 预生成 `.ply`
  - `SPLAT_CAPTURE_ENABLED = true`（未来切换）：`getUserMedia` 抓 24 角度图传后端
    `/upload-video` endpoint，后端跑训练，前端轮询训练进度替换假动画
  - 开关位置放 `front/lib/feature-flags.ts`，硬件就位时改一行
- **本地缓存预留**：把"用户上传的视频" / "训练好的 .ply" 在浏览器 `IndexedDB` 里
  缓存，重复进 viewer 不重训
- **训练进度协议预留**：后端要的 `POST /upload-video` 返回 `task_id`，前端
  `GET /3dgs-status/:task_id` 轮询的协议在 `lib/api.ts` 把 endpoint 常量先加上，
  实现明天补
- **路径切换的 UI 反馈**：假动画路径下角标显示"演示模式"，真训练路径下显示
  "实拍重建"，让用户能区分（也方便后续调试）

## 10. 风险与未决项

- **3DGS 渐进加载的切片方案**：`.ply` 文件内部点云顺序不保证按视觉重要性排，
  直接前 20% 截可能出现稀疏空洞。可能需要先按距离相机的距离排序再切片
- **PDF 单人导出后**，PK 对比页里的“对手”怎么处理：当前对比依赖全班数据，
  改成单人导出不影响展示，但后端聚合接口可能要拆
- **AI 分析修复**：如果 deepseek API 在演示当天不稳，需要本地兜底模板，
  但要清楚标“离线模式”，不要假装是 LLM 输出
