"""core/author_matcher.py — 本地学者画像库与名单匹配"""

import pandas as pd

from core.author_matcher import (
    _normalize_name,
    build_local_database,
    match_names_locally,
)

TARGET = "I0000000"


def _member(name, aid, aff="Synth Lab Alpha", internal=True):
    """构造一条 authorship，internal=False 时挂靠别的机构。"""
    inst = TARGET if internal else "I9999999"
    return {
        "author": {"id": f"https://openalex.org/{aid}", "display_name": name},
        "institutions": [{"id": f"https://openalex.org/{inst}",
                          "lineage": [f"https://openalex.org/{inst}"]}],
        "raw_affiliation_strings": [aff],
    }


def _work(wid, authors, concepts=None):
    return {
        "id": f"https://openalex.org/{wid}",
        "concepts": concepts or [{"display_name": "Machine Learning", "score": 0.9}],
        "authorships": authors,
    }


# --------------------------- _normalize_name ---------------------------

def test_normalize_name_strips_case_dots_dashes_spaces():
    assert _normalize_name("San  Zhang") == "sanzhang"
    assert _normalize_name("Zhang-San.") == "zhangsan"
    assert _normalize_name("SAN ZHANG") == "sanzhang"


def test_normalize_name_handles_non_string():
    assert _normalize_name(None) == "none"
    assert _normalize_name(123) == "123"


# --------------------------- build_local_database ---------------------------

def test_build_local_database_indexes_internal_authors():
    works = [
        _work("W1", [_member("San Zhang", "A1")]),
        _work("W2", [_member("San Zhang", "A1")]),
        _work("W3", [_member("Outsider", "A9", internal=False)]),
    ]
    db = build_local_database(works, parent_id=TARGET)

    assert "sanzhang" in db
    entry = db["sanzhang"]["A1"]
    assert entry["name"] == "San Zhang"
    assert entry["count"] == 2
    assert "Outsider" not in {v["name"] for g in db.values() for v in g.values()}


def test_build_local_database_separates_duplicate_names_by_openalex_id():
    # 同名不同 OpenAlex ID → 同一指纹下的两个分身
    works = [_work("W1", [_member("San Zhang", "A1"), _member("San Zhang", "A2")])]
    db = build_local_database(works, parent_id=TARGET)

    assert set(db["sanzhang"].keys()) == {"A1", "A2"}


def test_build_local_database_fallback_keywords_match_external():
    works = [_work("W1", [_member("Li Si", "A3", aff="SYNTHLAB unit", internal=False)])]
    db = build_local_database(works, parent_id=TARGET, fallback_keywords=["synthlab"])
    assert "lisi" in db


def test_build_local_database_filters_short_affiliations():
    works = [_work("W1", [_member("Li Si", "A3", aff="短")])]
    db = build_local_database(works, parent_id=TARGET, nlp_cfg={"min_aff_len": 5})
    assert db["lisi"]["A3"]["raw_affiliations"] == []


def test_build_local_database_tracks_collaborators():
    works = [_work("W1", [_member("San Zhang", "A1"), _member("Li Si", "A2")])]
    db = build_local_database(works, parent_id=TARGET)
    assert "https://openalex.org/A2" in db["sanzhang"]["A1"]["collaborators"]


def test_build_local_database_handles_empty_input():
    assert build_local_database([], parent_id=TARGET) == {}


# --------------------------- match_names_locally ---------------------------

def test_match_names_locally_finds_mentor_and_ranks_primary_id():
    works = [
        _work("W1", [_member("San Zhang", "A1")]),
        _work("W2", [_member("San Zhang", "A1")]),
        _work("W3", [_member("San Zhang", "A2")]),
    ]
    db = build_local_database(works, parent_id=TARGET)
    df = match_names_locally(pd.DataFrame({"导师姓名": ["San Zhang"]}),
                             "导师姓名", db)

    assert len(df) == 2
    # 发文量高的 A1 排在最前并标记为主号
    top = df.iloc[0]
    assert top["OpenAlex_ID"] == "A1"
    assert "主号" in top["ID归属状态"]
    assert top["发文量"] == 2
    assert top["匹配状态"] == " 内部匹配成功"


def test_match_names_locally_reports_missing_person():
    db = build_local_database([_work("W1", [_member("San Zhang", "A1")])],
                              parent_id=TARGET)
    df = match_names_locally(pd.DataFrame({"导师姓名": ["Nobody Here"]}),
                             "导师姓名", db)

    row = df.iloc[0]
    assert row["OpenAlex_ID"] is None
    assert row["匹配状态"] == " 查无此人"
    assert row["发文量"] == 0


def test_match_names_locally_matches_reversed_name_order():
    db = build_local_database([_work("W1", [_member("San Zhang", "A1")])],
                              parent_id=TARGET)
    # "Zhang San" 与库里的 "San Zhang" 应能通过反序指纹匹配上
    df = match_names_locally(pd.DataFrame({"导师姓名": ["Zhang San"]}),
                             "导师姓名", db)
    assert df.iloc[0]["OpenAlex_ID"] == "A1"


def test_match_names_locally_empty_input_returns_empty():
    db = build_local_database([_work("W1", [_member("San Zhang", "A1")])],
                              parent_id=TARGET)
    assert match_names_locally(pd.DataFrame(), "导师姓名", db).empty


def test_match_names_locally_missing_column_returns_empty():
    db = build_local_database([_work("W1", [_member("San Zhang", "A1")])],
                              parent_id=TARGET)
    df = match_names_locally(pd.DataFrame({"错误列名": ["San Zhang"]}),
                             "导师姓名", db)
    assert df.empty
