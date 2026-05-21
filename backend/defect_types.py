# -*- coding: utf-8 -*-
"""
焊缝缺陷类型定义 - 统一中英文映射
基于东北大学焊缝缺陷数据集标签

支持的17种缺陷类型：
- Poor Weld: 焊接不良
- Crack: 裂纹
- Excess Rebar: 钢筋过剩
- Good Weld: 良好焊缝 (非缺陷)
- Porosity: 气孔
- Spatter: 飞溅
- Undercut: 咬边
- Overlap: 焊瘤
- Incomplete Fusion: 未熔合
- Inclusion: 夹渣
- Distortion: 变形
- Surface Roughness: 表面粗糙
- Excess Penetration: 焊穿
- Misalignment: 错边
- Arc Strike: 电弧擦伤
- Discoloration: 变色
- Tool Mark: 工具痕迹
"""

# YOLO模型缺陷类别ID到英文名称的映射
DEFECT_CLASSES = {
    0: 'Poor Weld',
    1: 'Crack',
    2: 'Excess Rebar',
    3: 'Good Weld',
    4: 'Porosity',
    5: 'Spatter',
    6: 'Undercut',
    7: 'Overlap',
    8: 'Incomplete Fusion',
    9: 'Inclusion',
    10: 'Distortion',
    11: 'Surface Roughness',
    12: 'Excess Penetration',
    13: 'Misalignment',
    14: 'Arc Strike',
    15: 'Discoloration',
    16: 'Tool Mark'
}

# 英文到中文的映射
DEFECT_EN_TO_CN = {
    'Poor Weld': '焊接不良',
    'Crack': '裂纹',
    'Excess Rebar': '钢筋过剩',
    'Good Weld': '良好焊缝',
    'Porosity': '气孔',
    'Spatter': '飞溅',
    'Undercut': '咬边',
    'Overlap': '焊瘤',
    'Incomplete Fusion': '未熔合',
    'Inclusion': '夹渣',
    'Distortion': '变形',
    'Surface Roughness': '表面粗糙',
    'Excess Penetration': '焊穿',
    'Misalignment': '错边',
    'Arc Strike': '电弧擦伤',
    'Discoloration': '变色',
    'Tool Mark': '工具痕迹'
}

# 中文到英文的映射
DEFECT_CN_TO_EN = {v: k for k, v in DEFECT_EN_TO_CN.items()}

# 类别ID到中文名称的映射
DEFECT_ID_TO_CN = {id_: DEFECT_EN_TO_CN[en] for id_, en in DEFECT_CLASSES.items()}

# 真正的缺陷类型列表（排除Good Weld良好焊缝）
TRUE_DEFECT_TYPES = [
    '焊接不良', '裂纹', '钢筋过剩', '气孔', '飞溅',
    '咬边', '焊瘤', '未熔合', '夹渣', '变形',
    '表面粗糙', '焊穿', '错边', '电弧擦伤', '变色', '工具痕迹'
]

# 雷达图显示的主要缺陷类型（选取最常见的6种）
RADAR_DEFECT_TYPES = ['气孔', '夹渣', '未熔合', '焊瘤', '咬边', '裂纹']

# 所有缺陷类型（中文）
ALL_DEFECT_TYPES_CN = list(DEFECT_EN_TO_CN.values())


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
    """判断是否为真正的缺陷（非Good Weld）"""
    return class_id != 3


def get_severity_level(class_id: int) -> str:
    """
    根据缺陷类型获取严重程度
    严重缺陷: 裂纹、未熔合、焊穿、夹渣
    中等缺陷: 气孔、咬边、焊瘤、焊接不良
    轻微缺陷: 其他
    """
    severity_map = {
        1: '严重',   # Crack 裂纹
        8: '严重',   # Incomplete Fusion 未熔合
        9: '严重',   # Inclusion 夹渣
        12: '严重',  # Excess Penetration 焊穿
        0: '中等',   # Poor Weld 焊接不良
        4: '中等',   # Porosity 气孔
        6: '中等',   # Undercut 咬边
        7: '中等',   # Overlap 焊瘤
    }
    return severity_map.get(class_id, '轻微')


if __name__ == "__main__":
    # 测试输出
    print("=" * 60)
    print("焊缝缺陷类型对照表")
    print("=" * 60)
    print(f"{'ID':<4} {'英文名称':<25} {'中文名称':<12} {'严重程度':<8}")
    print("-" * 60)
    for id_, en in DEFECT_CLASSES.items():
        cn = DEFECT_EN_TO_CN[en]
        severity = get_severity_level(id_) if id_ != 3 else '良好'
        print(f"{id_:<4} {en:<25} {cn:<12} {severity:<8}")
    print("=" * 60)
    print(f"总共 {len(DEFECT_CLASSES)} 种类型，其中 {len(TRUE_DEFECT_TYPES)} 种为真正的缺陷")
