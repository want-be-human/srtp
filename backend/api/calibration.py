# -*- coding: utf-8 -*-
"""摄像头单目宽度标定。

教学场景下相机和工件距离基本固定，只需要拍一张含已知长度参考物（标定卡 /
钢直尺）的图，前端在画面上点两端、输入真实长度，后端算出 pixels_per_mm
存库；下次启动检测器时直接读出，宽度 mm 不再靠假设。
"""

import math
import os
import sys
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
sys.path.insert(0, backend_dir)

from database import SessionLocal
import models

router = APIRouter()

DEFAULT_CAMERA_ID = "default"


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class CalibrationSaveRequest(BaseModel):
    camera_id: str = Field(default=DEFAULT_CAMERA_ID, max_length=100)
    point1_x: float
    point1_y: float
    point2_x: float
    point2_y: float
    ref_distance_mm: float = Field(gt=0)
    image_width: int = Field(gt=0)
    image_height: int = Field(gt=0)


class CalibrationResponse(BaseModel):
    calibrated: bool
    camera_id: Optional[str] = None
    pixels_per_mm: Optional[float] = None
    ref_distance_pixels: Optional[float] = None
    ref_distance_mm: Optional[float] = None
    image_width: Optional[int] = None
    image_height: Optional[int] = None
    calibrated_at: Optional[str] = None


def _read_calibration(db: Session, camera_id: str) -> CalibrationResponse:
    row = db.query(models.CameraCalibration).filter_by(camera_id=camera_id).first()
    if not row:
        return CalibrationResponse(calibrated=False)
    return CalibrationResponse(
        calibrated=True,
        camera_id=row.camera_id,
        pixels_per_mm=float(row.pixels_per_mm),
        ref_distance_pixels=float(row.ref_distance_pixels),
        ref_distance_mm=float(row.ref_distance_mm),
        image_width=int(row.image_width),
        image_height=int(row.image_height),
        calibrated_at=row.calibrated_at.isoformat() if row.calibrated_at else None,
    )


def load_calibration_pixels_per_mm(camera_id: str = DEFAULT_CAMERA_ID) -> Optional[float]:
    """给检测器启动时调，未标定或 DB 暂不可用都返回 None。"""
    db = SessionLocal()
    try:
        row = db.query(models.CameraCalibration).filter_by(camera_id=camera_id).first()
        return float(row.pixels_per_mm) if row else None
    except SQLAlchemyError as e:
        print(f"读取摄像头标定失败，按未标定处理: {e}")
        return None
    finally:
        db.close()


@router.post("/calibration/save", response_model=CalibrationResponse)
async def save_calibration(req: CalibrationSaveRequest, db: Session = Depends(get_db)):
    pixel_distance = math.hypot(req.point2_x - req.point1_x, req.point2_y - req.point1_y)
    if pixel_distance < 1.0:
        raise HTTPException(status_code=400, detail="两点距离太近，无法标定，请重新点选")

    pixels_per_mm = pixel_distance / req.ref_distance_mm

    row = db.query(models.CameraCalibration).filter_by(camera_id=req.camera_id).first()
    if row is None:
        row = models.CameraCalibration(camera_id=req.camera_id)
        db.add(row)
    row.pixels_per_mm = pixels_per_mm
    row.ref_distance_pixels = pixel_distance
    row.ref_distance_mm = req.ref_distance_mm
    row.image_width = req.image_width
    row.image_height = req.image_height
    row.calibrated_at = datetime.utcnow()

    db.commit()
    db.refresh(row)

    return _read_calibration(db, req.camera_id)


@router.get("/calibration/current", response_model=CalibrationResponse)
async def get_calibration(camera_id: str = DEFAULT_CAMERA_ID, db: Session = Depends(get_db)):
    return _read_calibration(db, camera_id)


@router.delete("/calibration/{camera_id}")
async def delete_calibration(camera_id: str, db: Session = Depends(get_db)):
    row = db.query(models.CameraCalibration).filter_by(camera_id=camera_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="该摄像头没有标定记录")
    db.delete(row)
    db.commit()
    return {"status": "deleted", "camera_id": camera_id}
