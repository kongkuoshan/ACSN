# core/llm_labeler.py
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
        "temperature": 0,  # 强制0温度，保证实体提取的绝对稳定性
        "max_tokens": 60
    }
    try:
        res = requests.post(api_url, json=payload, timeout=20)
        res.raise_for_status()
        return res.json()['choices'][0]['message']['content'].strip()
    except Exception as e:
        logging.warning(f"LLM 请求失败 (输入: {user_input[:10]}...): {e}")
        return ""

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
            # 填入 Step 3 生成的表头对应的列
            df_res.at[i, "填写标准大类 (如：人工智能)"] = result
            
    return df_res

def auto_label_affiliations(df_aff: pd.DataFrame, api_url: str, sys_prompt: str) -> pd.DataFrame:
    """为机构表(Affiliations)自动预填标准名称"""
    if df_aff.empty:
        return df_aff
        
    df_res = df_aff.copy()
    for i, row in tqdm(df_res.iterrows(), total=len(df_res), desc="🏢 LLM 机构映射进度"):
        vanguard = str(row.get('🤖 AI 提取的【排头兵】', ''))
        if vanguard:
            result = ask_llm(api_url, sys_prompt, vanguard)
            df_res.at[i, "🧑‍🔧 填写标准名称 (抄左边/填中文/不认识留空)"] = result
            
    return df_res