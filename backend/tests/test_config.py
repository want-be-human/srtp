"""config.py 配置加载的回归测试。

config.py 是单一事实来源，必须保证：
1. AI_* / OPENAI_* 双套环境变量名都被识别；
2. base_url / model 默认值兜底到 DeepSeek；
3. yolo_config.json 缺失或损坏时 OPTIMAL_WELD_WIDTH_MM 走默认 5.5；
4. CORS_ORIGINS 包含 localhost 必要项；
5. YOLO_CONFIDENCE / IOU 阈值在合理区间。
"""

import importlib
import json
import sys
from pathlib import Path

import pytest


def _reload_config(monkeypatch, env: dict):
    """清空所有 AI/OPENAI 相关 env，再按 env 设置，最后 reload 拿到新值。"""
    for k in [
        "DEEPSEEK_API_KEY", "OPENAI_API_KEY",
        "AI_API_BASE_URL", "OPENAI_BASE_URL",
        "AI_MODEL", "OPENAI_MODEL",
    ]:
        monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)

    if "config" in sys.modules:
        del sys.modules["config"]
    import config
    importlib.reload(config)
    return config


class TestAIConfigPrecedence:
    def test_deepseek_key_takes_priority(self, monkeypatch):
        cfg = _reload_config(monkeypatch, {
            "DEEPSEEK_API_KEY": "sk-deepseek-aaa",
            "OPENAI_API_KEY": "sk-openai-bbb",
        })
        # 优先用 DEEPSEEK_API_KEY，OPENAI_API_KEY 仅作 fallback
        assert cfg.AI_API_KEY == "sk-deepseek-aaa"

    def test_openai_key_fallback(self, monkeypatch):
        cfg = _reload_config(monkeypatch, {
            "OPENAI_API_KEY": "sk-openai-only",
        })
        assert cfg.AI_API_KEY == "sk-openai-only"

    def test_no_key_returns_empty_string(self, monkeypatch):
        cfg = _reload_config(monkeypatch, {})
        assert cfg.AI_API_KEY == ""

    def test_base_url_default_to_deepseek(self, monkeypatch):
        cfg = _reload_config(monkeypatch, {})
        assert cfg.AI_API_BASE_URL == "https://api.deepseek.com"

    def test_base_url_no_v1_suffix(self, monkeypatch):
        # README 明确写"AI_API_BASE_URL 不需要手动追加 /v1"
        cfg = _reload_config(monkeypatch, {})
        assert not cfg.AI_API_BASE_URL.rstrip("/").endswith("/v1")

    def test_ai_model_default_to_deepseek_chat(self, monkeypatch):
        cfg = _reload_config(monkeypatch, {})
        assert cfg.AI_MODEL == "deepseek-chat"

    def test_openai_base_url_fallback(self, monkeypatch):
        # 没 AI_API_BASE_URL 就用 OPENAI_BASE_URL
        cfg = _reload_config(monkeypatch, {
            "OPENAI_BASE_URL": "https://example.com/openai",
        })
        assert cfg.AI_API_BASE_URL == "https://example.com/openai"


class TestServerConfig:
    def test_default_host_bind_all(self, monkeypatch):
        cfg = _reload_config(monkeypatch, {})
        assert cfg.BACKEND_HOST == "0.0.0.0"

    def test_default_port(self, monkeypatch):
        cfg = _reload_config(monkeypatch, {})
        assert cfg.BACKEND_PORT == 8000

    def test_port_override_from_env(self, monkeypatch):
        cfg = _reload_config(monkeypatch, {"BACKEND_PORT": "9001"})
        assert cfg.BACKEND_PORT == 9001


class TestCorsOrigins:
    def test_localhost_3000_included(self):
        # CORS 白名单必须含本地前端开发地址，否则联调会被 CORS 拦
        import config
        assert "http://localhost:3000" in config.CORS_ORIGINS
        assert "http://127.0.0.1:3000" in config.CORS_ORIGINS


class TestYoloThresholds:
    def test_confidence_in_range(self):
        import config
        assert 0.0 < config.YOLO_CONFIDENCE_THRESHOLD < 1.0

    def test_iou_in_range(self):
        import config
        assert 0.0 < config.YOLO_IOU_THRESHOLD < 1.0


class TestWidthThresholds:
    def test_optimal_width_default(self):
        import config
        # yolo_config.json 中读到 5.5 mm；没读到也兜底 5.5
        assert config.OPTIMAL_WELD_WIDTH_MM == pytest.approx(5.5, abs=0.01)

    def test_min_lt_optimal_lt_max(self):
        import config
        assert config.MIN_WELD_WIDTH_MM < config.OPTIMAL_WELD_WIDTH_MM
        assert config.OPTIMAL_WELD_WIDTH_MM < config.MAX_WELD_WIDTH_MM

    def test_corrupted_yolo_config_falls_back_to_default(self, tmp_path, monkeypatch):
        # 模拟 yolo_config.json 损坏：临时换文件路径指向无效文件，再调一次 _load_width_thresholds
        import config
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("{not valid json")
        monkeypatch.setattr(config, "YOLO_CONFIG_FILE", str(bad_file))
        # _load_width_thresholds 在 JSONDecodeError 时返回 {}，业务侧应走默认值
        assert config._load_width_thresholds() == {}


class TestHelperFunctions:
    def test_get_ai_config_shape(self):
        import config
        ai = config.get_ai_config()
        assert set(ai.keys()) == {"api_key", "base_url", "model"}

    def test_get_yolo_config_shape(self):
        import config
        y = config.get_yolo_config()
        assert set(y.keys()) == {"model_path", "confidence_threshold", "iou_threshold"}
