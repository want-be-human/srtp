# 3DGS 模块 — 本次提交说明

> 分支: `feature/3dgs-upgrade` | 2026-05-24

## 加了什么

本提交在项目根目录下新增 `3dgs/` 模块，实现 **3D Gaussian Splatting** 从视频到 3D 场景的完整流水线。

### 五个部分

| 部分 | 路径 | 用途 |
|------|------|------|
| **训练流水线** | `gaussian-splatting/` | 基于论文源码，从 COLMAP 稀疏点云训练高斯场景 |
| **CUDA 扩展** | `gaussian-splatting/submodules/` | 微分光栅化 + KNN 初始化，编译后供 PyTorch 调用 |
| **辅助脚本** | `scripts/` | 视频抽帧、PLY 降采样/修复、COLMAP 一键运行 |
| **Web 查看器** | `viewer/` | Three.js 网页，浏览器中拖拽查看 .ply 模型 |
| **前端集成** | `front/components/detection/` | React 组件嵌入主系统，支持在线 3D 重构视图 |

### 目录速览

```
3dgs/
├── gaussian-splatting/          # 训练+渲染 (train.py, render.py, ...)
│   ├── scene/                   #   相机模型、数据集、高斯模型
│   ├── utils/                   #   工具函数
│   ├── lpipsPyTorch/            #   感知损失
│   └── submodules/              #   CUDA 扩展 (需本地编译)
├── scripts/                     # extract_frames / downsample_ply / fix_ply / run_colmap
├── data/test/                   # COLMAP 自动化脚本 (.sh)
├── viewer/                      # index.html + Three.js
├── .gitignore
├── README.md
└── CHANGELOG.md                 # 本文件
```

### 变更详情

- **新增** — 以上全部 ~180 个文件
- **删除** — `viewer/start.bat`（含错误路径，替换为 `启动查看器.bat`）
- **忽略** — `ruler.mp4`（训练视频，不入库）、`output/`、`venv/`、`*.ply` 等

## 前端集成

### 新增组件 `gaussian-splat-viewer.tsx`

基于 `@react-three/fiber` + `Three.js` 的 React 3D 高斯点云渲染组件，嵌入焊板检测系统主界面。

**功能特性:**
- PLY 文件流式加载及逐批次渐显动画
- 模拟 COLMAP → 3DGS 训练全流程管道进度条
- 焊板检测分数叠加显示（总分 / 光滑度 / 宽度 / 缺陷类型）
- 完整交互：旋转、缩放、平移、俯视/正视/侧视快捷键、自动旋转、点大小调节

### 修改文件

| 文件 | 变更 |
|------|------|
| `front/components/detection/yolo-realtime-detector.tsx` | 顶部新增"实时检测 / 3D重构视图"模式切换按钮，重构模式下渲染 GaussianSplatViewer |
| `front/lib/api.ts` | 新增 `UPLOAD_VIDEO`（视频上传）和 `MODEL_3DGS`（模型静态文件）接口 |

## 快速开始

```bash
# 1. 编译 CUDA 扩展 (需 CUDA 11.8+)
cd gaussian-splatting/submodules/diff-gaussian-rasterization && pip install -e .
cd ../simple-knn && pip install -e .

# 2. 准备数据: 视频 → 图片帧
python scripts/extract_frames.py --video ruler.mp4 --out data/test/input

# 3. SfM 重建 (需安装 COLMAP)
python scripts/run_colmap.py --source data/test

# 4. 训练
python gaussian-splatting/train.py -s data/test -m output/my_model

# 5. 查看
双击 viewer/启动查看器.bat → 浏览器拖入 .ply 文件
```

## 依赖

`pip install torch torchvision plyfile tqdm opencv-python numpy`
