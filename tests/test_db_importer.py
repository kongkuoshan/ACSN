"""core/db_importer.py — U3 → Neo4j CSV 导出 (不连数据库)"""

import os
from collections import Counter

import pandas as pd
import pytest

from core.db_importer import _get_clean_id, _rank_counts, _safe_text, extract_graph_to_csv

CSV_FILES = ["s.csv", "p.csv", "l.csv", "t.csv", "r_w.csv", "r_b.csv", "r_m.csv", "r_c.csv"]


def _u3_work(wid="W1", concepts=("Machine Learning",), authors=None):
    if authors is None:
        authors = [
            {"author": {"id": "https://openalex.org/A100", "display_name": "Alice Chen"},
             "is_internal_node": True,
             "raw_affiliation_strings": ["Synthetic Brain Lab"]},
        ]
    return {
        "id": f"https://openalex.org/{wid}",
        "title": f"Synthetic work {wid}",
        "doi": f"https://doi.org/10.0000/{wid}",
        "primary_location": {"source": {"display_name": "Synthetic Journal"}},
        "concepts": [{"display_name": c} for c in concepts],
        "authorships": authors,
    }


def _read_csv_or_empty(path):
    """空 CSV (仅换行) 会触发 EmptyDataError，这里统一按空表处理。"""
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _mentor_df(rows):
    return pd.DataFrame([
        {"原始名单姓名": name, "OpenAlex_ID": aid, "ID归属状态": status}
        for name, aid, status in rows
    ])


# --------------------------- _get_clean_id ---------------------------

def test_get_clean_id_strips_url_prefix():
    assert _get_clean_id("https://openalex.org/W123") == "W123"


@pytest.mark.parametrize("bad", [None, "", "nan", "   "])
def test_get_clean_id_returns_none_for_empty(bad):
    assert _get_clean_id(bad) is None


def test_get_clean_id_strips_control_characters():
    assert _get_clean_id("https://openalex.org/W1\x002") == "W12"


# --------------------------- _safe_text ---------------------------

def test_safe_text_replaces_quotes_and_backslashes():
    assert _safe_text('a"b\\c') == "a'bc"


@pytest.mark.parametrize("bad", [None, "", "nan"])
def test_safe_text_returns_unknown_for_empty(bad):
    assert _safe_text(bad) == "未知"


def test_safe_text_trims_whitespace():
    assert _safe_text("  Lab X  ") == "Lab X"


# --------------------------- extract_graph_to_csv ---------------------------

def test_extract_graph_writes_all_csv_files(tmp_path):
    extract_graph_to_csv([_u3_work()], pd.DataFrame(), str(tmp_path))
    for name in CSV_FILES:
        assert (tmp_path / name).exists(), f"缺少 {name}"


def test_extract_graph_node_and_edge_counts(tmp_path):
    authors = [
        {"author": {"id": "https://openalex.org/A100", "display_name": "Alice Chen"},
         "is_internal_node": True, "raw_affiliation_strings": ["Synthetic Brain Lab"]},
        {"author": {"id": "https://openalex.org/A200", "display_name": "Bob Liu"},
         "is_internal_node": True, "raw_affiliation_strings": ["Synthetic Brain Lab"]},
        {"author": {"id": "https://openalex.org/A999", "display_name": "Outsider"},
         "is_internal_node": False, "raw_affiliation_strings": ["外部合作机构"]},
    ]
    works = [_u3_work("W1", ("Machine Learning", "Robotics"), authors)]

    extract_graph_to_csv(works, pd.DataFrame(), str(tmp_path))

    scholars = pd.read_csv(tmp_path / "s.csv")
    papers = pd.read_csv(tmp_path / "p.csv")
    topics = pd.read_csv(tmp_path / "t.csv")
    wrote = pd.read_csv(tmp_path / "r_w.csv")
    co_work = pd.read_csv(tmp_path / "r_c.csv")

    # 外部作者不入图
    assert sorted(scholars["id"]) == ["A100", "A200"]
    assert list(papers["id"]) == ["W1"]
    assert sorted(topics["name"]) == ["Machine Learning", "Robotics"]
    assert sorted(wrote["aid"]) == ["A100", "A200"]
    # 两位内部作者共同署名 → 一条合作边，权重为 1
    assert len(co_work) == 1
    assert co_work.iloc[0]["w"] == 1
    assert {co_work.iloc[0]["u"], co_work.iloc[0]["v"]} == {"A100", "A200"}


def test_extract_graph_accumulates_collaboration_weight(tmp_path):
    authors = [
        {"author": {"id": "https://openalex.org/A100", "display_name": "Alice Chen"},
         "is_internal_node": True, "raw_affiliation_strings": ["L"]},
        {"author": {"id": "https://openalex.org/A200", "display_name": "Bob Liu"},
         "is_internal_node": True, "raw_affiliation_strings": ["L"]},
    ]
    works = [_u3_work("W1", authors=authors), _u3_work("W2", authors=authors)]

    extract_graph_to_csv(works, pd.DataFrame(), str(tmp_path))

    co_work = pd.read_csv(tmp_path / "r_c.csv")
    assert len(co_work) == 1
    assert co_work.iloc[0]["w"] == 2


def test_extract_graph_marks_mentors_and_merges_historical_ids(tmp_path):
    # Alice Chen 有两个 OpenAlex ID，A101 是历史分身 → 应归并到主号 A100
    pi = _mentor_df([("Alice Chen", "A100", " 主号"),
                     ("Alice Chen", "A101", " 历史分身 1")])
    authors = [
        {"author": {"id": "https://openalex.org/A101", "display_name": "Alice Chen"},
         "is_internal_node": True, "raw_affiliation_strings": ["Synthetic Brain Lab"]},
    ]
    extract_graph_to_csv([_u3_work(authors=authors)], pi, str(tmp_path))

    scholars = pd.read_csv(tmp_path / "s.csv")
    assert list(scholars["id"]) == ["A100"]     # 分身被归一
    assert list(scholars["name"]) == ["Alice Chen"]
    assert list(scholars["role"]) == ["导师"]


def test_extract_graph_creates_one_belongs_to_edge_per_affiliation(tmp_path):
    authors = [{
        "author": {"id": "https://openalex.org/A100", "display_name": "Alice Chen"},
        "is_internal_node": True,
        "raw_affiliation_strings": ["Lab One", "Lab Two"],
    }]
    extract_graph_to_csv([_u3_work(authors=authors)], pd.DataFrame(), str(tmp_path))

    belongs = pd.read_csv(tmp_path / "r_b.csv")
    assert sorted(belongs["lab"]) == ["Lab One", "Lab Two"]
    labs = pd.read_csv(tmp_path / "l.csv")
    assert sorted(labs["name"]) == ["Lab One", "Lab Two"]


def test_extract_graph_falls_back_to_single_affiliation_string(tmp_path):
    authors = [{
        "author": {"id": "https://openalex.org/A100", "display_name": "Alice Chen"},
        "is_internal_node": True,
        "raw_affiliation_string": "Fallback Lab",
    }]
    extract_graph_to_csv([_u3_work(authors=authors)], pd.DataFrame(), str(tmp_path))

    labs = pd.read_csv(tmp_path / "l.csv")
    assert list(labs["name"]) == ["Fallback Lab"]


def test_extract_graph_uses_other_unit_when_no_affiliation(tmp_path):
    authors = [{"author": {"id": "https://openalex.org/A100", "display_name": "Alice Chen"},
                "is_internal_node": True}]
    extract_graph_to_csv([_u3_work(authors=authors)], pd.DataFrame(), str(tmp_path))

    labs = pd.read_csv(tmp_path / "l.csv")
    assert list(labs["name"]) == ["其他单元"]


def test_extract_graph_skips_work_without_id(tmp_path):
    extract_graph_to_csv([{"title": "no id"}], pd.DataFrame(), str(tmp_path))
    # 无有效文献时 CSV 里只有表头/换行，pandas 会抛 EmptyDataError，故容错读取
    assert _read_csv_or_empty(tmp_path / "p.csv").empty


def test_extract_graph_makes_csv_files_world_readable(tmp_path):
    extract_graph_to_csv([_u3_work()], pd.DataFrame(), str(tmp_path))
    mode = os.stat(tmp_path / "s.csv").st_mode & 0o777
    assert mode == 0o644      # Neo4j 容器需要能读到这些文件


# --------------------- _rank_counts (主归属排序稳定性) ---------------------

def test_rank_counts_sorts_by_count_desc_then_name_asc():
    assert _rank_counts(Counter()) == []
    assert _rank_counts(Counter({"B": 1, "A": 1, "C": 3})) == [("C", 3), ("A", 1), ("B", 1)]


# --------------------- 主归属 / 主主题物化 ---------------------

def _author(aid, affs=(), name="Alice Chen"):
    return {"author": {"id": f"https://openalex.org/{aid}", "display_name": name},
            "is_internal_node": True, "raw_affiliation_strings": list(affs)}


def test_extract_graph_materializes_primary_lab_by_frequency(tmp_path):
    works = [
        _u3_work("W1", authors=[_author("A100", ["Lab A"])]),
        _u3_work("W2", authors=[_author("A100", ["Lab B"])]),
        _u3_work("W3", authors=[_author("A100", ["Lab B"])]),
    ]
    extract_graph_to_csv(works, pd.DataFrame(), str(tmp_path))

    scholar = pd.read_csv(tmp_path / "s.csv").iloc[0]
    assert scholar["primary_lab"] == "Lab B"          # 出现次数多者胜
    assert scholar["labs"] == "Lab B|Lab A"           # 全部归属按 (次数降序, 名称升序)
    assert set(pd.read_csv(tmp_path / "s.csv").columns) >= {"labs", "primary_lab", "topics", "primary_topic"}


def test_extract_graph_primary_lab_breaks_tie_by_name(tmp_path):
    works = [
        _u3_work("W1", authors=[_author("A100", ["Lab B"])]),
        _u3_work("W2", authors=[_author("A100", ["Lab A"])]),
    ]
    extract_graph_to_csv(works, pd.DataFrame(), str(tmp_path))
    assert pd.read_csv(tmp_path / "s.csv").iloc[0]["primary_lab"] == "Lab A"


def test_extract_graph_bucket_labels_do_not_win_primary_lab(tmp_path):
    """外部合作机构出现更多次, 也不能压过真实机构。"""
    works = [
        _u3_work("W1", authors=[_author("A100", ["外部合作机构"])]),
        _u3_work("W2", authors=[_author("A100", ["外部合作机构"])]),
        _u3_work("W3", authors=[_author("A100", ["Real Lab"])]),
    ]
    extract_graph_to_csv(works, pd.DataFrame(), str(tmp_path))

    scholar = pd.read_csv(tmp_path / "s.csv").iloc[0]
    assert scholar["primary_lab"] == "Real Lab"
    assert scholar["labs"] == "外部合作机构|Real Lab"   # 桶仍保留在全部归属里


def test_extract_graph_primary_lab_falls_back_to_bucket(tmp_path):
    works = [_u3_work("W1", authors=[_author("A100", ["外部合作机构"])])]
    extract_graph_to_csv(works, pd.DataFrame(), str(tmp_path))
    assert pd.read_csv(tmp_path / "s.csv").iloc[0]["primary_lab"] == "外部合作机构"


def test_extract_graph_primary_lab_defaults_to_other_unit(tmp_path):
    works = [_u3_work("W1", authors=[_author("A100")])]   # 无任何机构字符串
    extract_graph_to_csv(works, pd.DataFrame(), str(tmp_path))
    assert pd.read_csv(tmp_path / "s.csv").iloc[0]["primary_lab"] == "其他单元"


def test_extract_graph_materializes_primary_topic(tmp_path):
    works = [
        _u3_work("W1", concepts=["AI"], authors=[_author("A100", ["Lab A"])]),
        _u3_work("W2", concepts=["AI"], authors=[_author("A100", ["Lab A"])]),
        _u3_work("W3", concepts=["Bio"], authors=[_author("A100", ["Lab A"])]),
    ]
    extract_graph_to_csv(works, pd.DataFrame(), str(tmp_path))

    scholar = pd.read_csv(tmp_path / "s.csv").iloc[0]
    assert scholar["primary_topic"] == "AI"
    assert scholar["topics"] == "AI|Bio"


def test_extract_graph_aliases_historical_ids_share_materialized_primary(tmp_path):
    """分身与主号是同一人: 机构计数必须合并, 不能各算一份。"""
    rows = [("Alice Chen", "https://openalex.org/A100", "主号"),
            ("Alice Chen", "https://openalex.org/A900", "历史分身")]
    works = [
        _u3_work("W1", authors=[_author("A100", ["Lab A"])]),
        _u3_work("W2", authors=[_author("A900", ["Lab A"])]),
        _u3_work("W3", authors=[_author("A900", ["Lab B"])]),
    ]
    extract_graph_to_csv(works, _mentor_df(rows), str(tmp_path))

    scholars = pd.read_csv(tmp_path / "s.csv")
    assert len(scholars) == 1
    assert scholars.iloc[0]["id"] == "A100"           # 归并到主号
    assert scholars.iloc[0]["labs"] == "Lab A|Lab B"  # 两个 ID 的机构计数已合并
