# -*- coding: utf-8 -*-
"""
预先把演示用的学生名单写到 students 表。

    cd backend
    python scripts/seed_students.py

重跑不会覆盖已经存在的学号；要重置密码先手工删行再跑。
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
    ("2024001", "张三", "焊接班2024-A"),
    ("2024002", "李四", "焊接班2024-A"),
    ("2024003", "王五", "焊接班2024-A"),
    ("2024004", "赵六", "焊接班2024-A"),
    ("2024005", "钱七", "焊接班2024-A"),
    ("2024006", "孙八", "焊接班2024-A"),
]

INITIAL_PASSWORD = "123456"


def main():
    models.Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
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
