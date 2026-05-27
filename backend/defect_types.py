# -*- coding: utf-8 -*-
"""焊缝缺陷类型定义 —— 跟 services/yolo/models/best.pt 实际类别对齐。

best.pt 是 6 类模型（model.names 见下），项目早期 17 类映射跟模型完全脱节，
cls=6~16 永远不会触发，导致雷达图维度也全是后端永远不输出的标签。这里把整套
体系收回到模型实际输出的 6 类，dead mapping 一并清掉。

如果将来要换 17 类模型或多类模型，统一改这一份 + RADAR_DEFECT_TYPES，下游
所有备用定义都会跟着对上。
"""

# YOLO模型类别ID到英文名称的映射（与 best.pt 的 model.names 严格对齐）
DEFECT_CLASSES = {
    0: 'Bad Welding',
    1: 'Crack',
    2: 'Excess Reinforcement',
    3: 'Good Welding',
    4: 'Porosity',
    5: 'Spatters',
}

DEFECT_EN_TO_CN = {
    'Bad Welding': '焊接不良',
    'Crack': '裂纹',
    'Excess Reinforcement': '焊缝过高',
    'Good Welding': '良好焊缝',
    'Porosity': '气孔',
    'Spatters': '飞溅',
}

DEFECT_CN_TO_EN = {v: k for k, v in DEFECT_EN_TO_CN.items()}

DEFECT_ID_TO_CN = {id_: DEFECT_EN_TO_CN[en] for id_, en in DEFECT_CLASSES.items()}

# 真正的缺陷类型（排除良好焊缝），5 项
TRUE_DEFECT_TYPES = ['焊接不良', '裂纹', '焊缝过高', '气孔', '飞溅']

# 雷达图维度：直接复用 TRUE_DEFECT_TYPES，5 维。
# 5 边形比 6 边形扁，但比"留着永远 0 的维度"诚实
RADAR_DEFECT_TYPES = list(TRUE_DEFECT_TYPES)

# 所有缺陷类型（中文）—— 含良好焊缝
ALL_DEFECT_TYPES_CN = list(DEFECT_EN_TO_CN.values())

# 这些 defect_type_name 值不算"实际缺陷"，统计时排除。
# 含 best.pt 的 'Good Welding' 和早期模型的 'Good Weld' 两种写法，
# 以及 DB 历史里出现过的占位/缺省值。
NON_DEFECT_LABELS = frozenset({
    'Good Welding',
    'Good Weld',
    '良好焊缝',
    '无缺陷',
    '无',
    '未知',
    '',
})


def get_defect_name_cn(class_id: int) -> str:
    """根据类别ID获取中文名称"""
    return DEFECT_ID_TO_CN.get(class_id, '未知缺陷')


def get_defect_name_safe(class_id: int) -> str:
    """已知类别返回中文名，未知的带上 id 方便排查。"""
    name = DEFECT_ID_TO_CN.get(class_id)
    if name:
        return name
    return f"未匹配类别 ID: {class_id}"


def get_defect_name_en(class_id: int) -> str:
    """根据类别ID获取英文名称"""
    return DEFECT_CLASSES.get(class_id, 'Unknown')


def translate_defect_to_cn(name_en: str) -> str:
    """将英文名称翻译为中文"""
    return DEFECT_EN_TO_CN.get(name_en, name_en)


def translate_defect_to_en(name_cn: str) -> str:
    """将中文名称翻译为英文"""
    return DEFECT_CN_TO_EN.get(name_cn, name_cn)


def is_true_defect(class_id: int) -> bool:
    """判断是否为真正的缺陷（非 Good Welding）"""
    return class_id != 3


def get_severity_level(class_id: int) -> str:
    """缺陷严重程度分级（按 best.pt 6 类映射）：
    - 严重：裂纹、焊接不良（综合性差，结构隐患）
    - 中等：气孔（影响强度但可控）
    - 轻微：焊缝过高、飞溅（外观 / 后处理问题）
    良好焊缝 (cls=3) 不参与缺陷分级，由调用方先过滤。
    """
    severity_map = {
        0: '严重',   # Bad Welding
        1: '严重',   # Crack
        4: '中等',   # Porosity
        2: '轻微',   # Excess Reinforcement
        5: '轻微',   # Spatters
    }
    return severity_map.get(class_id, '轻微')


if __name__ == "__main__":
    print("=" * 60)
    print("焊缝缺陷类型对照表（best.pt 6 类）")
    print("=" * 60)
    print(f"{'ID':<4} {'英文名称':<25} {'中文名称':<12} {'严重程度':<8}")
    print("-" * 60)
    for id_, en in DEFECT_CLASSES.items():
        cn = DEFECT_EN_TO_CN[en]
        severity = get_severity_level(id_) if id_ != 3 else '良好'
        print(f"{id_:<4} {en:<25} {cn:<12} {severity:<8}")
    print("=" * 60)
    print(f"总共 {len(DEFECT_CLASSES)} 种类型，其中 {len(TRUE_DEFECT_TYPES)} 种为真正的缺陷")
