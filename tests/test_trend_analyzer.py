"""core/trend_analyzer.py — 概念降维与演化/雷达/旭日图数据"""

import numpy as np
import pytest

from core import trend_analyzer


def _work(year=2021, concepts=None, internal_aff="Synthetic Brain Lab",
          scholar_id="A100", scholar_name="Alice Chen"):
    return {
        "publication_year": year,
        "concepts": concepts or [],
        "authorships": [
            {"author": {"id": f"https://openalex.org/{scholar_id}",
                        "display_name": scholar_name},
             "is_internal_node": True,
             "raw_affiliation_string": internal_aff},
            {"author": {"id": "https://openalex.org/A200", "display_name": "Bob Liu"},
             "is_internal_node": False,
             "raw_affiliation_string": "外部合作机构"},
        ],
    }


# --------------------------- reduce_concept_dimensions ---------------------------

def test_reduce_concepts_identity_when_below_cluster_target():
    u3 = [_work(concepts=[{"display_name": "Deep Learning", "level": 1, "score": 0.9}])]
    assert trend_analyzer.reduce_concept_dimensions(u3, target_clusters=25) == {
        "deep learning": "Deep Learning"
    }


def test_reduce_concepts_ignores_placeholder_names():
    u3 = [_work(concepts=[{"display_name": "Unknown"}, {"display_name": "未知"},
                          {"display_name": "N/A"}, {"display_name": "AI"}])]
    assert trend_analyzer.reduce_concept_dimensions(u3, target_clusters=25) == {"ai": "AI"}


def test_reduce_concepts_empty_dataset():
    assert trend_analyzer.reduce_concept_dimensions([], target_clusters=25) == {}


def test_reduce_concepts_clusters_when_above_target(monkeypatch):
    vectors = {
        "Alpha": [0.0, 0.0], "Alpha Long": [0.1, 0.0],
        "Beta": [10.0, 10.0], "Beta Long": [10.1, 10.0],
    }

    class _Model:
        def encode(self, texts, show_progress_bar=False):
            return np.array([vectors[t] for t in texts], dtype=float)

    monkeypatch.setattr(trend_analyzer, "load_sentence_transformer", lambda name: _Model())

    u3 = [_work(concepts=[{"display_name": name} for name in vectors])]
    out = trend_analyzer.reduce_concept_dimensions(u3, target_clusters=2)

    assert out == {"alpha": "Alpha", "alpha long": "Alpha",
                   "beta": "Beta", "beta long": "Beta"}


def test_reduce_concepts_falls_back_to_identity_on_model_failure(monkeypatch):
    class _Broken:
        def encode(self, texts, show_progress_bar=False):
            raise OSError("offline")

    monkeypatch.setattr(trend_analyzer, "load_sentence_transformer", lambda name: _Broken())

    u3 = [_work(concepts=[{"display_name": n} for n in ["A", "B", "C", "D"]])]
    out = trend_analyzer.reduce_concept_dimensions(u3, target_clusters=2)
    # 模型不可用时必须优雅降级为恒等映射，而不是抛异常
    assert out == {"a": "A", "b": "B", "c": "C", "d": "D"}


# --------------------------- generate_evolution_data ---------------------------

def test_evolution_data_matrix():
    u3 = [
        _work(2020, [{"display_name": "AI"}]),
        _work(2021, [{"display_name": "AI"}]),
        _work(2021, [{"display_name": "Robotics"}]),
    ]
    out = trend_analyzer.generate_evolution_data(u3, {"ai": "AI", "robotics": "Robotics"})

    assert out["years"] == [2020, 2021]
    assert out["categories"] == ["AI", "Robotics"]
    assert out["data"] == [
        ["2020", 1, "AI"],
        ["2021", 1, "AI"],
        ["2021", 1, "Robotics"],
    ]


def test_evolution_data_skips_works_without_year():
    out = trend_analyzer.generate_evolution_data(
        [{"publication_year": None, "concepts": [{"display_name": "AI"}]}], {}
    )
    assert out == {"years": [], "categories": [], "data": []}


def test_evolution_data_falls_back_to_raw_concept_name():
    out = trend_analyzer.generate_evolution_data(
        [_work(2020, [{"display_name": "Unmapped Topic"}])], {}
    )
    assert out["categories"] == ["Unmapped Topic"]


def test_evolution_data_counts_multi_work_years():
    u3 = [_work(2020, [{"display_name": "AI"}])] * 3
    out = trend_analyzer.generate_evolution_data(u3, {"ai": "AI"})
    assert out["data"] == [["2020", 3, "AI"]]


# --------------------------- generate_lab_radar_data ---------------------------

def test_lab_radar_normalizes_to_percentages():
    u3 = [_work(2020, [{"display_name": "AI"}], internal_aff="Synthetic Brain Lab")]
    out = trend_analyzer.generate_lab_radar_data(u3, {"ai": "AI"})

    assert out["labs"] == ["Synthetic Brain Lab"]
    assert out["indicators"] == ["AI"]
    assert out["series"] == [{"name": "Synthetic Brain Lab", "value": [100.0]}]


def test_lab_radar_excludes_external_authors_and_other_unit():
    work = _work(2020, [{"display_name": "AI"}])
    work["authorships"].append({
        "author": {"id": "https://openalex.org/A300", "display_name": "Ext"},
        "is_internal_node": True,
        "raw_affiliation_string": "外部合作机构",
    })
    out = trend_analyzer.generate_lab_radar_data([work], {"ai": "AI"})
    assert out["labs"] == ["Synthetic Brain Lab"]


def test_lab_radar_empty_dataset():
    out = trend_analyzer.generate_lab_radar_data([], {})
    assert out == {"labs": [], "indicators": [], "series": []}


# --------------------------- generate_topic_distribution ---------------------------

def test_topic_distribution_two_level_tree():
    u3 = [
        _work(concepts=[{"display_name": "人工智能", "original_name": "Deep Learning"}]),
        _work(concepts=[{"display_name": "人工智能", "original_name": "Deep Learning"}]),
        _work(concepts=[{"display_name": "人工智能", "original_name": "Machine Learning"}]),
    ]
    out = trend_analyzer.generate_topic_distribution(u3)

    assert out["name"] == "全部研究领域"
    assert len(out["children"]) == 1
    category = out["children"][0]
    assert category["name"] == "人工智能"
    assert category["value"] == 3
    # 子节点按出现次数降序
    assert category["children"] == [
        {"name": "Deep Learning", "value": 2},
        {"name": "Machine Learning", "value": 1},
    ]


def test_topic_distribution_falls_back_to_category_as_original():
    out = trend_analyzer.generate_topic_distribution(
        [_work(concepts=[{"display_name": "机器人学"}])]
    )
    assert out["children"][0]["children"] == [{"name": "机器人学", "value": 1}]


def test_topic_distribution_deduplicates_within_one_work():
    out = trend_analyzer.generate_topic_distribution(
        [_work(concepts=[{"display_name": "AI", "original_name": "ML"},
                         {"display_name": "AI", "original_name": "ML"}])]
    )
    assert out["children"][0]["value"] == 1


# --------------------------- generate_scholar_profile ---------------------------

def test_scholar_profile_collects_topics_lab_and_collaborators():
    u3 = [_work(2020, [{"display_name": "AI"},
                       {"display_name": "AI"},
                       {"display_name": "Robotics"}])]
    profile = trend_analyzer.generate_scholar_profile(u3, "A100")

    assert profile["name"] == "Scholar_A100"
    assert profile["topics"] == ["AI(2)", "Robotics(1)"]
    assert profile["lab"] == "Synthetic Brain Lab"
    assert profile["publication_years"] == [2020]
    assert profile["total_papers"] == 1
    assert set(profile["collaborators"]) == {"Alice Chen", "Bob Liu"}


def test_scholar_profile_unknown_id_returns_empty_profile():
    profile = trend_analyzer.generate_scholar_profile([_work()], "NOPE")
    assert profile["total_papers"] == 0
    assert profile["topics"] == []
    assert profile["lab"] == "未知"


def test_scholar_profile_respects_concept_dim_map():
    u3 = [_work(2020, [{"display_name": "Deep Learning"}])]
    profile = trend_analyzer.generate_scholar_profile(u3, "A100",
                                                     {"deep learning": "人工智能"})
    assert profile["topics"] == ["人工智能(1)"]
