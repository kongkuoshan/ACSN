"""core/visualizer.py — 图可视化纯函数。

FastAPI 路由依赖 Neo4j 驱动，不在单元测试范围内；这里只覆盖无需数据库的
名称截断逻辑 (它直接决定大屏上节点分类标签的显示)。
"""

import pytest

from core import visualizer


@pytest.mark.parametrize("placeholder", [None, "", "Unknown", "待分类", "N/A", "其他"])
def test_shorten_maps_placeholders_to_other_unit(placeholder):
    assert visualizer.shorten(placeholder) == "其他单元"


def test_shorten_keeps_short_names_intact():
    assert visualizer.shorten("Brain Lab") == "Brain Lab"


def test_shorten_keeps_names_within_tolerance():
    # 截断规则是 len > max_len + 2 才截断，超过上限 1~2 字符仍原样保留
    limit = visualizer._graph_cfg.get("shorten_max_len", 16)
    borderline = "B" * (limit + 2)
    assert visualizer.shorten(borderline) == borderline


def test_shorten_uses_first_comma_segment():
    assert visualizer.shorten("Brain Lab, Building 3, Beijing") == "Brain Lab"


def test_shorten_drops_dash_suffix():
    assert visualizer.shorten("Brain Lab - Unit B") == "Brain Lab"


def test_shorten_truncates_over_limit():
    out = visualizer.shorten("A" * 40)
    assert out.endswith("..")
    assert len(out) == visualizer._graph_cfg.get("shorten_max_len", 16) + 2


def test_shorten_respects_configured_limit(monkeypatch):
    monkeypatch.setitem(visualizer._graph_cfg, "shorten_max_len", 5)
    assert visualizer.shorten("abcdefghij") == "abcde.."
    assert visualizer.shorten("abcde") == "abcde"      # 恰好等于上限，不截断
