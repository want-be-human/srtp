from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from database import SessionLocal
import models
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()

# Pydantic model for response
class WeldingRecordOut(BaseModel):
    id: int
    timestamp: datetime
    speed_score: float
    angle_score: float
    depth_score: float
    defect_score: float
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
async def get_welding_history(db: Session = Depends(get_db)):
    """
    从数据库获取所有的焊接记录
    """
    records = db.query(models.WeldingRecord).order_by(models.WeldingRecord.timestamp.desc()).all()
    return records
