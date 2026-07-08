# gui/main_window.py
"""
MKIV 学术情报指挥舱 — 主窗口

整合参数面板、大屏面板、日志控制台、菜单栏和状态栏。
负责各组件之间的信号/槽连接和全局状态管理。
"""

import os
import logging
from PySide6.QtWidgets import (
    QMainWindow, QSplitter, QDockWidget, QPlainTextEdit,
    QMenuBar, QMenu, QMessageBox, QStatusBar, QLabel,
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton
)
from PySide6.QtCore import Qt, Signal, QTimer, QUrl
from PySide6.QtGui import QAction

from gui.parameter_panel import ParameterPanel
from gui.dashboard_panel import DashboardPanel
from gui.pipeline_runner import PipelineRunner
from gui.neo4j_manager import Neo4jManager
from gui.log_handler import LogSignal, install_gui_logger
from gui.dark_theme import apply_dark_theme
from gui.startup_wizard import StartupWizard, is_first_run, mark_initialized


class MainWindow(QMainWindow):
    """
    MKIV 学术情报指挥舱 — 主窗口

    结构:
        ┌──────────────────────────────────────────┐
        │ Menu Bar                                 │
        ├──────────────┬───────────────────────────┤
        │ Left Panel   │ Right Panel               │
        │ (Parameter)  │ ┌───────────────────────┐ │
        │              │ │ Dashboard (WebEngine) │ │
        │              │ ├───────────────────────┤ │
        │              │ │ Log Console (Dock)    │ │
        │              │ └───────────────────────┘ │
        ├──────────────┴───────────────────────────┤
        │ Status Bar                               │
        └──────────────────────────────────────────┘
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("MKIV 学术情报指挥舱 — 工业级客户端")
        self.resize(1500, 850)

        # 核心组件
        self._pipeline_runner = None
        self._neo4j_manager = Neo4jManager(self)
        self._log_signal = LogSignal()

        # 构建 UI
        self._setup_menu_bar()
        self._setup_central_splitter()
        self._setup_log_dock()
        self._setup_status_bar()

        # 安装日志拦截
        install_gui_logger(self._log_signal, level=logging.INFO)

        # 信号连接
        self._connect_signals()

        # 加载配置
        self._param_panel.load_config()

        # 初始环境检测
        QTimer.singleShot(500, self._initial_env_check)

        # 首次运行向导
        if is_first_run():
            QTimer.singleShot(1000, self._show_startup_wizard)

        logging.info("🌟 MKIV 学术情报指挥舱已就绪。")

    # ================================================================
    # UI 构建
    # ================================================================

    def _setup_menu_bar(self):
        menu_bar = self.menuBar()

        # === 文件 ===
        file_menu = menu_bar.addMenu("文件(&F)")

        save_action = QAction("保存配置(&S)", self)
        save_action.triggered.connect(self._save_config)
        file_menu.addAction(save_action)

        reload_action = QAction("重新加载配置(&R)", self)
        reload_action.triggered.connect(self._reload_config)
        file_menu.addAction(reload_action)

        file_menu.addSeparator()

        exit_action = QAction("退出(&Q)", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # === 工具 ===
        tools_menu = menu_bar.addMenu("工具(&T)")

        check_docker_action = QAction("检测 Docker 环境", self)
        check_docker_action.triggered.connect(self._check_docker)
        tools_menu.addAction(check_docker_action)

        check_neo4j_action = QAction("检测 Neo4j 连接", self)
        check_neo4j_action.triggered.connect(self._check_neo4j)
        tools_menu.addAction(check_neo4j_action)

        tools_menu.addSeparator()

        dashboard_action = QAction("打开大屏 (浏览器)", self)
        dashboard_action.triggered.connect(self._open_dashboard)
        tools_menu.addAction(dashboard_action)

        # === 帮助 ===
        help_menu = menu_bar.addMenu("帮助(&H)")

        wizard_action = QAction("重新运行设置向导", self)
        wizard_action.triggered.connect(self._show_startup_wizard)
        help_menu.addAction(wizard_action)

        help_menu.addSeparator()

        about_action = QAction("关于 MKIV", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _setup_central_splitter(self):
        splitter = QSplitter(Qt.Horizontal, self)
        self.setCentralWidget(splitter)

        # 左侧: 参数面板
        self._param_panel = ParameterPanel(config_path="config/config.yaml")
        splitter.addWidget(self._param_panel)

        # 右侧: 大屏面板 + 视图切换栏
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # 视图切换导航栏
        nav_widget = QWidget()
        nav_widget.setStyleSheet("background-color: #121216; border-bottom: 1px solid #222;")
        nav_layout = QHBoxLayout(nav_widget)
        nav_layout.setContentsMargins(12, 6, 12, 6)
        nav_layout.setSpacing(8)

        self.btn_graph_view = QPushButton("🕸️ 关系星图")
        self.btn_analytics_view = QPushButton("📈 情报分析")
        for btn in [self.btn_graph_view, self.btn_analytics_view]:
            btn.setCheckable(True)
            btn.setFixedHeight(32)
            btn.setStyleSheet("""
                QPushButton { padding: 6px 16px; border: 1px solid #333; border-radius: 6px;
                              background: #16161a; color: #aaa; font-size: 12px; font-weight: 600; }
                QPushButton:hover { border-color: #555; color: #fff; }
                QPushButton:checked { background: #1a2a3a; border-color: #3498db; color: #3498db; }
            """)

        self.btn_graph_view.setChecked(True)
        self.btn_graph_view.clicked.connect(lambda: self._switch_view("graph"))
        self.btn_analytics_view.clicked.connect(lambda: self._switch_view("analytics"))

        nav_layout.addWidget(self.btn_graph_view)
        nav_layout.addWidget(self.btn_analytics_view)
        nav_layout.addStretch()

        right_layout.addWidget(nav_widget)

        # 大屏面板
        self._dashboard_panel = DashboardPanel()
        right_layout.addWidget(self._dashboard_panel, 1)

        splitter.addWidget(right_container)

        # 初始比例 35:65
        splitter.setSizes([420, 1080])
        self._splitter = splitter

    def _switch_view(self, view: str):
        """切换右侧大屏视图: graph (关系星图) 或 analytics (情报分析)"""
        if view == "graph":
            self._dashboard_panel.load_dashboard("http://127.0.0.1:8000/")
            self.btn_graph_view.setChecked(True)
            self.btn_analytics_view.setChecked(False)
        else:
            self._dashboard_panel.load_dashboard("http://127.0.0.1:8000/analytics")
            self.btn_graph_view.setChecked(False)
            self.btn_analytics_view.setChecked(True)

    def _setup_log_dock(self):
        """底部日志面板 (可停靠)"""
        self._log_dock = QDockWidget("💻 系统实时运行日志", self)
        self._log_dock.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.RightDockWidgetArea)

        self._log_output = QPlainTextEdit()
        self._log_output.setReadOnly(True)
        self._log_output.setMaximumBlockCount(5000)  # 限制行数, 防止内存溢出
        self._log_output.setStyleSheet(
            "QPlainTextEdit { background-color: #0A0A0C; color: #00CC66; "
            "font-family: 'Consolas', 'Courier New', monospace; font-size: 12px; "
            "border: 1px solid #333; border-radius: 4px; }"
        )

        self._log_dock.setWidget(self._log_output)
        self.addDockWidget(Qt.BottomDockWidgetArea, self._log_dock)

        # 日志信号 -> 文本框
        self._log_signal.message.connect(self._append_log)

    def _setup_status_bar(self):
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)

        self._status_labels = {
            "docker": QLabel("Docker: 检测中..."),
            "neo4j": QLabel("Neo4j: 检测中..."),
            "progress": QLabel("就绪"),
        }
        self._status_bar.addWidget(self._status_labels["docker"])
        self._status_bar.addWidget(QLabel(" | "))
        self._status_bar.addWidget(self._status_labels["neo4j"])
        self._status_bar.addWidget(QLabel(" | "))
        self._status_bar.addWidget(self._status_labels["progress"])

    # ================================================================
    # 信号连接
    # ================================================================

    def _connect_signals(self):
        # 参数面板 -> 主窗口
        self._param_panel.start_requested.connect(self._on_start_pipeline)
        self._param_panel.stop_requested.connect(self._on_stop_pipeline)
        self._param_panel.deploy_neo4j_requested.connect(self._on_deploy_neo4j)

        # Neo4j 管理器 -> 状态栏
        self._neo4j_manager.docker_available.connect(self._on_docker_status)
        self._neo4j_manager.neo4j_status.connect(self._on_neo4j_status)
        self._neo4j_manager.deploy_finished.connect(self._on_deploy_finished)
        self._neo4j_manager.log_message.connect(lambda m: logging.info(m))
        self._neo4j_manager.operation_progress.connect(self._param_panel.update_progress)

    # ================================================================
    # 流水线控制
    # ================================================================

    def _on_start_pipeline(self, stages: list, mode: str):
        """用户点击「开始执行」"""
        # 先保存当前配置
        self._save_config()

        self._param_panel.set_running(True)
        self._param_panel.update_progress(0, "正在初始化...")
        self._dashboard_panel.show_loading()

        # 创建并启动流水线工作线程
        self._pipeline_runner = PipelineRunner(
            config=self._param_panel.config,
            stages=stages,
            parent=self
        )
        self._pipeline_runner.stage_started.connect(self._on_stage_started)
        self._pipeline_runner.stage_completed.connect(self._on_stage_completed)
        self._pipeline_runner.overall_progress.connect(self._param_panel.update_progress)
        self._pipeline_runner.log_line.connect(lambda m: logging.info(m))
        self._pipeline_runner.pipeline_finished.connect(self._on_pipeline_finished)

        self._pipeline_runner.start()
        self._status_labels["progress"].setText(f"运行中: {mode}")

    def _on_stop_pipeline(self):
        """用户点击「停止」"""
        if self._pipeline_runner and self._pipeline_runner.isRunning():
            self._pipeline_runner.stop()
            self._status_labels["progress"].setText("正在停止...")

    def _on_stage_started(self, stage_name: str):
        logging.info(f"▶ 开始执行: {stage_name}")
        self._status_labels["progress"].setText(f"执行中: {stage_name}")

    def _on_stage_completed(self, stage_name: str, success: bool):
        status = "✅" if success else "❌"
        logging.info(f"{status} 阶段完成: {stage_name}")

    def _on_pipeline_finished(self, success: bool, message: str):
        """流水线全部完成"""
        self._param_panel.set_running(False)
        self._param_panel.update_progress(100, "完成" if success else "中断")

        if success:
            self._status_labels["progress"].setText("完成 — 大屏已启动")
            # 加载大屏
            QTimer.singleShot(2000, lambda: self._dashboard_panel.auto_connect_with_retry(max_retries=15))
            logging.info(f"🎉 {message}")
        else:
            self._status_labels["progress"].setText("已中断")
            logging.error(f"⚠️ {message}")

    # ================================================================
    # Neo4j 部署
    # ================================================================

    def _on_deploy_neo4j(self):
        """用户点击一键部署 Neo4j"""
        reply = QMessageBox.question(
            self, "确认部署",
            "此操作需要您的电脑已安装 Docker。\n\n"
            "系统将自动下载 Neo4j 镜像 (约 500MB)\n"
            "并启动数据库容器。\n\n"
            "确定执行吗？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        self._save_config()
        config = self._param_panel.config
        self._neo4j_manager.deploy_neo4j(
            uri=config['database']['uri'],
            user=config['database']['user'],
            password=config['database']['password'],
            import_dir=(config.get('author_matcher', {}).get('neo4j_import_dir') or
                        config.get('paths', {}).get('neo4j_import_dir') or
                        './data/import')
        )

    # ================================================================
    # 环境检测
    # ================================================================

    def _initial_env_check(self):
        """启动时检测环境"""
        self._neo4j_manager.check_docker()
        config = self._param_panel.config or {}
        db = config.get('database', {})
        self._neo4j_manager.check_neo4j_connection(
            uri=db.get('uri', 'bolt://localhost:7688'),
            user=db.get('user', 'neo4j'),
            password=db.get('password', '12345678')
        )

    def _check_docker(self):
        self._neo4j_manager.check_docker()

    def _check_neo4j(self):
        config = self._param_panel.config
        if not config:
            self._load_and_check_neo4j()
            return
        db = config.get('database', {})
        self._neo4j_manager.check_neo4j_connection(
            uri=db.get('uri', 'bolt://localhost:7688'),
            user=db.get('user', 'neo4j'),
            password=db.get('password', '12345678')
        )

    def _load_and_check_neo4j(self):
        """从文件加载配置后再检测"""
        import yaml
        try:
            with open("config/config.yaml", 'r', encoding='utf-8') as f:
                cfg = yaml.safe_load(f)
            db = cfg.get('database', {})
            self._neo4j_manager.check_neo4j_connection(
                uri=db.get('uri', 'bolt://localhost:7688'),
                user=db.get('user', 'neo4j'),
                password=db.get('password', '12345678')
            )
        except Exception as e:
            logging.warning(f"无法读取配置进行 Neo4j 检测: {e}")

    # ================================================================
    # 配置管理
    # ================================================================

    def _save_config(self):
        self._param_panel.save_config()
        self._status_labels["progress"].setText("配置已保存")

    def _reload_config(self):
        self._param_panel.load_config()
        self._status_labels["progress"].setText("配置已重新加载")

    # ================================================================
    # 菜单操作
    # ================================================================

    def _open_dashboard(self):
        """在系统默认浏览器打开大屏"""
        import webbrowser
        url = self._dashboard_panel.default_url
        webbrowser.open(url)
        logging.info(f"🌐 已在默认浏览器打开: {url}")

    def _show_startup_wizard(self):
        wizard = StartupWizard(self)
        wizard.finished.connect(self._on_wizard_finished)
        wizard.exec()

    def _on_wizard_finished(self, result):
        if result:
            # 用户完成向导后刷新环境检测
            self._initial_env_check()

    def _show_about(self):
        from gui import __version__
        QMessageBox.about(
            self, "关于 MKIV",
            f"<h2>MKIV 学术情报图谱引擎</h2>"
            f"<p>版本: {__version__}</p>"
            f"<p>一个面向学术机构的智能情报分析平台，</p>"
            f"<p>集成爬虫、数据清洗、NLP 聚类、</p>"
            f"<p>LLM 标注、图数据库和可视化大屏。</p>"
            f"<hr>"
            f"<p style='color:#888;font-size:11px;'>"
            f"基于 OpenAlex | Neo4j | ECharts | PySide6</p>"
        )

    # ================================================================
    # 日志
    # ================================================================

    def _append_log(self, message: str, levelno: int):
        """将日志追加到底部控制台"""
        self._log_output.appendPlainText(message)

    # ================================================================
    # 状态更新回调
    # ================================================================

    def _on_docker_status(self, available: bool):
        text = "Docker: ✅" if available else "Docker: ❌ 未安装"
        color = "#27ae60" if available else "#e74c3c"
        self._status_labels["docker"].setText(text)
        self._status_labels["docker"].setStyleSheet(f"color: {color}; font-size: 12px; font-weight: bold;")
        if not available:
            self._status_labels["docker"].setToolTip("点击 工具→检测Docker 重新检查")

    def _on_neo4j_status(self, connected: bool, status: str):
        text = f"Neo4j: {'✅' if connected else '❌'} {status}"
        color = "#27ae60" if connected else "#e74c3c"
        self._status_labels["neo4j"].setText(text)
        self._status_labels["neo4j"].setStyleSheet(f"color: {color}; font-size: 12px; font-weight: bold;")

    def _on_deploy_finished(self, success: bool, message: str):
        if success:
            QMessageBox.information(self, "部署完成", f"Neo4j 已成功部署!\n\n{message}")
        else:
            QMessageBox.warning(self, "部署失败", f"部署过程中出现问题:\n\n{message}")

    # ================================================================
    # 窗口事件
    # ================================================================

    def closeEvent(self, event):
        """关闭窗口前的清理"""
        if self._pipeline_runner and self._pipeline_runner.isRunning():
            reply = QMessageBox.question(
                self, "确认退出",
                "流水线仍在运行中。确定退出吗？",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                event.ignore()
                return
            self._pipeline_runner.stop()
            self._pipeline_runner.wait(5000)

        # 尝试停止可视化服务器
        try:
            from core.visualizer import stop_visualizer_server
            stop_visualizer_server()
        except Exception:
            pass

        event.accept()
