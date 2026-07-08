# pipelines/data_pipeline.py
import os
import logging
from core.visualizer import start_visualizer_server, start_visualizer_server_background
from core.db_importer import extract_graph_to_csv, Neo4jImporter
from core.crawler import run_openalex_crawler
from core.author_matcher import build_local_database, match_names_locally
from core.cleaner import tag_internal_nodes, extract_and_clean_entities
from core.analyzer import build_cluster_mappings, apply_vanguard_mapping
from core.assembler import parse_mapping_rules, generate_final_u3
from core.llm_labeler import auto_label_concepts, auto_label_affiliations
from core.trend_analyzer import reduce_concept_dimensions, generate_evolution_data, generate_lab_radar_data, generate_topic_distribution
from utils.file_handler import load_json, save_json, load_excel, save_excel


class AcademicPipeline:
    """
    MKIV 主学术数据处理流水线 (7阶段: Step 0 → Step 6)
    """

    def __init__(self, config: dict):
        self.config = config

    # ================================================================
    # Step 0: 核心数据采集与作者画像匹配
    # ================================================================
    def run_author_mining_stage(self):
        cfg = self.config
        logging.info("=" * 50)
        logging.info(">> 🚀 [Step 0] 启动数据基石：全量抓取与作者画像分析...")

        # 1. 执行工业级爬虫 (生成或读取 U1.json)
        all_works = run_openalex_crawler(
            target_id=cfg['institution']['target_id'],
            email=cfg['institution']['email'],
            start_year=cfg['institution']['start_year'],
            end_year=cfg['institution'].get('end_year'),
            output_path=cfg['paths']['data_u1_raw']
        )

        if not all_works:
            logging.error("❌ 未获取到任何文献数据，流水线终止。")
            return

        # 2. 如果提供了原始名单，则执行画像匹配
        input_excel = cfg['paths']['input_author_excel']
        if os.path.exists(input_excel):
            target_id_short = cfg['institution']['target_id'].split("/")[-1]
            local_db = build_local_database(all_works, parent_id=target_id_short)

            df_input = load_excel(input_excel)
            df_out = match_names_locally(
                df_input=df_input,
                name_column=cfg['author_matcher']['name_column'],
                local_author_db=local_db
            )

            if not df_out.empty:
                save_excel(df_out, cfg['paths']['output_author_excel'])
                logging.info(f"🎉 强大的 0 号表已保存至: {cfg['paths']['output_author_excel']}")
        else:
            logging.warning(f"⚠️ 未找到输入名单 {input_excel}，已跳过画像匹配环节。")

    # ================================================================
    # Step 1: 靶向过滤与内部节点打标
    # ================================================================
    def run_tagging_stage(self):
        paths = self.config['paths']
        institution_cfg = self.config['institution']

        logging.info(">> 🚀 [Step 1] 启动 U1.5 靶向过滤引擎...")

        raw_data = load_json(paths['data_u1_raw'])
        if not raw_data:
            logging.error("❌ U1 数据读取失败，终止流水线。")
            return

        tagged_data, internal_count, external_count = tag_internal_nodes(
            raw_works=raw_data,
            target_id=institution_cfg['target_id'],
            fallback_patterns=institution_cfg.get('fallback_keywords', [])
        )

        save_json(tagged_data, paths['data_u1_5_tagged'])

        logging.info("=" * 50)
        logging.info("🎯 U1.5 靶向过滤完成！全量作者底细已被摸清。")
        logging.info(f"👨‍🔬 鉴定为【内部作者 / 核心节点】的挂靠记录: {internal_count} 条")
        logging.info(f"🤝 鉴定为【外部合作 / 边缘节点】的挂靠记录: {external_count} 条")
        logging.info("=" * 50)

    # ================================================================
    # Step 2: 脏数据物理清洗与实体提取
    # ================================================================
    def run_cleaning_stage(self):
        paths = self.config['paths']

        logging.info(">> 🚀 [Step 2] 启动 U2 引擎：同步清洗机构并提取领域...")

        tagged_data = load_json(paths['data_u1_5_tagged'])
        if not tagged_data:
            logging.error("❌ U1.5 数据读取失败，终止流水线。")
            return

        u2_data, unique_entities = extract_and_clean_entities(tagged_works=tagged_data)

        save_json(u2_data, paths['data_u2_cleaned'])
        save_json(unique_entities, paths['data_u2_unique'])

        logging.info("=" * 50)
        logging.info("🧹 U2 清洗与提取任务完成！")
        logging.info(f"🌌 成功提取精华领域大类: {len(unique_entities['concepts'])} 个")
        logging.info(f"🏢 成功提取待聚类的内部机构变体: {len(unique_entities['raw_affiliations'])} 个")
        logging.info("=" * 50)

    # ================================================================
    # Step 3: NLP 聚类生成排头兵模板，坍缩生成 U2.5
    # ================================================================
    def run_nlp_clustering_stage(self):
        paths = self.config['paths']
        nlp_cfg = self.config['nlp']

        logging.info(">> 🚀 [Step 3] 启动大模型 NLP 聚类与排头兵坍缩引擎...")

        unique_data = load_json(paths['data_u2_unique'])
        if not unique_data:
            logging.error("❌ Unique 字典读取失败，终止流水线。")
            return

        df_con, df_aff, variant_mapping = build_cluster_mappings(
            unique_data=unique_data,
            target_clusters=nlp_cfg.get('target_aff_clusters', 350)
        )

        if not df_con.empty:
            save_excel(df_con, paths['excel_con_mapping'])
        if not df_aff.empty:
            save_excel(df_aff, paths['excel_aff_mapping'])

        if variant_mapping:
            u2_data = load_json(paths['data_u2_cleaned'])
            if u2_data:
                u2_5_data = apply_vanguard_mapping(u2_data, variant_mapping)
                save_json(u2_5_data, paths['data_u2_5_nlp'])
                logging.info(f"✅ 完美！U2.5 中间件已成功生成: {paths['data_u2_5_nlp']}")

    # ================================================================
    # Step 3.5: LLM 自动化预填 Excel (可选)
    # ================================================================
    def run_llm_autofill_stage(self):
        llm_cfg = self.config.get('llm_assistant', {})
        if not llm_cfg.get('enabled', False):
            logging.info(">> ⏩ LLM 预填模块已在配置中禁用，跳过此步骤。")
            return

        paths = self.config['paths']
        api_url = llm_cfg['api_url']

        logging.info(">> 🚀 [Step 3.5] 启动 LLM 人工智能辅助预填引擎...")

        # 1. 预填研究领域表
        df_con = load_excel(paths['excel_con_mapping'])
        if not df_con.empty:
            df_con_ai = auto_label_concepts(
                df_con=df_con,
                api_url=api_url,
                target_fields=llm_cfg['concept_target_fields']
            )
            save_excel(df_con_ai, paths['excel_con_mapping_ai'])

        # 2. 预填机构表
        df_aff = load_excel(paths['excel_aff_mapping'])
        if not df_aff.empty:
            df_aff_ai = auto_label_affiliations(
                df_aff=df_aff,
                api_url=api_url,
                sys_prompt=llm_cfg['affiliation_system_prompt']
            )
            save_excel(df_aff_ai, paths['excel_aff_mapping_ai'])

        logging.info(">> 🎉 LLM 预填完毕！请人类专家打开 `_AI预填版.xlsx` 进行最终抽检和修改。")

    # ================================================================
    # Step 4: 终极清洗与真值注入
    # ================================================================
    def run_final_assembly_stage(self):
        paths = self.config['paths']
        casia_keys = self.config['institution'].get('casia_keys', {})

        logging.info(">> 🚀 [Step 4] 启动 U3 终极数据组装与注入引擎...")

        u2_5_data = load_json(paths['data_u2_5_nlp'])
        df_aff = load_excel(paths['excel_aff_mapping'])
        df_con = load_excel(paths['excel_con_mapping'])

        if not u2_5_data:
            logging.error("❌ U2.5 数据读取失败，终止流水线。")
            return

        aff_map, con_map = parse_mapping_rules(df_aff, df_con)

        u3_data, stats = generate_final_u3(
            u2_5_data=u2_5_data,
            aff_map=aff_map,
            con_map=con_map,
            casia_keys=casia_keys
        )

        save_json(u3_data, paths['data_u3_final'])

        logging.info("=" * 50)
        logging.info("🎉 恭喜！U3 终极数据清洗任务圆满完成！")
        logging.info(f"  🟢 成功映射并保留领域 (有效大类): {stats['replace_count']} 次")
        logging.info(f"  🔴 判定为底层噪音并彻底剔除: {stats['dropped_count']} 次")
        logging.info(f"  💾 黄金数据集已就绪，随时可导入 Neo4j: {paths['data_u3_final']}")
        logging.info("=" * 50)

    # ================================================================
    # Step 4.5: 情报挖掘与演化分析
    # ================================================================
    def run_analytics_stage(self):
        paths = self.config['paths']
        analytics_cfg = self.config.get('analytics', {})
        llm_cfg = self.config.get('llm_assistant', {})

        logging.info("=" * 50)
        logging.info(">> 🚀 [Step 4.5] 启动情报挖掘与演化分析引擎...")

        u3_data = load_json(paths['data_u3_final'])
        if not u3_data:
            logging.error("❌ U3 数据不可用，跳过分析阶段。")
            return

        # 1. 概念降维 (复用排头兵 + LLM 逻辑)
        api_url = llm_cfg.get('api_url') if analytics_cfg.get('use_llm_labels', True) else None
        concept_dim_map = reduce_concept_dimensions(
            u3_data,
            target_clusters=analytics_cfg.get('concept_clusters', 25),
            api_url=api_url
        )
        save_json(concept_dim_map, paths.get('data_concept_map', './data/output/concept_dim_map.json'))

        # 2. 演化分析 → Theme River
        trends = generate_evolution_data(u3_data, concept_dim_map)
        save_json(trends, paths.get('data_trends', './data/output/trends.json'))

        # 3. 实验室雷达
        lab_profiles = generate_lab_radar_data(u3_data, concept_dim_map)
        save_json(lab_profiles, paths.get('data_lab_radar', './data/output/lab_radar.json'))

        # 4. 主题分布 → Sunburst
        topic_tree = generate_topic_distribution(u3_data, concept_dim_map)
        save_json(topic_tree, paths.get('data_topic_sunburst', './data/output/topic_sunburst.json'))

        logging.info(">> 🎉 情报分析完成! 已生成演化趋势、实验室雷达和主题分布数据。")

    # ================================================================
    # Step 5: 导出 CSV 并装载进 Neo4j
    # ================================================================
    def run_db_import_stage(self):
        paths = self.config['paths']
        db_cfg = self.config['database']

        logging.info("=" * 50)
        logging.info(">> 🚀 [Step 5] 启动图数据库装载引擎...")

        u3_data = load_json(paths['data_u3_final'])
        df_pi = load_excel(paths['output_author_excel'])

        if not u3_data:
            logging.error("❌ 找不到 U3.json，无法执行入库。")
            return

        import_dir = self.config.get('author_matcher', {}).get('neo4j_import_dir', './data/import')
        extract_graph_to_csv(u3_data, df_pi, import_dir)

        try:
            importer = Neo4jImporter(uri=db_cfg['uri'], user=db_cfg['user'], password=db_cfg['password'])
            importer.execute_load()
        except Exception as e:
            logging.error(f"❌ Neo4j 入库失败，请检查数据库是否启动或配置是否正确: {e}")

    # ================================================================
    # Step 6: 启动可视化大屏
    # ================================================================
    def run_dashboard_stage(self, background=False):
        db_cfg = self.config['database']

        logging.info("=" * 50)
        logging.info(">> 🌐 [Step 6] 启动 ECharts 可视化服务端...")

        if background:
            start_visualizer_server_background(db_config=db_cfg, host="127.0.0.1", port=8000)
        else:
            start_visualizer_server(db_config=db_cfg, host="127.0.0.1", port=8000)
