# -*- coding: utf-8 -*-
"""只删名字为"演示账号"的孤儿账户产生的检测记录。

用法：
    cd backend
    python scripts/purge_demo_records.py

清理范围（保守，只清孤儿）：
- 所有 `student_id='student_demo'` 的 WeldingRecord
- 所有 `student_name='演示账号'` 的 WeldingRecord（兜底：student_id 写丢但姓名没改）
- 不动 `notes='demo_seed:v1'` 的 6 个学生（陈思远等）数据，这些是答辩演示用的画像
- 不动 Student 表，登录账号全部保留
"""

import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
sys.path.insert(0, backend_dir)

from database import SessionLocal
import models


ORPHAN_SID = "student_demo"
ORPHAN_NAME = "演示账号"


def main():
    db = SessionLocal()
    try:
        total_before = db.query(models.WeldingRecord).count()
        print(f"清理前 WeldingRecord 总数: {total_before}")

        by_sid = (
            db.query(models.WeldingRecord)
            .filter(models.WeldingRecord.student_id == ORPHAN_SID)
            .delete(synchronize_session=False)
        )
        print(f"  - student_id={ORPHAN_SID!r} 删除 {by_sid} 条")

        by_name = (
            db.query(models.WeldingRecord)
            .filter(models.WeldingRecord.student_name == ORPHAN_NAME)
            .delete(synchronize_session=False)
        )
        print(f"  - student_name={ORPHAN_NAME!r} 删除 {by_name} 条（兜底）")

        db.commit()
        total_after = db.query(models.WeldingRecord).count()
        print(f"清理后 WeldingRecord 总数: {total_after}")

        students = db.query(models.Student).count()
        print(f"Student 表保留: {students} 行（登录账号不动）")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
