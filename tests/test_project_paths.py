"""utils/project_paths.py — 路径解析单一真相来源"""

import os

from utils import project_paths


def test_project_root_points_at_repo():
    # 项目根应包含 config/config.example.yaml
    assert os.path.isfile(
        os.path.join(project_paths.PROJECT_ROOT, "config", "config.example.yaml")
    )


def test_get_data_path_joins_relative():
    out = project_paths.get_data_path("./data/01_raw/U1.json")
    assert os.path.isabs(out)
    assert out == os.path.join(project_paths.PROJECT_ROOT, "data", "01_raw", "U1.json")


def test_get_data_path_strips_dot_slash_prefix():
    assert project_paths.get_data_path("./x.json") == os.path.join(
        project_paths.PROJECT_ROOT, "x.json"
    )


def test_get_data_path_passes_through_absolute(tmp_path):
    absolute = str(tmp_path / "U1.json")
    assert project_paths.get_data_path(absolute) == absolute


def test_resolve_all_paths_only_touches_strings():
    config = {"paths": {"a": "./data/a.json", "n": 3, "b": "/abs/b.json"}}
    resolved = project_paths.resolve_all_paths(config)

    assert resolved is config  # 原地修改
    assert resolved["paths"]["a"] == os.path.join(
        project_paths.PROJECT_ROOT, "data", "a.json"
    )
    assert resolved["paths"]["b"] == "/abs/b.json"
    assert resolved["paths"]["n"] == 3  # 非字符串不动


def test_resolve_all_paths_without_paths_section():
    config = {"institution": {"target_id": "I1"}}
    assert project_paths.resolve_all_paths(config) == config


def test_ensure_in_sys_path_is_idempotent():
    import sys

    before = list(sys.path)
    count_before = sys.path.count(project_paths.PROJECT_ROOT)
    project_paths.ensure_in_sys_path()
    project_paths.ensure_in_sys_path()
    # 重复调用不得重复插入 (pytest 本身可能已把项目根放进 sys.path，故比较增量)
    assert sys.path.count(project_paths.PROJECT_ROOT) == max(count_before, 1)
    assert project_paths.PROJECT_ROOT in sys.path
    # 恢复，避免污染其它用例
    sys.path[:] = before
