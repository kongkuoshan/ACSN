# main.py
import sys
import os
import yaml
import logging

from utils.project_paths import ensure_in_sys_path, get_config_path, resolve_all_paths

ensure_in_sys_path()


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S'
    )


def ensure_config():
    """首次运行时自动从模板生成 config.yaml"""
    import shutil
    config_path = get_config_path("config.yaml")
    example_path = get_config_path("config.example.yaml")
    if not os.path.exists(config_path):
        if not os.path.exists(example_path):
            print("❌ 致命错误: config.example.yaml 也丢失了！请重新克隆项目。")
            sys.exit(1)
        shutil.copy(example_path, config_path)
        logging.info("📋 首次运行: 已从 config.example.yaml 生成 config/config.yaml")
        logging.info("   请编辑 config/config.yaml 填入你的机构 ID、邮箱和数据库密码。")


if __name__ == "__main__":
    # GUI 模式入口
    if "--gui" in sys.argv:
        from gui_main import main as gui_main
        gui_main()
        sys.exit(0)

    # 首次运行自动生成配置
    ensure_config()

    setup_logging()

    # 1. 加载唯一的全局配置
    config_path = get_config_path("config.yaml")
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        logging.error(f"❌ 找不到配置文件: {config_path}")
        exit(1)

    # 2. 将所有相对路径解析为绝对路径
    config = resolve_all_paths(config)

    # 3. 实例化流水线
    from pipelines.data_pipeline import AcademicPipeline
    pipeline = AcademicPipeline(config)

    # 4. 🚀 一键执行自动化流水线
    try:
        logging.info("🌟 欢迎使用 MKIV 学术情报图谱引擎 🌟")

        # 🟢 如果你需要重头跑，取消注释前置步骤：
        # pipeline.run_author_mining_stage()     # Step 0: 爬虫与作者匹配
        # pipeline.run_tagging_stage()           # Step 1: 靶向过滤
        # pipeline.run_cleaning_stage()          # Step 2: 硬规则清洗
        # pipeline.run_nlp_clustering_stage()    # Step 3: NLP 排头兵
        # pipeline.run_llm_autofill_stage()      # Step 3.5: AI预填
        # pipeline.run_final_assembly_stage()    # Step 4: U3 终极合并
        # pipeline.run_db_import_stage()         # Step 5: Neo4j 图数据库装载

        # 🔴 如果你只为了启动大屏看图，只需保留这一行！
        pipeline.run_dashboard_stage()           # Step 6: 启动大屏服务器

    except Exception as e:
        logging.error(f"❌ 系统发生严重错误: {e}", exc_info=True)
