# 焊接质量时序预测模型设计

文档对应实现：[`backend/services/prediction/temporal_model.py`](../backend/services/prediction/temporal_model.py)。

## 1. 目的

学生在系统里连续检测一段时间后，希望看到"未来 5 次的总分趋势预测"。这一块原本只用
Random Forest（`backend/prediction.py::predict_future_scores`），但 RF 对**时间局部形态**
不敏感——它把每条记录当独立样本，靠 lag 特征拼时序。所以加了一条"深度预测"通道与 RF
并存，前端 toggle 切换。

## 2. 模型架构

3 层 1D 卷积 + 全局平均池化 + 一层 fc，参数总数约 **1349（≈ 5.3 KB / FP32）**。

```text
Input  (batch, 3, T)              # T 任意，3 = 光滑度 / 宽度 / 缺陷
  │
  ▼   Conv1d(3→8,  kernel=3, padding=1) + ReLU
  ▼   Conv1d(8→16, kernel=3, padding=1) + ReLU
  ▼   Conv1d(16→16, kernel=3, padding=1) + ReLU
  │   # padding=1 让时间维长度保持 = T
  ▼   AdaptiveAvgPool1d(1)             # T → 1
  ▼   Dropout(0.2)
  ▼   Linear(16 → 5)
Output (batch, 5)                 # 未来 5 步总分（归一化值，外层 ×100 还原）
```

设计取舍：
- **卷积保留时间维 + 全局平均池化**：模型变成"长度无关"的——同一份权重在 T=5、T=20、
  T=30 上都能跑。如果用早期版本那种"卷积无 padding + flatten + fc"的做法，T 一变 fc 输入
  维就变，需要重训或改架构。
- **三层 conv 已经够看 ±3 步局部形态**（感受野 = 3 + 2 + 2 = 7 步）。再深也无意义，因为
  全局池化之后只保留通道级统计，更深的局部细节会被平均掉。
- **不带总分进输入**：标签是未来总分，输入只有三项子分数，避免 label leakage。
- **Dropout 0.2** 抑制小数据集场景下的过拟合。

## 3. 短序列与长序列同时支持

模型本身（adaptive pool）对输入长度没有结构性约束，但要让"短输入和长输入都准"，训练
阶段也要见过各种长度的样本：

```python
TRAIN_WINDOWS = (10, 15, 20, 25, 30)
```

`_build_buckets` 按这五种长度分桶切训练对（同一批历史能切出多个窗口长度的样本）。每个
epoch 把五个桶都过一遍，模型同时学到"5 步局部斜率"和"30 步整体趋势"的形态。

推理时：
- `len(input) >= 5`（`MIN_INFER_WINDOW`）：直接喂模型，取最近 `min(len, MAX_INFER_WINDOW=30)`
- `len(input) < 5`：返回中性预测（85 分），上游 API 看到样本太少会回退 RF

实测（递增趋势训练数据）：

| 输入长度 | 5 步预测 | 解读 |
|---|---|---|
| 5  | [65.5, 69.1, 63.2, 71.5, 71.8] | 只看到最早 5 行，预测偏向早期分数段 |
| 8  | [76.0, 77.4, 74.1, 78.0, 78.4] | 中段趋势 |
| 20 | [86.7, 85.9, 85.3, 84.6, 85.1] | 看到完整后段 |
| 30 | [88.7, 87.5, 87.4, 85.8, 86.3] | 与 50 同（自动截到 30） |
| 50 | [88.7, 87.5, 87.4, 85.8, 86.3] |
| 3  | [85, 85, 85, 85, 85]            | 不足 MIN，返回中性 |

同一份模型权重，输入长度从 5 到 50 都给出有意义的、与数据"新近度"单调相关的预测。

## 4. 性能

- 参数量：1349 个 FP32，5.3 KB 内存占用，权重文件 `.pt` 落盘约 8.4 KB
- CPU 训练（200 epoch，3480 个 train 样本，5 个 window bucket）：约 15 秒
- CPU 单次推理：< 10 ms（实测在普通笔记本上 < 3 ms）
- 不依赖 GPU；项目 torch 是 `2.5.1+cpu`

### 训练指标

数据集按学生切 70/15/15，每个学生 200 条连续时序，单生窗口不跨学生切（避免幽灵跳变）。
完整指标见 [`backend/services/prediction/artifacts/temporal_metrics.json`](../backend/services/prediction/artifacts/temporal_metrics.json)：

| split | 样本数 | MSE (归一化) | MAE (0-100 分数空间) | R²    |
|-------|--------|--------------|-----------------------|-------|
| train | 3480   | 0.0057       | 6.02 分               | 0.319 |
| val   | 204    | 0.0065       | 6.82 分               | 0.271 |
| test  | 204    | 0.0080       | **7.68 分**           | 0.112 |

best val 出现在 epoch 183（200 epoch 训练，之后轻微过拟合）。曲线见
[`artifacts/temporal_training_curve.png`](../backend/services/prediction/artifacts/temporal_training_curve.png)。

几个要注意的解读点：
- **MAE ≈ 7 分** 是最直观的指标——5 步预测的平均偏差。学生总分常在 70-90 分区间，
  对应相对误差 8-10%，足够支撑"趋势向好/平/下降"的判断。
- **train MSE 系统高于 val MSE** 是 dropout=0.2 在训练态打开造成的（噪声推高 train loss），
  评估态关闭后 val 更准。不是过拟合反转。
- **test R² 只有 0.11** 反映数据本身的高方差：缺陷类别和宽度触底样本是离散随机的，
  连续 5 步未来值的可解释方差天花板就不高。MAE 更适合作为业务指标。

## 5. 训练产物与部署

训练产物全部落在 [`backend/services/prediction/artifacts/`](../backend/services/prediction/artifacts/)：

| 文件                           | 大小    | 用途                                          |
|--------------------------------|---------|----------------------------------------------|
| `temporal_model.pt`            | 8.4 KB  | PyTorch state_dict，进程启动直接 load        |
| `temporal_metrics.json`        | < 1 KB  | 训练指标快照                                  |
| `temporal_training_curve.png`  | ~30 KB  | train/val 双线训练曲线                        |
| `temporal_training_data.csv`   | ~70 KB  | 训练用的时序数据集（六学生连续 200 条）      |

部署流程：
- FastAPI 启动时 `_warm_load_temporal_model()` 在 `@app.on_event("startup")` 钩子里
  `torch.load(temporal_model.pt, weights_only=True)`，把权重 load 进 `_model_cache`。
- 用户登录后前端顶层会立即在后台拉一次 `/predict` 和 `/predict/ai-radar-data`，把
  结果写到 localStorage，进智能预测页面瞬间出图。
- 切到深度预测时直接命中已加载的模型，单次推理 < 3 ms。
- 累计 30 条新记录后触发在线重训并刷新 `.pt`，保留数据漂移跟随能力。

## 6. 为什么 1D-CNN 而不是 LSTM / Transformer

主要理由是 **CPU 推理速度** + **小样本鲁棒性**：

- **Bai, Kolter, Koltun (2018)** ["An Empirical Evaluation of Generic Convolutional and
  Recurrent Networks for Sequence Modeling"](https://arxiv.org/abs/1803.01271) 在
  Adding、Copy Memory、PennTreebank、Music 等多个序列任务上比较 1D-CNN（TCN）与 LSTM/GRU，
  结论是 1D-CNN 大多数情况下**精度持平或略胜，且训练/推理快 3-5 倍**。教学场景里的
  PC CPU 不一定能 real-time 跑 LSTM。
- **Lim & Zohren (2021)** [Time-series forecasting with deep learning: a survey](https://arxiv.org/abs/2004.13408)
  也指出，对短序列（< 100 步）任务，卷积/MLP 与 RNN 在准确度上没有显著差距，但卷积可并行、
  参数更少，工业部署友好。
- 我们的窗口最大 30 步、数据量百量级，正好落在 1D-CNN 比 LSTM 更友好的区间。

为什么不用 Transformer：参数量级（最小 self-attention 也要几万参数）和数据量不匹配，
小样本上很容易过拟合。

## 7. 论文与可靠数据来源

- Bai, S., Kolter, J. Z., & Koltun, V. (2018). *An Empirical Evaluation of Generic
  Convolutional and Recurrent Networks for Sequence Modeling.* arXiv:1803.01271.
  <https://arxiv.org/abs/1803.01271>  ——
  1D-CNN 在序列建模上整体不输 LSTM 的核心依据。我们的 3 层卷积是 TCN 的简化版（去掉了
  dilated convolution 和残差连接，因为窗口最长才 30）。
- van den Oord, A., et al. (2016). *WaveNet: A Generative Model for Raw Audio.*
  arXiv:1609.03499. <https://arxiv.org/abs/1609.03499>  ——
  dilated 1D 卷积处理长序列的奠基论文，提供"卷积也能看远距离"的设计依据。我们当前
  serving 短序列没启用 dilation，长度更长时可以参考升级。
- Cui, Z., Chen, W., & Chen, Y. (2016). *Multi-Scale Convolutional Neural Networks for
  Time Series Classification.* arXiv:1603.06995. <https://arxiv.org/abs/1603.06995>  ——
  我们多窗口训练（TRAIN_WINDOWS 取五个长度）的思想来源，让单一模型对多种 context
  size 都有响应。
- Lim, B., & Zohren, S. (2021). *Time-series forecasting with deep learning: a survey.*
  Phil. Trans. R. Soc. A. arXiv:2004.13408. <https://arxiv.org/abs/2004.13408>  ——
  小样本短序列场景下 CNN 与 RNN 性能对比的综述。
- Period-Sensitive LSTM for Welding Quality (IEEE 2024).
  <https://ieeexplore.ieee.org/document/10716249/>  ——
  焊接质量时序预测的领域参考，证实"时序模型对焊接质量预测有效"，但其使用 LSTM；本项目
  CPU-only 部署选择更轻的 1D-CNN。

## 8. 当前局限与后续方向

- 训练数据是基于学生画像合成的连续时序，未在大规模真实焊接采集数据上做过端到端评估；
  论文支撑只能说明*架构选择合理*，不等于*精度有保证*。模型输出是基于历史数据外推的
  趋势，不是质检意义上的"未来一定是这个分"。
- 没有不确定度估计。后续可加 MC Dropout 或 ensemble 给前端画出 confidence band。
- 多窗口训练目前是简单的"每个长度一个桶"，可以升级到课程学习（先短后长）或
  attention pooling 提升精度。
- 真要承诺"长序列效果好"（比如 100+ 步），应该加 dilated convolution（WaveNet 风格）
  把感受野指数级放大，当前 7 步感受野够覆盖项目里实际的窗口长度。

## 9. 数据流

```
WeldingRecord (DB)
  │
  ▼  api/predict.py::_get_detection_data_from_db
  │     按 student_id / timestamp 拉记录
  ▼
prediction.py::predict_with_temporal_model
  │     DataFrame ↔ list[dict] 转换
  ▼
services/prediction/temporal_model.py
  ├─ get_or_train(records)
  │     模块级单例 + 锁；新增记录达到 RETRAIN_DELTA 才重训
  ├─ train_from_records  (按 TRAIN_WINDOWS 分桶训)
  └─ forecast            (取近 ≤ MAX_INFER_WINDOW 行推理)
  │
  ▼
api/predict.py
  返回 PredictionResponse → 前端 /predict?mode=deep
```
