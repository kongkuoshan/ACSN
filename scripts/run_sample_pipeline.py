#!/usr/bin/env python
"""在合成演示数据上离线跑通 MKIV 流水线 (Step 1 → Step 5)。

用途: 给 JOSS 审稿人/新用户一条可复现的端到端命令，不联网、不需要 Neo4j、
不需要 HuggingFace 模型。

    python scripts/run_sample_pipeline.py

与真实运行的差异 (都是为了让演示保持离线):
  - Step 0 的**云端抓取**被跳过，直接使用 data/sample/U1_SYNTHETIC.json；
    作者画像匹配仍调用真实的 core.author_matcher 逻辑。
  - Step 3 的 **SBERT 语义聚类**被跳过 (样本量太小)，改用恒等映射 +
    预填好的映射表。真实使用时会调用 paraphrase-multilingual-MiniLM-L12-v2。
  - Step 5 只导出 CSV (真实的 Neo4j 装载需要数据库在跑)。
"""

import argparse
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yaml  # noqa: E402

from core.analyzer import apply_vanguard_mapping  # noqa: E402
from core.author_matcher import build_local_database, match_names_locally  # noqa: E402
from core.db_importer import extract_graph_to_csv  # noqa: E402
from pipelines.data_pipeline import AcademicPipeline  # noqa: E402
from utils.file_handler import (  # noqa: E402
    load_excel,
    load_json,
    save_excel,
    save_json,
)
from utils.project_paths import PROJECT_ROOT  # noqa: E402

SYNTH_INSTITUTION_ID = "https://openalex.org/I0000000"

# 演示流程专用的中间件/输出目录 (不污染真实 data/ 的运行时目录)
SAMPLE_RUN_DIR = os.path.join(PROJECT_ROOT, "data", "sample", "_run")


def build_sample_config(run_dir=None, sample_dir=None):
    """基于用户配置模板 config.example.yaml 构造演示配置。

    直接复用随仓库发布的模板，保证演示配置与真实配置结构完全一致。

    参数:
        run_dir: 中间件/产物目录 (默认 data/sample/_run；测试里传 tmp 目录以隔离)
        sample_dir: 合成数据所在目录 (默认 data/sample/)
    """
    run_dir = run_dir or SAMPLE_RUN_DIR
    sample = sample_dir or os.path.join(PROJECT_ROOT, "data", "sample")

    template = os.path.join(PROJECT_ROOT, "config", "config.example.yaml")
    with open(template, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    cfg["institution"]["target_id"] = SYNTH_INSTITUTION_ID
    cfg["institution"]["email"] = "synthetic@example.com"
    cfg["institution"]["start_year"] = 2018
    cfg["institution"]["fallback_keywords"] = []
    cfg["institution"]["golden_keys"] = {}

    # 输入 = 合成数据；中间件与产物全部落在演示目录，绝不碰真实 data/
    cfg["paths"] = dict(cfg["paths"])
    cfg["paths"].update({
        # 输入 (来自 sample_dir)
        "data_u1_raw": os.path.join(sample, "U1_SYNTHETIC.json"),
        "input_author_excel": os.path.join(sample, "0_原始导师名单_SYNTHETIC.xlsx"),
        "excel_aff_mapping": os.path.join(sample, "1_机构映射表_SYNTHETIC_已填.xlsx"),
        "excel_con_mapping": os.path.join(sample, "2_研究领域映射表_SYNTHETIC_已填.xlsx"),
        # 中间件 (写到 scratch 目录)
        "data_u1_5_tagged": os.path.join(run_dir, "U1.5.json"),
        "data_u2_cleaned": os.path.join(run_dir, "U2.json"),
        "data_u2_unique": os.path.join(run_dir, "unique.json"),
        "data_u2_5_nlp": os.path.join(run_dir, "U2_5.json"),
        "data_u3_final": os.path.join(run_dir, "U3.json"),
        # 产物
        "output_author_excel": os.path.join(run_dir, "0_作者匹配画像表.xlsx"),
        "data_concept_map": os.path.join(run_dir, "concept_dim_map.json"),
        "data_trends": os.path.join(run_dir, "trends.json"),
        "data_lab_radar": os.path.join(run_dir, "lab_radar.json"),
        "data_topic_sunburst": os.path.join(run_dir, "topic_sunburst.json"),
        # 指向不存在的 AI 预填版，强制 Step 4 走预填表
        "excel_aff_mapping_ai": os.path.join(run_dir, "nonexistent_aff_ai.xlsx"),
        "excel_con_mapping_ai": os.path.join(run_dir, "nonexistent_con_ai.xlsx"),
    })
    cfg["author_matcher"]["neo4j_import_dir"] = os.path.join(run_dir, "import")

    cfg["mapping"] = dict(cfg.get("mapping", {}))
    cfg["mapping"]["source"] = "manual"      # 只用预填好的表
    cfg["llm_assistant"] = dict(cfg.get("llm_assistant", {}))
    cfg["llm_assistant"]["enabled"] = False  # 演示不发任何 LLM 请求
    cfg["analytics"] = dict(cfg.get("analytics", {}))
    cfg["analytics"]["use_llm_labels"] = False

    return cfg


def ensure_inputs(sample_dir=None):
    """没有演示数据就地生成一份。"""
    sample = sample_dir or os.path.join(PROJECT_ROOT, "data", "sample")
    if not os.path.exists(os.path.join(sample, "U1_SYNTHETIC.json")):
        logging.info(">> 未发现演示数据，先自动生成...")
        from generate_sample_data import write_sample_dataset
        write_sample_dataset(out_dir=sample)


def run_sample_pipeline(run_dir=None, sample_dir=None):
    run_dir = run_dir or SAMPLE_RUN_DIR
    ensure_inputs(sample_dir)
    os.makedirs(run_dir, exist_ok=True)

    cfg = build_sample_config(run_dir=run_dir, sample_dir=sample_dir)
    pipeline = AcademicPipeline(cfg)

    # ---- Step 0 (本地部分): 用合成名单生成作者画像表 ----
    logging.info("=" * 60)
    logging.info(">> [Step 0·本地] 作者画像匹配")
    all_works = load_json(cfg["paths"]["data_u1_raw"])
    df_input = load_excel(cfg["paths"]["input_author_excel"])
    local_db = build_local_database(all_works, parent_id=SYNTH_INSTITUTION_ID.split("/")[-1])
    df_profile = match_names_locally(df_input, "导师姓名", local_db)
    save_excel(df_profile, cfg["paths"]["output_author_excel"])

    # ---- Step 1 / 2 ----
    pipeline.run_tagging_stage()
    pipeline.run_cleaning_stage()

    # ---- Step 3 (等效替代): 恒等坍缩，替代 SBERT 聚类 ----
    logging.info("=" * 60)
    logging.info(">> [Step 3·替代] 跳过 SBERT 聚类，使用恒等映射生成 U2.5")
    unique = load_json(cfg["paths"]["data_u2_unique"])
    identity_map = {a: a for a in unique["raw_affiliations"]}
    u2_5 = apply_vanguard_mapping(
        load_json(cfg["paths"]["data_u2_cleaned"]), identity_map
    )
    save_json(u2_5, cfg["paths"]["data_u2_5_nlp"])

    # ---- Step 4 / 4.5 ----
    pipeline.run_final_assembly_stage()
    pipeline.run_analytics_stage()

    # ---- Step 5 (仅 CSV 导出，不连 Neo4j) ----
    logging.info("=" * 60)
    logging.info(">> [Step 5·导出] 生成 Neo4j CSV")
    u3 = load_json(cfg["paths"]["data_u3_final"])
    extract_graph_to_csv(u3, load_excel(cfg["paths"]["output_author_excel"]),
                         cfg["author_matcher"]["neo4j_import_dir"])

    logging.info("=" * 60)
    logging.info("🎉 演示流水线跑通! 产物目录: %s", run_dir)
    logging.info("   作者画像表 / U3.json / trends.json / lab_radar.json / topic_sunburst.json / import/*.csv")

    return cfg


def main():
    parser = argparse.ArgumentParser(description="在合成演示数据上离线跑通流水线")
    parser.add_argument("--quiet", action="store_true", help="只输出 WARNING 以上日志")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.WARNING if args.quiet else logging.INFO,
        format="%(message)s",
    )
    run_sample_pipeline()


if __name__ == "__main__":
    main()
