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
    """学生账号模型（C1 真实登录）。

    国赛演示阶段为演示账号；真实部署将由学校官网接入后填充，本表结构保持
    一致：学号 student_id（如：2024001）唯一标识身份，password_hash 用 bcrypt
    存储。批次 batch_id 与 WeldingRecord.batch_id 对应，便于按班级聚合 PK。
    """
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(String(50), unique=True, nullable=False, index=True, comment="学号，登录账号")
    name = Column(String(100), nullable=False, comment="学生姓名")
    password_hash = Column(String(255), nullable=False, comment="bcrypt 哈希后的密码")
    batch_id = Column(String(50), nullable=True, index=True, comment="所属班级")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
