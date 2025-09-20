from sqlalchemy import Column, Integer, Float, DateTime
from sqlalchemy.sql import func
from database import Base

class WeldingRecord(Base):
    __tablename__ = "welding_records"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    speed_score = Column(Float)
    angle_score = Column(Float)
    depth_score = Column(Float)
    defect_score = Column(Float)
    total_score = Column(Float)
