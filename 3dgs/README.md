# 3DGS — 视频到网页 3D 模型

> **srtp-main 独立模块** | `feature/3dgs-viewer` 分支 | 不与主项目代码耦合

将任意视频通过 3D Gaussian Splatting (3DGS) 技术重建为 3D 模型，并在网页端实时交互查看。

---

## 效果展示

- 输入：`test.mp4`（7 秒，720×1280，竖屏）
- 输出：**664,188** 个高斯点，网页端实时旋转/缩放/平移

---

## 环境要求

| 组件 | 版本/要求 |
|------|----------|
| OS | Windows 10/11 |
| GPU | NVIDIA RTX 2060+，8GB+ VRAM |
| CUDA | 12.1 |
| Python | 3.11 |
| MSVC | Visual Studio 2022 Build Tools |
| ffmpeg | 任意版本 |

---

## 目录结构

```
srtp-main/                    # 主项目根目录
├── backend/                  # 主项目后端
├── front/                    # 主项目前端
├── docs/                     # 主项目文档
└── 3dgs/                     # ← 本模块
    ├── README.md
    ├── .gitignore
    ├── viewer/               # 网页查看器
    │   ├── index.html        #   查看器页面
    │   ├── start.bat         #   一键启动
    │   └── lib/              #   Three.js (160KB)
    ├── scripts/
    │   └── run_colmap.py     #   pycolmap SfM 流水线
    └── gaussian-splatting/   #   训练核心代码
        ├── train.py
        ├── convert.py
        ├── arguments/
        ├── scene/
        ├── gaussian_renderer/
        ├── utils/
        └── submodules/       #   CUDA 扩展（已打 MSVC 兼容补丁）
```

---

## 完整复现步骤

### 1. 克隆仓库并切到 3DGS 分支

```bash
git clone https://gitee.com/shollorak/srtp-main.git
cd srtp-main
git checkout feature/3dgs-viewer
```

### 2. 安装 Python 依赖

```bash
cd 3dgs

# 创建虚拟环境
python -m venv venv
venv\Scripts\activate

# PyTorch (CUDA 12.1)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# SfM & 训练依赖
pip install pycolmap plyfile tqdm opencv-python numpy
```

### 3. 克隆完整的 gaussian-splatting 子模块

本仓库只包含核心 Python 脚本和已打补丁的 setup.py。CUDA 扩展源码需单独克隆：

```bash
cd gaussian-splatting

# 克隆 diff-gaussian-rasterization（渲染器）
git clone https://github.com/graphdeco-inria/diff-gaussian-rasterization.git submodules/diff-gaussian-rasterization

# 克隆 simple-knn（点云初始化）
git clone --recursive https://gitlab.inria.fr/bkerbl/simple-knn.git submodules/simple-knn

# 克隆 GLM 头文件依赖
git clone --depth 1 https://github.com/g-truc/glm.git submodules/diff-gaussian-rasterization/third_party/glm
```

> **注意**：submodules/ 下的 setup.py 已修改好（兼容 VS2022 + CUDA 12.1），**覆盖**克隆后的原始文件：
> ```bash
> cp submodules/diff-gaussian-rasterization/setup.py submodules/diff-gaussian-rasterization/setup.py.bak  # 可选备份
> # setup.py 已经是打了补丁的版本，不需要额外操作
> ```

### 4. 编译 CUDA 扩展

```bash
set CUDA_HOME=C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.1
set TORCH_CUDA_ARCH_LIST=8.9
pip install --no-build-isolation submodules/diff-gaussian-rasterization submodules/simple-knn
```

验证：
```bash
python -c "from diff_gaussian_rasterization import _C; from simple_knn import _C; print('OK')"
```

### 5. 视频 → 帧 → COLMAP → 训练

```bash
# 回到 3dgs/ 目录
cd ..\..

# 创建数据目录
mkdir -p data\test\input output

# 提取视频帧 (fps 根据视频长度调整)
ffmpeg -i "你的视频.mp4" -vf "fps=5" data\test\input\frame_%04d.jpg

# 运行 COLMAP SfM
python scripts\run_colmap.py

# 训练 (7000 迭代, RTX 4060 约 10-20 分钟)
cd gaussian-splatting
python train.py -s ..\data\test -m ..\output\test --iterations 7000 --disable_viewer
```

训练产物：`output\test\point_cloud\iteration_7000\point_cloud.ply`

### 6. 模型后处理（**必须执行**）

训练输出的 scale 为 log 空间、opacity 为 logit 空间——网页查看器需要线性值：

```python
import struct, numpy as np

ply_path = 'output/test/point_cloud/iteration_7000/point_cloud.ply'
out_path = 'viewer/model_fixed.ply'

with open(ply_path, 'rb') as f:
    header = b''
    while True:
        line = f.readline(); header += line
        if line.strip() == b'end_header': break
    header_len = len(header)
    f.seek(0); f.read(header_len)
    raw = f.read()

vertex_size = 62 * 4
count = len(raw) // vertex_size
new_data = bytearray()

for i in range(count):
    off = i * vertex_size
    vals = list(struct.unpack('<62f', raw[off:off+vertex_size]))
    vals[52] = np.exp(vals[52])
    vals[53] = np.exp(vals[53])
    vals[54] = np.exp(vals[54])
    vals[51] = 1.0 / (1.0 + np.exp(-vals[51]))
    new_data += struct.pack('<62f', *vals)

with open(out_path, 'wb') as f:
    f.write(header); f.write(new_data)
print(f'Done: {count} splats → {out_path}')
```

### 7. 启动查看器

```bash
cd viewer
start.bat
# 或 python -m http.server 8080
```

浏览器打开 **http://localhost:8080**

---

## 操作说明

| 操作 | 功能 |
|------|------|
| **鼠标左键拖拽** | 旋转视角 |
| **鼠标右键拖拽** | 平移 |
| **滚轮** | 缩放 |
| **W/S 或 ↑/↓** | 前进/后退 |
| **A/D 或 ←/→** | 左右平移 |
| **Q/E** | 升降 |
| **+/-** | 调大/调小点大小 |
| **R** | 重置视角 |
| 底部按钮 | Top / Front / Side / Reset |

---

## 技术原理

```
视频 (.mp4)
  ↓ ffmpeg
图像序列 (.jpg)
  ↓ pycolmap (SIFT + 特征匹配 + SfM)
稀疏点云 + 相机位姿
  ↓ 3D Gaussian Splatting 训练 (CUDA)
.ply 模型 (664K 高斯点)
  ↓ 后处理 (log→linear scale)
model_fixed.ply
  ↓ Three.js + WebGL (浏览器)
交互式 3D 查看
```

## 为什么作为独立分支

本模块与其 srtp-main 主项目**无代码耦合**：
- 独立的 Python 虚拟环境
- 独立的 CUDA 依赖
- 仅通过 Git 分支组织在一起
- 可随时合并到 main 或保持独立维护

---

## 常见问题

**Q: CUDA 扩展编译报 `unsupported Microsoft Visual Studio version`**

A: submodules/ 下的 setup.py 已预置补丁（`-allow-unsupported-compiler` + `_ALLOW_COMPILER_AND_STL_VERSION_MISMATCH`）。如果从原始仓库重新克隆了 setup.py，需重新添加这些标志。

**Q: 训练 OOM**

A: 减少 SH degree 或降低图片分辨率：
```bash
python train.py ... --sh_degree 1 --resolution 1
```

**Q: 查看器黑屏**

A: 检查是否执行了步骤 6（模型后处理）。未处理的 .ply 中 scale/opacity 不兼容网页渲染。

**Q: COLMAP 重建失败（0 个 3D 点）**

A: 视频需要足够的视角变化。静态场景需多角度拍摄；纯色平面区域（白墙、天空）缺乏纹理特征。

---

## 致谢

- [3D Gaussian Splatting for Real-Time Radiance Field Rendering](https://repo-sam.inria.fr/fungraph/3d-gaussian-splatting/) — INRIA, Kerbl et al.
- [pycolmap](https://github.com/colmap/pycolmap) — COLMAP Python 绑定
- [Three.js](https://threejs.org/) — WebGL 渲染引擎 (MIT)
