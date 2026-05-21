# -*- coding: utf-8 -*-
"""
往 welding.db 写一批演示用的历史检测记录。

    cd backend
    python scripts/seed_demo_data.py

重跑时会先按 notes 标记把上一批清掉再插，所以可以反复跑。
"""

import os
import random
import sys
from datetime import datetime, timedelta

current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
sys.path.insert(0, backend_dir)

from database import SessionLocal, engine
import models


DEMO_TAG = "demo_seed:v1"
ORPHAN_SID = "student_demo"

# weak 字段：哪一项打个折让画像更突出
PROFILES = [
    {
        "sid": "2024001", "name": "张三", "klass": "焊接班2024-A",
        "n": 22, "base": 72, "delta": 12, "noise": 4, "weak": "width",
        "defects": {"无缺陷": 5, "气孔": 2, "夹渣": 3, "焊瘤": 1, "咬边": 2, "未熔合": 1, "裂纹": 0},
    },
    {
        "sid": "2024002", "name": "李四", "klass": "焊接班2024-A",
        "n": 25, "base": 70, "delta": 10, "noise": 5, "weak": "defect",
        "defects": {"无缺陷": 2, "气孔": 5, "夹渣": 4, "焊瘤": 2, "咬边": 1, "未熔合": 1, "裂纹": 1},
    },
    {
        "sid": "2024003", "name": "王五", "klass": "焊接班2024-A",
        "n": 20, "base": 76, "delta": 8, "noise": 3, "weak": None,
        "defects": {"无缺陷": 6, "气孔": 2, "夹渣": 2, "焊瘤": 1, "咬边": 1, "未熔合": 1, "裂纹": 0},
    },
    {
        "sid": "2024004", "name": "赵六", "klass": "焊接班2024-A",
        "n": 18, "base": 86, "delta": 6, "noise": 3, "weak": None,
        "defects": {"无缺陷": 10, "气孔": 1, "夹渣": 1, "焊瘤": 0, "咬边": 1, "未熔合": 0, "裂纹": 0},
    },
    {
        "sid": "2024005", "name": "钱七", "klass": "焊接班2024-A",
        "n": 24, "base": 68, "delta": 20, "noise": 4, "weak": "smooth",
        "defects": {"无缺陷": 4, "气孔": 3, "夹渣": 2, "焊瘤": 2, "咬边": 2, "未熔合": 1, "裂纹": 0},
    },
    {
        "sid": "2024006", "name": "孙八", "klass": "焊接班2024-A",
        "n": 21, "base": 74, "delta": 6, "noise": 8, "weak": None,
        "defects": {"无缺陷": 4, "气孔": 3, "夹渣": 3, "焊瘤": 2, "咬边": 2, "未熔合": 1, "裂纹": 1},
    },
]


def clamp(v, lo=50, hi=98):
    return max(lo, min(hi, v))


def make_record(p, i, total):
    progress = i / max(1, total - 1)
    base = p["base"] + p["delta"] * progress
    noise = p["noise"]
    pick = lambda: clamp(base + random.uniform(-noise, noise))

    total_score = pick()
    smooth = pick()
    width = pick()
    defect = pick()

    weak = p.get("weak")
    if weak == "width":
        width = clamp(width - random.uniform(6, 10))
    elif weak == "defect":
        defect = clamp(defect - random.uniform(6, 10))
    elif weak == "smooth":
        smooth = clamp(smooth - random.uniform(6, 10))

    d = p["defects"]
    defect_name = random.choices(list(d), weights=list(d.values()), k=1)[0]

    # 目标焊缝宽度 6mm，宽度短板的偏差更大
    width_dev = 0.8 if weak == "width" else 0.4
    actual_width = round(6.0 + random.uniform(-width_dev, width_dev), 2)

    now = datetime.now()
    start = now - timedelta(days=14)
    span = (now - start).total_seconds()
    offset = span * progress + random.uniform(-1800, 1800)
    ts = start + timedelta(seconds=offset)

    return models.WeldingRecord(
        timestamp=ts,
        student_id=p["sid"],
        student_name=p["name"],
        batch_id=p["klass"],
        smoothness_score=round(smooth, 2),
        spacing_score=round(width, 2),
        defect_type_score=round(defect, 2),
        total_score=round(total_score, 2),
        actual_width=actual_width,
        defect_type_name=defect_name,
        notes=DEMO_TAG,
    )


def main():
    models.Base.metadata.create_all(bind=engine)
    random.seed(42)

    db = SessionLocal()
    try:
        deleted = (
            db.query(models.WeldingRecord)
            .filter(models.WeldingRecord.notes == DEMO_TAG)
            .delete(synchronize_session=False)
        )
        print(f"清理上轮演示数据：{deleted} 条")

        orphans = (
            db.query(models.WeldingRecord)
            .filter(models.WeldingRecord.student_id.is_(None))
            .update({"student_id": ORPHAN_SID, "student_name": "演示账号"},
                    synchronize_session=False)
        )
        print(f"孤立旧记录归到 {ORPHAN_SID}：{orphans} 条")

        total = 0
        for p in PROFILES:
            for i in range(p["n"]):
                db.add(make_record(p, i, p["n"]))
                total += 1
            print(f"  {p['sid']} {p['name']:>3}：{p['n']} 条"
                  f"  base {p['base']} → +{p['delta']}  weak={p.get('weak')}")

        db.commit()
        print()
        print(f"完成，共写入 {total} 条到 welding.db。")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
