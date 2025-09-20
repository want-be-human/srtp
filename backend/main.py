from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# 导入数据库设置
from database import engine, Base
import models

# 导入API路由
from api import detection, teacher, dashboard, prediction

# 创建数据库表
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="焊育智眸 - 后端API",
    description="为AI焊接教学系统提供后端服务",
    version="1.0.0",
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载API路由
app.include_router(detection.router, prefix="/api/v1", tags=["Detection"])
app.include_router(teacher.router, prefix="/api/v1", tags=["AI Teacher"])
app.include_router(dashboard.router, prefix="/api/v1", tags=["Dashboard"])
app.include_router(prediction.router, prefix="/api/v1", tags=["Prediction"])


@app.get("/")
async def root():
    return {"message": "欢迎使用焊育智眸后端服务"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
