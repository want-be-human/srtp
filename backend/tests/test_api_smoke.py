"""FastAPI 主要业务路由的冒烟测试。

不挂 main.py 整体（会触发 yolo_realtime 后台线程和 best.pt 加载），
只把 dashboard / predict / calibration 三个 router 挂到临时 app 上做端到端断言。
seed 库里 student_id='2024112434' 存在真实记录，用它走 /predict 完整路径。
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


KNOWN_STUDENT = "2024112434"


@pytest.fixture()
def client(isolated_db, monkeypatch):
    # 业务 router 在 import 时绑定了 SessionLocal，需要在 monkeypatch 之后再 import 才能拿到新引擎
    import database
    from api import dashboard, predict, calibration

    for mod in (dashboard, predict, calibration):
        monkeypatch.setattr(mod, "SessionLocal", database.SessionLocal, raising=True)

    app = FastAPI()
    app.include_router(dashboard.router, prefix="/api/v1")
    app.include_router(predict.router, prefix="/api/v1")
    app.include_router(calibration.router, prefix="/api/v1")
    return TestClient(app)


class TestDashboard:
    def test_quick_stats_returns_expected_fields(self, client):
        r = client.get("/api/v1/dashboard/quick-stats")
        assert r.status_code == 200
        body = r.json()
        # seed 库 130 条记录都应该被 count 到
        assert body["total_detections"] >= 1
        assert "avg_score" in body
        assert "batch_count" in body
        assert "system_status" in body
        # 平均分跑出来肯定在 [0, 100]
        assert 0 <= body["avg_score"] <= 100

    def test_history_with_student_filter(self, client):
        r = client.get("/api/v1/dashboard/history", params={"student_id": KNOWN_STUDENT})
        assert r.status_code == 200
        rows = r.json()
        # 这位学生 seed 里确实有记录
        assert len(rows) >= 1
        for row in rows:
            assert "total_score" in row
            assert "timestamp" in row


class TestCalibration:
    def test_current_default_camera(self, client):
        # seed 库 camera_calibrations 表为空，default camera 应返回 calibrated=false
        r = client.get("/api/v1/calibration/current")
        assert r.status_code == 200
        assert r.json()["calibrated"] is False

    def test_save_valid_payload(self, client):
        payload = {
            "camera_id": "smoke-test",
            "point1_x": 0.0, "point1_y": 0.0,
            "point2_x": 80.0, "point2_y": 60.0,  # hypot = 100
            "ref_distance_mm": 25.0,
            "image_width": 1920, "image_height": 1080,
        }
        r = client.post("/api/v1/calibration/save", json=payload)
        assert r.status_code == 200
        body = r.json()
        assert body["pixels_per_mm"] == pytest.approx(4.0)  # 100/25

    def test_save_two_points_too_close(self, client):
        payload = {
            "point1_x": 0, "point1_y": 0,
            "point2_x": 0.4, "point2_y": 0.4,  # dist ≈ 0.57 < 1
            "ref_distance_mm": 10.0,
            "image_width": 640, "image_height": 480,
        }
        r = client.post("/api/v1/calibration/save", json=payload)
        assert r.status_code == 400


class TestPredict:
    def test_predict_with_known_student(self, client):
        # seed 学生应能跑通完整 fast 路径，不能抛 500
        r = client.get("/api/v1/predict", params={"student_id": KNOWN_STUDENT})
        assert r.status_code == 200, r.text
        body = r.json()
        assert "history" in body
        assert "forecast" in body
        assert "skill_stats" in body
        assert "defect_stats" in body
        assert isinstance(body["history"], dict)
        assert isinstance(body["forecast"], dict)

    def test_predict_unknown_student_falls_back(self, client):
        # 不存在的学生 → 走 demo 数据兜底，is_fallback 应该是 True
        r = client.get("/api/v1/predict", params={"student_id": "no-such-student"})
        assert r.status_code == 200
        body = r.json()
        assert body["is_fallback"] is True
        # 至少给出 demo 兜底的预测点
        assert len(body["forecast"]) >= 1

    def test_predict_invalid_mode_returns_400(self, client):
        r = client.get("/api/v1/predict", params={"mode": "nonsense"})
        assert r.status_code == 400
