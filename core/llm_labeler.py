# core/llm_labeler.py
import json
import requests
import pandas as pd
from tqdm import tqdm
import logging


def ask_llm(api_url: str, system_prompt: str, user_input: str) -> str:
    """底层 LLM API 请求封装"""
    payload = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input}
        ],
        "temperature": 0,
        "max_tokens": 120
    }
    try:
        res = requests.post(api_url, json=payload, timeout=30)
        res.raise_for_status()
        return res.json()['choices'][0]['message']['content'].strip()
    except Exception as e:
        logging.warning(f"LLM 请求失败 (输入: {user_input[:20]}...): {e}")
        return ""


# ================================================================
# 领域分类 (单条)
# ================================================================

def auto_label_concepts(df_con: pd.DataFrame, api_url: str, target_fields: str) -> pd.DataFrame:
    """为领域表(Concepts)自动预填分类"""
    if df_con.empty:
        return df_con

    sys_prompt = f"你是一个学术分类专家。请将输入的学科词汇归类到以下列表中的一个：[{target_fields}]。只输出分类名称，严禁任何解释。"
    df_res = df_con.copy()

    for i, row in tqdm(df_res.iterrows(), total=len(df_res), desc="🤖 LLM 领域分类进度"):
        raw_name = str(row.get('原始领域名称', ''))
        if raw_name:
            result = ask_llm(api_url, sys_prompt, raw_name)
            df_res.at[i, "填写标准大类 (如：人工智能)"] = result

    return df_res


# ================================================================
# 机构映射 — 逐条模式 (兼容旧版)
# ================================================================

def auto_label_affiliations(df_aff: pd.DataFrame, api_url: str, sys_prompt: str) -> pd.DataFrame:
    """为机构表(Affiliations)逐条预填标准名称 (旧版兼容)"""
    if df_aff.empty:
        return df_aff

    df_res = df_aff.copy()
    for i, row in tqdm(df_res.iterrows(), total=len(df_res), desc="🏢 LLM 机构映射进度"):
        vanguard = str(row.get('🤖 AI 提取的【排头兵】', ''))
        if vanguard:
            result = ask_llm(api_url, sys_prompt, vanguard)
            df_res.at[i, "🧑‍🔧 填写标准名称 (抄左边/填中文/不认识留空)"] = result

    return df_res


# ================================================================
# 机构映射 — 批量模式 (推荐: 解决一名多类问题)
# ================================================================

def auto_label_affiliations_batch(df_aff: pd.DataFrame, api_url: str,
                                  sys_prompt: str = None) -> pd.DataFrame:
    """
    批量发送所有排头兵给 LLM，让 LLM 看到全景后再分类。

    优势:
      - LLM 能识别相似排头兵属于同一实验室
      - 杜绝「一名多类」问题
      - 大幅减少 API 调用次数

    参数:
        df_aff: 机构映射表 DataFrame (含「🤖 AI 提取的【排头兵】」列)
        api_url: LLM API 地址
        sys_prompt: 自定义提示词 (可选)

    返回:
        填写了标准名称的 DataFrame
    """
    if df_aff.empty:
        return df_aff

    vanguard_col = '🤖 AI 提取的【排头兵】'
    standard_col = '🧑‍🔧 填写标准名称 (抄左边/填中文/不认识留空)'

    if vanguard_col not in df_aff.columns:
        logging.warning("⚠️ 机构表中找不到排头兵列，跳过 LLM 预填。")
        return df_aff

    vanguards = df_aff[vanguard_col].dropna().astype(str).tolist()
    if not vanguards:
        return df_aff

    logging.info(f"🏢 LLM 批量机构映射: {len(vanguards)} 个排头兵 → 分批发送...")

    # 构建批量 prompt
    if sys_prompt is None:
        sys_prompt = (
            "你是一个机构识别专家。你收到一个机构名称变体列表。"
            "请将相似的名称归类到同一个标准名称。"
            "优先使用完整正式名称。不同实验室必须使用不同的标准名称。"
        )

    # 分批发送 (每批最多 80 个, 避免超 token 限制)
    batch_size = 80
    name_map = {}

    for batch_start in tqdm(range(0, len(vanguards), batch_size), desc="🏢 LLM 批量映射"):
        batch = vanguards[batch_start:batch_start + batch_size]
        numbered = "\n".join([f"{i+1}. {v}" for i, v in enumerate(batch)])

        user_prompt = (
            f"以下是一个学术机构的 {len(batch)} 个实验室/部门名称变体。\n"
            f"请将相同实验室的不同写法归类到同一个标准名称。\n\n"
            f"规则:\n"
            f"1. 同一实验室的缩写、别名、嵌套写法 → 统一标准名\n"
            f"2. 如果无法确定属于哪个实验室 → 保留原名称\n"
            f"3. 不同实验室必须有不同的标准名称，严禁重复\n\n"
            f"返回 JSON 格式，键是编号，值是标准名称:\n"
            f'{{"1": "标准名1", "2": "标准名2", ...}}\n\n'
            f"变体列表:\n{numbered}"
        )

        try:
            result = ask_llm(api_url, sys_prompt, user_prompt)
            # 尝试解析 JSON
            json_str = result.strip()
            if json_str.startswith("```"):
                json_str = json_str.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            if not json_str.startswith("{"):
                json_str = "{" + json_str.split("{", 1)[1].rsplit("}", 1)[0] + "}"

            batch_map = json.loads(json_str)

            # 编号 → 排头兵映射
            for num_str, std_name in batch_map.items():
                idx = int(num_str) - 1
                if 0 <= idx < len(batch):
                    name_map[batch[idx]] = str(std_name).strip()

        except Exception as e:
            logging.warning(f"   ⚠️ 批次 {batch_start//batch_size+1} LLM 解析失败: {e}")
            # 回退: 这批用原名
            for v in batch:
                name_map[v] = v

    # 填写结果
    df_res = df_aff.copy()
    for i, row in df_res.iterrows():
        vanguard = str(row.get(vanguard_col, ''))
        std_name = name_map.get(vanguard, vanguard)
        df_res.at[i, standard_col] = std_name

    # 去重检查
    seen = {}
    duplicates = []
    for v, name in name_map.items():
        if name in seen:
            duplicates.append((seen[name], v, name))
        else:
            seen[name] = v

    if duplicates:
        logging.warning(f"⚠️ LLM 仍产生了 {len(duplicates)} 个重名, 已自动合并:")
        for v1, v2, name in duplicates:
            logging.warning(f"   「{v1[:40]}」+「{v2[:40]}」→ 都归为「{name}」")

    logging.info(f"   ✅ 批量映射完成: {len(vanguards)} 排头兵 → {len(seen)} 唯一标准名")
    return df_res


# ================================================================
# 后处理: 合并同名排头兵
# ================================================================

def deduplicate_standard_names(df_aff: pd.DataFrame) -> pd.DataFrame:
    """
    检测并合并 LLM 打标后产生的重名。
    如果两个排头兵被赋予相同的标准名, 将所有变体统一归到最短的排头兵下。
    """
    vanguard_col = '🤖 AI 提取的【排头兵】'
    standard_col = '🧑‍🔧 填写标准名称 (抄左边/填中文/不认识留空)'

    if vanguard_col not in df_aff.columns or standard_col not in df_aff.columns:
        return df_aff

    # 找出重名
    name_to_vanguards = {}
    for _, row in df_aff.iterrows():
        std = str(row.get(standard_col, '')).strip()
        van = str(row.get(vanguard_col, '')).strip()
        if std and std.lower() != 'nan' and van:
            name_to_vanguards.setdefault(std, []).append(van)

    duplicates = {k: v for k, v in name_to_vanguards.items() if len(v) > 1}

    if duplicates:
        logging.info(f"🔧 后处理合并: 发现 {len(duplicates)} 组重名, 正在统一排头兵...")
        for std_name, vans in duplicates.items():
            # 选最短的排头兵作为代表
            canonical = min(vans, key=len)
            logging.info(f"   「{std_name}」: {len(vans)}个排头兵 → 统一为「{canonical}」")
            # 将其他排头兵的标准名改为指向同一个排头兵
            for van in vans:
                mask = df_aff[vanguard_col] == van
                df_aff.loc[mask, standard_col] = canonical

    # ---- 第二遍: 模糊合并相似标准名 (解决跨批次 LLM 命名不一致) ----
    from difflib import SequenceMatcher

    # 收集当前所有唯一标准名
    std_to_vanguards = {}
    for _, row in df_aff.iterrows():
        std = str(row.get(standard_col, '')).strip()
        van = str(row.get(vanguard_col, '')).strip()
        if std and std.lower() != 'nan' and van:
            std_to_vanguards.setdefault(std, []).append(van)

    unique_stds = list(std_to_vanguards.keys())
    if len(unique_stds) > 1:
        merge_map = {}
        SIMILARITY_THRESHOLD = 0.85

        for i, s1 in enumerate(unique_stds):
            if s1 in merge_map:
                continue
            for s2 in unique_stds[i + 1:]:
                if s2 in merge_map:
                    continue
                # 跳过完全相同的 (已在第一遍处理过)
                if s1 == s2:
                    continue
                if SequenceMatcher(None, s1, s2).ratio() > SIMILARITY_THRESHOLD:
                    canonical = s1 if len(s1) <= len(s2) else s2
                    other = s2 if canonical == s1 else s1
                    merge_map[other] = canonical

        if merge_map:
            logging.info(f"🔧 模糊合并: 发现 {len(merge_map)} 对相似标准名")
            for from_name, to_name in merge_map.items():
                vans = std_to_vanguards.get(from_name, [])
                logging.info(f"   「{from_name[:40]}」→「{to_name[:40]}」({len(vans)}个排头兵)")
                for van in vans:
                    mask = df_aff[vanguard_col] == van
                    df_aff.loc[mask, standard_col] = to_name

    return df_aff
