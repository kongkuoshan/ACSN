"""core/crawler.py — OpenAlex 抓取、缓存与重试 (全程不联网)"""

import types

import pytest

from core import crawler

PARAMS = {"target_id": "I0000000", "start_year": 2020, "end_year": 2021}


class _Resp:
    def __init__(self, payload=None, status=200):
        self._payload = payload or {}
        self.status_code = status

    def json(self):
        return self._payload


class _Session:
    """按顺序吐出预设响应；用完后重复最后一个。"""

    def __init__(self, responses):
        self._responses = list(responses)
        self.requests_made = 0

    def mount(self, *args, **kwargs):
        pass

    def get(self, url, params=None, timeout=None):
        index = min(self.requests_made, len(self._responses) - 1)
        self.requests_made += 1
        return self._responses[index]


def _patch_session(monkeypatch, responses):
    """注入假 Session，并让 time.sleep 变成空操作。"""
    session = _Session(responses)
    monkeypatch.setattr(crawler, "requests",
                        types.SimpleNamespace(Session=lambda: session))
    monkeypatch.setattr(crawler, "time", types.SimpleNamespace(sleep=lambda s: None))
    return session


def _patch_save(monkeypatch):
    saved = {}
    monkeypatch.setattr(crawler, "save_json",
                        lambda data, path: saved.__setitem__(path, data))
    return saved


# --------------------------- 缓存路径 ---------------------------

def test_valid_cache_skips_network_entirely(tmp_path, monkeypatch):
    out = str(tmp_path / "U1.json")
    (tmp_path / "U1.json").write_text("x" * 2048, encoding="utf-8")
    (tmp_path / "U1.json.meta.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        crawler, "load_json",
        lambda path: PARAMS if path.endswith(".meta.json") else [{"id": "W1"}],
    )

    def _explode():
        raise AssertionError("命中缓存时不应创建网络会话")

    monkeypatch.setattr(crawler, "requests", types.SimpleNamespace(Session=_explode))

    got = crawler.run_openalex_crawler("I0000000", "e@x.com", 2020, out, end_year=2021)
    assert got == [{"id": "W1"}]


def test_cache_ignored_when_file_too_small(tmp_path, monkeypatch):
    out = str(tmp_path / "U1.json")
    (tmp_path / "U1.json").write_text("x" * 10, encoding="utf-8")  # < cache_min_bytes

    session = _patch_session(monkeypatch, [_Resp({"results": [{"id": "W9"}],
                                                  "meta": {"next_cursor": None}})])
    _patch_save(monkeypatch)

    got = crawler.run_openalex_crawler("I0000000", "e@x.com", 2020, out, end_year=2021)
    assert [w["id"] for w in got] == ["W9"]
    assert session.requests_made == 1


def test_cache_invalidated_when_parameters_change(tmp_path, monkeypatch):
    out = str(tmp_path / "U1.json")
    (tmp_path / "U1.json").write_text("x" * 2048, encoding="utf-8")
    (tmp_path / "U1.json.meta.json").write_text("{}", encoding="utf-8")
    # 缓存里的参数与本次请求不一致 (机构已变)
    monkeypatch.setattr(
        crawler, "load_json",
        lambda path: ({"target_id": "OTHER", "start_year": 1999, "end_year": 2000}
                      if path.endswith(".meta.json") else [{"id": "STALE"}]),
    )
    _patch_session(monkeypatch, [_Resp({"results": [{"id": "FRESH"}],
                                        "meta": {"next_cursor": None}})])
    _patch_save(monkeypatch)

    got = crawler.run_openalex_crawler("I0000000", "e@x.com", 2020, out, end_year=2021)
    assert [w["id"] for w in got] == ["FRESH"]


# --------------------------- 抓取与分页 ---------------------------

def test_paginates_following_cursor_and_writes_cache(tmp_path, monkeypatch):
    out = str(tmp_path / "U1.json")
    session = _patch_session(monkeypatch, [
        _Resp({"results": [{"id": "W1"}], "meta": {"next_cursor": "cursor-2"}}),
        _Resp({"results": [{"id": "W2"}], "meta": {"next_cursor": None}}),
    ])
    saved = _patch_save(monkeypatch)

    got = crawler.run_openalex_crawler("I0000000", "e@x.com", 2020, out, end_year=2021)

    assert [w["id"] for w in got] == ["W1", "W2"]
    assert session.requests_made == 2
    # 只有抓完整了才写缓存
    assert saved[out] == got
    assert saved[out + ".meta.json"] == PARAMS


def test_retries_rate_limited_page_then_succeeds(tmp_path, monkeypatch):
    out = str(tmp_path / "U1.json")
    session = _patch_session(monkeypatch, [
        _Resp(status=429),
        _Resp({"results": [{"id": "W1"}], "meta": {"next_cursor": None}}),
    ])
    saved = _patch_save(monkeypatch)

    got = crawler.run_openalex_crawler("I0000000", "e@x.com", 2020, out,
                                       end_year=2021, crawler_cfg={"retry_total": 3})

    assert [w["id"] for w in got] == ["W1"]
    assert session.requests_made == 2
    assert out in saved


def test_aborts_on_unexpected_status_without_caching(tmp_path, monkeypatch):
    out = str(tmp_path / "U1.json")
    session = _patch_session(monkeypatch, [_Resp(status=404)])
    saved = _patch_save(monkeypatch)

    got = crawler.run_openalex_crawler("I0000000", "e@x.com", 2020, out, end_year=2021)

    assert got == []
    assert session.requests_made == 1
    assert saved == {}


def test_aborts_after_exhausting_retries_without_caching(tmp_path, monkeypatch):
    out = str(tmp_path / "U1.json")
    session = _patch_session(monkeypatch, [_Resp(status=503)])
    saved = _patch_save(monkeypatch)

    got = crawler.run_openalex_crawler("I0000000", "e@x.com", 2020, out,
                                       end_year=2021, crawler_cfg={"retry_total": 3})

    assert got == []
    assert session.requests_made == 3
    assert saved == {}


def test_network_exception_is_retried(tmp_path, monkeypatch):
    out = str(tmp_path / "U1.json")
    calls = {"n": 0}

    class _Flaky:
        def mount(self, *args, **kwargs):
            pass

        def get(self, url, params=None, timeout=None):
            calls["n"] += 1
            if calls["n"] == 1:
                raise ConnectionError("boom")
            return _Resp({"results": [{"id": "W1"}], "meta": {"next_cursor": None}})

    monkeypatch.setattr(crawler, "requests", types.SimpleNamespace(Session=_Flaky))
    monkeypatch.setattr(crawler, "time", types.SimpleNamespace(sleep=lambda s: None))
    _patch_save(monkeypatch)

    got = crawler.run_openalex_crawler("I0000000", "e@x.com", 2020, out,
                                       end_year=2021, crawler_cfg={"retry_total": 3})
    assert [w["id"] for w in got] == ["W1"]


def test_defaults_end_year_to_current_year(tmp_path, monkeypatch):
    out = str(tmp_path / "U1.json")
    _patch_session(monkeypatch, [_Resp({"results": [{"id": "W1"}],
                                        "meta": {"next_cursor": None}})])
    saved = _patch_save(monkeypatch)

    crawler.run_openalex_crawler("I0000000", "e@x.com", 2020, out)

    from datetime import datetime
    assert saved[out + ".meta.json"]["end_year"] == datetime.now().year


def test_empty_result_is_not_cached(tmp_path, monkeypatch):
    # 抓完但一篇都没有 → 不写缓存，避免下次被当成有效缓存
    out = str(tmp_path / "U1.json")
    _patch_session(monkeypatch, [_Resp({"results": [], "meta": {"next_cursor": None}})])
    saved = _patch_save(monkeypatch)

    got = crawler.run_openalex_crawler("I0000000", "e@x.com", 2020, out, end_year=2021)

    assert got == []
    assert saved == {}
