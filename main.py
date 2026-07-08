# main.py
import sys
import os
import yaml
import logging
from pipelines.data_pipeline import AcademicPipeline


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S'
    )


def ensure_config():
    """首次运行时自动从模板生成 config.yaml"""
    import shutil
    config_path = "config/config.yaml"
    example_path = "config/config.example.yaml"
    if not os.path.exists(config_path):
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
    if not os.path.exists("config/config.yaml"):
        if not os.path.exists("config/config.example.yaml"):
            print("❌ 致命错误: config.example.yaml 也丢失了！请重新克隆项目。")
            sys.exit(1)
        import shutil
        shutil.copy("config/config.example.yaml", "config/config.yaml")
        print("📋 首次运行: 已从 config.example.yaml 生成 config/config.yaml")
        print("   请编辑 config/config.yaml 填入你的机构 ID、邮箱和数据库密码。")
        print()

    setup_logging()

    # 1. 加载唯一的全局配置
    try:
        with open("config/config.yaml", 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        logging.error("❌ 找不到 config/config.yaml 文件，请先创建！")
        exit(1)

    # 2. 实例化流水线
    pipeline = AcademicPipeline(config)

    # 3. 🚀 一键执行自动化流水线
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
