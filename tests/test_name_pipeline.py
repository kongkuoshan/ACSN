"""pipelines/name_pipeline.py — 姓名转换流水线"""

import pandas as pd

from pipelines.name_pipeline import NameConversionPipeline
from utils.file_handler import load_excel


def test_run_from_raw_text_writes_excel(tmp_path):
    out = tmp_path / "names.xlsx"
    cfg = {"paths": {"output_names_excel": str(out)}}

    NameConversionPipeline(cfg).run_from_raw_text("张三 李四 张三")

    df = load_excel(str(out))
    assert df.iloc[:, 0].tolist() == ["张三", "李四"]      # 去重且保持顺序
    assert df["English Name"].tolist() == ["San Zhang", "Si Li"]


def test_run_from_excel_reads_second_column(tmp_path):
    src = tmp_path / "in.xlsx"
    pd.DataFrame({"序号": [1, 2], "姓名": ["张三", "李四"]}).to_excel(src, index=False)
    out = tmp_path / "names.xlsx"
    cfg = {"paths": {"input_names_excel": str(src), "output_names_excel": str(out)}}

    NameConversionPipeline(cfg).run_from_excel()

    assert load_excel(str(out)).iloc[:, 0].tolist() == ["张三", "李四"]


def test_run_from_excel_without_input_file_is_noop(tmp_path):
    out = tmp_path / "names.xlsx"
    cfg = {"paths": {"input_names_excel": str(tmp_path / "missing.xlsx"),
                     "output_names_excel": str(out)}}

    NameConversionPipeline(cfg).run_from_excel()

    assert not out.exists()
