#!/usr/bin/env python
"""在合成演示数据上离线跑通 MKIV 流水线 (Step 1 → Step 5)。

用途: 给 JOSS 审稿人/新用户一条可复现的端到端命令，不联网、不需要 Neo4j、
不需要 HuggingFace 模型。

    python scripts/run_sample_pipeline.py

与真实运行的差异 (都是为了让演示保持离线):
  - Step 0 的**云端抓取**被跳过，直接使用 data/sample/U1_SYNTHETIC.json；
    作者画像匹配仍调用真实的 core.author_matcher 逻辑。
  - Step 3 的 **SBERT 模型下载**被跳过: 换成按合成真值分组的确定性编码器，
    但聚类、排头兵提取、模板生成走的仍是流水线自己的 build_cluster_mappings()。
    生成的模板再按同一份真值自动填写标准名称列，落到演示目录。因此
    「Step 3 出模板 → Step 4 读表」这条契约路径是真的被走了一遍，
    也没有任何手工维护的映射表会随代码漂移。
    真实使用时的唯一变化: 编码器换成 paraphrase-multilingual-MiniLM-L12-v2，
    标准名称列由人工 (或 Step 3.5 的 LLM 预填) 填写。
  - Step 5 只导出 CSV (真实的 Neo4j 装载需要数据库在跑)。
"""

import argparse
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yaml  # noqa: E402

from core import analyzer  # noqa: E402
from core.author_matcher import build_local_database, match_names_locally  # noqa: E402
from core.db_importer import extract_graph_to_csv  # noqa: E402
from pipelines.data_pipeline import AcademicPipeline  # noqa: E402
from utils.file_handler import (  # noqa: E402
    load_excel,
    load_json,
    save_excel,
)
from utils.project_paths import PROJECT_ROOT  # noqa: E402

from generate_sample_data import (  # noqa: E402
    build_affiliation_ground_truth,
    build_concept_ground_truth,
)

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
        # 映射表由 Step 3 现场生成 (不是随数据发布的预填表)
        "excel_aff_mapping": os.path.join(run_dir, "1_机构映射表.xlsx"),
        "excel_con_mapping": os.path.join(run_dir, "2_研究领域映射表.xlsx"),
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


def _ground_truth_encoder(variant_to_group):
    """假编码器: 同一课题组的变体得到相同向量，组间向量正交。

    因此在流水线真实的 AgglomerativeClustering 下，聚类结果精确等于合成真值
    的分组。它唯一的职责是替掉 SBERT 的 500MB 模型下载，其余环节全是真代码。
    """
    class _Encoder:
        def encode(self, texts, show_progress_bar=False, **kwargs):
            texts = list(texts)
            groups = {}
            for text in texts:
                groups.setdefault(variant_to_group.get(text, text), len(groups))
            width = max(len(groups), 1)
            return [[1.0 if i == groups[variant_to_group.get(t, t)] else 0.0
                     for i in range(width)] for t in texts]

    return _Encoder()


def _fill_mapping_table(path, source_keyword, target_keyword, answers):
    """按合成真值填写 Step 3 生成的映射表模板 (原地覆盖)。

    等价于真实流程里的「人工打开 Excel 填写」那一步，只是答案来自真值字典。
    列名按关键字定位，不写死模板列名，因此不与 analyzer.py 的模板耦合。
    """
    df = load_excel(path)
    src_col = next((c for c in df.columns if source_keyword in c), None)
    dst_col = next((c for c in df.columns if target_keyword in c), None)
    if src_col is None or dst_col is None:
        raise RuntimeError(f"映射表模板列不符合预期: {list(df.columns)}")
    df[dst_col] = [answers.get(str(v).strip(), "") for v in df[src_col]]
    save_excel(df, path)
    logging.info("   📝 已按合成真值预填 %s (%d 行)",
                 os.path.basename(path), len(df))


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

    # ---- Step 3: 真实聚类/模板代码 + 合成真值编码器 ----
    logging.info("=" * 60)
    logging.info(">> [Step 3] 合成真值编码器 → 调用流水线自身的聚类与模板生成")
    aff_truth = build_affiliation_ground_truth()
    con_truth = build_concept_ground_truth()

    unique = load_json(cfg["paths"]["data_u2_unique"])
    # 簇数 = 合成数据里实际出现的课题组数/大类数 → 层次聚类精确还原真值分组
    pipeline.config["nlp"]["target_aff_clusters"] = len(
        {aff_truth.get(a, a) for a in unique["raw_affiliations"]}
    )
    pipeline.config["nlp"]["target_con_clusters"] = len(
        {con_truth.get(c, c) for c in unique["concepts"]}
    )

    real_loader = analyzer.load_sentence_transformer
    # 机构与领域两通道共用同一个确定性编码器 (两组真值键空间不重叠)
    analyzer.load_sentence_transformer = lambda _name: _ground_truth_encoder({**aff_truth, **con_truth})
    try:
        pipeline.run_nlp_clustering_stage()
    finally:
        analyzer.load_sentence_transformer = real_loader

    # 模板已由流水线生成，这里按同一份真值把标准名称列填上 (相当于人工填写那一步)
    _fill_mapping_table(cfg["paths"]["excel_aff_mapping"],
                        source_keyword="排头兵", target_keyword="填写标准名称",
                        answers=aff_truth)
    _fill_mapping_table(cfg["paths"]["excel_con_mapping"],
                        source_keyword="排头兵", target_keyword="填写标准大类",
                        answers=con_truth)

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
