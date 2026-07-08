# gui/help_texts.py
"""
中文帮助文本字典。每个 config 参数对应一段详细的中文解释。
键名与 config.yaml 的路径一一对应。
"""

HELP = {
    # === 机构设置 ===
    "institution.email": (
        "OpenAlex API 身份标识邮箱\n\n"
        "OpenAlex 要求提供邮箱地址以进入 Polite Pool，\n"
        "从而提高 API 请求额度(每秒可达 10 次请求)。\n"
        "推荐使用您的机构邮箱。\n\n"
        "默认值: youremail@example.com"
    ),
    "institution.start_year": (
        "文献抓取起始年份\n\n"
        "设定爬虫从哪一年开始抓取文献数据。\n"
        "例如设为 2021 将抓取 2021 年至今的所有文献。\n"
        "建议范围: 2018-2026"
    ),
    "institution.target_id": (
        "目标机构 OpenAlex ID\n\n"
        "机构在 OpenAlex 数据库中的唯一标识符。\n"
        "这是爬虫搜索文献的核心锚点。\n"
        "格式: https://openalex.org/I4210112150\n\n"
        "可在 OpenAlex 官网搜索机构名称获取。"
    ),
    "institution.fallback_keywords": (
        "兜底关键词列表\n\n"
        "当官方机构 ID 匹配失败时，\n"
        "使用这些关键词进行正则表达式兜底匹配。\n"
        "常用于捕获机构缩写或别名变体。\n"
        "每行一个关键词。\n\n"
        "示例: automation, NLPR, CASIA"
    ),
    "institution.casia_keys": (
        "金钥匙映射表\n\n"
        "机构标准名称的硬编码映射字典。\n"
        "格式: 原始文本关键字 → 标准中文名称\n"
        "用于最终装配阶段的机构名称标准化。\n\n"
        "示例: NLPR → 模式识别国家重点实验室"
    ),

    # === 路径配置 ===
    "paths.data_u1_raw": (
        "U1 原始数据路径\n\n"
        "OpenAlex 爬虫的原始输出 JSON 文件。\n"
        "包含未经处理的全部文献数据。\n\n"
        "默认: ./data/01_raw/U1.json"
    ),
    "paths.data_u1_5_tagged": (
        "U1.5 打标数据路径\n\n"
        "经过靶向过滤后的中间数据，\n"
        "每位作者已被标记为内部/外部节点。\n\n"
        "默认: ./data/02_analyzed/U1.5.json"
    ),
    "paths.data_u2_cleaned": (
        "U2 清洗数据路径\n\n"
        "经过硬规则清洗后的数据，\n"
        "机构名称已去除邮箱、邮编等噪音。\n\n"
        "默认: ./data/03_cleaned/U2.json"
    ),
    "paths.data_u2_unique": (
        "U2 唯一实体字典路径\n\n"
        "从 U2 数据中提取的唯一机构和领域列表，\n"
        "用于后续 NLP 聚类分析。\n\n"
        "默认: ./data/03_cleaned/unique.json"
    ),
    "paths.data_u2_5_nlp": (
        "U2.5 NLP 数据路径\n\n"
        "经过 NLP 聚类坍缩后的数据，\n"
        "数千种机构变体已被映射为排头兵。\n\n"
        "默认: ./data/03_cleaned/U2_5.json"
    ),
    "paths.data_u3_final": (
        "U3 最终黄金数据路径\n\n"
        "经过终极清洗和人工规则注入后的最终数据。\n"
        "这是导入 Neo4j 的数据源。\n\n"
        "默认: ./data/output/U3.json"
    ),
    "paths.input_author_excel": (
        "导师名单输入路径\n\n"
        "包含原始导师姓名的 Excel 文件。\n"
        "用于与爬虫数据进行作者画像匹配。\n\n"
        "默认: ./data/input/0_原始导师名单.xlsx"
    ),
    "paths.output_author_excel": (
        "作者画像输出路径\n\n"
        "作者匹配画像表的输出位置。\n"
        "包含每位导师的 OpenAlex ID、发文量、\n"
        "研究领域和合作者网络等画像信息。\n\n"
        "默认: ./data/output/0_作者匹配画像表.xlsx"
    ),
    "paths.excel_aff_mapping": (
        "机构映射表路径\n\n"
        "NLP 聚类生成 + 人工校验后的机构名称映射表。\n"
        "将数百种机构变体映射到标准中文名称。\n\n"
        "默认: ./data/input/1_机构映射表.xlsx"
    ),
    "paths.excel_con_mapping": (
        "领域映射表路径\n\n"
        "NLP 提取 + 人工校验后的研究领域分类表。\n"
        "将原始领域名称归类到标准大类。\n\n"
        "默认: ./data/input/2_研究领域映射表.xlsx"
    ),
    "paths.excel_aff_mapping_ai": (
        "AI 预填机构映射表路径\n\n"
        "LLM 自动预填的机构映射表。\n"
        "作为人工校验的起点，可大幅减少手工工作量。\n\n"
        "默认: ./data/input/1_机构映射表_AI预填版.xlsx"
    ),
    "paths.excel_con_mapping_ai": (
        "AI 预填领域映射表路径\n\n"
        "LLM 自动预填的领域分类表。\n"
        "作为人工校验的起点，可大幅减少手工工作量。\n\n"
        "默认: ./data/input/2_研究领域映射表_AI预填版.xlsx"
    ),

    # === NLP 参数 ===
    "nlp.target_aff_clusters": (
        "目标聚类簇数\n\n"
        "层次聚类 (AgglomerativeClustering) 的目标簇数量。\n"
        "数值越大 → 分类越精细 → 需要更多人工审核。\n"
        "数值越小 → 分类越粗 → 可能合并不够准确。\n\n"
        "推荐范围: 300-500\n"
        "默认值: 350"
    ),

    # === LLM 助手 ===
    "llm_assistant.enabled": (
        "启用 LLM 自动预填\n\n"
        "开启后，将在 Step 3.5 自动调用 LLM API\n"
        "为空白 Excel 映射表填写标准分类。\n"
        "需要本地或远程运行兼容 OpenAI 格式的 LLM 服务。\n\n"
        "关闭后跳过此步骤，需人工填写所有映射。"
    ),
    "llm_assistant.api_url": (
        "LLM API 接口地址\n\n"
        "兼容 OpenAI Chat Completions 格式的 API 地址。\n"
        "本地部署示例:\n"
        "  • Ollama: http://localhost:11434/v1/chat/completions\n"
        "  • vLLM: http://localhost:8080/v1/chat/completions\n"
        "  • text-generation-webui: http://localhost:5000/v1/chat/completions"
    ),
    "llm_assistant.concept_target_fields": (
        "领域分类目标列表\n\n"
        "LLM 将把输入的研究领域归类到这些类别之一。\n"
        "多个类别用逗号分隔。\n\n"
        "示例: 人工智能, 计算机视觉, 机器人学, 自动控制, ..."
    ),
    "llm_assistant.affiliation_system_prompt": (
        "机构识别 System Prompt\n\n"
        "发送给 LLM 的系统提示词，\n"
        "指导模型如何判断和输出机构名称。\n\n"
        "模型会根据此提示词判断机构变体是否属于目标机构，\n"
        "并输出标准化的中文名称。"
    ),

    # === 数据库 ===
    "database.uri": (
        "Neo4j Bolt 连接地址\n\n"
        "Neo4j 图数据库的 Bolt 协议连接 URI。\n"
        "默认端口: 7687 (标准) 或 7688 (本项目)\n\n"
        "格式: bolt://localhost:7688"
    ),
    "database.user": (
        "Neo4j 用户名\n\n"
        "图数据库的登录用户名。\n"
        "Docker 部署时默认: neo4j\n\n"
        "默认值: neo4j"
    ),
    "database.password": (
        "Neo4j 密码\n\n"
        "图数据库的登录密码。\n"
        "首次使用 Docker 部署时会自动设置此密码。\n\n"
        "注意: 密码为敏感信息，请勿分享配置文件。"
    ),
    "author_matcher.paths.neo4j_import_dir": (
        "Neo4j Import 目录\n\n"
        "Neo4j 用于 LOAD CSV 的专属导入文件夹路径。\n"
        "生成的 CSV 文件会自动复制到此目录。\n"
        "Docker 部署时此目录会挂载到容器内。\n\n"
        "提示: 确保此目录有足够的磁盘空间。"
    ),

    # === 作者匹配 ===
    "author_matcher.name_column": (
        "姓名列名\n\n"
        "输入 Excel 中导师姓名所在的列标题。\n"
        "程序会按此列名读取名单并进行匹配。\n\n"
        "示例: 导师姓名, Name, 姓名"
    ),
}
