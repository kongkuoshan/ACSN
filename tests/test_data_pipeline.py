"""pipelines/data_pipeline.py — 阶段编排 + 合成数据端到端冒烟。

这是 JOSS 评审最关心的一条: 一条命令、离线、无 Neo4j、无 SBERT，
从合成 U1 一路跑到 U3 与导出 CSV。
"""

import os

import pandas as pd
import pytest

from generate_sample_data import LABS, TOPICS, write_sample_dataset
from pipelines.data_pipeline import AcademicPipeline, _save_template_if_unfilled
from run_sample_pipeline import build_sample_config, run_sample_pipeline
from utils.file_handler import load_excel, load_json

CSV_FILES = ["s.csv", "p.csv", "l.csv", "t.csv", "r_w.csv", "r_b.csv", "r_m.csv", "r_c.csv"]


# --------------------------- _save_template_if_unfilled ---------------------------

def test_save_template_writes_when_file_missing(tmp_path):
    path = str(tmp_path / "aff.xlsx")
    _save_template_if_unfilled(pd.DataFrame({"a": [1]}), path, "填写标准名称")
    assert os.path.exists(path)


def test_save_template_skips_when_already_filled(tmp_path):
    path = str(tmp_path / "aff.xlsx")
    original = pd.DataFrame({"填写标准名称 (抄左边)": ["Brain Lab"]})
    original.to_excel(path, index=False)

    _save_template_if_unfilled(pd.DataFrame({"填写标准名称 (抄左边)": ["别的"]}), path,
                               "填写标准名称")

    assert load_excel(path)["填写标准名称 (抄左边)"].tolist() == ["Brain Lab"]


def test_save_template_overwrites_when_columns_empty(tmp_path):
    path = str(tmp_path / "aff.xlsx")
    pd.DataFrame({"填写标准名称 (抄左边)": [None, None]}).to_excel(path, index=False)

    _save_template_if_unfilled(pd.DataFrame({"填写标准名称 (抄左边)": ["新模板"]}), path,
                               "填写标准名称")

    assert load_excel(path)["填写标准名称 (抄左边)"].tolist() == ["新模板"]


# --------------------------- AcademicPipeline 路径解析 ---------------------------

def test_pipeline_resolves_relative_paths():
    cfg = {"paths": {"data_u1_raw": "data/input/U1.json"}, "institution": {}}
    resolved = AcademicPipeline(cfg).config["paths"]["data_u1_raw"]
    assert os.path.isabs(resolved)


# --------------------------- 演示配置结构 ---------------------------

def test_sample_config_is_offline_and_isolated(tmp_path):
    cfg = build_sample_config(run_dir=str(tmp_path / "run"), sample_dir=str(tmp_path))

    assert cfg["llm_assistant"]["enabled"] is False
    assert cfg["analytics"]["use_llm_labels"] is False
    assert cfg["mapping"]["source"] == "manual"
    assert cfg["institution"]["target_id"].endswith("I0000000")
    # 中间件全部落在临时 run 目录，绝不碰真实 data/
    for key in ("data_u3_final", "data_u1_5_tagged", "data_trends",
                "excel_aff_mapping", "excel_con_mapping"):
        assert str(tmp_path) in cfg["paths"][key]


def test_sample_dataset_ships_inputs_only(tmp_path):
    """演示数据只发布输入；映射表由 Step 3 现场生成，不随数据发布。"""
    out = tmp_path / "sample"
    write_sample_dataset(out_dir=str(out), seed=0, n_works=10)

    assert sorted(p.name for p in out.iterdir()) == [
        "0_原始导师名单_SYNTHETIC.xlsx", "README.md", "U1_SYNTHETIC.json"]


def test_ground_truth_covers_every_cleaned_variant():
    """真值表必须覆盖每一条清洗后的机构串，否则演示会静默失配。"""
    from generate_sample_data import build_affiliation_ground_truth, _clean_noise

    ground_truth = build_affiliation_ground_truth()
    for variants in LABS.values():
        for raw in variants:
            cleaned = _clean_noise(raw)
            if cleaned:
                assert cleaned in ground_truth


# --------------------------- 端到端冒烟 ---------------------------

@pytest.fixture(scope="module")
def sample_run(tmp_path_factory):
    """在临时目录里生成合成数据并跑完整条流水线 (模块级，只跑一次)。"""
    root = tmp_path_factory.mktemp("sample")
    sample_dir = root / "sample"
    run_dir = root / "run"
    write_sample_dataset(out_dir=str(sample_dir), seed=0, n_works=60)
    run_sample_pipeline(run_dir=str(run_dir), sample_dir=str(sample_dir))
    return run_dir


def test_end_to_end_produces_all_artifacts(sample_run):
    for name in ("U1.5.json", "U2.json", "unique.json", "U2_5.json", "U3.json",
                 "trends.json", "lab_radar.json", "topic_sunburst.json",
                 "concept_dim_map.json", "0_作者匹配画像表.xlsx"):
        assert (sample_run / name).exists(), f"缺少产物 {name}"


def test_end_to_end_mapping_tables_come_from_step3(sample_run):
    """映射表必须是 Step 3 聚出来的**簇**表，而不是一条变体一行的预填表。"""
    aff_path = sample_run / "1_机构映射表.xlsx"
    con_path = sample_run / "2_研究领域映射表.xlsx"
    assert aff_path.exists() and con_path.exists()

    aff = load_excel(str(aff_path))
    unique = load_json(str(sample_run / "unique.json"))
    n_variants = len(unique["raw_affiliations"])

    # 多个变体坍缩成一簇 → 行数严格少于变体数；但变体总数守恒
    assert 0 < len(aff) < n_variants
    assert aff["包含变体数"].sum() == n_variants

    fill_col = next(c for c in aff.columns if "填写标准名称" in c)
    assert aff[fill_col].notna().all()


def test_end_to_end_exports_eight_neo4j_csvs(sample_run):
    for name in CSV_FILES:
        assert (sample_run / "import" / name).exists(), f"缺少 {name}"


def test_end_to_end_concepts_are_strictly_mapped(sample_run):
    u3 = load_json(str(sample_run / "U3.json"))
    canonical = set(TOPICS)

    seen = set()
    for work in u3:
        for c in work.get("concepts", []):
            assert c["display_name"] in canonical          # 未映射的必须被剔除
            assert "original_name" in c                    # 保留原始名以便追溯
            seen.add(c["display_name"])

    # 合成数据里每个原始概念都至少出现过一次 → 三个大类都应被映射到
    assert seen == canonical


def test_end_to_end_affiliations_are_normalized(sample_run):
    # U2 是清洗后的中间件 (仍是原始写法)；U3 才是映射后的真值
    u2 = load_json(str(sample_run / "U2.json"))
    u2_affs = set()
    for work in u2:
        for auth in work.get("authorships", []):
            if auth.get("is_internal_node"):
                u2_affs.update(auth.get("raw_affiliation_strings", []))
    # 清洗必须去掉邮箱/邮编/国名
    assert not any("@" in a or "China" in a or "100190" in a for a in u2_affs)

    u3 = load_json(str(sample_run / "U3.json"))
    u3_affs = set()
    for work in u3:
        for auth in work.get("authorships", []):
            if auth.get("is_internal_node"):
                u3_affs.update(auth.get("raw_affiliation_strings", []))

    canonical_labs = {"Synthetic Brain Lab", "Synthetic Vision Lab", "Synthetic Robotics Lab"}
    assert u3_affs <= canonical_labs
    assert u3_affs == canonical_labs     # 三个课题组都应出现


def test_end_to_end_analytics_covers_all_concepts(sample_run):
    trends = load_json(str(sample_run / "trends.json"))
    assert trends, "演化数据不应为空"

    dim_map = load_json(str(sample_run / "concept_dim_map.json"))
    assert set(dim_map.values()) <= set(TOPICS)
