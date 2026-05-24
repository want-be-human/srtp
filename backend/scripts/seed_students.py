# -*- coding: utf-8 -*-
"""
预先把演示用的学生名单写到 students 表。

    cd backend
    python scripts/seed_students.py

重跑不会覆盖已经存在的学号；要重置密码先手工删行再跑。

--purge 模式会先把不在当前 ROSTER 里的学生删掉再插，用于演示前清掉旧学号：

    python scripts/seed_students.py --purge
"""

import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
sys.path.insert(0, backend_dir)

import bcrypt
from database import SessionLocal, engine
import models


ROSTER = [
    ("2024112434", "陈思远", "焊接班2024-A"),
    ("2024111216", "王俊杰", "焊接班2024-A"),
    ("2024112605", "林雨晴", "焊接班2024-A"),
    ("2024110853", "赵嘉宁", "焊接班2024-A"),
    ("2024113182", "黄子睿", "焊接班2024-A"),
    ("2024110741", "周文静", "焊接班2024-A"),
]

INITIAL_PASSWORD = "123456"


def main():
    models.Base.metadata.create_all(bind=engine)
    purge = "--purge" in sys.argv

    db = SessionLocal()
    try:
        if purge:
            keep_ids = {sid for sid, _, _ in ROSTER}
            removed = (
                db.query(models.Student)
                .filter(~models.Student.student_id.in_(keep_ids))
                .delete(synchronize_session=False)
            )
            print(f"清理不在 ROSTER 里的学生：{removed} 行")

        hashed = bcrypt.hashpw(INITIAL_PASSWORD.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        added = skipped = 0
        for sid, name, batch in ROSTER:
            existing = (
                db.query(models.Student)
                .filter(models.Student.student_id == sid)
                .first()
            )
            if existing:
                print(f"跳过：{sid} {name}（已存在）")
                skipped += 1
                continue
            db.add(models.Student(
                student_id=sid,
                name=name,
                password_hash=hashed,
                batch_id=batch,
            ))
            added += 1
        db.commit()
        print()
        print(f"完成：新增 {added}，跳过 {skipped}。")
        print(f"初始密码：{INITIAL_PASSWORD}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
