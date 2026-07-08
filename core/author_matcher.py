# 创建新文件: core/author_matcher.py
import pandas as pd
from tqdm import tqdm
from collections import Counter
import logging

def _normalize_name(name: str) -> str:
    """特征指纹归一化"""
    return str(name).lower().replace('-', '').replace('.', '').replace(' ', '').strip()

def build_local_database(all_works: list, parent_id: str) -> dict:
    """构建本地学者特征画像数据库"""
    logging.info(">> 🧠 [Step 0.2] 正在提取特征，构建【本地学者画像引擎】...")
    local_author_db = {}
    
    for work in tqdm(all_works, desc="解析学术特征"):
        if not work: continue
        
        concepts = [c.get('display_name') for c in work.get('concepts', []) if c and c.get('score', 0) > 0.4]
        co_authors = [a.get("author", {}).get("id") for a in work.get("authorships", []) if a and a.get("author", {}).get("id")]

        for auth in work.get("authorships", []):
            if not auth: continue
            
            cand_name = auth.get("author", {}).get("display_name", "")
            cand_id_raw = auth.get("author", {}).get("id", "")
            if not cand_id_raw or not cand_name: continue
            cand_id = cand_id_raw.split("/")[-1]

            # 提取 raw strings
            raw_strs = auth.get("raw_affiliation_strings", [])[:]
            if auth.get("raw_affiliation_string"): raw_strs.append(auth.get("raw_affiliation_string"))
            for aff in (auth.get("affiliations") or []):
                if aff.get("raw_affiliation_string"): raw_strs.append(aff.get("raw_affiliation_string"))
            
            clean_raw_strs = list(set([s.strip() for s in raw_strs if s and len(s.strip()) > 5]))
            
            # 判断是否为内部人员
            is_internal = False
            for inst in auth.get("institutions", []):
                if not inst: continue 
                lineage = [l.split("/")[-1] for l in inst.get("lineage", []) if l]
                inst_id = inst.get("id", "").split("/")[-1]
                if parent_id in lineage or inst_id == parent_id:
                    is_internal = True
                    break
                    
            if not is_internal and clean_raw_strs:
                for raw_s in clean_raw_strs:
                    raw_lower = raw_s.lower()
                    if "automation" in raw_lower or "casia" in raw_lower or "自动化" in raw_lower:
                         is_internal = True
                         break
            
            # 记录特征库
            if is_internal:
                fingerprint = _normalize_name(cand_name)
                if fingerprint not in local_author_db:
                    local_author_db[fingerprint] = {}
                    
                if cand_id not in local_author_db[fingerprint]:
                    local_author_db[fingerprint][cand_id] = {
                        'name': cand_name, 'count': 0, 'raw_affiliations': [], 
                        'concepts': [], 'collaborators': set()  
                    }
                
                entry = local_author_db[fingerprint][cand_id]
                entry['count'] += 1
                entry['raw_affiliations'].extend(clean_raw_strs) 
                entry['concepts'].extend([c for c in concepts if c])
                collabs = [aid for aid in co_authors if aid and aid != cand_id_raw]
                entry['collaborators'].update(collabs)
                
    return local_author_db

def match_names_locally(df_input: pd.DataFrame, name_column: str, local_author_db: dict) -> pd.DataFrame:
    """根据输入的名单匹配数据库，生成0号画像表"""
    logging.info(">> ⚡ [Step 0.3] 启动本地画像交叉匹配...")
    if df_input.empty:
        logging.error("❌ 输入名单为空，无法进行画像匹配。")
        return pd.DataFrame()

    if name_column not in df_input.columns:
        logging.error(f"❌ 输入名单中找不到列名「{name_column}」")
        logging.error(f"   可用列名: {list(df_input.columns)}")
        logging.error(f"   请在 config.yaml 中修改 author_matcher.name_column")
        return pd.DataFrame()

    unique_names = df_input[name_column].dropna().unique()
    all_results = []

    for raw_name in tqdm(unique_names, desc="生成画像"):
        raw_name = str(raw_name).strip()
        fingerprint = _normalize_name(raw_name)
        matched_ids_dict = None
        
        if fingerprint in local_author_db:
            matched_ids_dict = local_author_db[fingerprint]
        else:
            parts = str(raw_name).lower().replace('-', ' ').replace('.', '').split()
            if len(parts) == 2:
                reverse_fp = parts[1] + parts[0]
                if reverse_fp in local_author_db:
                    matched_ids_dict = local_author_db[reverse_fp]

        if matched_ids_dict:
            sorted_ids = sorted(matched_ids_dict.items(), key=lambda x: x[1]['count'], reverse=True)
            for index, (aid, data) in enumerate(sorted_ids):
                top_lab = Counter(data['raw_affiliations']).most_common(1)[0][0] if data['raw_affiliations'] else "N/A"
                top_keywords = "N/A"
                if data['concepts']:
                    top_3 = Counter(data['concepts']).most_common(3)
                    top_keywords = " | ".join([f"{k}({v})" for k, v in top_3])
                    
                all_results.append({
                    "原始名单姓名": raw_name, "OpenAlex_ID": aid, "数据库真实姓名": data['name'],
                    "匹配状态": " 内部匹配成功", "ID归属状态": " 主号" if index == 0 else f" 历史分身 {index}",
                    "发文量": data['count'], "高频挂靠实验室(RawStr)": top_lab,
                    "近5年主攻领域": top_keywords, "合作者规模(人)": len(data['collaborators'])
                })
        else:
            all_results.append({
                "原始名单姓名": raw_name, "OpenAlex_ID": None, "数据库真实姓名": "N/A",
                "匹配状态": " 查无此人", "ID归属状态": "N/A", "发文量": 0,
                "高频挂靠实验室(RawStr)": "N/A", "近5年主攻领域": "N/A", "合作者规模(人)": 0
            })

    df_out = pd.DataFrame(all_results)
    if not df_out.empty:
        df_out.sort_values(by=["原始名单姓名", "发文量"], ascending=[True, False], inplace=True)
    return df_out