# gui/dashboard_panel.py
"""
大屏展示面板 — QWebEngineView 内嵌浏览器

加载 FastAPI/ECharts 可视化大屏,
支持自动重试连接、加载状态指示、错误处理。

关键设计:
  1. 自动重试时使用后台线程做 HTTP HEAD 探测，不在主线程阻塞。
  2. 只有在服务器确认可连通后才调用 setUrl() 一次加载 — 避免反复 setUrl() 导致白屏闪烁。
  3. 定时器仅检查探测结果 → 不触碰 QWebEngineView 直到就绪。
"""

import threading
import urllib.request
import urllib.error
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import QUrl, QTimer, Qt

from core.constants import DASHBOARD_BASE_URL

# QWebEngineView 是可选的 (某些环境下可能不可用)
try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
    HAS_WEBENGINE = True
except ImportError:
    HAS_WEBENGINE = False


PLACEHOLDER_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        * { margin: 0; padding: 0; }
        body {
            background: #0a0a0c;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
            flex-direction: column;
            color: #555;
        }
        .logo { font-size: 64px; margin-bottom: 20px; }
        .title { font-size: 28px; font-weight: bold; color: #3498db; margin-bottom: 10px; }
        .subtitle { font-size: 16px; color: #666; margin-bottom: 30px; }
        .pulse {
            width: 40px; height: 40px;
            border-radius: 50%;
            background: #3498db;
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0% { transform: scale(1); opacity: 1; }
            50% { transform: scale(1.3); opacity: 0.5; }
            100% { transform: scale(1); opacity: 1; }
        }
        .hint {
            margin-top: 30px;
            font-size: 13px;
            color: #444;
            text-align: center;
            line-height: 1.8;
        }
    </style>
</head>
<body>
    <div class="logo">&#127758;</div>
    <div class="title">MKIV 学术情报指挥舱</div>
    <div class="subtitle">等待流水线处理完毕...</div>
    <div class="pulse"></div>
    <div class="hint">
        提示：点击左侧「开始执行」启动流水线<br>
        或在「运行模式」中选择「一键启动大屏」直接查看已有数据
    </div>
</body>
</html>
"""

LOADING_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body { background: #0a0a0c; display: flex; justify-content: center; align-items: center;
               height: 100vh; font-family: sans-serif; color: #666; flex-direction: column; }
        .spinner { width: 50px; height: 50px; border: 4px solid #333; border-top: 4px solid #3498db;
                   border-radius: 50%; animation: spin 1s linear infinite; margin-bottom: 20px; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    </style>
</head>
<body>
    <div class="spinner"></div>
    <div>正在连接大屏服务器...</div>
    <div style="font-size:12px;margin-top:10px;color:#444;">请确保 Neo4j 数据库已启动</div>
</body>
</html>
"""

ERROR_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body { background: #0a0a0c; display: flex; justify-content: center; align-items: center;
               height: 100vh; font-family: sans-serif; color: #e74c3c; flex-direction: column; }
        .err { font-size: 48px; margin-bottom: 20px; }
        .msg { font-size: 18px; margin-bottom: 10px; }
        .sub { font-size: 13px; color: #666; }
    </style>
</head>
<body>
    <div class="err">&#9888;</div>
    <div class="msg">无法连接到大屏服务</div>
    <div class="sub">请确认 Neo4j 已启动且 U3 数据已导入</div>
</body>
</html>
"""


class DashboardPanel(QWidget):
    """
    大屏展示面板。

    方法:
        load_dashboard(url): 加载指定 URL 的可视化大屏
        show_placeholder(): 显示等待提示页
        show_loading(): 显示加载中动画
        show_error(): 显示连接错误页
        reload(): 刷新当前页
    """

    def __init__(self, default_url: str = DASHBOARD_BASE_URL, parent=None):
        super().__init__(parent)
        self.default_url = default_url
        self._current_url = default_url
        self._probe_generation = 0

        # 防止闪烁穿透: 自身填充纯黑背景
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)
        self.setAutoFillBackground(True)
        from PySide6.QtGui import QPalette, QColor
        pal = self.palette()
        pal.setColor(QPalette.Window, QColor(10, 10, 12))
        self.setPalette(pal)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        if HAS_WEBENGINE:
            self._browser = QWebEngineView()

            # 多层防御: 页面背景 + widget 属性 + 不透明标志
            self._browser.page().setBackgroundColor(QColor(10, 10, 12))
            self._browser.setAttribute(Qt.WA_OpaquePaintEvent, True)
            self._browser.setAutoFillBackground(True)
            self._browser.setStyleSheet("background-color: #0a0a0c; border: none;")

            self._browser.setHtml(PLACEHOLDER_HTML)
            layout.addWidget(self._browser)
        else:
            self._browser = None
            fallback = QLabel(
                "⚠️ QWebEngineView 不可用\n\n"
                "请安装 PySide6-QtWebEngine:\n"
                "pip install PySide6-QtWebEngine\n\n"
                "或直接在浏览器访问: " + default_url
            )
            fallback.setAlignment(Qt.AlignCenter)
            fallback.setStyleSheet("color: #e74c3c; font-size: 16px; padding: 40px;")
            layout.addWidget(fallback)

        self.setStyleSheet("background-color: #0a0a0c;")

    # ================================================================
    # 公共 API
    # ================================================================

    def load_dashboard(self, url: str = None):
        """加载可视化大屏 URL"""
        # 先停止任何进行中的自动重连, 避免旧 URL 覆盖用户当前视图
        self._stop_retry()
        if url:
            self._current_url = url
        if self._browser and self._current_url:
            self._browser.setUrl(QUrl(self._current_url))

    def show_placeholder(self):
        """显示等待提示页"""
        if self._browser:
            self._browser.setHtml(PLACEHOLDER_HTML)

    def show_loading(self):
        """显示加载中动画 (保持显示，不做额外 setUrl 以避免闪烁)"""
        if self._browser:
            self._browser.setHtml(LOADING_HTML)

    def show_error(self):
        """显示连接错误页"""
        if self._browser:
            self._browser.setHtml(ERROR_HTML)

    def reload(self):
        """刷新当前页面"""
        if self._browser:
            self._browser.reload()

    def set_url(self, url: str):
        """更新默认 URL"""
        self._current_url = url

    # ================================================================
    # 自动连接 (不闪烁版本)
    # ================================================================

    def auto_connect_with_retry(self, url: str = None, max_retries: int = 10, interval_ms: int = 3000):
        """
        自动重试连接大屏服务器。

        原理:
          - 显示 LOADING 静态 HTML (旋转动画，不加载任何外部资源)
          - 每 interval_ms 启动一个后台线程做 HTTP HEAD 探测 (timeout=2s)
          - 定时器只检查探测结果: 成功→load URL 一次，失败→继续等
          - QWebEngineView 在就绪前只被 setHtml() 过一次，零闪烁

        参数:
            url: 目标 URL (默认为实例化时设置的值)
            max_retries: 最大重试次数
            interval_ms: 重试间隔 (毫秒)
        """
        if url:
            self._current_url = url

        # 停止之前的定时器（如果有）
        self._stop_retry()

        self.show_loading()
        self._retry_count = 0
        self._max_retries = max_retries
        self._probe_result = None   # None=等待线程结果, True=成功, False=失败
        self._probe_thread = None

        # 立即启动第一次探测
        self._start_probe()

        self._retry_timer = QTimer(self)
        self._retry_timer.timeout.connect(self._on_retry_tick)
        self._retry_timer.start(interval_ms)

    def _start_probe(self):
        """启动后台 HTTP 探测线程"""
        self._probe_generation += 1
        gen = self._probe_generation
        self._probe_result = None
        self._probe_thread = threading.Thread(target=self._do_probe, args=(gen,), daemon=True)
        self._probe_thread.start()

    def _do_probe(self, gen):
        """后台线程: HTTP HEAD 探测服务器是否就绪 (结果仅在代数匹配时写回)"""
        try:
            req = urllib.request.Request(self._current_url, method='HEAD')
            urllib.request.urlopen(req, timeout=2)
            ok = True
        except Exception:
            ok = False
        # 只接受当前代数的结果, 丢弃已过期的在途探测
        if gen == self._probe_generation:
            self._probe_result = ok

    def _on_retry_tick(self):
        """
        定时器回调 (主线程)。

        不做任何 HTTP 请求 — 只检查后台线程的探测结果:
          - None (还跑着): 跳过，等下一个 tick
          - True (成功): 关定时器，加载 URL 一次
          - False (失败): 计数 + 1，达到上限则显示错误，否则启动新探测
        """
        if self._probe_result is None:
            # 上一次探测线程还在运行中，不操作
            return

        if self._probe_result is True:
            # 服务器就绪 → 一次性加载，停止一切
            self._stop_retry()
            if self._browser:
                self._browser.setUrl(QUrl(self._current_url))
            return

        # 探测失败
        self._retry_count += 1
        if self._retry_count >= self._max_retries:
            self._stop_retry()
            self.show_error()
            return

        # 启动新一轮探测
        self._start_probe()

    def _stop_retry(self):
        """停止重试定时器并清理状态"""
        self._probe_generation += 1  # 使在途探测结果失效
        if hasattr(self, '_retry_timer') and self._retry_timer is not None:
            self._retry_timer.stop()
            self._retry_timer = None
