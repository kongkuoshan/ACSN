# core/analyzer.py
import pandas as pd
from sentence_transformers import SentenceTransformer
from sklearn.cluster import AgglomerativeClustering
from collections import defaultdict
from tqdm import tqdm
import logging

def build_cluster_mappings(unique_data: dict, target_clusters: int) -> tuple:
    """
    [核心逻辑] 生成领域 Excel 模板，并利用 NLP 聚类生成机构排头兵及变体映射字典。
    
    参数:
        unique_data: 包含 'concepts' 和 'raw_affiliations' 的字典
        target_clusters: 目标簇的数量 (如 350)
    返回:
        (领域DataFrame, 机构DataFrame, 机构变体映射字典 variant_mapping)
    """
    # ---------------------------------------------------------
    # 1. 通道一：研究领域 (Concepts) - 直接直出
    # ---------------------------------------------------------
    raw_concepts = unique_data.get("concepts", [])
    df_con = pd.DataFrame()
    if raw_concepts:
        logging.info(f"🌌 发现 {len(raw_concepts)} 条领域数据，正在生成领域映射表模板...")
        df_con = pd.DataFrame({
            "原始领域名称": raw_concepts,
            "填写标准大类 (如：人工智能)": ""
        })
    else:
        logging.warning("⚠️ 未发现领域数据 (concepts为空)。")

    # ---------------------------------------------------------
    # 2. 通道二：机构 (Affiliations) - 大模型排头兵聚类
    # ---------------------------------------------------------
    raw_affs = unique_data.get("raw_affiliations", [])
    variant_mapping = {}
    df_aff = pd.DataFrame()

    if raw_affs:
        logging.info(f"🏢 启动 AI 聚类引擎，处理 {len(raw_affs)} 条机构变体...")
        
        # 加载语言模型 (首次运行会自动下载)
        model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        embeddings = model.encode(raw_affs, show_progress_bar=True)

        logging.info(f"🎯 执行层次聚类 (强制输出 {target_clusters} 个簇)...")
        clustering_model = AgglomerativeClustering(
            n_clusters=target_clusters,
            metric='euclidean',
            linkage='ward',
            compute_distances=True
        )
        labels = clustering_model.fit_predict(embeddings)
        logging.info(f"📊 动态等效误差阈值: {clustering_model.distances_[-target_clusters]:.4f}")

        # 将结果按簇分组
        cluster_dict = defaultdict(list)
        for text, label in zip(raw_affs, labels):
            cluster_dict[int(label)].append(text)

        rows = []
        for cid, texts in cluster_dict.items():
            # 💡 提取“排头兵”
            shortest_text = min(texts, key=len)
            longest_text = max(texts, key=len)
            reference = longest_text if len(longest_text) <= 60 else longest_text[:57] + "..."
            
            # 将这个簇里所有的长尾变体，都指向这个最短的“排头兵”
            for text in texts:
                variant_mapping[text] = shortest_text

            rows.append({
                "簇编号": cid,
                "包含变体数": len(texts),
                "🤖 AI 提取的【排头兵】": shortest_text,
                "🧑‍🔧 填写标准名称 (抄左边/填中文/不认识留空)": "",
                "🔍 辅助参考 (可忽略)": reference if reference != shortest_text else ""
            })
        
        df_aff = pd.DataFrame(rows).sort_values(by="包含变体数", ascending=False)
        logging.info(f"✅ 成功生成 {len(df_aff)} 个机构排头兵及其变体映射字典。")

    return df_con, df_aff, variant_mapping


def apply_vanguard_mapping(u2_data: list, variant_mapping: dict) -> list:
    """
    [核心逻辑] 将 U2 数据中的几千种乱七八糟机构，全部坍缩替换为极简的排头兵。
    """
    logging.info(">> 🔄 开始前置替换：将 U2 数据批量坍缩为排头兵 (生成 U2.5)...")
    
    for work in tqdm(u2_data, desc="U2 -> U2.5 坍缩进度"):
        if 'authorships' not in work: continue
        
        for auth in work['authorships']:
            if auth.get('is_internal_node'):
                raw_strs = auth.get('raw_affiliation_strings', [])
                # 核心：内存字典极速映射替换
                new_strs = [variant_mapping.get(s, s) for s in raw_strs]
                
                auth['raw_affiliation_strings'] = new_strs
                if new_strs:
                    auth['raw_affiliation_string'] = new_strs[0]
                    
    return u2_data