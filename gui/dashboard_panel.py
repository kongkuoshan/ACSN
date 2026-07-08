# gui/dashboard_panel.py
"""
大屏展示面板 — QWebEngineView 内嵌浏览器

加载 FastAPI/ECharts 可视化大屏,
支持自动重试连接、加载状态指示、错误处理。
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import QUrl, QTimer, Qt

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

    def __init__(self, default_url: str = "http://127.0.0.1:8000", parent=None):
        super().__init__(parent)
        self.default_url = default_url
        self._current_url = default_url

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        if HAS_WEBENGINE:
            self._browser = QWebEngineView()

            # 防止白屏闪烁：设置页面背景色 + 禁用透明
            from PySide6.QtGui import QColor
            self._browser.page().setBackgroundColor(QColor(10, 10, 12))
            self._browser.setStyleSheet("background-color: #0a0a0c;")

            self._browser.setHtml(PLACEHOLDER_HTML)
            layout.addWidget(self._browser)
        else:
            # 降级模式: 仅显示提示标签
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
        if url:
            self._current_url = url
        if self._browser and self._current_url:
            self._browser.setUrl(QUrl(self._current_url))

    def show_placeholder(self):
        """显示等待提示页"""
        if self._browser:
            self._browser.setHtml(PLACEHOLDER_HTML)

    def show_loading(self):
        """显示加载中动画"""
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
    # 自动连接
    # ================================================================

    def auto_connect_with_retry(self, url: str = None, max_retries: int = 30, interval_ms: int = 2000):
        """
        自动重试连接大屏服务器。

        参数:
            url: 目标 URL (默认为实例化时设置的值)
            max_retries: 最大重试次数
            interval_ms: 重试间隔 (毫秒)
        """
        if url:
            self._current_url = url

        self.show_loading()
        self._retry_count = 0
        self._max_retries = max_retries

        self._retry_timer = QTimer(self)
        self._retry_timer.timeout.connect(self._on_retry_tick)
        self._retry_timer.start(interval_ms)

    def _on_retry_tick(self):
        """定时器回调: 尝试加载 URL"""
        self._retry_count += 1
        if self._browser:
            # 尝试加载 - 如果服务器未就绪, QWebEngineView 会显示错误页
            self._browser.setUrl(QUrl(self._current_url))

        if self._retry_count >= self._max_retries:
            self._retry_timer.stop()
            self.show_error()
