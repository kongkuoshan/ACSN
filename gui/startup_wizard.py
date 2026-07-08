# gui/startup_wizard.py
"""
首次运行设置向导

新用户首次启动时的 3 页引导向导:
  1. 欢迎页 — 项目简介
  2. 环境检测页 — Docker / Neo4j 状态
  3. 模式选择页 — 选择运行模式
"""

import os
from pathlib import Path
from PySide6.QtWidgets import (
    QWizard, QWizardPage, QVBoxLayout, QLabel,
    QRadioButton, QPushButton, QButtonGroup, QGroupBox,
    QProgressBar
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont


HOME = Path.home()
SENTINEL_FILE = HOME / ".mkiv_gui_initialized"


def is_first_run() -> bool:
    """检测是否为首次运行"""
    return not SENTINEL_FILE.exists()


def mark_initialized():
    """标记初始化完成 (之后不再弹出向导)"""
    SENTINEL_FILE.write_text("initialized")


class WelcomePage(QWizardPage):
    """第 1 页: 欢迎"""

    def __init__(self):
        super().__init__()
        self.setTitle("欢迎使用 MKIV 学术情报图谱引擎")
        self.setSubTitle("一站式学术情报分析平台 — 从数据采集到可视化大屏")

        layout = QVBoxLayout()

        # 简介
        intro = QLabel(
            "MKIV 是一个面向学术机构的智能情报分析系统。\n\n"
            "它能帮您:\n"
            "  • 🕷 自动爬取 OpenAlex 学术文献数据库\n"
            "  • 🧹 智能清洗和标准化机构与领域名称\n"
            "  • 🤖 利用 NLP 和 LLM 辅助分类\n"
            "  • 📊 一键导入 Neo4j 图数据库\n"
            "  • 🌐 在交互式 ECharts 星图中探索合作网络\n\n"
            "首次使用请跟随向导完成基本设置。"
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("font-size: 14px; line-height: 1.8; padding: 20px;")
        layout.addWidget(intro)

        layout.addStretch()
        self.setLayout(layout)


class EnvCheckPage(QWizardPage):
    """第 2 页: 环境检测"""

    def __init__(self, neo4j_manager=None):
        super().__init__()
        self.setTitle("环境检测")
        self.setSubTitle("检测 Docker 和 Neo4j 的运行环境")

        self._neo4j_mgr = neo4j_manager

        layout = QVBoxLayout()
        layout.setSpacing(15)

        # Docker 状态
        docker_group = QGroupBox("Docker 环境")
        docker_layout = QVBoxLayout(docker_group)
        self._docker_status = QLabel("正在检测...")
        self._docker_status.setStyleSheet("font-size: 14px; padding: 10px;")
        docker_layout.addWidget(self._docker_status)
        layout.addWidget(docker_group)

        # Neo4j 状态
        neo4j_group = QGroupBox("Neo4j 数据库")
        neo4j_layout = QVBoxLayout(neo4j_group)
        self._neo4j_status = QLabel("正在检测...")
        self._neo4j_status.setStyleSheet("font-size: 14px; padding: 10px;")
        neo4j_layout.addWidget(self._neo4j_status)

        self._deploy_btn = QPushButton("🐳 一键部署 Neo4j (Docker)")
        self._deploy_btn.setStyleSheet(
            "background-color: #27ae60; color: white; padding: 10px; "
            "font-weight: bold; font-size: 14px; border-radius: 5px;"
        )
        self._deploy_btn.setVisible(False)
        neo4j_layout.addWidget(self._deploy_btn)

        self._deploy_progress = QProgressBar()
        self._deploy_progress.setVisible(False)
        neo4j_layout.addWidget(self._deploy_progress)

        layout.addWidget(neo4j_group)

        # 提示
        hint = QLabel(
            "💡 提示: 如果已安装 Neo4j (无论本地还是 Docker),\n"
            "  只要连接成功即可继续。Docker 部署为可选步骤。"
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #888; font-size: 12px; padding: 10px;")
        layout.addWidget(hint)

        layout.addStretch()
        self.setLayout(layout)

    def initializePage(self):
        """页面显示时触发"""
        if self._neo4j_mgr:
            self._neo4j_mgr.docker_available.connect(self._on_docker_check)
            self._neo4j_mgr.neo4j_status.connect(self._on_neo4j_check)

    def _on_docker_check(self, available: bool):
        if available:
            self._docker_status.setText("✅ Docker 已安装且可用")
            self._docker_status.setStyleSheet("color: #27ae60; font-size: 14px; padding: 10px;")
            self._deploy_btn.setVisible(True)
        else:
            self._docker_status.setText(
                "❌ Docker 未安装\n\n"
                "请访问 https://www.docker.com/products/docker-desktop/ 下载安装\n"
                "Docker 用于一键部署 Neo4j 数据库 (非必需，可手动安装)"
            )
            self._docker_status.setStyleSheet("color: #e74c3c; font-size: 14px; padding: 10px;")

    def _on_neo4j_check(self, connected: bool, status: str):
        if connected:
            self._neo4j_status.setText(f"✅ Neo4j 已连接 — {status}")
            self._neo4j_status.setStyleSheet("color: #27ae60; font-size: 14px; padding: 10px;")
        else:
            self._neo4j_status.setText(f"❌ Neo4j 未连接 — {status}")
            self._neo4j_status.setStyleSheet("color: #e74c3c; font-size: 14px; padding: 10px;")


class ModeSelectionPage(QWizardPage):
    """第 3 页: 运行模式选择"""

    def __init__(self):
        super().__init__()
        self.setTitle("选择运行模式")
        self.setSubTitle("根据您的需求选择合适的工作模式")

        layout = QVBoxLayout()
        layout.setSpacing(15)

        self._btn_group = QButtonGroup(self)

        # 模式 1
        mode1 = QRadioButton("一键启动大屏 — 直接查看已有图谱数据")
        mode1.setToolTip("适用于已经完成数据导入，仅需查看可视化大屏的情况")
        mode1.setStyleSheet("font-size: 14px; font-weight: bold; padding: 8px;")
        mode1_desc = QLabel("    无需重新爬取数据，直接连接 Neo4j 并启动可视化服务。")
        mode1_desc.setStyleSheet("color: #888; font-size: 12px; padding: 0 0 10px 0;")
        self._btn_group.addButton(mode1, 0)
        layout.addWidget(mode1)
        layout.addWidget(mode1_desc)

        # 模式 2
        mode2 = QRadioButton("完整流水线 — 从爬虫到展示全流程自动执行")
        mode2.setToolTip("适用于首次使用或需要更新全部数据")
        mode2.setStyleSheet("font-size: 14px; font-weight: bold; padding: 8px;")
        mode2_desc = QLabel(
            "    自动执行: 爬虫采集 → 数据清洗 → NLP聚类 → LLM预填 → "
            "终极组装 → 入库 → 启动大屏 (可能需要 10-60 分钟)"
        )
        mode2_desc.setStyleSheet("color: #888; font-size: 12px; padding: 0 0 10px 0;")
        self._btn_group.addButton(mode2, 1)
        layout.addWidget(mode2)
        layout.addWidget(mode2_desc)

        # 模式 3
        mode3 = QRadioButton("分步执行 — 手动选择要执行的具体阶段")
        mode3.setToolTip("适用于调试特定环节或增量更新")
        mode3.setStyleSheet("font-size: 14px; font-weight: bold; padding: 8px;")
        mode3_desc = QLabel(
            "    在左侧面板中手动勾选需要执行的步骤，灵活控制流水线行为。"
        )
        mode3_desc.setStyleSheet("color: #888; font-size: 12px; padding: 0 0 10px 0;")
        self._btn_group.addButton(mode3, 2)
        layout.addWidget(mode3)
        layout.addWidget(mode3_desc)

        # 默认选中完整流水线
        mode2.setChecked(True)

        layout.addStretch()
        self.setLayout(layout)

    def selected_mode(self) -> int:
        """返回选中模式的 ID: 0=大屏, 1=完整流水线, 2=分步执行"""
        return self._btn_group.checkedId()


class StartupWizard(QWizard):
    """首次运行设置向导"""

    def __init__(self, neo4j_manager=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("MKIV 首次运行设置向导")
        self.setWizardStyle(QWizard.ModernStyle)
        self.resize(650, 520)
        self.setStyleSheet("""
            QWizard { background-color: #121212; color: #E0E0E0; }
            QWizardPage { background-color: #121212; }
            QWizard QLabel { color: #E0E0E0; }
        """)

        self._page_env = EnvCheckPage(neo4j_manager)
        self._page_mode = ModeSelectionPage()

        self.addPage(WelcomePage())
        self.addPage(self._page_env)
        self.addPage(self._page_mode)

        self.finished.connect(self._on_finished)

    def _on_finished(self, result):
        if result:
            mark_initialized()
