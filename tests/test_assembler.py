"""core/assembler.py — 人工映射表解析 + U3 终极组装"""

import logging

import pandas as pd
import pytest

from core.assembler import _get_standard_name, generate_final_u3, parse_mapping_rules

# 列名必须与 analyzer 生成的模板逐字一致 (emoji 也是表头的一部分)
VANGUARD_COL = "🤖 AI 提取的【排头兵】"
STANDARD_COL = "🧑‍🔧 填写标准名称 (抄左边/填中文/不认识留空)"
# 概念表与机构表同构: 源列是聚类出的"排头兵", 只填"标准大类"
CON_ORIG_COL = "🤖 AI 提取的【排头兵】"
CON_TARGET_COL = "🧑‍🔧 填写标准大类 (如：人工智能)"


def _aff_df(rows):
    return pd.DataFrame([{VANGUARD_COL: v, STANDARD_COL: s} for v, s in rows])


def _con_df(rows):
    return pd.DataFrame([{CON_ORIG_COL: o, CON_TARGET_COL: t} for o, t in rows])


# --------------------------- parse_mapping_rules ---------------------------

def test_parse_affiliation_mappings():
    aff_map, con_map = parse_mapping_rules(
        _aff_df([("Brain Lab", "脑科学实验室"), ("Vision Dept", "视觉实验室")]),
        pd.DataFrame(),
    )
    assert aff_map == {"Brain Lab": "脑科学实验室", "Vision Dept": "视觉实验室"}
    assert con_map == {}


def test_parse_affiliation_skips_unfilled_rows():
    aff_map, _ = parse_mapping_rules(
        _aff_df([("Brain Lab", "脑科学实验室"), ("Empty Lab", ""), ("Na Lab", "nan")]),
        pd.DataFrame(),
    )
    assert set(aff_map) == {"Brain Lab"}


def test_parse_affiliation_merges_duplicate_standard_names():
    """两个排头兵被人工判定为同一实验室时，两者都要保留映射。

    否则第二个排头兵的变体会掉进 golden_keys/垃圾桶，与日志承诺的「合并」不符。
    """
    aff_map, _ = parse_mapping_rules(
        _aff_df([("Brain Lab Old", "脑科学实验室"), ("Brain Lab New", "脑科学实验室")]),
        pd.DataFrame(),
    )
    assert aff_map == {
        "Brain Lab Old": "脑科学实验室",
        "Brain Lab New": "脑科学实验室",
    }


def test_parse_concept_mappings_keep_original_when_target_blank():
    _, con_map = parse_mapping_rules(
        pd.DataFrame(),
        _con_df([("deep learning", ""), ("robotics", "机器人")]),
    )
    # 没填目标大类 → 保留原名；填了就换成新大类。键统一小写
    assert con_map == {"deep learning": "deep learning", "robotics": "机器人"}


def test_parse_concept_skips_nan_original():
    _, con_map = parse_mapping_rules(pd.DataFrame(), _con_df([("nan", "x"), ("", "y")]))
    assert con_map == {}


def test_parse_mapping_rules_empty_frames():
    assert parse_mapping_rules(pd.DataFrame(), pd.DataFrame()) == ({}, {})


def test_parse_mapping_rules_tolerates_legacy_vanguard_header():
    # 兼容旧版表头「提取的【排头兵】」
    df = pd.DataFrame([{"提取的【排头兵】": "Legacy Lab", STANDARD_COL: "旧实验室"}])
    aff_map, _ = parse_mapping_rules(df, pd.DataFrame())
    assert aff_map == {"Legacy Lab": "旧实验室"}


# --------------------------- _get_standard_name ---------------------------

@pytest.mark.parametrize("bad", ["", None, "nan"])
def test_get_standard_name_unknown_for_empty(bad):
    assert _get_standard_name(bad, {}, {}) == "(未知部门)"


def test_get_standard_name_prefers_explicit_mapping():
    assert _get_standard_name("Brain Lab", {"Brain Lab": "脑科学实验室"}, {}) == "脑科学实验室"


def test_get_standard_name_golden_key_fallback_is_case_insensitive():
    out = _get_standard_name("BRAIN LAB, Building 3", {}, {"brain": "脑科学实验室"})
    assert out == "脑科学实验室"


def test_get_standard_name_falls_back_to_other_dept():
    assert _get_standard_name("Mystery Unit", {}, {}) == "(其他部门)"


def test_get_standard_name_ignores_blank_golden_keys():
    assert _get_standard_name("X", {}, {"": "nope", "x": "   "}) == "(其他部门)"


def test_get_standard_name_respects_custom_labels():
    out = _get_standard_name("X", {}, {}, labels_cfg={"other_dept": "OTHER"})
    assert out == "OTHER"


# --------------------------- generate_final_u3 ---------------------------

def _u2_5(concepts, internal_affs, external_count=0):
    authors = [{"is_internal_node": True,
                "raw_affiliation_strings": list(internal_affs)}]
    authors += [{"is_internal_node": False,
                 "raw_affiliation_strings": ["x"]} for _ in range(external_count)]
    return [{"concepts": concepts, "authorships": authors}]


def test_generate_final_u3_drops_concepts_missing_from_mapping():
    data = _u2_5(
        [{"display_name": "Deep Learning", "level": 1},
         {"display_name": "Tea Ceremony", "level": 2}],
        ["Brain Lab"],
    )
    out, stats = generate_final_u3(data, {}, {"deep learning": "人工智能"}, {})

    kept = out[0]["concepts"]
    assert len(kept) == 1
    assert kept[0]["display_name"] == "人工智能"
    assert kept[0]["original_name"] == "Deep Learning"
    assert stats == {"replace_count": 1, "dropped_count": 1}


def test_generate_final_u3_preserves_original_name_from_step3():
    """Step 3 概念坍缩时已把原始名写进 original_name, 组装时不能覆盖它。"""
    data = _u2_5(
        [{"display_name": "人工智能", "original_name": "Deep Learning", "level": 1}],
        [],
    )
    out, _ = generate_final_u3(data, {}, {"人工智能": "人工智能"}, {})
    kept = out[0]["concepts"][0]
    assert kept["original_name"] == "Deep Learning"
    assert kept["display_name"] == "人工智能"


def test_generate_final_u3_standardizes_internal_affiliations():
    data = _u2_5([], ["Brain Lab Old"])
    out, _ = generate_final_u3(
        data, {"Brain Lab Old": "脑科学实验室"}, {}, {}, labels_cfg={"external": "EXT"}
    )
    auth = out[0]["authorships"][0]
    assert auth["raw_affiliation_strings"] == ["脑科学实验室"]
    assert auth["raw_affiliation_string"] == "脑科学实验室"


def test_generate_final_u3_uses_golden_keys_then_other_dept():
    data = _u2_5([], ["Brain Lab 3F", "Mystery Unit"])
    out, _ = generate_final_u3(data, {}, {}, {"brain": "脑科学实验室"})
    assert out[0]["authorships"][0]["raw_affiliation_strings"] == [
        "脑科学实验室",
        "(其他部门)",
    ]


def test_generate_final_u3_collapses_external_authors():
    data = _u2_5([], ["Brain Lab"], external_count=1)
    out, _ = generate_final_u3(data, {}, {}, {}, labels_cfg={"external": "外部合作机构"})

    external = out[0]["authorships"][1]
    assert external["raw_affiliation_strings"] == ["外部合作机构"]
    assert external["raw_affiliation_string"] == "外部合作机构"


def test_generate_final_u3_leaves_untouched_works_alone():
    data = [{"id": "W1"}]
    out, stats = generate_final_u3(data, {}, {}, {})
    assert out == [{"id": "W1"}]
    assert stats == {"replace_count": 0, "dropped_count": 0}
