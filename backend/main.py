from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
from dotenv import load_dotenv

# 在所有模块导入之前先加载 .env 文件，确保环境变量可用
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
load_dotenv(dotenv_path=_env_path)

# 导入数据库设置
from database import engine, Base
import models

# 导入API路由
from api import teacher, dashboard, predict, lesson_plan, yolo_realtime

# 创建数据库表
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="焊育智眸 - 后端API",
    description="为AI焊接教学系统提供后端服务",
    version="2.1.0",
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载API路由 - 只保留必要的模块
app.include_router(yolo_realtime.router, prefix="/api/v1", tags=["YOLO Realtime"])
app.include_router(teacher.router, prefix="/api/v1", tags=["AI Teacher"])
app.include_router(dashboard.router, prefix="/api/v1", tags=["Dashboard"])
app.include_router(predict.router, prefix="/api/v1", tags=["Predict"])
app.include_router(lesson_plan.router, prefix="/api/v1", tags=["Lesson Plan"])


@app.get("/")
async def root():
    return {"message": "欢迎使用焊育智眸后端服务"}

if __name__ == "__main__":
    # 优化服务器配置，提高响应速度
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        access_log=False,  # 关闭访问日志，提高性能
        timeout_keep_alive=30,  # 保持连接30秒，减少连接建立开销
    )
