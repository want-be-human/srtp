from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional

from database import SessionLocal
import models
from pydantic import BaseModel
from datetime import datetime
import psutil
import platform
import os

router = APIRouter()

# Pydantic model for response
class WeldingRecordOut(BaseModel):
    id: int
    timestamp: datetime
    smoothness_score: float
    spacing_score: float
    defect_type_score: float
    total_score: float

    class Config:
        from_attributes = True

# Dependency to get the database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/dashboard/history", response_model=List[WeldingRecordOut])
async def get_welding_history(
    student_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """焊接记录历史，可选 student_id 过滤；单人 PDF 报告也走这个接口拉详情。"""
    q = db.query(models.WeldingRecord)
    if student_id:
        q = q.filter(models.WeldingRecord.student_id == student_id)
    return q.order_by(models.WeldingRecord.timestamp.desc()).all()


# ========== 系统状态监控API ==========
class SystemStatusResponse(BaseModel):
    """系统状态响应模型 - 美观展示用"""
    uptime_formatted: str       # 系统运行时间（格式化）
    detection_count: int        # 总检测次数
    today_detections: int       # 今日检测次数
    student_count: int          # 学生数量
    batch_count: int            # 批次数（每30个为一批）
    avg_score: float            # 平均分数
    system_status: str          # 系统状态描述
    current_time: str           # 当前时间


@router.get("/dashboard/system-status", response_model=SystemStatusResponse)
async def get_system_status(db: Session = Depends(get_db)):
    """
    获取系统状态信息（美观展示用）
    """
    try:
        # 系统运行时间
        boot_time = psutil.boot_time()
        uptime_seconds = datetime.now().timestamp() - boot_time

        # 格式化运行时间
        days = int(uptime_seconds // 86400)
        hours = int((uptime_seconds % 86400) // 3600)
        minutes = int((uptime_seconds % 3600) // 60)
        uptime_formatted = f"{days}天{hours}时{minutes}分" if days > 0 else f"{hours}时{minutes}分"

        # 检测统计
        detection_count = db.query(models.WeldingRecord).count()

        # 今日检测数
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_detections = db.query(models.WeldingRecord).filter(
            models.WeldingRecord.timestamp >= today_start
        ).count()

        # 学生数量
        student_count = db.query(models.WeldingRecord.student_id).filter(
            models.WeldingRecord.student_id.isnot(None),
            models.WeldingRecord.student_id != ''
        ).distinct().count()

        # 批次数（每30个为一批）
        batch_count = detection_count // 30

        # 平均分数
        avg_result = db.query(models.WeldingRecord.total_score).limit(30).all()
        avg_score = sum(r[0] for r in avg_result if r[0]) / len(avg_result) if avg_result else 0

        # 系统状态
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        if cpu_percent < 50 and memory.percent < 50:
            system_status = "系统运行良好"
        elif cpu_percent < 80 and memory.percent < 80:
            system_status = "系统运行正常"
        else:
            system_status = "系统负载较高"

        return SystemStatusResponse(
            uptime_formatted=uptime_formatted,
            detection_count=detection_count,
            today_detections=today_detections,
            student_count=max(student_count, detection_count),  # 每次检测算一个学生
            batch_count=batch_count,
            avg_score=round(avg_score, 1),
            system_status=system_status,
            current_time=datetime.now().strftime("%H:%M:%S")
        )

    except Exception as e:
        return SystemStatusResponse(
            uptime_formatted="计算中...",
            detection_count=0,
            today_detections=0,
            student_count=0,
            batch_count=0,
            avg_score=0.0,
            system_status="状态获取中",
            current_time=datetime.now().strftime("%H:%M:%S")
        )


@router.get("/dashboard/quick-stats")
async def get_quick_stats(db: Session = Depends(get_db)):
    """
    获取快速统计数据（用于主界面底部状态框）
    """
    try:
        # 检测统计
        total_detections = db.query(models.WeldingRecord).count()

        # 今日检测数
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_detections = db.query(models.WeldingRecord).filter(
            models.WeldingRecord.timestamp >= today_start
        ).count()

        # 批次数
        batch_count = total_detections // 30

        # 平均分数
        avg_result = db.query(models.WeldingRecord.total_score).limit(30).all()
        avg_score = sum(r[0] for r in avg_result if r[0]) / len(avg_result) if avg_result else 0

        # 运行时间
        boot_time = psutil.boot_time()
        uptime_seconds = datetime.now().timestamp() - boot_time
        hours = int(uptime_seconds // 3600)

        return {
            "total_detections": total_detections,
            "today_detections": today_detections,
            "batch_count": batch_count,
            "avg_score": round(avg_score, 1),
            "uptime_hours": hours,
            "system_status": "运行正常"
        }

    except Exception as e:
        return {
            "total_detections": 0,
            "today_detections": 0,
            "batch_count": 0,
            "avg_score": 0,
            "uptime_hours": 0,
            "system_status": "获取中"
        }
