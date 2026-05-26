from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import shutil
import uvicorn
import os
from dotenv import load_dotenv

_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))

# 在所有模块导入之前先加载 .env 文件，确保环境变量可用
load_dotenv(dotenv_path=os.path.join(_BACKEND_DIR, '.env'))

# welding.db 不再入仓（标定/记录被 pull 覆盖过太多次），新机器从 welding.db.seed
# 复制一份冷启动。已存在就不动，保留用户本地的标定与记录。
_db_path = os.path.join(_BACKEND_DIR, 'welding.db')
_seed_path = os.path.join(_BACKEND_DIR, 'welding.db.seed')
if not os.path.exists(_db_path) and os.path.exists(_seed_path):
    shutil.copyfile(_seed_path, _db_path)
    print("[INFO] welding.db 不存在，从 welding.db.seed 复制初始化")

# 导入数据库设置
from database import engine, Base
import models

# 导入API路由
from api import teacher, dashboard, predict, lesson_plan, yolo_realtime, auth, calibration

# 创建数据库表
models.Base.metadata.create_all(bind=engine)


def _ensure_welding_records_columns() -> None:
    # 老库没有 defect_bboxes，create_all 不会补列，这里幂等地 ALTER 一下
    from sqlalchemy import inspect, text
    from sqlalchemy.exc import SQLAlchemyError
    try:
        insp = inspect(engine)
        if "welding_records" not in insp.get_table_names():
            return
        cols = {c["name"] for c in insp.get_columns("welding_records")}
        if "defect_bboxes" in cols:
            return
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE welding_records ADD COLUMN defect_bboxes JSON"))
    except SQLAlchemyError as exc:
        # DB 被锁/权限不足等场景下不阻塞服务启动，新列没补上的话 /detection-heatmap 自然返回空
        print(f"[WARN] defect_bboxes 列升级失败: {exc}")


_ensure_welding_records_columns()

app = FastAPI(
    title="焊育智眸 - 后端API",
    description="为AI焊接教学系统提供后端服务",
    version="2.1.0",
)


@app.on_event("startup")
async def _warm_load_temporal_model() -> None:
    """启动时把 1D-CNN 的 .pt 提前 load 进 _model_cache，深度预测首请求不用 lazy train。

    成本约 8KB IO + 一次 state_dict 反序列化，毫秒级。trained_on_count 留 0，让
    第一个 deep 请求像 lazy-load 路径一样把 baseline 设到当时的 n；之后累计 +30
    新数据才触发 retrain（保留 data-drift 跟随能力）。失败也只是退化到首请求
    lazy train，不阻塞启动。
    """
    try:
        from services.prediction.temporal_model import _load_pretrained, _model_cache
        model = _load_pretrained()
        if model is not None:
            _model_cache["model"] = model
            # trained_on_count 保持 0，首请求会按"n - 0 < 30"判断（单生 22 条命中）
            print("[OK] startup: 1D-CNN .pt 已 warm-load，深度预测首请求 < 200ms")
        else:
            print("[INFO] startup: 未找到 .pt 权重文件，深度预测首请求会走 lazy train")
    except Exception as exc:
        print(f"[WARN] startup: 1D-CNN warm-load 失败（不阻塞启动）: {exc}")

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
app.include_router(auth.router, prefix="/api/v1", tags=["Auth"])
app.include_router(calibration.router, prefix="/api/v1", tags=["Calibration"])

# /static 给前端 3DGS viewer 拉 .ply 用，目录缺则建空
_static_dir = os.path.join(_BACKEND_DIR, 'static')
os.makedirs(_static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=_static_dir), name="static")


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
