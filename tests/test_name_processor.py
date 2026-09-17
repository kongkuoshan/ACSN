"""core/name_processor.py — 中文名 → 西式拼音"""

import pandas as pd
import pytest

from core.name_processor import _chinese_to_western_formatted, build_name_mapping_dataframe


@pytest.mark.parametrize(
    "chinese,expected",
    [
        ("张三", "San Zhang"),          # 2 字: 名 姓
        ("张小明", "Xiaoming Zhang"),   # 3 字: 名合并后仅首字母大写
        ("王", "Wang"),                 # 单字
    ],
)
def test_western_formatted_names(chinese, expected):
    assert _chinese_to_western_formatted(chinese) == expected


@pytest.mark.parametrize("bad", ["", "   ", None, 123])
def test_western_formatted_handles_empty_input(bad):
    assert _chinese_to_western_formatted(bad) == ""


def test_build_name_mapping_dataframe_columns_and_dedup():
    df = build_name_mapping_dataframe(["张三", "张三", " 李四 ", ""])

    assert list(df.columns) == ["", "English Name"]
    # 去重 + 去空，保持首次出现顺序
    assert df.iloc[:, 0].tolist() == ["张三", "李四"]
    assert df["English Name"].tolist() == ["San Zhang", "Si Li"]


def test_build_name_mapping_dataframe_empty_input():
    df = build_name_mapping_dataframe([])
    assert isinstance(df, pd.DataFrame)
    assert df.empty
