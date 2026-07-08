# core/assembler.py
import logging
from tqdm import tqdm
import pandas as pd

def parse_mapping_rules(df_aff: pd.DataFrame, df_con: pd.DataFrame) -> tuple:
    """
    [内部核心] 解析 Excel DataFrame，生成极其严格的映射字典。
    注：这里的表头名称与 Step 3 自动生成的模板完美对齐。
    """
    aff_map = {}
    con_map = {}

    logging.info(">> 📂 正在解析人工校验后的 Excel 映射规则...")

    # 机构映射表预期表头
    AFF_VANGUARD_KEY = '🤖 AI 提取的【排头兵】'
    AFF_STANDARD_KEY = '🧑‍🔧 填写标准名称 (抄左边/填中文/不认识留空)'

    # 1. 解析机构映射表
    if not df_aff.empty:
        # 验证表头
        if AFF_VANGUARD_KEY not in df_aff.columns:
            logging.warning(f"⚠️ 机构映射表缺少列「{AFF_VANGUARD_KEY}」，可用列: {list(df_aff.columns)}")
        if AFF_STANDARD_KEY not in df_aff.columns:
            logging.warning(f"⚠️ 机构映射表缺少列「{AFF_STANDARD_KEY}」，可用列: {list(df_aff.columns)}")

        for _, row in df_aff.iterrows():
            # 兼容各种表头写法，优先读取 Step 3 生成的表头
            vanguard = str(row.get(AFF_VANGUARD_KEY, row.get('提取的【排头兵】', ''))).strip()
            std_name = str(row.get(AFF_STANDARD_KEY, '')).strip()

            if vanguard and std_name and std_name.lower() != 'nan':
                # 检查重复: 同一标准名对应多个排头兵
                existing_vanguard = {v: k for k, v in aff_map.items()}
                if std_name in existing_vanguard:
                    logging.warning(f"⚠️ 重名冲突: 「{vanguard}」与「{existing_vanguard[std_name]}」都映射为「{std_name}」")
                    logging.warning(f"   → 将合并到「{existing_vanguard[std_name]}」")
                else:
                    aff_map[vanguard] = std_name
        logging.info(f"   ✅ 成功加载 {len(aff_map)} 条【机构】映射规则。")

    # 2. 解析领域映射表
    CON_ORIG_KEY = '原始领域名称'
    CON_TARGET_KEY = '填写标准大类 (如：人工智能)'

    if not df_con.empty:
        # 验证表头
        if CON_ORIG_KEY not in df_con.columns:
            logging.warning(f"⚠️ 领域映射表缺少列「{CON_ORIG_KEY}」，可用列: {list(df_con.columns)}")
        if CON_TARGET_KEY not in df_con.columns:
            logging.warning(f"⚠️ 领域映射表缺少列「{CON_TARGET_KEY}」，可用列: {list(df_con.columns)}")

        for _, row in df_con.iterrows():
            raw_orig = str(row.get(CON_ORIG_KEY, '')).strip()
            raw_target = str(row.get(CON_TARGET_KEY, '')).strip()

            if raw_orig and raw_orig.lower() != 'nan':
                # 如果没填目标，默认保留原名；填了，就映射为新大类
                final_target = raw_target if (raw_target and raw_target.lower() != 'nan') else raw_orig
                con_map[raw_orig.lower()] = final_target
        logging.info(f"   ✅ 成功加载 {len(con_map)} 条【领域】映射规则。")
            
    return aff_map, con_map


def _get_standard_name(raw_text: str, aff_map: dict, casia_keys: dict) -> str:
    """[内部辅助] 单个机构字符串的标准化判定逻辑"""
    if not raw_text or str(raw_text) == 'nan':
        return "(未知部门)"
        
    # 1. 优先使用 Excel 字典映射
    if raw_text in aff_map:
        return aff_map[raw_text]
        
    v_upper = str(raw_text).upper()
    
    # 2. 启用 config.yaml 中的金钥匙兜底映射
    for key, std_name in casia_keys.items():
        if key in v_upper:
            return std_name
            
    # 3. 极其特殊的硬编码防线 (可根据实际情况删减)
    if '主机构名称' in v_upper and '另一个名称' in v_upper:
        return "主机构映射"
        
    # 4. 终极垃圾桶兜底
    return " (其他部门)"


def generate_final_u3(u2_5_data: list, aff_map: dict, con_map: dict, casia_keys: dict) -> tuple:
    """
    [暴露的主函数] 终极组装：执行领域严格过滤与机构最终映射。
    """
    logging.info(">> ⚔️ 开始执行 U3 终极清洗替换 (启用严格过滤模式)...")
    
    concept_replace_count = 0 
    concept_dropped_count = 0  
    
    for work in tqdm(u2_5_data, desc="U3 黄金组装"):
        # --- 1. 领域 (Concepts) 严格清洗 ---
        if 'concepts' in work:
            cleaned_concepts = [] 
            for c in work['concepts']:
                orig_name_raw = c.get('display_name', '')
                match_key = str(orig_name_raw).strip().lower()
                
                # 生死判决：只有在 Excel 里出现的，才能活下来
                if match_key in con_map:
                    c['display_name'] = con_map[match_key]
                    cleaned_concepts.append(c)
                    concept_replace_count += 1
                else:
                    concept_dropped_count += 1
            
            # 覆写纯净版领域
            work['concepts'] = cleaned_concepts

        # --- 2. 机构 (Affiliations) 终极映射 ---
        if 'authorships' in work:
            for auth in work['authorships']:
                if not auth.get('is_internal_node'):
                    auth['raw_affiliation_strings'] = ["外部合作机构"]
                    auth['raw_affiliation_string'] = "外部合作机构"
                    continue
                
                raw_strs = auth.get('raw_affiliation_strings', [])
                new_affs = [_get_standard_name(s, aff_map, casia_keys) for s in raw_strs]
                
                auth['raw_affiliation_strings'] = new_affs
                if new_affs:
                    auth['raw_affiliation_string'] = new_affs[0]

    stats = {
        "replace_count": concept_replace_count,
        "dropped_count": concept_dropped_count
    }
    return u2_5_data, stats
