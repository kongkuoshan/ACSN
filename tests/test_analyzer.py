"""core/analyzer.py — 排头兵聚类与变体坍缩。

机构与领域两个通道都需要 SBERT + sklearn；测试里用假编码器替换模型加载，
使聚类逻辑本身可以在离线、无 ML 依赖的环境下被验证。
"""

import numpy as np
import pytest

from core import analyzer

# 机构四变体 → 两个语义簇 (坐标明显分离，聚类结果确定)
_VECTORS = {
    "Lab Alpha": [0.0, 0.0],
    "Lab Alpha Long": [0.1, 0.0],
    "Dept Beta": [10.0, 10.0],
    "Dept Beta Long": [10.1, 10.0],
}

# 领域四变体 → 两个语义簇
_CON_VECTORS = {
    "Alpha Topic": [0.0, 0.0],
    "Alpha Topic Long": [0.1, 0.0],
    "Beta Topic": [10.0, 10.0],
    "Beta Topic Long": [10.1, 10.0],
}

CON_VANGUARD_COL = "🤖 AI 提取的【排头兵】"
CON_STANDARD_COL = "🧑‍🔧 填写标准大类 (如：人工智能)"
AFF_STANDARD_COL = "🧑‍🔧 填写标准名称 (抄左边/填中文/不认识留空)"


class _FakeModel:
    """按文本查表返回固定向量的假 SBERT 模型。"""

    def __init__(self, vectors):
        self._vectors = vectors

    def encode(self, texts, show_progress_bar=False):
        return np.array([self._vectors[t] for t in texts], dtype=float)


class _BrokenModel:
    def encode(self, texts, show_progress_bar=False):
        raise OSError("simulated download failure")


def _patch_model(monkeypatch, vectors=None):
    """把 analyzer 的模型加载替换成假编码器 (完全离线)。"""
    table = _VECTORS if vectors is None else vectors
    monkeypatch.setattr(
        analyzer, "load_sentence_transformer", lambda name: _FakeModel(table)
    )


# --------------------------- _pick_vanguard ---------------------------

def test_pick_vanguard_shortest_and_longest():
    texts = ["abc", "a", "ab"]
    assert analyzer._pick_vanguard(texts, "shortest") == "a"
    assert analyzer._pick_vanguard(texts, "longest") == "abc"


def test_pick_vanguard_defaults_to_shortest():
    assert analyzer._pick_vanguard(["long name", "x"]) == "x"


# --------------------------- build_cluster_mappings: 概念通道 ---------------------------

def test_concepts_channel_clusters_variants_to_vanguards(monkeypatch):
    _patch_model(monkeypatch, _CON_VECTORS)

    df_con, df_aff, aff_map, con_map = analyzer.build_cluster_mappings(
        {"concepts": list(_CON_VECTORS)}, target_clusters=10,
        nlp_cfg={"target_con_clusters": 2},
    )

    assert len(df_con) == 2
    assert df_con["包含变体数"].sum() == 4
    # 每个概念都坍缩到所在簇的排头兵 (最短名)
    assert con_map == {
        "Alpha Topic": "Alpha Topic",
        "Alpha Topic Long": "Alpha Topic",
        "Beta Topic": "Beta Topic",
        "Beta Topic Long": "Beta Topic",
    }
    # 概念表列名与机构表同构, 只换"填写"列
    assert CON_VANGUARD_COL in df_con.columns
    assert CON_STANDARD_COL in df_con.columns
    assert df_aff.empty and aff_map == {}


def test_concept_cluster_target_is_capped_at_sample_size(monkeypatch):
    """目标簇数 > 概念数时不能崩，退化为每个概念一簇。"""
    _patch_model(monkeypatch, _CON_VECTORS)

    df_con, _, _, con_map = analyzer.build_cluster_mappings(
        {"concepts": list(_CON_VECTORS)}, target_clusters=10,
        nlp_cfg={"target_con_clusters": 100},
    )

    assert len(df_con) == 4
    assert con_map == {t: t for t in _CON_VECTORS}


def test_concepts_channel_handles_empty_concepts():
    df_con, df_aff, aff_map, con_map = analyzer.build_cluster_mappings(
        {"concepts": []}, target_clusters=10
    )
    assert df_con.empty and df_aff.empty and aff_map == {} and con_map == {}


def test_empty_unique_data_returns_empty_everything():
    df_con, df_aff, aff_map, con_map = analyzer.build_cluster_mappings({}, target_clusters=10)
    assert df_con.empty and df_aff.empty and aff_map == {} and con_map == {}


# --------------------------- build_cluster_mappings: 机构通道 ---------------------------

def test_affiliation_clustering_collapses_variants_to_vanguards(monkeypatch):
    _patch_model(monkeypatch)

    df_con, df_aff, aff_map, con_map = analyzer.build_cluster_mappings(
        {"raw_affiliations": list(_VECTORS)}, target_clusters=2
    )

    assert len(df_aff) == 2
    assert df_aff["包含变体数"].sum() == 4
    # 每个变体都坍缩到所在簇的排头兵 (最短名)
    assert aff_map == {
        "Lab Alpha": "Lab Alpha",
        "Lab Alpha Long": "Lab Alpha",
        "Dept Beta": "Dept Beta",
        "Dept Beta Long": "Dept Beta",
    }
    # 模板列名必须与 Step 4 解析的表头保持一致
    assert CON_VANGUARD_COL in df_aff.columns
    assert AFF_STANDARD_COL in df_aff.columns
    assert set(df_aff["簇编号"]) == {0, 1}
    assert df_con.empty and con_map == {}


def test_affiliation_clustering_respects_longest_strategy(monkeypatch):
    _patch_model(monkeypatch)

    _, _, aff_map, _ = analyzer.build_cluster_mappings(
        {"raw_affiliations": list(_VECTORS)},
        target_clusters=2,
        nlp_cfg={"vanguard_strategy": "longest"},
    )

    assert aff_map["Lab Alpha"] == "Lab Alpha Long"
    assert aff_map["Dept Beta"] == "Dept Beta Long"


def test_affiliation_clustering_truncates_long_reference(monkeypatch):
    long_name = "Lab Alpha " + "X" * 100
    vectors = dict(_VECTORS)
    vectors[long_name] = [0.05, 0.0]
    _patch_model(monkeypatch, vectors)

    _, df_aff, _, _ = analyzer.build_cluster_mappings(
        {"raw_affiliations": list(vectors)},
        target_clusters=2,
        nlp_cfg={"reference_max_len": 20},
    )

    references = [r for r in df_aff["🔍 辅助参考 (可忽略)"] if r]
    assert any(r.endswith("...") and len(r) <= 20 for r in references)


def test_affiliation_clustering_kmeans_branch(monkeypatch):
    _patch_model(monkeypatch)

    _, df_aff, aff_map, _ = analyzer.build_cluster_mappings(
        {"raw_affiliations": list(_VECTORS)},
        target_clusters=2,
        nlp_cfg={"kmeans_switch_threshold": 1},  # 强制走 KMeans 分支
    )

    assert len(df_aff) == 2
    assert set(aff_map) == set(_VECTORS)


def test_clustering_model_failure_returns_empty(monkeypatch):
    monkeypatch.setattr(analyzer, "load_sentence_transformer", lambda name: _BrokenModel())

    df_con, df_aff, aff_map, con_map = analyzer.build_cluster_mappings(
        {"raw_affiliations": list(_VECTORS), "concepts": list(_CON_VECTORS)},
        target_clusters=2,
    )

    # 编码失败时必须优雅降级，而不是把异常抛给流水线
    assert df_aff.empty and aff_map == {}
    assert df_con.empty and con_map == {}


def test_cluster_mappings_loads_model_once_for_both_channels(monkeypatch):
    calls = []

    def _loader(name):
        calls.append(name)
        return _FakeModel({**_VECTORS, **_CON_VECTORS})

    monkeypatch.setattr(analyzer, "load_sentence_transformer", _loader)

    df_con, df_aff, aff_map, con_map = analyzer.build_cluster_mappings(
        {"raw_affiliations": list(_VECTORS), "concepts": list(_CON_VECTORS)},
        target_clusters=2, nlp_cfg={"target_con_clusters": 2},
    )

    assert len(calls) == 1                      # 两通道共用一次模型加载
    assert len(df_aff) == 2 and len(df_con) == 2
    assert set(aff_map) == set(_VECTORS)
    assert set(con_map) == set(_CON_VECTORS)


# --------------------------- apply_vanguard_mapping ---------------------------

def test_apply_vanguard_mapping_rewrites_internal_only():
    data = [{
        "authorships": [
            {"is_internal_node": True, "raw_affiliation_strings": ["Lab Alpha Long", "Other"]},
            {"is_internal_node": False, "raw_affiliation_strings": ["External U"]},
        ]
    }]
    out = analyzer.apply_vanguard_mapping(data, {"Lab Alpha Long": "Lab Alpha"})

    internal, external = out[0]["authorships"]
    assert internal["raw_affiliation_strings"] == ["Lab Alpha", "Other"]
    assert internal["raw_affiliation_string"] == "Lab Alpha"
    # 外部作者不参与坍缩
    assert external["raw_affiliation_strings"] == ["External U"]


def test_apply_vanguard_mapping_keeps_unmapped_strings():
    data = [{"authorships": [
        {"is_internal_node": True, "raw_affiliation_strings": ["Unknown Lab"]}]}]
    out = analyzer.apply_vanguard_mapping(data, {})
    assert out[0]["authorships"][0]["raw_affiliation_strings"] == ["Unknown Lab"]


def test_apply_vanguard_mapping_without_authorships():
    data = [{"id": "W1"}]
    assert analyzer.apply_vanguard_mapping(data, {"a": "b"}) == [{"id": "W1"}]


def test_apply_vanguard_mapping_empty_input():
    assert analyzer.apply_vanguard_mapping([], {"a": "b"}) == []


# --------------------------- apply_concept_vanguard_mapping ---------------------------

def test_apply_concept_vanguard_mapping_collapses_and_keeps_original():
    data = [{"concepts": [
        {"display_name": "Alpha Topic Long", "level": 1},
        {"display_name": "Gamma Topic", "level": 1},
    ]}]
    out = analyzer.apply_concept_vanguard_mapping(data, {"Alpha Topic Long": "Alpha Topic"})

    collapsed, untouched = out[0]["concepts"]
    assert collapsed["display_name"] == "Alpha Topic"
    assert collapsed["original_name"] == "Alpha Topic Long"
    # 未在映射里的概念不动 (低置信概念留给 Step 4 剔除)
    assert untouched["display_name"] == "Gamma Topic"
    assert "original_name" not in untouched


def test_apply_concept_vanguard_mapping_is_idempotent():
    data = [{"concepts": [{"display_name": "Alpha Topic Long", "level": 1}]}]
    mapping = {"Alpha Topic Long": "Alpha Topic", "Alpha Topic": "Alpha Topic"}

    analyzer.apply_concept_vanguard_mapping(data, mapping)
    analyzer.apply_concept_vanguard_mapping(data, mapping)

    c = data[0]["concepts"][0]
    assert c["original_name"] == "Alpha Topic Long"   # 原始名不被排头兵覆盖
    assert c["display_name"] == "Alpha Topic"


def test_apply_concept_vanguard_mapping_without_concepts():
    assert analyzer.apply_concept_vanguard_mapping([{"id": "W1"}], {"a": "b"}) == [{"id": "W1"}]


def test_apply_concept_vanguard_mapping_empty_mapping():
    data = [{"concepts": [{"display_name": "Gamma Topic"}]}]
    out = analyzer.apply_concept_vanguard_mapping(data, {})
    assert out[0]["concepts"][0]["display_name"] == "Gamma Topic"
