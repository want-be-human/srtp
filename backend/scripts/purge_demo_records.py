# -*- coding: utf-8 -*-
"""清除 welding.db 里所有演示账号产生的检测记录（WeldingRecord 表）。

用法：
    cd backend
    python scripts/purge_demo_records.py

清理范围：
- 所有 `notes='demo_seed:v1'` 的记录（seed_demo_data 写入的画像数据）
- 所有 `student_id='student_demo'` 的孤立旧记录
- Student 表的 6 个演示账号**保留**，登录功能要用；只清检测历史

要重新填充演示数据：
    python scripts/seed_demo_data.py
    python scripts/seed_demo_bboxes.py
"""

import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
sys.path.insert(0, backend_dir)

from database import SessionLocal
import models


DEMO_TAGS = ("demo_seed:v1",)
ORPHAN_SID = "student_demo"


def main():
    db = SessionLocal()
    try:
        total_before = db.query(models.WeldingRecord).count()
        print(f"清理前 WeldingRecord 总数: {total_before}")

        by_tag = (
            db.query(models.WeldingRecord)
            .filter(models.WeldingRecord.notes.in_(DEMO_TAGS))
            .delete(synchronize_session=False)
        )
        print(f"  - notes in {DEMO_TAGS} 删除 {by_tag} 条")

        orphans = (
            db.query(models.WeldingRecord)
            .filter(models.WeldingRecord.student_id == ORPHAN_SID)
            .delete(synchronize_session=False)
        )
        print(f"  - student_id={ORPHAN_SID!r} 删除 {orphans} 条")

        # 谨慎兜底：notes=None 的孤儿（早期没打 tag 写入的）
        nulls = (
            db.query(models.WeldingRecord)
            .filter(models.WeldingRecord.notes.is_(None))
            .delete(synchronize_session=False)
        )
        print(f"  - notes IS NULL 删除 {nulls} 条")

        db.commit()
        total_after = db.query(models.WeldingRecord).count()
        print(f"清理后 WeldingRecord 总数: {total_after}")

        # Student 表不动
        students = db.query(models.Student).count()
        print(f"Student 表保留: {students} 行")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
