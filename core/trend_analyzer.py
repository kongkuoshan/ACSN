# core/trend_analyzer.py
"""
MKIV 情报分析引擎 — Concept Dimension Reduction & Trend Analytics
=================================================================

复用"排头兵 + AI 打标"模式对研究领域进行降维分析。
从 U3 黄金数据中提取演化趋势、实验室研究倾向、主题分布。

核心功能:
  1. reduce_concept_dimensions() — 概念降维 (SBERT聚类 + LLM命名)
  2. generate_evolution_data()   — 年份×主题演化矩阵 (Theme River)
  3. generate_lab_radar_data()   — 实验室×主题倾向矩阵 (Radar)
  4. generate_topic_distribution() — 层级主题分布 (Sunburst)
"""

import logging
from collections import defaultdict
from tqdm import tqdm

from utils.model_loader import load_sentence_transformer


# ================================================================
# 1. 概念维度降低 — 复用排头兵逻辑
# ================================================================

def reduce_concept_dimensions(u3_data: list, target_clusters: int = 25,
                              api_url: str = None, nlp_cfg: dict = None,
                              llm_cfg: dict = None) -> dict:
    """
    提取 U3 中所有研究领域概念，通过 NLP 聚类 + 可选 LLM 命名
    生成 macro_category 映射表。

    参数:
        u3_data: U3 黄金数据列表
        target_clusters: 目标宏类别数量 (默认 25)
        api_url: LLM API 地址 (None 表示不使用 LLM 命名)
        nlp_cfg: NLP 参数 (model_name)
        llm_cfg: LLM 参数 (concept_naming_prompt 等)

    返回:
        concept_dim_map: {原始概念小写: 宏类别名称}
    """
    nlp_cfg = nlp_cfg or {}
    model_name = nlp_cfg.get('model_name', 'paraphrase-multilingual-MiniLM-L12-v2')

    logging.info(">> 🧠 [Analytics] 启动概念维度降低引擎...")

    # 1. 收集全量唯一概念
    all_concepts = set()
    concept_info = {}  # name -> {level, score} for reference

    for work in tqdm(u3_data, desc="提取全量概念"):
        for c in work.get('concepts', []):
            if not isinstance(c, dict):
                continue
            name = c.get('display_name', '').strip()
            if name and name not in ('Unknown', '未知', 'N/A'):
                all_concepts.add(name)
                if name not in concept_info:
                    concept_info[name] = {
                        'level': c.get('level', 99),
                        'score': c.get('score', 0)
                    }

    unique_concepts = sorted(all_concepts)
    logging.info(f"   -> 提取到 {len(unique_concepts)} 个唯一概念")

    # 2. 如果概念数量很少（如 U3 中已标准化的 ~11 个），直接返回恒等映射
    if len(unique_concepts) <= target_clusters:
        logging.info(f"   -> 概念数 ({len(unique_concepts)}) ≤ 目标簇数 ({target_clusters})，跳过聚类。")
        return {c.lower(): c for c in unique_concepts}

    # 3. NLP 聚类 (仅在概念数量足够多时执行)
    try:
        from sklearn.cluster import AgglomerativeClustering
        import numpy as np

        try:
            model = load_sentence_transformer(model_name)
            embeddings = model.encode(unique_concepts, show_progress_bar=True)
        except (OSError, ConnectionError, TimeoutError) as e:
            logging.warning(f"⚠️ 模型下载失败 (网络不通): {e}")
            logging.warning("   💡 设置 export HF_ENDPOINT=https://hf-mirror.com 后重试")
            return {c.lower(): c for c in unique_concepts}

        n_clusters = min(target_clusters, len(unique_concepts))
        clustering = AgglomerativeClustering(
            n_clusters=n_clusters,
            metric='euclidean',
            linkage='ward'
        )
        labels = clustering.fit_predict(embeddings)

        # 按簇分组
        clusters = defaultdict(list)
        for text, label in zip(unique_concepts, labels):
            clusters[int(label)].append(text)

        # 每个簇选"排头兵" (最短且有代表性的)
        concept_dim_map = {}
        for cid, texts in clusters.items():
            vanguard = min(texts, key=len)
            # 为簇中所有概念分配排头兵名称
            for t in texts:
                concept_dim_map[t.lower()] = vanguard

        logging.info(f"   ✅ NLP 聚类完成: {len(unique_concepts)} 概念 → {n_clusters} 宏类别")

        # 4. LLM 命名 (可选)
        if api_url:
            concept_dim_map = _llm_label_clusters(clusters, concept_dim_map, api_url, llm_cfg)

        return concept_dim_map

    except ImportError as e:
        logging.warning(f"   ⚠️ NLP/LLM 依赖不可用 ({e})，使用原始概念名称。")
        return {c.lower(): c for c in unique_concepts}
    except Exception as e:
        logging.warning(f"   ⚠️ 聚类过程异常 ({e})，使用原始概念名称。")
        return {c.lower(): c for c in unique_concepts}


def _llm_label_clusters(clusters: dict, concept_dim_map: dict, api_url: str,
                        llm_cfg: dict = None) -> dict:
    """使用 LLM 为每个概念簇命名"""
    try:
        from core.llm_labeler import ask_llm

        llm_cfg = llm_cfg or {}
        temperature = llm_cfg.get('temperature', 0)
        max_tokens = llm_cfg.get('max_tokens', 120)
        timeout = llm_cfg.get('request_timeout', 30)
        naming_prompt = llm_cfg.get(
            'concept_naming_prompt',
            "以下研究概念属于同一个主题簇:\n{sample}\n\n请为这个主题簇命名一个 2-6 字的中文名称..."
        )
        system_prompt = llm_cfg.get(
            'concept_naming_system_prompt',
            "你是学术分类专家。请根据输入的概念列表，给出一个简洁的中文主题名称。只输出名称。"
        )

        new_map = {}
        for cid, texts in clusters.items():
            vanguard = min(texts, key=len)
            sample = ', '.join(texts[:5])
            prompt = naming_prompt.format(sample=sample)
            label = ask_llm(api_url, system_prompt, prompt,
                            temperature=temperature, max_tokens=max_tokens, timeout=timeout)
            if label and len(label) > 1:
                for t in texts:
                    new_map[t.lower()] = label
                logging.info(f"   -> 簇 {cid} ({vanguard}...) → LLM命名: {label}")
            else:
                # 回退到排头兵
                for t in texts:
                    new_map[t.lower()] = concept_dim_map.get(t.lower(), vanguard)

        return new_map
    except Exception as e:
        logging.warning(f"   ⚠️ LLM 命名失败 ({e})，保留排头兵名称。")
        return concept_dim_map


# ================================================================
# 2. 演化分析 — Theme River 数据
# ================================================================

def generate_evolution_data(u3_data: list, concept_dim_map: dict = None) -> dict:
    """
    生成研究主题随年份演化的数据矩阵 (用于 ECharts Theme River)。

    返回格式:
    {
        "years": [2020, 2021, ...],
        "categories": ["人工智能", "机器人", ...],
        "data": [
            ["2020", 45, "人工智能"],
            ["2020", 32, "机器人"],
            ...
        ]
    }
    """
    logging.info(">> 📈 [Analytics] 生成研究演化数据...")

    if concept_dim_map is None:
        concept_dim_map = {}

    # year -> macro_category -> count
    year_topic = defaultdict(lambda: defaultdict(int))

    for work in tqdm(u3_data, desc="演化分析"):
        year = work.get('publication_year')
        if not year:
            continue

        for c in work.get('concepts', []):
            if not isinstance(c, dict):
                continue
            name = c.get('display_name', '').strip()
            if not name:
                continue

            macro = concept_dim_map.get(name.lower(), name)
            year_topic[year][macro] += 1

    # 格式化为 ECharts Theme River 需要的格式
    years = sorted(year_topic.keys())
    all_categories = set()
    for yt in year_topic.values():
        all_categories.update(yt.keys())
    categories = sorted(all_categories)

    # data 格式: [[year, count, category], ...]
    data = []
    for year in years:
        for cat in categories:
            count = year_topic[year].get(cat, 0)
            if count > 0:
                data.append([str(year), count, cat])

    result = {
        "years": years,
        "categories": categories,
        "data": data
    }

    logging.info(f"   ✅ 演化分析完成: {len(years)} 年 × {len(categories)} 主题")
    return result


# ================================================================
# 3. 实验室雷达图 — Lab Research Tendency
# ================================================================

def generate_lab_radar_data(u3_data: list, concept_dim_map: dict = None) -> dict:
    """
    生成各实验室/课题组的科研倾向雷达图数据。

    返回格式:
    {
        "labs": ["实验室A", "实验室B", ...],
        "indicators": ["人工智能", "计算机视觉", ...],
        "series": [
            {"name": "实验室A", "value": [35, 20, ...]},
            ...
        ]
    }
    """
    logging.info(">> 🎯 [Analytics] 生成实验室研究倾向雷达数据...")

    if concept_dim_map is None:
        concept_dim_map = {}

    # lab -> macro_category -> count
    lab_topic = defaultdict(lambda: defaultdict(int))
    all_categories = set()

    for work in tqdm(u3_data, desc="实验室分析"):
        # 提取该论文涉及的主题
        work_cats = set()
        for c in work.get('concepts', []):
            if not isinstance(c, dict):
                continue
            name = c.get('display_name', '').strip()
            if name:
                macro = concept_dim_map.get(name.lower(), name)
                work_cats.add(macro)
                all_categories.add(macro)

        # 提取该论文涉及的内部实验室
        work_labs = set()
        for auth in work.get('authorships', []):
            if not auth.get('is_internal_node'):
                continue
            aff = auth.get('raw_affiliation_string',
                           auth.get('raw_affiliation_strings', ['其他单元']))
            if isinstance(aff, list):
                aff = aff[0] if aff else '其他单元'
            if aff and aff != '外部合作机构':
                work_labs.add(aff)

        # 交叉统计
        for lab in work_labs:
            for cat in work_cats:
                lab_topic[lab][cat] += 1

    # 格式化为雷达图数据
    indicators = sorted(all_categories)
    labs = sorted(lab_topic.keys())

    series = []
    for lab in labs:
        values = [lab_topic[lab].get(ind, 0) for ind in indicators]
        # 归一化为百分比
        total = sum(values)
        if total > 0:
            values = [round(v / total * 100, 1) for v in values]
        series.append({"name": lab, "value": values})

    result = {
        "labs": labs,
        "indicators": indicators,
        "series": series
    }

    logging.info(f"   ✅ 雷达分析完成: {len(labs)} 实验室 × {len(indicators)} 维度")
    return result


# ================================================================
# 4. 主题分布 — Sunburst / Treemap
# ================================================================

def generate_topic_distribution(u3_data: list, concept_dim_map: dict = None, nlp_cfg: dict = None) -> dict:
    """
    生成层级主题分布数据 (用于 ECharts Sunburst)。

    返回格式:
    {
        "name": "全部研究",
        "children": [
            {
                "name": "人工智能",
                "value": 450,
                "children": [
                    {"name": "深度学习", "value": 200},
                    ...
                ]
            },
            ...
        ]
    }
    """
    level_threshold = (nlp_cfg or {}).get('level_threshold', 1)

    logging.info(">> 🌳 [Analytics] 生成主题层级分布数据...")

    if concept_dim_map is None:
        concept_dim_map = {}

    # 按 level 构建层级
    # level <= level_threshold: 大类 → 更深层级: 子类
    level_counts = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))

    for work in u3_data:
        for c in work.get('concepts', []):
            if not isinstance(c, dict):
                continue
            name = c.get('display_name', '').strip()
            if not name:
                continue
            level = c.get('level', 99)

            if level <= level_threshold:
                level_counts['L0'][name]['__total__'] += 1
            else:
                # 找其父级概念 (同work中的 level <= level_threshold 概念)
                parent = "其他"
                for cp in work.get('concepts', []):
                    if isinstance(cp, dict) and cp.get('level', 99) <= level_threshold:
                        parent = cp.get('display_name', '其他')
                        break
                level_counts[parent][name]['__total__'] += 1

    # 构建 Sunburst 层级
    children = []
    for parent, sub_topics in level_counts.items():
        if parent == 'L0':
            continue  # L0 作为顶层

        sub_children = []
        parent_total = 0
        for topic, counts in sorted(sub_topics.items(),
                                     key=lambda x: sum(x[1].values()),
                                     reverse=True):
            cnt = sum(counts.values())
            if cnt > 0:
                sub_children.append({"name": topic, "value": cnt})
                parent_total += cnt

        if parent_total > 0:
            children.append({
                "name": parent,
                "value": parent_total,
                "children": sub_children
            })

    # 按 value 排序
    children.sort(key=lambda x: x['value'], reverse=True)

    result = {"name": "全部研究领域", "children": children}

    logging.info(f"   ✅ 主题分布完成: {len(children)} 个大类")
    return result


# ================================================================
# 5. 学者画像 — Individual Scholar Profile
# ================================================================

def generate_scholar_profile(u3_data: list, scholar_id: str,
                             concept_dim_map: dict = None) -> dict:
    """
    为指定学者生成个人研究画像。

    返回:
    {
        "name": "张三",
        "topics": ["人工智能(35)", "计算机视觉(28)", ...],
        "collaborators": ["李四", "王五", ...],
        "lab": "实验室A",
        "publication_years": [2020, 2021, ...],
        "topic_timeline": {"人工智能": [2020, 2021, 2023], ...}
    }
    """
    if concept_dim_map is None:
        concept_dim_map = {}

    scholar_papers = []
    topic_counts = defaultdict(int)
    collaborators = set()
    labs = set()
    years = []

    for work in u3_data:
        found = False
        for auth in work.get('authorships', []):
            if not isinstance(auth, dict):
                continue
            a = auth.get('author', {})
            aid = a.get('id', '')
            if isinstance(aid, str) and aid.endswith(scholar_id):
                found = True
                break

        if not found:
            continue

        scholar_papers.append(work)
        year = work.get('publication_year')
        if year:
            years.append(year)

        for c in work.get('concepts', []):
            if isinstance(c, dict):
                name = c.get('display_name', '').strip()
                if name:
                    macro = concept_dim_map.get(name.lower(), name)
                    topic_counts[macro] += 1

        for auth in work.get('authorships', []):
            if not isinstance(auth, dict):
                continue
            if auth.get('is_internal_node'):
                aff = auth.get('raw_affiliation_string', '')
                if isinstance(aff, list):
                    aff = aff[0] if aff else ''
                if aff:
                    labs.add(aff)
            a = auth.get('author', {})
            c_name = a.get('display_name', '')
            if c_name:
                collaborators.add(c_name)

    # 主题排序
    top_topics = [f"{k}({v})" for k, v in
                  sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)[:10]]

    return {
        "name": f"Scholar_{scholar_id}",
        "topics": top_topics,
        "collaborators": list(collaborators)[:20],
        "lab": list(labs)[0] if labs else "未知",
        "publication_years": sorted(set(years)),
        "total_papers": len(scholar_papers)
    }
