"""defect_types 模块的单元测试。

defect_types 是焊缝缺陷的中英文映射 + 严重程度划分的单一事实来源，
其它模块（YOLO 检测、AI 分析、雷达图、PDF 报告）都依赖它，必须保住：
1. 6 类映射跟 best.pt 严格对齐、双向无歧义；
2. NON_DEFECT_LABELS 覆盖所有"非缺陷"称呼，否则统计会把良品当缺陷；
3. 严重程度分级符合工程语义（裂纹 / 焊接不良 = 严重）。
"""

import pytest

import defect_types as dt


class TestDefectMapping:
    def test_class_count_matches_best_pt(self):
        # best.pt model.names 是 6 类，必须对齐
        assert len(dt.DEFECT_CLASSES) == 6

    def test_en_cn_bijection(self):
        assert len(dt.DEFECT_EN_TO_CN) == 6
        assert len(dt.DEFECT_CN_TO_EN) == 6
        for en, cn in dt.DEFECT_EN_TO_CN.items():
            assert dt.DEFECT_CN_TO_EN[cn] == en

    def test_id_to_cn_complete(self):
        for cls_id, en in dt.DEFECT_CLASSES.items():
            assert dt.DEFECT_ID_TO_CN[cls_id] == dt.DEFECT_EN_TO_CN[en]

    def test_true_defects_excludes_good_weld(self):
        assert "良好焊缝" not in dt.TRUE_DEFECT_TYPES
        # 6 类减掉 Good Welding = 5 个真实缺陷
        assert len(dt.TRUE_DEFECT_TYPES) == 5


class TestNonDefectLabels:
    @pytest.mark.parametrize("label", [
        "Good Welding",
        "Good Weld",
        "良好焊缝",
        "无缺陷",
        "无",
        "未知",
        "",
    ])
    def test_labels_in_non_defect_set(self, label):
        assert label in dt.NON_DEFECT_LABELS

    def test_real_defect_not_in_set(self):
        # 真正的缺陷绝不能误进 NON_DEFECT_LABELS，否则统计会丢
        for defect in ["Crack", "Porosity", "气孔", "裂纹", "Spatters"]:
            assert defect not in dt.NON_DEFECT_LABELS


class TestSeverityLevel:
    @pytest.mark.parametrize("cls_id,expected", [
        (0, "严重"),   # Bad Welding
        (1, "严重"),   # Crack
        (4, "中等"),   # Porosity
        (2, "轻微"),   # Excess Reinforcement
        (5, "轻微"),   # Spatters
    ])
    def test_severity(self, cls_id, expected):
        assert dt.get_severity_level(cls_id) == expected

    def test_unknown_id_defaults_to_mild(self):
        # 兜底逻辑：未知类别默认"轻微"，不能崩溃
        assert dt.get_severity_level(999) == "轻微"


class TestNameLookup:
    def test_get_defect_name_cn(self):
        assert dt.get_defect_name_cn(1) == "裂纹"
        assert dt.get_defect_name_cn(4) == "气孔"

    def test_unknown_id_returns_placeholder(self):
        # 不能抛异常，需要给可追踪的回退串
        result = dt.get_defect_name_cn(999)
        assert isinstance(result, str)
        assert result != ""

    def test_get_defect_name_safe_keeps_id(self):
        # safe 版本未知 ID 时带上 id 方便排查
        assert "999" in dt.get_defect_name_safe(999)

    def test_translate_roundtrip(self):
        for en in dt.DEFECT_CLASSES.values():
            cn = dt.translate_defect_to_cn(en)
            assert dt.translate_defect_to_en(cn) == en


class TestIsTrueDefect:
    def test_good_weld_is_not_defect(self):
        # 类别 3 = Good Welding，必须返回 False
        assert dt.is_true_defect(3) is False

    @pytest.mark.parametrize("cls_id", [0, 1, 2, 4, 5])
    def test_others_are_true_defects(self, cls_id):
        assert dt.is_true_defect(cls_id) is True
