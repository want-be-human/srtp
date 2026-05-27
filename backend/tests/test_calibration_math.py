"""摄像头标定接口的数学逻辑 + 端到端读写测试。

calibration 模块对外承诺三件事：
1. pixels_per_mm = hypot(p2-p1) / ref_distance_mm，公式不能漂；
2. 两点几乎重合（< 1px）或参考长度非正时拒绝保存；
3. 写进 DB 之后再 GET /calibration/current 能拿到同一组数。
"""

import math

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from api import calibration


@pytest.fixture()
def client(isolated_db, monkeypatch):
    # calibration.SessionLocal 是 import 时绑定的旧 SessionLocal，重定向后要替换
    import database
    monkeypatch.setattr(calibration, "SessionLocal", database.SessionLocal, raising=True)

    app = FastAPI()
    app.include_router(calibration.router, prefix="/api/v1")
    return TestClient(app)


class TestPixelDistanceMath:
    @pytest.mark.parametrize("p1,p2,expected", [
        ((0.0, 0.0), (3.0, 4.0), 5.0),       # 3-4-5
        ((10.0, 10.0), (10.0, 20.0), 10.0),  # 纯垂直
        ((5.0, 5.0), (15.0, 5.0), 10.0),     # 纯水平
        ((0.0, 0.0), (1.0, 1.0), math.sqrt(2)),
    ])
    def test_hypot_matches_manual(self, p1, p2, expected):
        d = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
        assert d == pytest.approx(expected)

    def test_ratio_is_distance_over_mm(self):
        # 100px 对应 50mm，ppmm 必须是 2.0
        d = math.hypot(100.0 - 0.0, 0.0 - 0.0)
        assert d / 50.0 == pytest.approx(2.0)


class TestSaveRequestValidation:
    def test_zero_ref_distance_rejected(self):
        # pydantic Field(gt=0) 应该挡住 ref_distance_mm=0
        with pytest.raises(ValidationError):
            calibration.CalibrationSaveRequest(
                point1_x=0, point1_y=0, point2_x=10, point2_y=10,
                ref_distance_mm=0, image_width=640, image_height=480,
            )

    def test_negative_ref_distance_rejected(self):
        with pytest.raises(ValidationError):
            calibration.CalibrationSaveRequest(
                point1_x=0, point1_y=0, point2_x=10, point2_y=10,
                ref_distance_mm=-1, image_width=640, image_height=480,
            )

    def test_zero_image_size_rejected(self):
        with pytest.raises(ValidationError):
            calibration.CalibrationSaveRequest(
                point1_x=0, point1_y=0, point2_x=10, point2_y=10,
                ref_distance_mm=10, image_width=0, image_height=480,
            )


class TestLoadCalibrationFromEmptyDb:
    def test_empty_db_returns_none(self, isolated_db, monkeypatch):
        # seed 库里 camera_calibrations 表是空的，load_calibration_pixels_per_mm 应返回 None
        import database
        monkeypatch.setattr(calibration, "SessionLocal", database.SessionLocal, raising=True)
        assert calibration.load_calibration_pixels_per_mm("default") is None

    def test_read_unknown_camera_returns_uncalibrated(self, isolated_db, monkeypatch):
        import database
        monkeypatch.setattr(calibration, "SessionLocal", database.SessionLocal, raising=True)
        db = database.SessionLocal()
        try:
            resp = calibration._read_calibration(db, "never-existed")
            assert resp.calibrated is False
            assert resp.pixels_per_mm is None
        finally:
            db.close()


class TestApiRoundtrip:
    def test_get_current_empty_returns_false(self, client):
        r = client.get("/api/v1/calibration/current")
        assert r.status_code == 200
        assert r.json()["calibrated"] is False

    def test_save_then_get_returns_same_values(self, client):
        payload = {
            "camera_id": "test-cam-1",
            "point1_x": 0.0, "point1_y": 0.0,
            "point2_x": 100.0, "point2_y": 0.0,
            "ref_distance_mm": 50.0,
            "image_width": 1280, "image_height": 720,
        }
        r = client.post("/api/v1/calibration/save", json=payload)
        assert r.status_code == 200, r.text
        body = r.json()
        # 100px / 50mm = 2.0 ppmm
        assert body["calibrated"] is True
        assert body["pixels_per_mm"] == pytest.approx(2.0)
        assert body["ref_distance_pixels"] == pytest.approx(100.0)

        r2 = client.get("/api/v1/calibration/current", params={"camera_id": "test-cam-1"})
        assert r2.status_code == 200
        same = r2.json()
        assert same["pixels_per_mm"] == pytest.approx(2.0)
        assert same["ref_distance_mm"] == 50.0
        assert same["image_width"] == 1280

    def test_save_two_points_too_close_returns_400(self, client):
        payload = {
            "point1_x": 100.0, "point1_y": 100.0,
            "point2_x": 100.3, "point2_y": 100.4,  # 距离 0.5px < 1
            "ref_distance_mm": 10.0,
            "image_width": 640, "image_height": 480,
        }
        r = client.post("/api/v1/calibration/save", json=payload)
        assert r.status_code == 400
        assert "太近" in r.json()["detail"]

    def test_save_invalid_ref_distance_returns_422(self, client):
        payload = {
            "point1_x": 0.0, "point1_y": 0.0,
            "point2_x": 100.0, "point2_y": 0.0,
            "ref_distance_mm": 0,  # 触发 Field(gt=0)
            "image_width": 640, "image_height": 480,
        }
        r = client.post("/api/v1/calibration/save", json=payload)
        assert r.status_code == 422
