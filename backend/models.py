from sqlalchemy import Column, Integer, Float, DateTime, String
from sqlalchemy.sql import func
from database import Base

class WeldingRecord(Base):
    """焊接检测记录模型"""
    __tablename__ = "welding_records"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    # 学生标识（支持批次比较）
    student_id = Column(String(50), index=True, nullable=True, comment="学生ID/学号")
    student_name = Column(String(100), nullable=True, comment="学生姓名")
    batch_id = Column(String(50), index=True, nullable=True, comment="批次ID（如：日期+班级）")

    # 检测分数
    smoothness_score = Column(Float, comment="光滑度分数")
    spacing_score = Column(Float, comment="间距/宽度分数")
    defect_type_score = Column(Float, comment="缺陷控制分数")
    total_score = Column(Float, comment="总分")

    # 额外信息
    actual_width = Column(Float, nullable=True, comment="实际焊缝宽度(mm)")
    defect_type_name = Column(String(50), nullable=True, comment="缺陷类型名称")
    notes = Column(String(500), nullable=True, comment="备注")


class Student(Base):
    """学生账号。batch_id 与 WeldingRecord.batch_id 对应。"""
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    password_hash = Column(String(255), nullable=False)
    batch_id = Column(String(50), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class CameraCalibration(Base):
    """摄像头单目宽度标定记录。一个 camera_id 一行，新标定 upsert 覆盖旧值。"""
    __tablename__ = "camera_calibrations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    camera_id = Column(String(100), unique=True, nullable=False, index=True,
                       comment="摄像头标识；多机时区分，单机演示用 'default'")
    pixels_per_mm = Column(Float, nullable=False, comment="每毫米对应的像素数")
    ref_distance_pixels = Column(Float, nullable=False, comment="参考物在画面里量到的像素长度")
    ref_distance_mm = Column(Float, nullable=False, comment="参考物的真实长度 (mm)")
    image_width = Column(Integer, nullable=False, comment="标定时画面宽，分辨率变了应重新标定")
    image_height = Column(Integer, nullable=False, comment="标定时画面高")
    calibrated_at = Column(DateTime(timezone=True),
                           server_default=func.now(), onupdate=func.now())
