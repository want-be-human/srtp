# -*- coding: utf-8 -*-
"""
学生班级名单预播种脚本（C1）

国赛演示阶段在本机执行一次即可：

    cd backend
    python scripts/seed_students.py

效果：
- 在 students 表里插入 ROSTER 列出的 6 名学生
- 初始密码统一为 INITIAL_PASSWORD（bcrypt 哈希入库）
- 重复运行时，已存在的 student_id 会被跳过，**不会**重置密码

未来对接学校官网后，可写一个等价的导入器替换本脚本，本表结构不变。
"""

import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
sys.path.insert(0, backend_dir)

import bcrypt
from database import SessionLocal, engine
import models


# 演示班级名单。学号格式 YYYY+三位序号，便于一眼看出班级年份。
ROSTER = [
    ("2024001", "张三", "焊接班2024-A"),
    ("2024002", "李四", "焊接班2024-A"),
    ("2024003", "王五", "焊接班2024-A"),
    ("2024004", "赵六", "焊接班2024-A"),
    ("2024005", "钱七", "焊接班2024-A"),
    ("2024006", "孙八", "焊接班2024-A"),
]

INITIAL_PASSWORD = "123456"


def main() -> None:
    # 确保 students 表已创建（首次运行时数据库可能尚未拥有该表）
    models.Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        hashed = bcrypt.hashpw(INITIAL_PASSWORD.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        added, skipped = 0, 0
        for student_id, name, batch_id in ROSTER:
            existing = (
                db.query(models.Student)
                .filter(models.Student.student_id == student_id)
                .first()
            )
            if existing:
                print(f"跳过：{student_id} {name}（已存在）")
                skipped += 1
                continue
            db.add(
                models.Student(
                    student_id=student_id,
                    name=name,
                    password_hash=hashed,
                    batch_id=batch_id,
                )
            )
            added += 1
        db.commit()
        print()
        print(f"完成：新增 {added} 名学生，跳过 {skipped} 名已存在。")
        print(f"初始密码统一为：{INITIAL_PASSWORD}")
        print("演示时学号示例：2024001 / 2024002 ...")
    finally:
        db.close()


if __name__ == "__main__":
    main()
