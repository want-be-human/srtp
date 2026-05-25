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

- [ ] 页头标题：`焊缝检测` → `WeldNet 智能检测系统`
- [ ] 当前已经在 `YOLORealtimeDetector` 内做了 `realtime / 3dgs` toggle，
      但 3DGS 视图是“替换主画面”形态。**调整为：实时检测主区在上，3DGS 区在下**
      （独立 Card，纵向排布），去掉 toggle
- [ ] 修“3DGS 加载到一半切走再回来从头重来”的问题
  - 当前 `GaussianSplatViewer` 挂在被切走时会 unmount，three.js scene 被销毁
  - 方案：把 viewer 实例提到父级（`page.tsx` 或 detection layout）保活，
    或者在父级用 `useRef` 缓存已加载的 `.ply` blob，重新 mount 时直接复用

## 3. 高斯泼溅交付形态 — P1

队友默认形态是“用户上传视频 → 训练 → 显示”。教学场景里没法等训练，改成预设。

- [ ] 移除前端上传视频入口（`UPLOAD_VIDEO` endpoint 保留但 UI 隐藏）
- [ ] 后端预生成 1 个示范 `.ply`（焊缝样本），放到 `backend/static/3dgs/model_light.ply`
- [ ] 渐进式显示：分轮加载点云，先显示低密度版（前 20% 高斯点）→ 30% → 60% → 100%
  - 实现：把 `.ply` 切成 3-4 个分块文件，按序拉取并 merge 到 BufferGeometry
  - 或者用 LOD：单文件按 opacity 阈值排序后切片
- [ ] 首屏时间预算：30 秒内出可辨识形态，剩余精细化在背景继续
- [ ] 不追求极致渲染质量，重点是“评委进页面就能看到东西”

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

```
P0 控制中心  →  独立可并行
P1 检测页    ←  依赖 GaussianSplatViewer 形态调整
P1 3DGS 渐进 ←  需要先有切片好的 .ply（后端 / 离线脚本）
P1 预测+报告 ←  独立
P2 数据树+PK ←  独立
P2 AI 教师   ←  独立
P3 PDF 模板  ←  依赖 P1 报告导出合并
```

建议执行顺序：P0 控制中心 → P1 检测页样式 → P1 预测+报告合并 →
P1 3DGS 渐进形态 → P2 → P3。

## 9. 风险与未决项

- **3DGS 渐进加载的切片方案**：`.ply` 文件内部点云顺序不保证按视觉重要性排，
  直接前 20% 截可能出现稀疏空洞。可能需要先按距离相机的距离排序再切片
- **PDF 单人导出后**，PK 对比页里的“对手”怎么处理：当前对比依赖全班数据，
  改成单人导出不影响展示，但后端聚合接口可能要拆
- **AI 分析修复**：如果 deepseek API 在演示当天不稳，需要本地兜底模板，
  但要清楚标“离线模式”，不要假装是 LLM 输出
