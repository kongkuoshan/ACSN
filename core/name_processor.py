# core/name_processor.py
import pandas as pd
from pypinyin import pinyin, Style

def _chinese_to_western_formatted(name: str) -> str:
    """
    [内部核心算法] 将中文名转换为西式拼音格式。
    - 2字：San Zhang (名和姓首字母均大写)
    - 3字：Sanfeng Zhang (名部分合并且仅首字母大写)
    """
    if not name or not isinstance(name, str):
        return ""
    
    # 获取纯小写拼音列表
    py = [p[0].lower() for p in pinyin(name.strip(), style=Style.NORMAL)]
    
    if len(py) == 0:
        return ""
    if len(py) == 1:
        return py[0].capitalize()
    
    # 姓：第一个字，首字母大写
    surname = py[0].capitalize()
    
    # 名：剩余部分合并，并整体执行 capitalize
    given_name = "".join(py[1:]).capitalize()
    
    return f"{given_name} {surname}"

def build_name_mapping_dataframe(raw_names: list) -> pd.DataFrame:
    """
    [暴露的主函数] 接收人名列表，去重并生成对照表 DataFrame。
    """
    # 1. 去重并保留原始顺序
    unique_names = list(dict.fromkeys([n.strip() for n in raw_names if n.strip()]))

    # 2. 转换拼音
    english_names = [_chinese_to_western_formatted(n) for n in unique_names]

    # 3. 构造要求的 DataFrame 结构
    df = pd.DataFrame({
        "": unique_names,              # 第一列内容，表头为空
        "English Name": english_names  # 第二列内容
    })
    
    return df