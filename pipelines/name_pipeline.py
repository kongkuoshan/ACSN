# pipelines/name_pipeline.py
import logging
from utils.file_handler import load_excel, save_excel
from core.name_processor import build_name_mapping_dataframe

class NameConversionPipeline:
    """
    姓名转换流水线 (涵盖了你原始的 0 和 0_1 脚本的两种工作模式)
    """
    def __init__(self, config: dict):
        self.config = config

    def run_from_excel(self):
        """模式 1: 从已有的 Excel 中读取名字并转换 (对应 0_1_excel.py)"""
        paths = self.config['paths']
        input_path = paths.get('input_names_excel', paths.get('input_author_excel', ''))
        output_path = paths.get('output_names_excel', paths.get('output_author_excel', ''))
        
        logging.info(">> 🚀 开始执行基于 Excel 的姓名转换流水线...")
        
        # 读取第二列（索引为 1）
        raw_names_list = load_excel(input_path, usecol_index=1)
        if not raw_names_list:
            return
            
        # 核心转换
        df_result = build_name_mapping_dataframe(raw_names_list)
        
        # 结果保存
        save_excel(df_result, output_path)

    def run_from_raw_text(self, raw_text: str):
        """模式 2: 从直接输入的文本转换 (对应 0_trans2.py)"""
        paths = self.config['paths']
        output_path = paths.get('output_names_excel', paths.get('output_author_excel', 'data/output/0_作者匹配画像表.xlsx'))
        
        logging.info(">> 🚀 开始执行基于纯文本的姓名转换流水线...")
        
        raw_names_list = raw_text.split()
        
        # 核心转换
        df_result = build_name_mapping_dataframe(raw_names_list)
        
        # 结果保存
        save_excel(df_result, output_path)