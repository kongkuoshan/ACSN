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

        # 加载语言模型 (首次运行会自动下载 ~500MB 到 ~/.cache/huggingface/)
        MODEL_NAME = 'paraphrase-multilingual-MiniLM-L12-v2'
        try:
            logging.info(f"   📦 加载 NLP 模型 {MODEL_NAME}...")
            logging.info(f"   💡 首次运行需从 HuggingFace 下载约 500MB 模型文件")
            logging.info(f"   💡 如网络受限，设置环境变量: export HF_ENDPOINT=https://hf-mirror.com")
            model = SentenceTransformer(MODEL_NAME)
            embeddings = model.encode(raw_affs, show_progress_bar=True)
        except (OSError, ConnectionError, TimeoutError) as e:
            logging.error("=" * 60)
            logging.error("❌ 模型下载失败 — 无法连接 HuggingFace")
            logging.error(f"   错误详情: {e}")
            logging.error("   解决方案:")
            logging.error("   1. 设置镜像: export HF_ENDPOINT=https://hf-mirror.com")
            logging.error("   2. 或手动下载模型:")
            logging.error(f"      git clone https://huggingface.co/sentence-transformers/{MODEL_NAME}")
            logging.error(f"      放到 ~/.cache/huggingface/hub/models--sentence-transformers--{MODEL_NAME}/")
            logging.error("=" * 60)
            return pd.DataFrame(), pd.DataFrame(), {}
        except MemoryError:
            logging.error("❌ 内存不足！请关闭其他程序后重试，或减少数据量。")
            return pd.DataFrame(), pd.DataFrame(), {}
        except Exception as e:
            logging.error(f"❌ 模型加载/编码失败: {e}")
            return pd.DataFrame(), pd.DataFrame(), {}

        logging.info(f"🎯 执行层次聚类 (目标 {target_clusters} 簇)...")

        # 对于大批量数据使用 KMeans 避免 O(n²) 内存
        try:
            if len(raw_affs) > 3000:
                from sklearn.cluster import KMeans
                logging.info("   -> 数据量较大，切换为 KMeans 聚类 (内存更安全)")
                clustering_model = KMeans(n_clusters=target_clusters, random_state=42, n_init='auto')
                labels = clustering_model.fit_predict(embeddings)
            else:
                clustering_model = AgglomerativeClustering(
                    n_clusters=target_clusters, metric='euclidean', linkage='ward'
                )
                labels = clustering_model.fit_predict(embeddings)
        except Exception as e:
            logging.error(f"❌ 聚类失败: {e}")
            return pd.DataFrame(), pd.DataFrame(), {}

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