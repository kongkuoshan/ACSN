"""core/llm_labeler.py — LLM 预填与去重 (不发起真实请求)"""

import types

import pandas as pd
import pytest

from core import llm_labeler

VANGUARD_COL = "🤖 AI 提取的【排头兵】"
STANDARD_COL = "🧑‍🔧 填写标准名称 (抄左边/填中文/不认识留空)"
CON_ORIG_COL = "原始领域名称"
CON_TARGET_COL = "填写标准大类 (如：人工智能)"


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def _patch_post(monkeypatch, content=None, exc=None):
    def _post(url, json=None, timeout=None):
        if exc:
            raise exc
        return _Resp({"choices": [{"message": {"content": content}}]})

    monkeypatch.setattr(llm_labeler, "requests",
                        types.SimpleNamespace(post=_post))


def _aff_df(pairs):
    return pd.DataFrame([{VANGUARD_COL: v, STANDARD_COL: s} for v, s in pairs])


# --------------------------- ask_llm ---------------------------

def test_ask_llm_returns_stripped_content(monkeypatch):
    _patch_post(monkeypatch, content="  计算机科学  ")
    assert llm_labeler.ask_llm("http://x", "sys", "user") == "计算机科学"


def test_ask_llm_returns_empty_on_request_failure(monkeypatch):
    _patch_post(monkeypatch, exc=ConnectionError("down"))
    assert llm_labeler.ask_llm("http://x", "sys", "user") == ""


def test_ask_llm_returns_empty_on_malformed_response(monkeypatch):
    monkeypatch.setattr(
        llm_labeler, "requests",
        types.SimpleNamespace(post=lambda url, json=None, timeout=None: _Resp({"oops": 1})),
    )
    assert llm_labeler.ask_llm("http://x", "sys", "user") == ""


# --------------------------- auto_label_concepts ---------------------------

def test_auto_label_concepts_fills_target_column(monkeypatch):
    monkeypatch.setattr(llm_labeler, "ask_llm", lambda *a, **k: "计算机科学")
    df = pd.DataFrame({CON_ORIG_COL: ["Deep Learning", "Robotics"], CON_TARGET_COL: ["", ""]})

    out = llm_labeler.auto_label_concepts(df, "http://x", "计算机科学, 机器人学")

    assert out[CON_TARGET_COL].tolist() == ["计算机科学", "计算机科学"]


def test_auto_label_concepts_passes_through_empty_frame():
    empty = pd.DataFrame()
    assert llm_labeler.auto_label_concepts(empty, "http://x", "fields").empty


# --------------------------- auto_label_affiliations_batch ---------------------------

def test_batch_affiliation_mapping_parses_json(monkeypatch):
    monkeypatch.setattr(
        llm_labeler, "ask_llm",
        lambda *a, **k: '{"1": "Synthetic Brain Lab", "2": "Synthetic Vision Lab"}',
    )
    df = _aff_df([("SBL", ""), ("SVL", "")])

    out = llm_labeler.auto_label_affiliations_batch(df, "http://x")

    assert out[STANDARD_COL].tolist() == ["Synthetic Brain Lab", "Synthetic Vision Lab"]


def test_batch_affiliation_mapping_unwraps_code_fence(monkeypatch):
    monkeypatch.setattr(
        llm_labeler, "ask_llm",
        lambda *a, **k: '```json\n{"1": "Synthetic Brain Lab"}\n```',
    )
    out = llm_labeler.auto_label_affiliations_batch(_aff_df([("SBL", "")]), "http://x")
    assert out[STANDARD_COL].tolist() == ["Synthetic Brain Lab"]


def test_batch_affiliation_mapping_falls_back_to_original_on_bad_json(monkeypatch):
    monkeypatch.setattr(llm_labeler, "ask_llm", lambda *a, **k: "对不起我不会")
    out = llm_labeler.auto_label_affiliations_batch(_aff_df([("SBL", "")]), "http://x")
    # 解析失败必须保留原名，不能丢数据
    assert out[STANDARD_COL].tolist() == ["SBL"]


def test_batch_affiliation_mapping_ignores_out_of_range_indices(monkeypatch):
    monkeypatch.setattr(llm_labeler, "ask_llm", lambda *a, **k: '{"99": "Ghost"}')
    out = llm_labeler.auto_label_affiliations_batch(_aff_df([("SBL", "")]), "http://x")
    assert out[STANDARD_COL].tolist() == ["SBL"]


def test_batch_affiliation_mapping_without_vanguard_column():
    df = pd.DataFrame({"other": ["x"]})
    out = llm_labeler.auto_label_affiliations_batch(df, "http://x")
    assert out is df


def test_batch_affiliation_mapping_empty_frame():
    empty = pd.DataFrame()
    assert llm_labeler.auto_label_affiliations_batch(empty, "http://x").empty


def test_batch_affiliation_mapping_splits_into_batches(monkeypatch):
    calls = []

    def _ask(api_url, sys_prompt, user_prompt, **kwargs):
        calls.append(user_prompt)
        start = len(calls) * 10 - 9
        return '{"%d": "B%d"}' % (start, start)

    monkeypatch.setattr(llm_labeler, "ask_llm", _ask)
    df = _aff_df([(f"v{i}", "") for i in range(5)])

    llm_labeler.auto_label_affiliations_batch(df, "http://x", llm_cfg={"batch_size": 2})

    assert len(calls) == 3        # 5 个排头兵按每批 2 个切分


# --------------------------- deduplicate_standard_names ---------------------------

def test_deduplicate_merges_exact_duplicate_standard_names():
    df = _aff_df([("Lab A", "Brain Lab"), ("Lab B", "Brain Lab")])
    out = llm_labeler.deduplicate_standard_names(df)
    # 同一标准名下的多个排头兵统一到最短的那个
    assert out[STANDARD_COL].tolist() == ["Lab A", "Lab A"]


def test_deduplicate_fuzzy_merges_similar_names():
    df = _aff_df([("L1", "Brain Lab"), ("L2", "Brain Labs")])
    out = llm_labeler.deduplicate_standard_names(df)
    assert out[STANDARD_COL].tolist() == ["Brain Lab", "Brain Lab"]


def test_deduplicate_keeps_distinct_names_separate():
    df = _aff_df([("L1", "Brain Lab"), ("L2", "Vision Lab")])
    out = llm_labeler.deduplicate_standard_names(df)
    assert out[STANDARD_COL].tolist() == ["Brain Lab", "Vision Lab"]


def test_deduplicate_ignores_unfilled_rows():
    df = _aff_df([("L1", ""), ("L2", "")])
    out = llm_labeler.deduplicate_standard_names(df)
    assert out[STANDARD_COL].tolist() == ["", ""]


def test_deduplicate_requires_expected_columns():
    df = pd.DataFrame({"a": [1]})
    assert llm_labeler.deduplicate_standard_names(df) is df


def test_deduplicate_respects_similarity_threshold():
    df = _aff_df([("L1", "Brain Lab"), ("L2", "Brain Labs")])
    # 阈值调到 1.0 → 除完全相同外都不合并
    out = llm_labeler.deduplicate_standard_names(df, llm_cfg={"similarity_threshold": 1.0})
    assert out[STANDARD_COL].tolist() == ["Brain Lab", "Brain Labs"]
