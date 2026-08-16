# core/constants.py
"""
全局运行时常量 — 单一真相来源
=================================
集中管理跨模块共享的地址/端口等硬编码值，避免在多个文件中重复。

使用方式:
    from core.constants import DASHBOARD_HOST, DASHBOARD_PORT, DASHBOARD_BASE_URL
"""

# 可视化大屏服务端 (FastAPI + ECharts)
DASHBOARD_HOST = "127.0.0.1"
DASHBOARD_PORT = 8001
DASHBOARD_BASE_URL = f"http://{DASHBOARD_HOST}:{DASHBOARD_PORT}"
