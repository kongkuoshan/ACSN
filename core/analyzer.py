# core/analyzer.py
import pandas as pd
from utils.model_loader import load_sentence_transformer
from collections import defaultdict
from tqdm import tqdm
import logging

# 模板列名 (机构表与领域表共用排头兵/簇编号/辅助参考列, 只有"填写"列不同)
VANGUARD_COL = '🤖 AI 提取的【排头兵】'
AFF_STANDARD_COL = '🧑‍🔧 填写标准名称 (抄左边/填中文/不认识留空)'
CON_STANDARD_COL = '🧑‍🔧 填写标准大类 (如：人工智能)'
REFERENCE_COL = '🔍 辅助参考 (可忽略)'


def _pick_vanguard(texts, strategy='shortest'):
    """根据策略选择簇内"排头兵" (默认最短名)。"""
    if strategy == 'longest':
        return max(texts, key=len)
    return min(texts, key=len)


def _cluster_texts_to_vanguards(texts, embeddings, target_clusters, nlp_cfg, standard_col):
    """
    [内部辅助] 将一批文本按 embeddings 聚类，产出排头兵模板行与变体映射字典。

    机构与领域两个通道共用这段逻辑，唯一区别是 standard_col (待人工/LLM 填写的列名)。

    返回:
        (rows, variant_mapping)
        rows: 每个簇一行 {簇编号, 包含变体数, 排头兵, standard_col:"", 辅助参考}
        variant_mapping: {原始文本 -> 所在簇的排头兵}
    """
    kmeans_switch = nlp_cfg.get('kmeans_switch_threshold', 3000)
    random_state = nlp_cfg.get('random_state', 42)
    cluster_metric = nlp_cfg.get('cluster_metric', 'euclidean')
    cluster_linkage = nlp_cfg.get('cluster_linkage', 'ward')
    reference_max_len = nlp_cfg.get('reference_max_len', 60)
    vanguard_strategy = nlp_cfg.get('vanguard_strategy', 'shortest')

    # 簇数不能超过样本数，否则 sklearn 直接报错
    n_clusters = min(target_clusters, len(texts))

    if len(texts) > kmeans_switch:
        from sklearn.cluster import KMeans
        logging.info("   -> 数据量较大，切换为 KMeans 聚类 (内存更安全)")
        clustering_model = KMeans(n_clusters=n_clusters, random_state=random_state, n_init='auto')
        labels = clustering_model.fit_predict(embeddings)
    else:
        # 懒加载: sklearn 仅在真正跑聚类时才需要 (打包 EXE 默认不含 sklearn)
        from sklearn.cluster import AgglomerativeClustering
        clustering_model = AgglomerativeClustering(
            n_clusters=n_clusters, metric=cluster_metric, linkage=cluster_linkage
        )
        labels = clustering_model.fit_predict(embeddings)

    # 将结果按簇分组
    cluster_dict = defaultdict(list)
    for text, label in zip(texts, labels):
        cluster_dict[int(label)].append(text)

    rows = []
    variant_mapping = {}
    for cid, texts_in_cluster in cluster_dict.items():
        # 💡 提取"排头兵"
        vanguard = _pick_vanguard(texts_in_cluster, vanguard_strategy)
        longest_text = max(texts_in_cluster, key=len)
        reference = longest_text if len(longest_text) <= reference_max_len else longest_text[:reference_max_len - 3] + "..."

        # 将这个簇里所有的长尾变体，都指向这个"排头兵"
        for text in texts_in_cluster:
            variant_mapping[text] = vanguard

        rows.append({
            "簇编号": cid,
            "包含变体数": len(texts_in_cluster),
            VANGUARD_COL: vanguard,
            standard_col: "",
            REFERENCE_COL: reference if reference != vanguard else ""
        })

    return rows, variant_mapping


def build_cluster_mappings(unique_data: dict, target_clusters: int, nlp_cfg: dict = None) -> tuple:
    """
    [核心逻辑] 利用 NLP 聚类生成机构与领域两张排头兵模板及变体映射字典。

    参数:
        unique_data: 包含 'concepts' 和 'raw_affiliations' 的字典
        target_clusters: 机构目标簇的数量 (如 350)
        nlp_cfg: NLP 参数 (model_name / target_con_clusters / random_state / ... )
    返回:
        (领域DataFrame, 机构DataFrame, 机构变体映射字典, 领域变体映射字典)
    """
    nlp_cfg = nlp_cfg or {}
    model_name = nlp_cfg.get('model_name', 'paraphrase-multilingual-MiniLM-L12-v2')
    target_con_clusters = nlp_cfg.get('target_con_clusters', 100)

    raw_concepts = unique_data.get("concepts", [])
    raw_affs = unique_data.get("raw_affiliations", [])

    df_con = pd.DataFrame()
    df_aff = pd.DataFrame()
    aff_variant_mapping = {}
    con_variant_mapping = {}

    if not raw_affs and not raw_concepts:
        logging.warning("⚠️ 未发现机构变体或研究领域数据。")
        return df_con, df_aff, aff_variant_mapping, con_variant_mapping

    # 加载语言模型 (首次运行会自动下载 ~500MB 到 ~/.cache/huggingface/)
    try:
        logging.info(f"   📦 加载 NLP 模型 {model_name}...")
        logging.info(f"   💡 首次运行需从 HuggingFace 下载约 500MB 模型文件")
        logging.info(f"   💡 如网络受限，设置环境变量: export HF_ENDPOINT=https://hf-mirror.com")
        model = load_sentence_transformer(model_name)
    except (OSError, ConnectionError, TimeoutError) as e:
        logging.error("=" * 60)
        logging.error("❌ 模型下载失败 — 无法连接 HuggingFace")
        logging.error(f"   错误详情: {e}")
        logging.error("   解决方案:")
        logging.error("   1. 设置镜像: export HF_ENDPOINT=https://hf-mirror.com")
        logging.error("   2. 或手动下载模型:")
        logging.error(f"      git clone https://huggingface.co/sentence-transformers/{model_name}")
        logging.error(f"      放到 ~/.cache/huggingface/hub/models--sentence-transformers--{model_name}/")
        logging.error("=" * 60)
        return pd.DataFrame(), pd.DataFrame(), {}, {}
    except MemoryError:
        logging.error("❌ 内存不足！请关闭其他程序后重试，或减少数据量。")
        return pd.DataFrame(), pd.DataFrame(), {}, {}
    except Exception as e:
        logging.error(f"❌ 模型加载失败: {e}")
        return pd.DataFrame(), pd.DataFrame(), {}, {}

    # ---------------------------------------------------------
    # 通道一：机构 (Affiliations) - 大模型排头兵聚类
    # ---------------------------------------------------------
    if raw_affs:
        logging.info(f"🏢 启动 AI 聚类引擎，处理 {len(raw_affs)} 条机构变体...")
        try:
            embeddings = model.encode(raw_affs, show_progress_bar=True)
            logging.info(f"🎯 执行层次聚类 (目标 {target_clusters} 簇)...")
            rows, aff_variant_mapping = _cluster_texts_to_vanguards(
                raw_affs, embeddings, target_clusters, nlp_cfg, AFF_STANDARD_COL
            )
            df_aff = pd.DataFrame(rows).sort_values(by="包含变体数", ascending=False)
            logging.info(f"✅ 成功生成 {len(df_aff)} 个机构排头兵及其变体映射字典。")
        except Exception as e:
            logging.error(f"❌ 机构聚类失败: {e}")
            df_aff = pd.DataFrame()
            aff_variant_mapping = {}
    else:
        logging.warning("⚠️ 未发现机构变体 (raw_affiliations为空)。")

    # ---------------------------------------------------------
    # 通道二：研究领域 (Concepts) - 同款排头兵聚类
    # ---------------------------------------------------------
    if raw_concepts:
        logging.info(f"🌌 启动 AI 聚类引擎，处理 {len(raw_concepts)} 条领域变体...")
        try:
            embeddings = model.encode(raw_concepts, show_progress_bar=True)
            logging.info(f"🎯 执行层次聚类 (目标 {target_con_clusters} 簇)...")
            rows, con_variant_mapping = _cluster_texts_to_vanguards(
                raw_concepts, embeddings, target_con_clusters, nlp_cfg, CON_STANDARD_COL
            )
            df_con = pd.DataFrame(rows).sort_values(by="包含变体数", ascending=False)
            logging.info(f"✅ 成功生成 {len(df_con)} 个领域排头兵及其变体映射字典。")
        except Exception as e:
            logging.error(f"❌ 领域聚类失败: {e}")
            df_con = pd.DataFrame()
            con_variant_mapping = {}
    else:
        logging.warning("⚠️ 未发现领域数据 (concepts为空)。")

    return df_con, df_aff, aff_variant_mapping, con_variant_mapping


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


def apply_concept_vanguard_mapping(u2_data: list, con_variant_mapping: dict) -> list:
    """
    [核心逻辑] 将 U2 数据中的原始领域概念坍缩为所在簇的排头兵，
    并把原始概念名保留在 original_name，供旭日图二级追溯。
    """
    logging.info(">> 🔄 开始前置替换：将 U2 数据的研究领域批量坍缩为排头兵...")

    for work in tqdm(u2_data, desc="U2 -> U2.5 领域坍缩进度"):
        for c in work.get('concepts', []) or []:
            if not isinstance(c, dict):
                continue
            name = str(c.get('display_name', '')).strip()
            # 只坍缩来自 Step 2 的原始概念；未聚类的低置信概念留待 Step 4 剔除
            if name and name in con_variant_mapping:
                if 'original_name' not in c:
                    c['original_name'] = name
                c['display_name'] = con_variant_mapping[name]

    return u2_data
