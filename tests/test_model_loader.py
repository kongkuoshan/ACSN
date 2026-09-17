"""utils/model_loader.py — SBERT 模型本地优先解析"""

import os

from utils import model_loader
from utils.project_paths import PROJECT_ROOT


def test_resolve_model_path_absolute_dir(tmp_path):
    assert model_loader.resolve_model_path(str(tmp_path)) == str(tmp_path)


def test_resolve_model_path_relative_to_project_root(tmp_path, monkeypatch):
    monkeypatch.setattr(model_loader, "PROJECT_ROOT", str(tmp_path))
    local = tmp_path / "my-model"
    local.mkdir()
    assert model_loader.resolve_model_path("my-model") == str(local)


def test_resolve_model_path_falls_back_to_models_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(model_loader, "PROJECT_ROOT", str(tmp_path))
    local = tmp_path / "models" / "some-model"
    local.mkdir(parents=True)
    # 传 HuggingFace 风格的 ID，应命中 models/<basename>
    assert model_loader.resolve_model_path("org/some-model") == str(local)


def test_resolve_model_path_returns_none_when_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(model_loader, "PROJECT_ROOT", str(tmp_path))
    assert model_loader.resolve_model_path("nonexistent-model") is None


def test_resolve_model_path_returns_none_for_empty():
    assert model_loader.resolve_model_path("") is None
    assert model_loader.resolve_model_path(None) is None


def test_resolve_model_path_never_returns_missing_dir():
    # models/ 是 gitignored 的运行时目录：开发机可能已下载模型，CI 上则没有。
    # 无论哪种情况，返回值要么是 None，要么必须是真实存在的目录。
    resolved = model_loader.resolve_model_path("paraphrase-multilingual-MiniLM-L12-v2")
    assert resolved is None or os.path.isdir(resolved)


def test_resolve_model_path_uses_project_root_by_default():
    # 默认分支必须基于项目内的 models/ 目录，而不是 CWD
    assert model_loader.PROJECT_ROOT == PROJECT_ROOT
