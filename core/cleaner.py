# core/cleaner.py
import re
from tqdm import tqdm
import logging

def tag_internal_nodes(raw_works: list, target_id: str, fallback_patterns: list) -> tuple:
    """
    [核心逻辑] 遍历原始学术成果，为作者打上内部/外部标签。
    
    参数:
        raw_works: 包含学术成果字典的列表 (U1 数据)
        target_id: 目标机构的 OpenAlex ID
        fallback_patterns: 用于正则兜底的关键词列表
    返回:
        (打好标签的数据列表, 内部挂靠次数, 外部挂靠次数)
    """
    # 编译正则兜底引擎
    if fallback_patterns:
        fallback_regex = re.compile('|'.join(fallback_patterns), re.IGNORECASE)
    else:
        fallback_regex = None

    internal_count = 0
    external_count = 0

    logging.info(">> 🔍 开始逐篇审查作者背景 (Lineage 溯源)...")
    
    for work in tqdm(raw_works, desc="打标进度 (U1 -> U1.5)"):
        if not work or not work.get("authorships"): 
            continue
            
        for auth in work["authorships"]:
            is_internal = False
            
            # 1. 优先通过官方 ID 或 Lineage (上级机构树) 匹配
            institutions = auth.get("institutions") or []
            for inst in institutions:
                inst_id = inst.get("id", "")
                lineage = inst.get("lineage", [])
                if target_id == inst_id or target_id in lineage:
                    is_internal = True
                    break
            
            # 2. 如果官方没认出来，启动正则兜底防线
            if not is_internal and fallback_regex:
                raw_strs = auth.get("raw_affiliation_strings", [])
                # 兼容部分只有单个 string 的极端情况
                if not raw_strs and auth.get("raw_affiliation_string"):
                    raw_strs = [auth.get("raw_affiliation_string")]
                
                for s in raw_strs:
                    if s and fallback_regex.search(s):
                        is_internal = True
                        break
            
            # 3. 写入打标结果并统计
            auth["is_internal_node"] = is_internal
            
            if is_internal:
                internal_count += 1
            else:
                external_count += 1

    return raw_works, internal_count, external_count

DEFAULT_STOP_WORDS = ["People's Republic of China", "P. R. China", "P.R. China", "PRC", "China", "Beijing"]


def _clean_noise(text: str, stop_words=None) -> str:
    """
    [内部辅助函数] 物理硬规则清洗器，专门对付乱码和冗余信息。
    """
    if not text or not isinstance(text, str):
        return ""

    if stop_words is None:
        stop_words = DEFAULT_STOP_WORDS

    # 1. 剔除邮箱
    text = re.sub(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', '', text)
    # 2. 剔除邮编 (5-7位连续数字)
    text = re.sub(r'\b\d{5,7}\b', '', text)
    # 3. 剔除无用国家/城市名
    for word in stop_words:
        text = re.compile(re.escape(word), re.IGNORECASE).sub('', text)
    # 4. 替换标点符号为空格并去除多余空白
    text = re.sub(r'[.,;，。；]+', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()

    return text

def extract_and_clean_entities(tagged_works: list, nlp_cfg: dict = None,
                               cleaning_cfg: dict = None, labels_cfg: dict = None) -> tuple:
    """
    [核心逻辑] 清洗 U1.5 数据，并提取出用于 AI 聚类的 Unique 实体字典。

    参数:
        tagged_works: 经过 U1.5 打标的数据列表
        nlp_cfg: 阈值参数 (score_threshold / level_threshold)
        cleaning_cfg: 清洗参数 (stop_words)
        labels_cfg: 标签参数 (external)
    返回:
        (清洗后的 U2 数据列表, 提取出的 Unique 实体字典)
    """
    nlp_cfg = nlp_cfg or {}
    cleaning_cfg = cleaning_cfg or {}
    labels_cfg = labels_cfg or {}
    score_threshold = nlp_cfg.get('score_threshold', 0.4)
    level_threshold = nlp_cfg.get('level_threshold', 2)
    stop_words = cleaning_cfg.get('stop_words', DEFAULT_STOP_WORDS)
    external_label = labels_cfg.get('external', '外部合作机构')

    unique_internal_affiliations = set()
    unique_concepts = set()

    logging.info(">> 🧹 开始执行脏数据物理清洗与实体提取...")

    for work in tqdm(tagged_works, desc="清洗进度 (U1.5 -> U2)"):
        if not work: continue

        # 1. 提取高质量领域 (Concepts)
        for c in work.get('concepts') or []:
            # 仅保留大类学科 (level <= level_threshold) 且置信度较高 (score > score_threshold)
            if c and c.get('level', 99) <= level_threshold and c.get('score', 0) > score_threshold:
                name = c.get('display_name')
                if name:
                    unique_concepts.add(name.strip())

        # 2. 清洗机构 (Affiliations)
        for auth in work.get("authorships") or []:
            # 如果是外部人员，直接暴力覆盖为外部标签，节约后续算力
            if not auth.get("is_internal_node"):
                auth["raw_affiliation_strings"] = [external_label]
                continue

            # 如果是内部人员，执行严格的硬规则清洗
            raw_strs = auth.get("raw_affiliation_strings", [])
            cleaned_strs = [_clean_noise(s, stop_words) for s in raw_strs if _clean_noise(s, stop_words)]

            # 记录到集合中去重
            unique_internal_affiliations.update(cleaned_strs)

            # 写回清洗后的干净数据
            auth["raw_affiliation_strings"] = cleaned_strs

    # 构建用于大模型分析的字典
    unique_data = {
        "raw_affiliations": sorted(list(unique_internal_affiliations)),
        "concepts": sorted(list(unique_concepts))
    }

    return tagged_works, unique_data