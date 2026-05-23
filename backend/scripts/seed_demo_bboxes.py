# -*- coding: utf-8 -*-
"""
给 welding.db 里已有的演示记录补上 mock 缺陷 bbox，让缺陷分布热图能演示。

    cd backend
    python scripts/seed_demo_bboxes.py

针对所有 student_id 不为空的历史记录都灌（不限定 demo_seed tag），可反复跑——
脚本会把每条记录的 defect_bboxes 字段重新覆盖一遍，幂等。

每个学生有一个固定的「常错位置」画像（起弧端 / 中段 / 收弧端等），bbox 围绕
画像中心做高斯扰动；defect_type_name == '无缺陷' 的记录大概率不灌任何 bbox。
"""

import os
import random
import sys
from typing import Optional

current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
sys.path.insert(0, backend_dir)

from database import SessionLocal, engine
import models
from defect_types import DEFECT_CN_TO_EN, NON_DEFECT_LABELS


# 每个学生分配一个常错位置画像 —— 让热图能直观看出"这人焊缝起弧不稳"vs"收弧瘤多"
# (cx, cy) 是热点中心；scatter 是高斯扰动 sigma；count_range 是单次按键灌几个框
HOTSPOTS = [
    {"sid": "2024001", "cx": 0.30, "cy": 0.48, "scatter": 0.06, "count": (1, 2), "note": "起弧端 + 上沿"},
    {"sid": "2024002", "cx": 0.55, "cy": 0.52, "scatter": 0.12, "count": (2, 3), "note": "中段散布、缺陷多"},
    {"sid": "2024003", "cx": 0.50, "cy": 0.50, "scatter": 0.05, "count": (1, 1), "note": "中线集中、稳定"},
    {"sid": "2024004", "cx": 0.50, "cy": 0.50, "scatter": 0.04, "count": (0, 1), "note": "极少出错"},
    {"sid": "2024005", "cx": 0.40, "cy": 0.62, "scatter": 0.07, "count": (1, 2), "note": "下沿光滑度差"},
    {"sid": "2024006", "cx": 0.72, "cy": 0.50, "scatter": 0.08, "count": (1, 3), "note": "收弧端起伏大"},
]

# 没在 HOTSPOTS 里的学生（包括 student_demo / 旧账号）走默认画像
DEFAULT_HOTSPOT = {"cx": 0.50, "cy": 0.50, "scatter": 0.10, "count": (1, 2), "note": "默认散布"}


def _pick_hotspot(student_id: Optional[str]) -> dict:
    for h in HOTSPOTS:
        if h["sid"] == student_id:
            return h
    return DEFAULT_HOTSPOT


def _clip01(v: float) -> float:
    return max(0.02, min(0.98, v))


def _gen_bbox(hotspot: dict, label_cn: str) -> dict:
    cx = _clip01(random.gauss(hotspot["cx"], hotspot["scatter"]))
    cy = _clip01(random.gauss(hotspot["cy"], hotspot["scatter"]))
    w = round(random.uniform(0.05, 0.12), 4)
    h = round(random.uniform(0.04, 0.10), 4)
    # bbox 中心 ± w/2、h/2 不能溢出画面，给 cx/cy 留边界
    cx = max(w / 2 + 0.01, min(1 - w / 2 - 0.01, cx))
    cy = max(h / 2 + 0.01, min(1 - h / 2 - 0.01, cy))
    label_en = DEFECT_CN_TO_EN.get(label_cn, label_cn)
    return {
        "label": label_en,
        "label_cn": label_cn,
        "cx": round(cx, 4),
        "cy": round(cy, 4),
        "w": w,
        "h": h,
        "conf": round(random.uniform(0.62, 0.92), 3),
    }


def _bboxes_for_record(record: models.WeldingRecord) -> list:
    hotspot = _pick_hotspot(record.student_id)
    main_label = (record.defect_type_name or "").strip()

    if main_label in NON_DEFECT_LABELS:
        # 良品记录大部分什么也不出，少量出 1 个边缘小框模拟误检
        return [_gen_bbox(hotspot, random.choice(["气孔", "夹渣"]))] if random.random() < 0.15 else []

    lo, hi = hotspot["count"]
    n = random.randint(lo, hi)
    if n == 0:
        return []

    # 主缺陷 + 偶尔混一两个杂项，更真实
    bag = [main_label] * 3 + ["气孔", "夹渣", "咬边", "焊瘤"]
    return [_gen_bbox(hotspot, random.choice(bag)) for _ in range(n)]


def main():
    random.seed(2026)
    db = SessionLocal()
    try:
        records = (
            db.query(models.WeldingRecord)
            .filter(models.WeldingRecord.student_id.isnot(None))
            .all()
        )
        print(f"扫描到 {len(records)} 条带 student_id 的记录")

        touched = 0
        per_student = {}
        for r in records:
            boxes = _bboxes_for_record(r)
            r.defect_bboxes = boxes
            touched += 1
            per_student.setdefault(r.student_id, [0, 0])
            per_student[r.student_id][0] += 1
            per_student[r.student_id][1] += len(boxes)

        db.commit()

        print()
        print(f"已重写 defect_bboxes：{touched} 条记录")
        print()
        print(f"  {'学生':<14} {'记录':>4} {'累计框':>6}")
        for sid in sorted(per_student):
            rec_n, box_n = per_student[sid]
            hotspot = _pick_hotspot(sid)
            print(f"  {sid:<14} {rec_n:>4} {box_n:>6}   ← {hotspot.get('note', '')}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
