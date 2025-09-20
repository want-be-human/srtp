from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# 数据库文件路径
SQLALCHEMY_DATABASE_URL = "sqlite:///./welding.db"

# 创建数据库引擎
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    connect_args={"check_same_thread": False} # "check_same_thread" is only needed for SQLite.
)

# 创建数据库会话
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 创建ORM模型的基础类
Base = declarative_base()
