"""utils/file_handler.py — JSON / Excel 读写"""

import pandas as pd
import pytest

from utils.file_handler import load_excel, load_json, save_excel, save_json


# ----------------------------- JSON -----------------------------

def test_json_roundtrip_keeps_unicode(tmp_path):
    path = str(tmp_path / "u.json")
    data = [{"名称": "人工智能", "n": 3}]
    save_json(data, path)
    assert load_json(path) == data


def test_load_json_missing_returns_none(tmp_path):
    assert load_json(str(tmp_path / "nope.json")) is None


def test_load_json_malformed_returns_none(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")
    assert load_json(str(path)) is None


def test_save_json_creates_parent_dirs(tmp_path):
    path = str(tmp_path / "deep" / "nested" / "u.json")
    save_json({"a": 1}, path)
    assert load_json(path) == {"a": 1}


# ----------------------------- Excel -----------------------------

def test_excel_roundtrip(tmp_path):
    path = str(tmp_path / "m.xlsx")
    df = pd.DataFrame({"原始领域名称": ["ML", "NLP"], "填写标准大类": ["", ""]})
    save_excel(df, path)

    out = load_excel(path)
    assert list(out.columns) == list(df.columns)
    assert out["原始领域名称"].tolist() == ["ML", "NLP"]


def test_load_excel_missing_returns_empty_dataframe(tmp_path):
    out = load_excel(str(tmp_path / "nope.xlsx"))
    assert isinstance(out, pd.DataFrame)
    assert out.empty


def test_load_excel_missing_with_usecol_returns_list(tmp_path):
    # 返回类型必须跟着调用方式走，否则调用方会拿到 DataFrame 当 list 用
    out = load_excel(str(tmp_path / "nope.xlsx"), usecol_index=1)
    assert out == []


def test_load_excel_usecol_returns_str_list_and_drops_nan(tmp_path):
    path = str(tmp_path / "names.xlsx")
    pd.DataFrame({"a": ["张三", None, "李四"], "b": ["Zhang San", "x", None]}).to_excel(
        path, index=False
    )

    out = load_excel(path, usecol_index=1)
    assert out == ["Zhang San", "x"]


def test_load_excel_usecol_out_of_range_returns_empty_list(tmp_path):
    path = str(tmp_path / "one.xlsx")
    pd.DataFrame({"only": [1, 2]}).to_excel(path, index=False)
    assert load_excel(path, usecol_index=5) == []


def test_load_excel_corrupt_file_returns_empty(tmp_path):
    path = tmp_path / "corrupt.xlsx"
    path.write_text("this is not a spreadsheet", encoding="utf-8")
    assert load_excel(str(path)).empty
    assert load_excel(str(path), usecol_index=0) == []
