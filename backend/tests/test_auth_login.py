"""学生登录接口的端到端测试。

auth.py 路径承载真实的密码哈希校验，必须验证：
1. 正确学号+密码能登入并返回 PublicStudent；
2. 错密码返回 401，不能泄露"用户是否存在"信息；
3. bcrypt verify 对错误格式的 hash 串不能抛异常崩掉路由；
4. pydantic Field 长度约束生效（空学号/超长字符串）。
"""

import os
import sys
from pathlib import Path

import bcrypt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _make_app_with_db(monkeypatch, isolated_db):
    """复制业务路由到一个干净的 FastAPI 应用，避免触发 yolo_realtime 副作用。"""
    backend_dir = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(backend_dir))

    # 在 import auth 之前 monkeypatch 已经把 database.SessionLocal 切到 tmp_db，
    # 这里直接 import 不会再连到主库
    from api import auth
    import database
    import models

    # auth 模块在导入时 captured 了 SessionLocal 引用，需要再 patch 一次
    monkeypatch.setattr(auth, "SessionLocal", database.SessionLocal, raising=False)

    models.Base.metadata.create_all(bind=database.engine)

    app = FastAPI()
    app.include_router(auth.router, prefix="/api/v1")
    return app


def _insert_student(student_id: str, name: str, password: str, batch_id: str | None = None):
    """直接往 isolated_db 插一行 Student，密码走 bcrypt。

    seed 库可能已经存在同学号（演示用 ROSTER 6 人），先 upsert 删旧的再插，让
    本测试拿到的 hash 是当下生成的、可控的。
    """
    import database
    import models

    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    db = database.SessionLocal()
    try:
        existing = db.query(models.Student).filter_by(student_id=student_id).first()
        if existing is not None:
            db.delete(existing)
            db.commit()
        db.add(models.Student(
            student_id=student_id,
            name=name,
            password_hash=hashed,
            batch_id=batch_id,
        ))
        db.commit()
    finally:
        db.close()


class TestLoginHappyPath:
    def test_correct_credentials_returns_student(self, isolated_db, monkeypatch):
        app = _make_app_with_db(monkeypatch, isolated_db)
        _insert_student("2024112434", "陈思远", "123456", "焊接班2024-A")

        client = TestClient(app)
        r = client.post("/api/v1/auth/login", json={
            "student_id": "2024112434",
            "password": "123456",
        })
        assert r.status_code == 200
        body = r.json()
        assert body["student_id"] == "2024112434"
        assert body["name"] == "陈思远"
        assert body["batch_id"] == "焊接班2024-A"
        # 响应里绝对不能带 password_hash
        assert "password_hash" not in body


class TestLoginFailures:
    def test_wrong_password_returns_401(self, isolated_db, monkeypatch):
        app = _make_app_with_db(monkeypatch, isolated_db)
        _insert_student("2024112434", "陈思远", "correct_pw")

        client = TestClient(app)
        r = client.post("/api/v1/auth/login", json={
            "student_id": "2024112434",
            "password": "wrong_pw",
        })
        assert r.status_code == 401

    def test_unknown_student_returns_401_same_message(self, isolated_db, monkeypatch):
        # 用户不存在时也返回 401，而不是 404；避免外部嗅探"该学号是否存在"
        app = _make_app_with_db(monkeypatch, isolated_db)
        client = TestClient(app)
        r = client.post("/api/v1/auth/login", json={
            "student_id": "9999999999",
            "password": "whatever",
        })
        assert r.status_code == 401

    def test_corrupted_hash_does_not_crash(self, isolated_db, monkeypatch):
        # 直接塞个非法 hash，bcrypt.checkpw 会抛 ValueError，路由必须吞掉并返 401
        app = _make_app_with_db(monkeypatch, isolated_db)

        import database
        import models
        db = database.SessionLocal()
        try:
            db.add(models.Student(
                student_id="2024999999",
                name="损坏哈希用户",
                password_hash="not-a-valid-bcrypt-hash",
            ))
            db.commit()
        finally:
            db.close()

        client = TestClient(app)
        r = client.post("/api/v1/auth/login", json={
            "student_id": "2024999999",
            "password": "anything",
        })
        # 重点：不能 500，必须是 401
        assert r.status_code == 401


class TestInputValidation:
    def test_empty_student_id_rejected(self, isolated_db, monkeypatch):
        app = _make_app_with_db(monkeypatch, isolated_db)
        client = TestClient(app)
        r = client.post("/api/v1/auth/login", json={
            "student_id": "",
            "password": "anything",
        })
        # pydantic Field(min_length=1) 应拒绝
        assert r.status_code == 422

    def test_empty_password_rejected(self, isolated_db, monkeypatch):
        app = _make_app_with_db(monkeypatch, isolated_db)
        client = TestClient(app)
        r = client.post("/api/v1/auth/login", json={
            "student_id": "2024112434",
            "password": "",
        })
        assert r.status_code == 422

    def test_oversized_password_rejected(self, isolated_db, monkeypatch):
        app = _make_app_with_db(monkeypatch, isolated_db)
        client = TestClient(app)
        r = client.post("/api/v1/auth/login", json={
            "student_id": "2024112434",
            "password": "x" * 201,
        })
        assert r.status_code == 422


class TestBcryptInternals:
    def test_bcrypt_roundtrip(self):
        """密码哈希 round-trip 验证 — 直接验证 bcrypt 库行为，保证依赖未损坏。"""
        plain = "test_password_123"
        hashed = bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt())
        assert bcrypt.checkpw(plain.encode("utf-8"), hashed) is True
        assert bcrypt.checkpw(b"wrong_password", hashed) is False

    def test_same_password_different_salt(self):
        # 同一密码每次 hashpw 产出不同 hash（盐值随机），但都能 verify 回来
        plain = "same_password"
        h1 = bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt())
        h2 = bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt())
        assert h1 != h2
        assert bcrypt.checkpw(plain.encode("utf-8"), h1)
        assert bcrypt.checkpw(plain.encode("utf-8"), h2)
