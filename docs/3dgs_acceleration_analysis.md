# COLMAP + 3DGS 端到端能否压缩到 1 min 内的可行性分析

> 触发问题：当前 `gaussian-splat-viewer.tsx` 的 `PIPELINE_STAGES` 里宣称"采集 → COLMAP
> SfM → 3DGS 训练 → 优化"全流程跑完。**如果真要把假动画换成真训练**，社区主流流程
> 在 RTX 4060 笔记本上跑 24 张图大概 10-30 min，跟教学演示节奏完全不兼容。
>
> 本文回答：能不能压到 1 min 内？答案是**能，但要换掉 vanilla COLMAP + 3DGS 这两步
> 中的至少一步**，并且需要 GPU。下面拆出来讲。

## 1. 现状基线

vanilla 流程（队友 `3dgs/gaussian-splatting/` 引入的就是这套上游实现，对应 Kerbl 等
SIGGRAPH 2023 原论文）：

| 阶段                                    | 工具                                              | 24 张图、RTX 4060 单卡耗时    |
|-----------------------------------------|---------------------------------------------------|-------------------------------|
| (1) 特征提取 + 匹配                     | COLMAP `feature_extractor` + `exhaustive_matcher` | 1-3 min（CPU bottleneck）     |
| (2) Sparse Reconstruction (SfM/BA)      | COLMAP `mapper`                                   | 1-5 min                       |
| (3) 稠密化（可选，3DGS 输入只需 sparse）| `image_undistorter` + `patch_match_stereo`        | 5-15 min（这一步通常被跳过）  |
| (4) 3DGS 训练                           | `train.py`，30 000 iter                           | 20-40 min                     |
| (4') 3DGS 训练，7 000 iter              | 同上                                              | 5-10 min                      |
| (5) 渲染 / 导出 `.ply`                  | `render.py`                                       | < 30 s                        |

跳过 (3) 用 7 000 iter 训练的最短路径：**7-18 min**。仍然不在 1 min 量级。

## 2. 为什么 1 min 是真的可达：feed-forward 方法

2024 年开始有一类完全不同的方法——**不做逐场景训练**，而是把"多视图 → 3DGS"当成一个
回归问题，训一个大模型（一次性，离线，几天），推理时单次前向出 3DGS：

| 方法                  | 输入                       | 推理时间（A100/4090）        | 备注 |
|-----------------------|----------------------------|------------------------------|------|
| Splatter Image        | 单图                       | ~24 ms                       | CVPR 2024，单图 → 3DGS |
| PixelSplat            | 2 视图（已知 pose）        | ~50 ms                       | CVPR 2024 |
| MVSplat               | N 视图（已知 pose）        | 几十 ms                      | ECCV 2024 |
| LGM                   | 4 视图（任意 pose）        | ~5 s                         | ECCV 2024，4 张图重建物体 |
| GS-LRM                | 4 视图                     | ~0.5 s                       | ECCV 2024，输出 ~50万高斯点 |
| InstantSplat          | unposed 视频               | < 1 min 端到端               | arXiv 2024，结合 MASt3R |

代价：
- 这些方法都依赖**大模型 + GPU 推理**，参数量 GB 级
- "可推理时间快"不等于"可在 4060 笔记本上跑"——很多论文报告的数字是 A100/H100
- 输出的 3DGS 质量比逐场景训 30K iter 弱，物体边缘 / 细节会糊

但对**焊接板这种物体级、几乎平面、可以固定相机轨道**的场景，feed-forward 路径
可能性最高。

## 3. SfM/COLMAP 这一步的加速选项

如果还是想保留"先做几何对齐再训练"的逐场景管线，COLMAP 本身可以替换：

| 替代                  | 收益                              | 代价                                 |
|-----------------------|-----------------------------------|--------------------------------------|
| GPU COLMAP            | 3-5× 加速 feature matching        | 仍然需要 minutes 量级，不改本质      |
| **VGGSfM** (CVPR 2024)| feed-forward SfM，秒级出 pose + sparse cloud | GPU 推理，输入图像数受限（~30 张以内） |
| **DUSt3R** (CVPR 2024)| 不需要 intrinsics，直接出 dense pointmap | 输出几何精度不如 COLMAP，但够 3DGS 用 |
| **MASt3R** (ECCV 2024)| DUSt3R 升级版，更快更准           | InstantSplat 用的就是它              |
| **VGGT** (CVPR 2025)  | 单次前向出 pose + depth + 点云    | 极快（秒级），但很新，代码稳定性待验证 |
| **跳过 SfM**          | 直接用预标定的相机轨道（相机装在转台上，内外参一次性标完） | 需要硬件配合（教学场景完全可行）     |

**结论**：教学场景里"焊板 + 转台"或"机械臂"相机轨道一旦固定，相机内外参可以离线标定
一次。**这时 SfM 完全可以省掉**——给训练脚本直接喂预标定参数就行。从 10 min 缩到 0 s。

## 4. 3DGS 训练这一步的加速选项

| 路径                            | 收益                                  | 代价                          |
|---------------------------------|---------------------------------------|-------------------------------|
| 减少 iter（30K → 7K → 3K → 1K） | 线性加速                              | 物体清晰度逐档下降            |
| 学习率 schedule 优化            | 1.5-2× 加速                           | 调参成本                      |
| **MCMC-based densification**（2024）| 收敛更快                          | 还在论文阶段，代码不一定稳    |
| **Mini-Splatting**（CVPR 2024） | 更紧凑的高斯点初始化                  | 实现门槛                      |
| **直接用 feed-forward 模型**    | 跳过逐场景训练，秒级                  | 不能 fine-tune 到本场景特性   |

针对焊板这种几乎平面的物体，**1 000-3 000 iter 通常已经够看**（焊缝纹理本身就不
丰富），3-5 min 量级。

## 5. 针对本项目的可行方案矩阵

把 SfM 和训练两步组合，从慢到快列出：

| 方案 | SfM             | 训练                | 总时间预算   | GPU 要求     | 实现难度   |
|------|-----------------|---------------------|--------------|--------------|------------|
| 现状 | vanilla COLMAP  | 30K iter            | 25-50 min    | RTX 4060+    | 已落地     |
| 短路 | vanilla COLMAP  | 7K iter             | 7-15 min     | RTX 4060+    | 改一行 arg |
| 加速 | MASt3R          | 1K iter + MCMC      | 1-3 min      | RTX 4060+    | 中（接 MASt3R）|
| **跳 SfM**| 预标定轨道（0 s）| 1K iter             | 30-60 s      | RTX 4060+    | 中（标定一次性）|
| **feed-forward** | （跳过）   | LGM / GS-LRM 推理   | 5-30 s       | A100 / 4090  | 高（要训自己的模型，或用通用模型接受质量损失）|

**推荐路径（综合考虑项目硬件 + 演示节奏 + 实现难度）**：

1. **第一步先做"跳 SfM + 短 iter"**：硬件上把转台 / 机械臂相机轨道固定下来，离线
   标定一次相机内外参，前端采集 24 张图直接喂训练脚本（跳过 COLMAP）。训练 1K
   iter 出 `.ply`。**预算 30-60 s**，在 RTX 4060 上完全可行。
2. **第二步可选升级到 feed-forward**：如果第一步实测 30 s 仍嫌慢，再考虑接 LGM /
   GS-LRM。这条路径需要：
   - GPU 显存（LGM 大约 8GB 推理时显存）
   - 或者拿通用预训练模型直接推理（焊板场景质量可能掉，但 < 5 s 出 3DGS）

## 6. 跟本项目"CPU-only 部署"硬约束的冲突

项目当前 `requirements.txt` 是 `torch==2.5.1+cpu`，没有 GPU 依赖。**3DGS 训练 100%
需要 CUDA**（`diff-gaussian-rasterization` 就是 CUDA 内核）。如果要把实时训练接进去，
**必须接受**：

- 演示机器装一张 GPU（RTX 4060+ 起步，工业 PC 也能装）
- 或者训练放云端：教学机器只做拍图 + 上传 + 渲染，云端机器跑训练
- 或者完全保留假动画（当前决策）

渲染端（看 `.ply`）不需要 GPU——浏览器 WebGL 走显卡通用渲染路径，集成显卡也能跑。
**所以"训练 vs 渲染"是天然的 GPU vs CPU 分工**。

## 7. 当前决策与落地节奏

跟 `frontend_refactor_plan.md` §9.3 同步：

- **现阶段（5 月底前）**：保留假动画 + 预生成 `.ply`。前端 9.4 节列出的接入工作
  （摄像头选择器 / `getUserMedia` / 训练进度协议）写代码骨架但默认关闭
- **硬件就绪后第一步**：装 GPU + 固定相机轨道，标定相机内外参一次，跳掉 COLMAP，
  3DGS 跑 1K iter 出 `.ply`，目标 30-60 s
- **未来再升级**：如果实测 30 s 还慢，引入 MASt3R 或 LGM-class feed-forward 模型，
  目标 < 10 s

## 8. 论文与可靠数据来源

**3DGS 原论文**
- Kerbl, B., Kopanas, G., Leimkühler, T., Drettakis, G. (2023). *3D Gaussian Splatting
  for Real-Time Radiance Field Rendering.* SIGGRAPH 2023 (best paper).
  <https://repo-sam.inria.fr/fungraph/3d-gaussian-splatting/>

**SfM 替代 / 加速**
- Wang, J., Karaev, N., Rupprecht, C., Novotny, D. (2024). *VGGSfM: Visual Geometry
  Grounded Deep Structure From Motion.* CVPR 2024. <https://vggsfm.github.io/>
- Wang, S., Leroy, V., Cabon, Y., Chidlovskii, B., Revaud, J. (2024). *DUSt3R:
  Geometric 3D Vision Made Easy.* CVPR 2024. <https://dust3r.europe.naverlabs.com/>
- Leroy, V., Cabon, Y., Revaud, J. (2024). *Grounding Image Matching in 3D with
  MASt3R.* ECCV 2024. <https://github.com/naver/mast3r>
- Wang, J., Chen, M., Karaev, N., Vedaldi, A., Rupprecht, C., Novotny, D. (2025).
  *VGGT: Visual Geometry Grounded Transformer.* CVPR 2025.
  <https://github.com/facebookresearch/vggt>

**Feed-forward 3DGS**
- Charatan, D., Li, S., Tagliasacchi, A., Sitzmann, V. (2024). *PixelSplat: 3D
  Gaussian Splats from Image Pairs for Scalable Generalizable 3D Reconstruction.*
  CVPR 2024. <https://davidcharatan.com/pixelsplat/>
- Chen, Y., Xu, H., Zheng, C., Zhuang, B., Pollefeys, M., Geiger, A., Cham, T.-J.,
  Cai, J. (2024). *MVSplat: Efficient 3D Gaussian Splatting from Sparse Multi-View
  Images.* ECCV 2024. <https://donydchen.github.io/mvsplat/>
- Tang, J., Chen, Z., Chen, X., Wang, T., Zeng, G., Liu, Z. (2024). *LGM: Large
  Multi-View Gaussian Model for High-Resolution 3D Content Creation.* ECCV 2024.
  <https://me.kiui.moe/lgm/>
- Zhang, K., Bi, S., Tan, H., Xiangli, Y., Zhao, N., Sunkavalli, K., Xu, Z. (2024).
  *GS-LRM: Large Reconstruction Model for 3D Gaussian Splatting.* ECCV 2024.
  <https://sai-bi.github.io/project/gs-lrm/>
- Szymanowicz, S., Rupprecht, C., Vedaldi, A. (2024). *Splatter Image: Ultra-Fast
  Single-View 3D Reconstruction.* CVPR 2024. <https://szymanowiczs.github.io/splatter-image>
- Fan, Z., Cong, W., Wen, K., Wang, K., Zhang, J., Ding, X., Xu, D., Ivanovic, B.,
  Pavone, M., Pavlakos, G., Wang, Z., Wang, Y. (2024). *InstantSplat: Unbounded
  Sparse-view Pose-free Gaussian Splatting in 40 Seconds.* arXiv:2403.20309.
  <https://instantsplat.github.io/>

**3DGS 训练加速**
- Yu, Z., Chen, A., Huang, B., Sattler, T., Geiger, A. (2024). *Mip-Splatting:
  Alias-free 3D Gaussian Splatting.* CVPR 2024.
- Huang, B., Yu, Z., Chen, A., Geiger, A., Gao, S. (2024). *2D Gaussian Splatting
  for Geometrically Accurate Radiance Fields.* SIGGRAPH 2024.
- Fan, Z., Wang, K., Wen, K., Zhu, Z., Xu, D., Wang, Z. (2024). *LightGaussian: Unbounded
  3D Gaussian Compression with 15× Reduction and 200+ FPS.* NeurIPS 2024.

## 9. 不在本期范围

- 用 NeRF 系（Instant-NGP / Plenoxels）替代 3DGS：实时渲染不如 3DGS，跟队友
  已经接好的 viewer 不兼容，不考虑
- 4D-GS（动态场景）：焊接是静态板，没必要
- Mesh 提取（SuGaR）：项目不需要导出网格
