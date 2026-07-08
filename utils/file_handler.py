# utils/file_handler.py
import json
import pandas as pd
import logging
import os

def load_json(filepath: str):
    if not os.path.exists(filepath):
        # 很多时候中间件还没生成，提示 info 而非 error 更温和
        logging.info(f"⏭️  文件未生成或不存在，跳过加载: {filepath}")
        return None
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"❌ 读取 JSON 失败: {filepath} | 错误: {e}")
        return None

def save_json(data, filepath: str):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logging.info(f"💾 数据已存入: {filepath}")

def load_excel(filepath: str, usecol_index: int = None):
    """
    通用的 Excel 读取器。修复了返回类型不一致的问题。
    """
    if not os.path.exists(filepath):
        logging.warning(f"⚠️ 找不到 Excel 文件: {filepath}")
        # ✨ 关键修复：根据调用方式返回不同的空对象
        return pd.DataFrame() if usecol_index is None else []
        
    try:
        df_raw = pd.read_excel(filepath)
        if usecol_index is not None:
            if df_raw.shape[1] > usecol_index:
                return df_raw.iloc[:, usecol_index].dropna().astype(str).tolist()
            else:
                logging.error(f"❌ Excel 文件不足 {usecol_index + 1} 列。")
                return []
        return df_raw
    except Exception as e:
        logging.error(f"❌ 读取 Excel 失败: {e}")
        # ✨ 关键修复
        return pd.DataFrame() if usecol_index is None else []

def save_excel(df: pd.DataFrame, filepath: str) -> None:
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        df.to_excel(filepath, index=False)
        logging.info(f"✅ Excel 数据已成功保存至: {filepath}")
    except Exception as e:
        logging.error(f"❌ 保存 Excel 失败: {e}")