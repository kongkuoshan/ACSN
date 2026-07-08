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
        "建议范围: 2018-当前"
    ),
    "institution.end_year": (
        "文献抓取结束年份\n\n"
        "设定爬虫抓取文献的截止年份。\n"
        "设为 0 或留空 = 自动使用当前年份。\n"
        "设置具体年份可以限定分析的时间窗口。\n\n"
        "默认: 0 (自动=当前年份)"
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
        "当 OpenAlex 官方机构 ID 匹配失败时，\n"
        "用这些关键词在原始挂靠文本中做模糊匹配。\n"
        "用于捕获机构缩写、别名或英文变体。\n"
        "每行一个关键词，不区分大小写。\n\n"
        "示例:\n"
        "  清华大学 → Tsinghua, THU, 清华\n"
        "  自动化所 → automation, CASIA, NLPR"
    ),
    "institution.casia_keys": (
        "金钥匙映射表\n\n"
        "机构名称的最后一道兜底映射。\n"
        "当 Excel 映射表和 LLM 都无法识别某个机构变体时，\n"
        "用这张表的关键字做文本匹配。\n\n"
        "左边: 关键字（会出现在原始挂靠文本中的词）\n"
        "右边: 标准名称（你要统一成的规范名）\n\n"
        "示例:\n"
        "  NLPR → 模式识别国家重点实验室\n"
        "  THU → 清华大学\n"
        "提示: 关键字不区分大小写。"
    ),

    # === 情报分析 ===
    "analytics.concept_clusters": (
        "概念降维目标簇数\n\n"
        "分析模块将研究领域关键词聚类为宏观主题。\n"
        "数值 = 期望的宏观主题数量。\n\n"
        "建议 15-50，默认 25。\n"
        "太小 → 主题过粗，区分度低\n"
        "太大 → 主题过细，图表混乱"
    ),
    "analytics.use_llm_labels": (
        "LLM 命名概念簇\n\n"
        "开启后，分析模块会调用 LLM API\n"
        "为每个概念簇自动生成中文主题名称（如「具身智能与机器人」）。\n\n"
        "关闭后使用簇内最短词汇作为名称。\n"
        "需要 llm_assistant.enabled=true 且 API 可用。"
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
        "SBERT 聚类后生成的排头兵数量。\n"
        "⚠️ 这不是你机构的实际实验室数量！\n"
        "设为你实际实验室/部门数量的 3~5 倍。\n\n"
        "为什么设大?\n"
        "  簇稍多 → 人工在 Excel 中合并几行即可\n"
        "  簇太少 → 不同实验室被错误合并, 无法拆分\n\n"
        "示例:\n"
        "  5个实验室 → 设 20-30\n"
        "  50个部门   → 设 150-200\n\n"
        "默认值: 30 (适合 5-10 个实验室的研究所)"
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
