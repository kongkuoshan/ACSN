# core/crawler.py
import os
import time
import requests
import logging
from datetime import datetime
from requests.adapters import HTTPAdapter
from utils.file_handler import load_json, save_json

def run_openalex_crawler(target_id: str, email: str, start_year: int,
                         output_path: str, end_year: int = None,
                         crawler_cfg: dict = None):
    """全量拉取引擎 (带缓存)。爬虫参数从 crawler_cfg 读取 (缺省用默认值)。

    设计要点:
      - 逐页重试: 单页网络抖动/限流只重试该页, 不中断整次抓取。
      - 仅缓存完整结果: 抓取中断时不写缓存, 避免下次误判为有效缓存。
    """
    crawler_cfg = crawler_cfg or {}
    api_url = crawler_cfg.get('api_url', 'https://api.openalex.org/works')
    per_page = crawler_cfg.get('per_page', 200)
    request_timeout = crawler_cfg.get('request_timeout', 60)
    rate_limit_sleep = crawler_cfg.get('rate_limit_sleep', 0.5)
    cache_min_bytes = crawler_cfg.get('cache_min_bytes', 1024)
    retry_total = crawler_cfg.get('retry_total', 5)
    retry_backoff = crawler_cfg.get('retry_backoff', 2)
    retry_status = crawler_cfg.get('retry_status_codes', [429, 500, 502, 503, 504])

    if end_year is None:
        end_year = datetime.now().year
    logging.info(f">> 🌐 [Step 0.1] 准备加载 {target_id} ({start_year}-{end_year}年) 全量文献...")

    # 检查本地缓存 (即 U1.json)
    if os.path.exists(output_path) and os.path.getsize(output_path) > cache_min_bytes:
        logging.info(f">> 📦 发现有效本地缓存 {output_path}，跳过云端抓取。")
        return load_json(output_path)

    logging.info(f">> 🚀 启动云端全量抓取...")

    # 高可用请求会话 (连接池复用, 重试逻辑在下方逐页实现)
    session = requests.Session()
    session.mount('https://', HTTPAdapter(pool_connections=10, pool_maxsize=10))

    all_works = []
    cursor = "*"
    completed = False

    while cursor:
        modern_filter = f'authorships.institutions.lineage:{target_id},publication_year:{start_year}-{end_year}'
        params = {'filter': modern_filter, 'per-page': per_page, 'cursor': cursor, 'mailto': email}

        # 单页重试：网络抖动/限流时只重试本页，不中断整次抓取
        page_ok = False
        fatal = False
        for attempt in range(1, retry_total + 1):
            try:
                resp = session.get(api_url, params=params, timeout=request_timeout)
            except Exception as e:
                wait = retry_backoff * attempt
                logging.warning(f"   ⚠️ 请求异常 ({type(e).__name__})，{wait}s 后重试 ({attempt}/{retry_total})...")
                time.sleep(wait)
                continue

            if resp.status_code == 200:
                data = resp.json()
                results = data.get("results", [])
                all_works.extend(results)
                logging.info(f"   -> 已成功下载 {len(all_works)} 篇文献...")
                cursor = data.get("meta", {}).get("next_cursor")
                page_ok = True
                break
            elif resp.status_code in retry_status:
                wait = retry_backoff * attempt
                logging.warning(f"   ⚠️ HTTP {resp.status_code}（限流/服务端），{wait}s 后重试 ({attempt}/{retry_total})...")
                time.sleep(wait)
            else:
                logging.error(f"   ❌ HTTP {resp.status_code}，非预期状态，终止抓取。")
                fatal = True
                break

        if page_ok:
            # 本页成功；next_cursor 为空表示已取完所有页
            if not cursor:
                completed = True
                break
            time.sleep(rate_limit_sleep)
            continue

        # 本页失败
        if fatal:
            break
        logging.error(f"   ❌ 连续 {retry_total} 次请求失败，终止抓取（已获取 {len(all_works)} 篇）。")
        break

    if completed:
        logging.info(f">> ✅ 云端抓取完成！共获取 {len(all_works)} 篇文献。")
        if all_works:
            save_json(all_works, output_path)
            logging.info(f"   💾 完整数据已缓存到 {output_path}")
    else:
        logging.warning(f">> ⚠️ 云端抓取中断，已获取 {len(all_works)} 篇（未完成，未缓存，下次运行将重抓）。")
    return all_works
