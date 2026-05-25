# 焊育智眸 - 智能焊缝检测与教学分析系统

焊育智眸是一套面向焊接实训教学场景的智能检测系统，集成焊缝质量检测、缺陷识别、成绩预测、智能问答、数据树可视化和 PDF 报告导出等功能。系统服务于日常焊接教学、学生训练记录管理和阶段性质量分析。

## 项目定位

本系统围绕焊接训练中的“检测、反馈、分析、报告、成长记录”形成闭环：

- 通过摄像头或图片采集焊缝图像。
- 使用 YOLOv8 和 OpenCV 对焊缝质量进行识别与评分。
- 将检测结果沉淀为学生训练数据。
- 基于历史数据生成趋势预测、教学建议和质量报告。
- 通过 3D 数据树展示学生训练过程和成长轨迹。

## 核心功能

### 焊缝智能检测

- 支持实时摄像头检测和图片上传检测。
- 检测维度包括光滑度、焊缝宽度、缺陷控制和综合评分。
- 支持 17 类焊缝缺陷中英文映射。
- 后端通过多线程拆分视频采集、YOLO 推理和数据输出。

### 智能问答

- 支持基于检测结果的焊接技术问答。
- 可围绕缺陷原因、工艺参数、训练建议等问题生成指导。
- 支持 OpenAI 兼容接口，默认按 DeepSeek 接口格式配置。

### 智能预测

- 基于历史检测记录生成质量趋势预测。
- 展示历史分数和预测分数折线图。
- 提供技能雷达图、缺陷统计和智能分析建议。

### 数据树可视化

- 使用 Three.js / React Three Fiber 构建 3D 数据树。
- 每次检测记录可以转化为树上的一个数据点。
- 支持点击查看检测编号、缺陷类型、分数等细节。

### 报告导出

- 后端基于 ReportLab 生成 PDF 报告。
- 支持异步生成、进度轮询和下载。
- 报告内容包含统计概况、趋势分析、技能分析、缺陷分析和改进建议。

## 技术栈

### 后端

- Python
- FastAPI
- Uvicorn
- SQLAlchemy
- SQLite
- OpenCV
- Ultralytics YOLOv8
- scikit-learn
- ReportLab
- Matplotlib
- OpenAI 兼容 API

### 前端

- Next.js 15
- React 19
- TypeScript
- Tailwind CSS
- Radix UI / shadcn 风格组件
- lucide-react
- Recharts
- Three.js
- @react-three/fiber
- @react-three/drei

## 目录结构

```text
srtp-main/
├── backend/                         # FastAPI 后端
│   ├── api/                         # API 路由
│   │   ├── yolo_realtime.py         # 实时 YOLO 检测、视频流、分数保存
│   │   ├── teacher.py               # 智能问答
│   │   ├── predict.py               # 成绩预测与时序模型推理
│   │   ├── dashboard.py             # 仪表板统计
│   │   ├── calibration.py           # 摄像头单目标定
│   │   └── lesson_plan.py           # 报告数据和 PDF 生成任务
│   ├── services/
│   │   ├── yolo/                    # YOLO 与 OpenCV 检测模块
│   │   ├── prediction/              # 1D-CNN 时序预测器 + 训练产物
│   │   └── pdf_generator/           # 独立 PDF 报告生成器
│   ├── main.py                      # 后端入口
│   ├── models.py                    # SQLAlchemy 数据模型
│   ├── database.py                  # SQLite 数据库连接
│   ├── config.py                    # 统一配置
│   └── defect_types.py              # 焊缝缺陷类型映射
├── front/                           # Next.js 前端
│   ├── app/                         # App Router 页面入口
│   ├── components/
│   │   ├── detection/               # 焊缝检测页面组件
│   │   ├── ai-teacher/              # 智能问答组件
│   │   ├── prediction/              # 智能预测组件
│   │   ├── lesson-plan/             # 报告导出组件
│   │   ├── data-tree/               # 3D 数据树组件
│   │   └── ui/                      # 通用 UI 组件
│   ├── lib/api.ts                   # 前端 API 地址统一配置
│   └── package.json                 # 前端依赖和脚本
├── docs/                            # 项目说明文档
│   ├── temporal_model_design.md     # 1D-CNN 时序预测器设计说明
│   └── welding-3d-setup.html        # 3D 数据树静态演示页
├── lizi/                            # 独立粒子展示实验页面
├── start_all.bat                    # Windows 一键启动脚本
└── push_to_gitee.bat                # Gitee 推送辅助脚本
```

## 环境要求

- Windows 10/11
- Python 3.8 或更高版本
- Node.js 16 或更高版本
- 摄像头或 IP 摄像头
- 可选：NVIDIA GPU，用于提升 YOLO 推理速度

## 快速启动

### 方式一：一键启动

在项目根目录运行：

```bat
start_all.bat
```

脚本会分别启动：

- 后端服务：`http://localhost:8000`
- 前端页面：`http://localhost:3000`
- API 文档：`http://localhost:8000/docs`

### 方式二：手动启动

启动后端：

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

启动前端：

```bash
cd front
npm install --legacy-peer-deps
npm run dev
```

访问前端：

```text
http://localhost:3000
```

## 环境变量配置

后端需要在 `backend/` 目录下创建 `.env` 文件。可以参考 `backend/.env.example`。

示例：

```env
DEEPSEEK_API_KEY=your_api_key_here
AI_API_BASE_URL=https://api.deepseek.com
AI_MODEL=deepseek-chat
```

前端如需修改后端 API 地址，可在 `front/.env.local` 中配置：

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

注意：

- 不要将 `.env`、`.env.local`、API Key、账号密码或访问令牌提交到仓库。
- `AI_API_BASE_URL` 不需要手动追加 `/v1`。
- 未配置 Key 时，问答和文本分析功能不可用，但检测、预测、数据展示和报告仍可继续使用。

## 常用接口

后端接口统一挂载在 `/api/v1` 下：

```text
POST /api/v1/start-yolo                  启动实时检测
POST /api/v1/stop-yolo                   停止实时检测
GET  /api/v1/yolo-data                   获取最新检测数据
GET  /api/v1/video-stream                获取 MJPEG 视频流
POST /api/v1/detect-image                上传图片检测
POST /api/v1/save-score                  保存检测分数
GET  /api/v1/recent-scores               获取最近检测记录
GET  /api/v1/student-comparison          学生对比数据
GET  /api/v1/dashboard/quick-stats       仪表板快速统计
GET  /api/v1/predict                     获取预测数据
GET  /api/v1/predict/ai-radar-data       获取技能与缺陷六维雷达数据
GET  /api/v1/predict/ai-analysis         获取预测文本分析
POST /api/v1/teacher/chat                焊接技术问答
GET  /api/v1/lesson-plan                 获取报告数据
POST /api/v1/lesson-plan/generate-pdf    启动 PDF 生成任务
GET  /api/v1/calibration/current         获取当前摄像头标定参数
POST /api/v1/calibration/save            保存摄像头标定参数
```

完整接口可访问：

```text
http://localhost:8000/docs
```

## 数据库说明

当前使用 SQLite，本地数据库文件位于：

```text
backend/welding.db
```

核心数据表为 `welding_records`，主要字段包括：

- `student_id`
- `student_name`
- `batch_id`
- `smoothness_score`
- `spacing_score`
- `defect_type_score`
- `total_score`
- `actual_width`
- `defect_type_name`
- `timestamp`

这些字段可支撑后续学生登录、训练记录归属、数据树展示和 PK 对比功能。

## YOLO 检测说明

检测模型默认放置在：

```text
backend/services/yolo/models/best.pt
```

综合检测入口：

```text
backend/services/yolo/zonghe_hanjie_zhiliang_jiance_xitong.py
```

当前检测系统由三部分组成：

- 光滑度检测：基于焊缝区域亮度分布。
- 宽度检测：基于亮度梯度和边界搜索。
- 缺陷检测：基于 YOLOv8 目标检测。

综合评分权重：

```text
光滑度 0.3
宽度   0.3
缺陷   0.4
```

## 开发注意事项

- 前端安装依赖时建议使用 `npm install --legacy-peer-deps`。
- `front/` 中同时存在 `package-lock.json` 和 `pnpm-lock.yaml`，目前以 npm 为准。
- `next.config.mjs` 当前忽略 TypeScript 和 ESLint 构建错误，开发时仍应主动检查关键问题。
- 摄像头地址需要根据现场网络和设备情况调整。
- PDF、预测和文本分析模块都保留本地兜底分支，远程接口不可用时仍能出结果。
- 不要提交 `node_modules/`、`.next/`、数据库临时文件、API Key 和个人凭据。

## 使用流程

1. 启动后端和前端。
2. 进入控制中心查看系统状态。
3. 打开焊缝检测模块，启动实时检测或上传焊缝图片。
4. 查看总分、光滑度、宽度、缺陷控制和缺陷类型。
5. 保存当前检测数据。
6. 打开智能预测页面，查看历史趋势、预测曲线和技能雷达。
7. 打开数据树页面，查看训练数据的 3D 可视化。
8. 打开报告导出页面，生成并下载 PDF 报告。
9. 在问答页面针对当前检测结果进行咨询。

## 许可证

本项目暂未设置开源许可证。
