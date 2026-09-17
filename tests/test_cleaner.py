"""core/cleaner.py — 内部节点打标 + 脏数据物理清洗"""

from core.cleaner import (
    DEFAULT_STOP_WORDS,
    _clean_noise,
    extract_and_clean_entities,
    tag_internal_nodes,
)

# tag_internal_nodes 比对的是完整 OpenAlex URL (与 config.yaml 中 institution.target_id 一致)
TARGET = "https://openalex.org/I0000000"


def _auth(internal_inst_id=None, raw=("Some Lab, Beijing, China",)):
    """internal_inst_id=None 表示不挂靠任何机构。"""
    institutions = []
    if internal_inst_id:
        institutions = [{"id": internal_inst_id, "lineage": [internal_inst_id]}]
    return {"institutions": institutions, "raw_affiliation_strings": list(raw)}


# --------------------------- _clean_noise ---------------------------

def test_clean_noise_removes_email():
    assert "a@b.com" not in _clean_noise("Lab X a@b.com Beijing China")


def test_clean_noise_removes_postal_code():
    assert "100190" not in _clean_noise("Institute of Automation 100190 China")


def test_clean_noise_removes_stop_words_case_insensitively():
    out = _clean_noise("Lab X, beijing, CHINA")
    assert "beijing" not in out.lower()
    assert "china" not in out.lower()
    assert out == "Lab X"


def test_clean_noise_collapses_punctuation_and_whitespace():
    assert _clean_noise("A,,,B;;;C   D") == "A B C D"


def test_clean_noise_full_pipeline():
    raw = "Key Lab of AI, Beijing 100190, China   zhang@ia.ac.cn"
    assert _clean_noise(raw) == "Key Lab of AI"


def test_clean_noise_accepts_custom_stop_words():
    out = _clean_noise("Alpha Lab Beta", stop_words=["Beta"])
    assert out == "Alpha Lab"


def test_clean_noise_handles_empty_and_non_string():
    for bad in ("", None, 123, [], {}):
        assert _clean_noise(bad) == ""


def test_default_stop_words_are_non_empty():
    assert "China" in DEFAULT_STOP_WORDS


# --------------------------- tag_internal_nodes ---------------------------

def test_tag_internal_nodes_matches_institution_id():
    works = [{"authorships": [_auth(TARGET)]}]
    _, internal, external = tag_internal_nodes(works, TARGET, [])
    assert works[0]["authorships"][0]["is_internal_node"] is True
    assert (internal, external) == (1, 0)


def test_tag_internal_nodes_matches_lineage():
    # lineage 上级机构树里出现目标机构，也算内部人员
    auth = {"institutions": [{"id": "https://openalex.org/I5",
                              "lineage": ["https://openalex.org/I5", TARGET]}],
            "raw_affiliation_strings": []}
    works = [{"authorships": [auth]}]
    _, internal, _ = tag_internal_nodes(works, TARGET, [])
    assert internal == 1
    assert auth["is_internal_node"] is True


def test_tag_internal_nodes_regex_fallback():
    works = [{"authorships": [_auth(None, raw=("SYNTHLAB, Somewhere",))]}]
    _, internal, _ = tag_internal_nodes(works, TARGET, ["synthlab"])
    assert internal == 1
    assert works[0]["authorships"][0]["is_internal_node"] is True


def test_tag_internal_nodes_external_when_no_match():
    works = [{"authorships": [_auth(None, raw=("Other University, USA",))]}]
    _, internal, external = tag_internal_nodes(works, TARGET, ["synthlab"])
    assert (internal, external) == (0, 1)
    assert works[0]["authorships"][0]["is_internal_node"] is False


def test_tag_internal_nodes_falls_back_to_single_raw_string():
    # 只有单个 raw_affiliation_string (无复数列表) 时也要能兜底
    auth = _auth(None, raw=())
    auth["raw_affiliation_string"] = "SYNTHLAB unit"
    works = [{"authorships": [auth]}]
    _, internal, _ = tag_internal_nodes(works, TARGET, ["synthlab"])
    assert internal == 1


def test_tag_internal_nodes_counts_across_works():
    works = [
        {"authorships": [_auth(TARGET), _auth(None, raw=("Other U",))]},
        {"authorships": [_auth(TARGET)]},
    ]
    _, internal, external = tag_internal_nodes(works, TARGET, [])
    assert (internal, external) == (2, 1)


def test_tag_internal_nodes_skips_empty_works():
    works = [{}, None, {"authorships": []}]
    _, internal, external = tag_internal_nodes(works, TARGET, [])
    assert (internal, external) == (0, 0)


# --------------------------- extract_and_clean_entities ---------------------------

def test_extract_collapses_external_authors():
    work = {"authorships": [
        {"is_internal_node": False, "raw_affiliation_strings": ["Noisy, Beijing, China"]},
    ]}
    out, _ = extract_and_clean_entities([work])
    assert out[0]["authorships"][0]["raw_affiliation_strings"] == ["外部合作机构"]


def test_extract_cleans_internal_affiliations():
    work = {"authorships": [
        {"is_internal_node": True,
         "raw_affiliation_strings": ["Synth Lab Alpha, Beijing 100190, China", "  "]},
    ]}
    out, unique = extract_and_clean_entities([work])
    assert out[0]["authorships"][0]["raw_affiliation_strings"] == ["Synth Lab Alpha"]
    assert unique["raw_affiliations"] == ["Synth Lab Alpha"]


def test_extract_filters_concepts_by_level_and_score():
    work = {
        "concepts": [
            {"display_name": "Keep", "level": 1, "score": 0.9},
            {"display_name": "TooDeep", "level": 3, "score": 0.9},
            {"display_name": "TooLow", "level": 1, "score": 0.2},
            {"display_name": "BoundaryScore", "level": 2, "score": 0.4},
        ],
        "authorships": [],
    }
    _, unique = extract_and_clean_entities([work])
    # level<=2 且 score>0.4 (严格大于，0.4 被排除)
    assert unique["concepts"] == ["Keep"]


def test_extract_respects_custom_thresholds():
    work = {
        "concepts": [{"display_name": "Deep", "level": 5, "score": 0.9}],
        "authorships": [],
    }
    _, unique = extract_and_clean_entities(
        [work], nlp_cfg={"level_threshold": 5, "score_threshold": 0.1}
    )
    assert unique["concepts"] == ["Deep"]


def test_extract_respects_custom_labels():
    work = {"authorships": [
        {"is_internal_node": False, "raw_affiliation_strings": ["x"]}]}
    out, _ = extract_and_clean_entities([work], labels_cfg={"external": "EXTERNAL"})
    assert out[0]["authorships"][0]["raw_affiliation_strings"] == ["EXTERNAL"]


def test_extract_unique_output_is_sorted_and_deduplicated():
    def w(a, b):
        return {"concepts": [], "authorships": [
            {"is_internal_node": True, "raw_affiliation_strings": [a, b]}]}

    _, unique = extract_and_clean_entities([w("Zeta Lab", "Alpha Lab"),
                                            w("Alpha Lab", "Zeta Lab")])
    assert unique["raw_affiliations"] == ["Alpha Lab", "Zeta Lab"]


def test_extract_handles_empty_input():
    out, unique = extract_and_clean_entities([])
    assert out == []
    assert unique == {"raw_affiliations": [], "concepts": []}
