# -*- coding: utf-8 -*-
"""焊接质量时序预测：3 层 1D-CNN + AdaptiveAvgPool 吃任意长度的历史。

卷积保留时间维度（padding=1），最后做 global average pooling 把时间维 collapse 掉，
所以同一个模型对短序列（>= MIN_INFER_WINDOW）和长序列都能跑。训练时按几种典型
长度采样窗口，让模型见过多种 context size。CPU 上几秒训完，推理几毫秒。
"""

import json
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Sequence

import numpy as np
import torch
import torch.nn as nn

logger = logging.getLogger(__name__)

# docs/ 落盘训练曲线 + metrics，给答辩页和 docs/algorithm_upgrades.md 引用
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_DOCS_DIR = _REPO_ROOT / "docs"
_CURVE_PATH = _DOCS_DIR / "temporal_training_curve.png"
_METRICS_PATH = _DOCS_DIR / "temporal_metrics.json"
# state_dict 文件路径：每层 weight + bias 的 tensor 序列化结果。
# 进程启动时 _load_pretrained() 先尝试 load 它当作初始权重，跳过冷启动 train。
_WEIGHTS_PATH = _DOCS_DIR / "temporal_model.pt"


# 预测的步数
FORECAST_SIZE = 5
# 输入特征：光滑度 / 宽度 / 缺陷 三项子分数；不带总分以免和 label 同源泄漏
FEATURE_DIM = 3
# 分数归一化系数：原始 0-100，模型里走 0-1
SCORE_SCALE = 100.0
# 训练采样的几种 window 长度，让模型对短/长 context 都鲁棒
TRAIN_WINDOWS = (10, 15, 20, 25, 30)
# 推理时至少需要这么多行才走深度模型，少于这个数让调用方回退 RF
MIN_INFER_WINDOW = 5
# 推理时吃最多这么多最近的行，再长就截尾
MAX_INFER_WINDOW = 30
# 训练超参，CPU 几秒能跑完
DEFAULT_EPOCHS = 80
DEFAULT_LR = 1e-3
# 多收到这么多新记录就重新训一次模型
RETRAIN_DELTA = 30


class WeldTemporalCNN(nn.Module):
    """3 层 conv1d + GAP + 1 层 fc，参数约 5 KB，输入长度任意。"""

    def __init__(self):
        super().__init__()
        # padding=1 让卷积不改变时间维长度，从而支持任意长度输入
        self.conv1 = nn.Conv1d(FEATURE_DIM, 8, kernel_size=3, padding=1)
        self.conv2 = nn.Conv1d(8, 16, kernel_size=3, padding=1)
        self.conv3 = nn.Conv1d(16, 16, kernel_size=3, padding=1)
        # AdaptiveAvgPool 把变长时间维 collapse 成 1
        self.pool = nn.AdaptiveAvgPool1d(1)
        self.dropout = nn.Dropout(0.2)
        self.fc = nn.Linear(16, FORECAST_SIZE)

    def forward(self, x):
        # x shape: (batch, FEATURE_DIM, T) — T 可以是任意 >= 1 的整数
        x = torch.relu(self.conv1(x))
        x = torch.relu(self.conv2(x))
        x = torch.relu(self.conv3(x))
        x = self.pool(x).squeeze(-1)
        x = self.dropout(x)
        return self.fc(x)


def _rows_to_array(rows: Sequence) -> np.ndarray:
    """记录 dict 或 ORM 行都接受，统一成数组。"""
    out = []
    for r in rows:
        def _pick(key):
            if isinstance(r, dict):
                v = r.get(key)
            else:
                v = getattr(r, key, None)
            return float(v) if v is not None else 0.0

        out.append([
            _pick("smoothness_score"),
            # DB 列叫 spacing_score，业务里其实是宽度分数；两个键都查一下
            _pick("width_score") or _pick("spacing_score"),
            _pick("defect_score") or _pick("defect_type_score"),
            _pick("total_score"),
        ])
    return np.asarray(out, dtype=np.float32)


def _build_buckets(arr: np.ndarray):
    """按 TRAIN_WINDOWS 里的几个长度分桶切训练对，同长度的样本能在同一个 batch 里训。"""
    buckets = {}
    for L in TRAIN_WINDOWS:
        if len(arr) < L + FORECAST_SIZE:
            continue
        xs, ys = [], []
        for i in range(len(arr) - L - FORECAST_SIZE + 1):
            window = arr[i : i + L, :FEATURE_DIM] / SCORE_SCALE
            future = arr[i + L : i + L + FORECAST_SIZE, FEATURE_DIM] / SCORE_SCALE
            xs.append(window.T)
            ys.append(future)
        if xs:
            buckets[L] = (np.stack(xs), np.stack(ys))
    return buckets


def train_from_records(records: Sequence, epochs: int = DEFAULT_EPOCHS, lr: float = DEFAULT_LR) -> Optional[WeldTemporalCNN]:
    """样本不够拟合就返 None，让调用方回退 RF。records 必须按时间升序。"""
    arr = _rows_to_array(records)
    buckets = _build_buckets(arr)
    # 至少一组桶有 5+ 样本才训
    if not buckets or sum(len(x) for x, _ in buckets.values()) < 5:
        return None

    model = WeldTemporalCNN()
    optim = torch.optim.Adam(model.parameters(), lr=lr)
    loss_fn = nn.MSELoss()

    # 各桶先转成 tensor，每个 epoch 把每个桶都过一遍，让模型见过多种长度
    tensor_buckets = [
        (torch.from_numpy(X), torch.from_numpy(y))
        for X, y in buckets.values()
    ]

    epoch_losses: List[float] = []
    model.train()
    for _ in range(epochs):
        ep_losses: List[float] = []
        for X, y in tensor_buckets:
            optim.zero_grad()
            loss = loss_fn(model(X), y)
            loss.backward()
            optim.step()
            ep_losses.append(float(loss.item()))
        epoch_losses.append(float(np.mean(ep_losses)) if ep_losses else float("nan"))
    model.eval()

    sample_count = int(sum(len(x) for x, _ in buckets.values()))
    _dump_training_artifacts(model, tensor_buckets, epoch_losses, sample_count)
    return model


def _dump_training_artifacts(
    model: WeldTemporalCNN,
    tensor_buckets: Sequence,
    epoch_losses: Sequence[float],
    sample_count: int,
) -> None:
    """每次重训完都更新 docs/ 下的曲线 + metrics；任何 IO 失败都不影响训练成功。"""
    try:
        _DOCS_DIR.mkdir(parents=True, exist_ok=True)

        # 训练集自评 R²（数据量小不切验证集，标清楚口径就好）
        with torch.no_grad():
            preds: List[np.ndarray] = []
            targets: List[np.ndarray] = []
            for X, y in tensor_buckets:
                preds.append(model(X).cpu().numpy())
                targets.append(y.cpu().numpy())
        p = np.concatenate(preds, axis=0).reshape(-1)
        t = np.concatenate(targets, axis=0).reshape(-1)
        ss_res = float(np.sum((t - p) ** 2))
        ss_tot = float(np.sum((t - t.mean()) ** 2)) if t.size else 0.0
        r2_train = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")

        # 把 state_dict（每层 weight + bias 的 tensor）落盘成 .pt，跟 metrics 同步刷新；
        # 进程重启或别的脚本评估都可 `torch.load(_WEIGHTS_PATH)` 拿回这次训练的权重。
        torch.save(model.state_dict(), _WEIGHTS_PATH)

        metrics = {
            "trained_at": datetime.now().isoformat(timespec="seconds"),
            "sample_count": sample_count,
            "epochs": len(epoch_losses),
            "final_loss": epoch_losses[-1] if epoch_losses else None,
            "min_loss": min(epoch_losses) if epoch_losses else None,
            "r2_train": r2_train,
            "feature_dim": FEATURE_DIM,
            "forecast_size": FORECAST_SIZE,
            "windows": list(TRAIN_WINDOWS),
            "weights_path": str(_WEIGHTS_PATH.relative_to(_REPO_ROOT)).replace("\\", "/"),
        }
        _METRICS_PATH.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")

        # matplotlib 是可选依赖；没装就只保留 metrics.json
        try:
            import matplotlib
            # force=True 容忍 pyplot 已被别处 import 过的情况（比如 ultralytics 内置 plot）
            matplotlib.use("Agg", force=True)
            import matplotlib.pyplot as plt
        except ImportError:
            logger.info("matplotlib 不可用，跳过训练曲线 PNG")
            return

        fig, ax = plt.subplots(figsize=(6, 3.5), dpi=120)
        ax.plot(range(1, len(epoch_losses) + 1), epoch_losses, color="#3B82F6")
        ax.set_xlabel("epoch")
        ax.set_ylabel("MSE loss")
        ax.set_title(f"1D-CNN training loss (n={sample_count}, R²={r2_train:.3f})")
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        fig.savefig(_CURVE_PATH)
        plt.close(fig)
    except Exception as e:
        logger.warning(f"训练曲线落盘失败（不影响模型）: {e}")


def forecast(model: WeldTemporalCNN, recent_records: Sequence) -> List[float]:
    """有多少行就用多少行（截到 MAX_INFER_WINDOW），少于 MIN_INFER_WINDOW 返回中性预测。"""
    arr = _rows_to_array(recent_records)
    if len(arr) < MIN_INFER_WINDOW:
        return [85.0] * FORECAST_SIZE
    L = min(MAX_INFER_WINDOW, len(arr))
    window = arr[-L:, :FEATURE_DIM] / SCORE_SCALE
    x = torch.from_numpy(window.T[None, ...])
    with torch.no_grad():
        y = model(x).cpu().numpy()[0]
    return [float(np.clip(v * SCORE_SCALE, 0.0, 100.0)) for v in y]


# 模块级单例：用一把锁挡住并发训练，记录上次训练时的样本数判断是否需要重训
_model_lock = threading.Lock()
_model_cache = {"model": None, "trained_on_count": 0}


def _load_pretrained() -> Optional[WeldTemporalCNN]:
    """有 docs/temporal_model.pt 就 load 当冷启动权重，跳过首请求等训练。"""
    if not _WEIGHTS_PATH.exists():
        return None
    try:
        model = WeldTemporalCNN()
        # weights_only=True 让 torch 只反序列化 tensor，不执行任意 pickle，安全得多；
        # 也消掉 torch 2.5+ 的 FutureWarning，2.6 之后会默认 True。
        state = torch.load(_WEIGHTS_PATH, map_location="cpu", weights_only=True)
        model.load_state_dict(state)
        model.eval()
        logger.info(f"已加载预训练权重 {_WEIGHTS_PATH}")
        return model
    except Exception as e:
        logger.warning(f"加载 {_WEIGHTS_PATH} 失败，退回 lazy train: {e}")
        return None


def get_or_train(records: Sequence) -> Optional[WeldTemporalCNN]:
    """单例 + 数据漂移触发重训：新增 >= RETRAIN_DELTA 条记录就重新拟合一次。

    冷启动优先 load 离线训练的 .pt，让首次 deep 预测不用等 lazy train。

    n 在锁外读取是安全的，因为 trained_on_count 只单调增长，并发 caller 看到的总是合法快照。
    """
    n = len(records)
    with _model_lock:
        cached = _model_cache["model"]
        # 进程首次进来 cached 必然为 None，先试 load .pt 当 warm start
        if cached is None:
            pretrained = _load_pretrained()
            if pretrained is not None:
                _model_cache["model"] = pretrained
                # 把 trained_on_count 设到当前 n，让 RETRAIN_DELTA 计数从这里起步；
                # 不能设 0，否则首请求带 130 条立刻触发重训，white .pt 等于白 load
                _model_cache["trained_on_count"] = n
                return pretrained

        trained_n = _model_cache["trained_on_count"]
        if cached is not None and (n - trained_n) < RETRAIN_DELTA:
            return cached
        model = train_from_records(records)
        if model is not None:
            _model_cache["model"] = model
            _model_cache["trained_on_count"] = n
        return model
