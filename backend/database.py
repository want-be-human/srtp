from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# 数据库文件路径
SQLALCHEMY_DATABASE_URL = "sqlite:///./welding.db"

# 创建数据库引擎（优化连接池配置）
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 30},  # SQLite连接超时设置
    pool_pre_ping=True,  # 连接前检查连接是否有效
    pool_recycle=3600,   # 1小时回收连接
    echo=False           # 关闭SQL日志输出，提高性能
)

# 创建数据库会话
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 创建ORM模型的基础类
Base = declarative_base()
