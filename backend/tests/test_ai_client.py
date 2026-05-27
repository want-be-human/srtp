"""AI 共享客户端的容错路径测试。

ai_client.py 是 teacher / lesson_plan / ai_analysis 共用的入口，必须保证：
1. 没配 KEY 时 get_shared_ai_client() 返回 None，调用方走 fallback 不崩；
2. 初始化失败一次后下次不再重试（_init_failed 闸门）；
3. classify_ai_error 把 OpenAI SDK 异常归类到稳定 key，前端按 key 翻文案。
"""

import importlib

import pytest


def _reload_ai_client(monkeypatch, *, api_key: str = ""):
    """重新 import ai_client，让 module 级全局变量按当前 env 重新初始化。"""
    import sys
    import config
    monkeypatch.setattr(config, "AI_API_KEY", api_key, raising=False)
    # 模块已经被加载过，必须 reload 才能重新跑 module-level 代码
    if "ai_client" in sys.modules:
        del sys.modules["ai_client"]
    import ai_client
    importlib.reload(ai_client)
    monkeypatch.setattr(ai_client, "AI_API_KEY", api_key, raising=False)
    # 重置模块级 cache，避免上个 test 残留
    ai_client._shared_client = None
    ai_client._init_failed = False
    return ai_client


class TestMissingKeyFallback:
    def test_returns_none_when_key_empty(self, monkeypatch):
        ai_client = _reload_ai_client(monkeypatch, api_key="")
        assert ai_client.get_shared_ai_client() is None

    def test_multiple_calls_with_no_key_stay_none(self, monkeypatch):
        # 没 key 时反复调也不应该突然返回非 None
        ai_client = _reload_ai_client(monkeypatch, api_key="")
        assert ai_client.get_shared_ai_client() is None
        assert ai_client.get_shared_ai_client() is None
        assert ai_client.get_shared_ai_client() is None


class TestClientInitFailureGate:
    def test_init_failure_caches_and_does_not_retry(self, monkeypatch):
        ai_client = _reload_ai_client(monkeypatch, api_key="sk-fake-but-nonempty")

        call_count = {"n": 0}

        def _bad_openai_ctor(*args, **kwargs):
            call_count["n"] += 1
            raise RuntimeError("simulated init failure")

        monkeypatch.setattr(ai_client, "OpenAI", _bad_openai_ctor)

        # 第一次 init 失败
        assert ai_client.get_shared_ai_client() is None
        # 后续调用不应该再尝试构造 client（_init_failed 闸门）
        ai_client.get_shared_ai_client()
        ai_client.get_shared_ai_client()
        assert call_count["n"] == 1


class TestSuccessfulInit:
    def test_returns_singleton(self, monkeypatch):
        ai_client = _reload_ai_client(monkeypatch, api_key="sk-fake-but-nonempty")

        sentinel = object()

        def _fake_openai_ctor(*args, **kwargs):
            return sentinel

        monkeypatch.setattr(ai_client, "OpenAI", _fake_openai_ctor)

        c1 = ai_client.get_shared_ai_client()
        c2 = ai_client.get_shared_ai_client()
        assert c1 is sentinel
        assert c2 is sentinel
        # 共享单例：两次返回同一对象，不是新建
        assert c1 is c2


class TestErrorClassification:
    def test_auth_error(self):
        from ai_client import classify_ai_error
        from openai import AuthenticationError

        # OpenAI SDK 的异常类有特殊签名，构造时给最少必要参数
        # 任何 AuthenticationError 实例都应归类到 "auth"
        class FakeAuth(AuthenticationError):
            def __init__(self):
                pass

        assert classify_ai_error(FakeAuth()) == "auth"

    def test_timeout_error(self):
        from ai_client import classify_ai_error
        from openai import APITimeoutError

        class FakeTimeout(APITimeoutError):
            def __init__(self):
                pass

        assert classify_ai_error(FakeTimeout()) == "timeout"

    def test_rate_limit_error(self):
        from ai_client import classify_ai_error
        from openai import RateLimitError

        class FakeRate(RateLimitError):
            def __init__(self):
                pass

        assert classify_ai_error(FakeRate()) == "rate_limit"

    def test_connection_error(self):
        from ai_client import classify_ai_error
        from openai import APIConnectionError

        class FakeConn(APIConnectionError):
            def __init__(self):
                pass

        assert classify_ai_error(FakeConn()) == "network"

    def test_unknown_error_classification(self):
        from ai_client import classify_ai_error

        # 任意非 OpenAI SDK 异常应该归为 "unknown"
        assert classify_ai_error(ValueError("boom")) == "unknown"
        assert classify_ai_error(RuntimeError()) == "unknown"
        assert classify_ai_error(Exception()) == "unknown"

    def test_classification_returns_stable_keys(self):
        """所有归类 key 必须是前端可识别的稳定字符串集合。"""
        from ai_client import classify_ai_error

        valid_keys = {"auth", "timeout", "rate_limit", "network", "unknown"}
        # 跑一遍各种异常，确保返回值都在白名单内
        for exc in [ValueError(), RuntimeError(), KeyError(), TypeError()]:
            assert classify_ai_error(exc) in valid_keys
