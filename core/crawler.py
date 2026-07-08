# core/crawler.py
import os
import time
import requests
import logging
from datetime import datetime
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from utils.file_handler import load_json, save_json

def run_openalex_crawler(target_id: str, email: str, start_year: int,
                         output_path: str, end_year: int = None):
    """工业级全量拉取引擎 (带断点续传与缓存)"""
    if end_year is None:
        end_year = datetime.now().year
    logging.info(f">> 🌐 [Step 0.1] 准备加载 {target_id} ({start_year}-{end_year}年) 全量文献...")
    
    # 检查本地缓存 (即 U1.json)
    if os.path.exists(output_path) and os.path.getsize(output_path) > 1024:
        logging.info(f">> 📦 发现有效本地缓存 {output_path}，跳过云端抓取。")
        return load_json(output_path)

    logging.info(f">> 🚀 启动云端全量抓取...")
    
    # 配置高可用请求会话
    session = requests.Session()
    retries = Retry(total=5, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    session.mount('https://', HTTPAdapter(max_retries=retries, pool_connections=10))
    
    api_url = "https://api.openalex.org/works"
    all_works = []
    cursor = "*" 
    
    try:
        while cursor:
            modern_filter = f'authorships.institutions.lineage:{target_id},publication_year:{start_year}-{end_year}'
            params = {'filter': modern_filter, 'per-page': 200, 'cursor': cursor, 'mailto': email}
            
            resp = session.get(api_url, params=params, timeout=30)
            if resp.status_code != 200: 
                break
            data = resp.json()
            results = data.get("results", [])
            if not results: break
            
            all_works.extend(results)
            logging.info(f"   -> 已成功下载 {len(all_works)} 篇文献...")
            
            cursor = data.get("meta", {}).get("next_cursor")
            if not cursor: break
            time.sleep(0.15) 
            
    except Exception as e:
        logging.error(f"❌ 爬虫异常中断: {e}")

    logging.info(f">> ✅ 云端抓取完成！共获取 {len(all_works)} 篇文献。")
    if all_works:
        save_json(all_works, output_path)
    return all_works