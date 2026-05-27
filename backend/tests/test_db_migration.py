"""数据库迁移与 Schema 一致性测试。

main.py::_ensure_welding_records_columns 是用来补老库缺列的幂等 ALTER；
必须保证：
1. 全新库（已含 defect_bboxes 列）调一次不会报错；
2. 老库（无 defect_bboxes 列）调一次能补上；
3. 已补过的库再调一次仍然没事（幂等）；
4. 不阻塞主库启动（DB 锁住 / 权限不足时只 print warning 不抛）。
"""

import shutil
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text


_BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND_DIR))


def _make_legacy_db(tmp_path: Path) -> Path:
    """造一个没有 defect_bboxes 列的"老库"，模拟升级前数据。"""
    db = tmp_path / "legacy.db"
    engine = create_engine(f"sqlite:///{db}")
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE welding_records (
                id INTEGER PRIMARY KEY,
                timestamp DATETIME,
                student_id VARCHAR(50),
                student_name VARCHAR(100),
                batch_id VARCHAR(50),
                smoothness_score FLOAT,
                spacing_score FLOAT,
                defect_type_score FLOAT,
                total_score FLOAT,
                actual_width FLOAT,
                defect_type_name VARCHAR(50),
                notes VARCHAR(500)
            )
        """))
    engine.dispose()
    return db


def _ensure_columns(engine):
    """复制 main.py 里的迁移函数本体在此测试里跑（避免 import main 触发 router 加载）。"""
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
    except SQLAlchemyError:
        pass


class TestSchemaUpgrade:
    def test_legacy_db_gains_column(self, tmp_path):
        db = _make_legacy_db(tmp_path)
        engine = create_engine(f"sqlite:///{db}")

        # 老库本来没这列
        cols_before = {c["name"] for c in inspect(engine).get_columns("welding_records")}
        assert "defect_bboxes" not in cols_before

        _ensure_columns(engine)

        cols_after = {c["name"] for c in inspect(engine).get_columns("welding_records")}
        assert "defect_bboxes" in cols_after
        engine.dispose()

    def test_idempotent_double_call(self, tmp_path):
        """补完一次后再调应该 no-op，不抛 ALTER 重复列错。"""
        db = _make_legacy_db(tmp_path)
        engine = create_engine(f"sqlite:///{db}")
        _ensure_columns(engine)
        # 关键：第二次调用必须是 no-op
        _ensure_columns(engine)  # 不抛即过
        engine.dispose()

    def test_missing_table_does_not_crash(self, tmp_path):
        """空库没 welding_records 表，迁移函数应 early return。"""
        db = tmp_path / "empty.db"
        engine = create_engine(f"sqlite:///{db}")
        # 不抛即过
        _ensure_columns(engine)
        engine.dispose()


class TestSeedDb:
    def test_seed_db_already_has_new_column(self, seed_db_path, tmp_path):
        """welding.db.seed 应该已经含 defect_bboxes 列（最新 schema 同步过）。"""
        tmp_db = tmp_path / "seed_copy.db"
        shutil.copyfile(seed_db_path, tmp_db)
        engine = create_engine(f"sqlite:///{tmp_db}")
        cols = {c["name"] for c in inspect(engine).get_columns("welding_records")}
        engine.dispose()
        # 这一项断言会随 schema 演进——本意是把 seed 漂移的情况暴露出来
        # 如果失败：要么 seed 没更新，要么 schema 加了新列没回写 seed
        expected_cols = {
            "id", "timestamp", "student_id", "student_name", "batch_id",
            "smoothness_score", "spacing_score", "defect_type_score",
            "total_score", "actual_width", "defect_type_name", "notes",
            "defect_bboxes",
        }
        missing = expected_cols - cols
        assert not missing, f"seed 库缺少列：{missing}"


class TestModelsCreateAll:
    def test_create_all_idempotent(self, tmp_path, monkeypatch):
        """models.Base.metadata.create_all 调两次不应该报错。"""
        db = tmp_path / "fresh.db"
        engine = create_engine(f"sqlite:///{db}")

        import database
        monkeypatch.setattr(database, "engine", engine, raising=False)

        import models
        models.Base.metadata.create_all(bind=engine)
        # 再来一次 — SQLAlchemy 自带 IF NOT EXISTS，不应抛
        models.Base.metadata.create_all(bind=engine)

        tables = set(inspect(engine).get_table_names())
        assert "welding_records" in tables
        assert "students" in tables
        assert "camera_calibrations" in tables
        engine.dispose()

    def test_camera_calibration_unique_constraint(self, tmp_path):
        """同一 camera_id 不能插两次（upsert 语义靠这条约束保住）。"""
        db = tmp_path / "calib.db"
        engine = create_engine(f"sqlite:///{db}")

        import models
        models.Base.metadata.create_all(bind=engine)

        from sqlalchemy.exc import IntegrityError
        from sqlalchemy.orm import sessionmaker

        Session = sessionmaker(bind=engine)
        s = Session()
        try:
            s.add(models.CameraCalibration(
                camera_id="default",
                pixels_per_mm=10.0,
                ref_distance_pixels=50.0,
                ref_distance_mm=5.0,
                image_width=1920,
                image_height=1080,
            ))
            s.commit()

            s.add(models.CameraCalibration(
                camera_id="default",  # 同 ID
                pixels_per_mm=20.0,
                ref_distance_pixels=100.0,
                ref_distance_mm=5.0,
                image_width=1920,
                image_height=1080,
            ))
            with pytest.raises(IntegrityError):
                s.commit()
        finally:
            s.rollback()
            s.close()
            engine.dispose()
