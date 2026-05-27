"""测试公用 fixture。

把 backend/ 注册到 sys.path，让 tests 里 `from defect_types ...` 跟业务代码同款写法；
顺便准备一个临时 SQLite 库给 API 冒烟测试用，避免污染主库。
"""

import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

_BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND_DIR))


@pytest.fixture(scope="session")
def backend_dir() -> Path:
    return _BACKEND_DIR


@pytest.fixture(scope="session")
def seed_db_path(backend_dir: Path) -> Path:
    p = backend_dir / "welding.db.seed"
    if not p.exists():
        pytest.skip(f"welding.db.seed 不存在，跳过依赖 seed 数据的用例（{p}）")
    return p


@pytest.fixture()
def isolated_db(tmp_path: Path, seed_db_path: Path, monkeypatch):
    """每个用例一份独立的 sqlite 文件，避免相互污染。

    通过 monkeypatch 把 database._DB_PATH 与 SQLALCHEMY_DATABASE_URL 重定向到 tmp_path，
    再重建 engine + SessionLocal。需要在 import 任何业务模块前完成。
    """
    tmp_db = tmp_path / "welding.db"
    shutil.copyfile(seed_db_path, tmp_db)

    import database
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    url = f"sqlite:///{tmp_db}"
    engine = create_engine(
        url,
        connect_args={"check_same_thread": False, "timeout": 30},
        pool_pre_ping=True,
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    monkeypatch.setattr(database, "engine", engine, raising=False)
    monkeypatch.setattr(database, "SessionLocal", SessionLocal, raising=False)
    monkeypatch.setattr(database, "_DB_PATH", str(tmp_db), raising=False)
    monkeypatch.setattr(database, "SQLALCHEMY_DATABASE_URL", url, raising=False)

    yield tmp_db

    engine.dispose()
