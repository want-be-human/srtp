# -*- coding: utf-8 -*-
"""
往 welding.db 写一批演示用的历史检测记录。

    cd backend
    python scripts/seed_demo_data.py

重跑时会先按 notes 标记把上一批清掉再插，所以可以反复跑。

分数 / 宽度规则对齐真实检测器：
- 单项分钳到 [20, 100]：宽度超 3-8mm 范围时检测器直接给 20，单项分理论保底就是 20
- 综合评分 = 0.3·光滑 + 0.3·宽 + 0.4·缺陷（学校规定）
- 最佳宽度 5.5mm，超 3-8 范围出现概率 ~10%，让评委看到「触底样本」存在
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

# 单项分边界：与 zonghe_*.py / guanghuadu_*.py 实际 clamp 行为对齐
SCORE_FLOOR = 20.0
SCORE_CEIL = 100.0

# 宽度参数：从 yolo_config.json 摘出来，必须和检测器一致
OPTIMAL_WIDTH_MM = 5.5
MIN_WIDTH_MM = 3.0
MAX_WIDTH_MM = 8.0
# 多少比例的样本主动放到 3-8mm 之外，让 weak=width 的学生数据更"真实"
OUT_OF_RANGE_RATIO = 0.10

# weak 字段：哪一项打个折让画像更突出；ID 故意不连号
PROFILES = [
    {
        "sid": "2024112434", "name": "陈思远", "klass": "焊接班2024-A",
        "n": 22, "base": 70, "delta": 14, "noise": 6, "weak": "width",
        "defects": {"无缺陷": 5, "气孔": 2, "夹渣": 3, "焊瘤": 1, "咬边": 2, "未熔合": 1, "裂纹": 0},
    },
    {
        "sid": "2024111216", "name": "王俊杰", "klass": "焊接班2024-A",
        "n": 25, "base": 65, "delta": 12, "noise": 7, "weak": "defect",
        "defects": {"无缺陷": 2, "气孔": 5, "夹渣": 4, "焊瘤": 2, "咬边": 1, "未熔合": 1, "裂纹": 1},
    },
    {
        "sid": "2024112605", "name": "林雨晴", "klass": "焊接班2024-A",
        "n": 20, "base": 78, "delta": 8, "noise": 4, "weak": None,
        "defects": {"无缺陷": 6, "气孔": 2, "夹渣": 2, "焊瘤": 1, "咬边": 1, "未熔合": 1, "裂纹": 0},
    },
    {
        "sid": "2024110853", "name": "赵嘉宁", "klass": "焊接班2024-A",
        "n": 18, "base": 86, "delta": 6, "noise": 4, "weak": None,
        "defects": {"无缺陷": 10, "气孔": 1, "夹渣": 1, "焊瘤": 0, "咬边": 1, "未熔合": 0, "裂纹": 0},
    },
    {
        "sid": "2024113182", "name": "黄子睿", "klass": "焊接班2024-A",
        "n": 24, "base": 62, "delta": 22, "noise": 5, "weak": "smooth",
        "defects": {"无缺陷": 4, "气孔": 3, "夹渣": 2, "焊瘤": 2, "咬边": 2, "未熔合": 1, "裂纹": 0},
    },
    {
        "sid": "2024110741", "name": "周文静", "klass": "焊接班2024-A",
        "n": 21, "base": 72, "delta": 6, "noise": 10, "weak": None,
        "defects": {"无缺陷": 4, "气孔": 3, "夹渣": 3, "焊瘤": 2, "咬边": 2, "未熔合": 1, "裂纹": 1},
    },
]


def clamp(v: float, lo: float = SCORE_FLOOR, hi: float = SCORE_CEIL) -> float:
    return max(lo, min(hi, v))


def _pick_actual_width(weak_width: bool) -> tuple[float, bool]:
    """随机摇一个 actual_width。返回 (width_mm, out_of_range_flag)。

    weak=width 的学生触底概率翻倍，其他学生少量触底（让宽度保底=20 真实出现）。
    """
    base_ratio = OUT_OF_RANGE_RATIO * (2.0 if weak_width else 1.0)
    if random.random() < base_ratio:
        # 越界样本：偏向上限或下限
        if random.random() < 0.5:
            return round(random.uniform(1.5, MIN_WIDTH_MM - 0.1), 2), True
        return round(random.uniform(MAX_WIDTH_MM + 0.1, 10.0), 2), True
    # 正常样本：围绕 5.5mm，weak=width 偏差更大
    dev = 1.2 if weak_width else 0.6
    w = OPTIMAL_WIDTH_MM + random.uniform(-dev, dev)
    return round(max(MIN_WIDTH_MM, min(MAX_WIDTH_MM, w)), 2), False


def _width_score_from_mm(width_mm: float) -> float:
    """复用 zonghe_*.py::_calculate_width_score 的逻辑，让 seed 分数和检测器口径一致。"""
    if width_mm < MIN_WIDTH_MM or width_mm > MAX_WIDTH_MM:
        return SCORE_FLOOR
    dist = abs(width_mm - OPTIMAL_WIDTH_MM)
    max_dist = max(OPTIMAL_WIDTH_MM - MIN_WIDTH_MM, MAX_WIDTH_MM - OPTIMAL_WIDTH_MM)
    return clamp(100.0 - (dist / max_dist) * 60.0)


def make_record(p: dict, i: int, total: int) -> models.WeldingRecord:
    progress = i / max(1, total - 1)
    base = p["base"] + p["delta"] * progress
    noise = p["noise"]
    weak = p.get("weak")

    smooth = clamp(base + random.uniform(-noise, noise))
    defect = clamp(base + random.uniform(-noise, noise))
    actual_width, _ = _pick_actual_width(weak == "width")
    width = _width_score_from_mm(actual_width)

    if weak == "defect":
        defect = clamp(defect - random.uniform(8, 14))
    elif weak == "smooth":
        smooth = clamp(smooth - random.uniform(8, 14))

    # 综合分严格按学校规定权重算出来，不再单独 noise
    total_score = round(smooth * 0.3 + width * 0.3 + defect * 0.4, 2)

    d = p["defects"]
    defect_name = random.choices(list(d), weights=list(d.values()), k=1)[0]

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
        total_score=total_score,
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
        out_of_range = 0
        for p in PROFILES:
            for i in range(p["n"]):
                r = make_record(p, i, p["n"])
                if r.actual_width < MIN_WIDTH_MM or r.actual_width > MAX_WIDTH_MM:
                    out_of_range += 1
                db.add(r)
                total += 1
            print(f"  {p['sid']} {p['name']}：{p['n']} 条"
                  f"  base {p['base']} → +{p['delta']}  weak={p.get('weak')}")

        db.commit()
        print()
        print(f"完成，共写入 {total} 条到 welding.db，其中 {out_of_range} 条宽度越界 → 触发保底 20。")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
