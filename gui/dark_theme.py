# gui/dark_theme.py
"""
MKIV 学术情报指挥舱 — 深色主题 QSS 样式表
"""

DARK_QSS = """
/* === 全局基础 === */
QMainWindow, QWidget {
    background-color: #121212;
    color: #E0E0E0;
    font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
}

/* === 标签 === */
QLabel {
    font-size: 13px;
    font-weight: bold;
    color: #CCCCCC;
    background: transparent;
}

/* === 输入框与数字选择框 === */
QLineEdit, QSpinBox, QDoubleSpinBox {
    background-color: #1E1E1E;
    color: #4CAF50;
    border: 1px solid #444444;
    padding: 6px 8px;
    border-radius: 4px;
    font-size: 13px;
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #3498db;
}
QLineEdit:disabled, QSpinBox:disabled {
    background-color: #2A2A2A;
    color: #666666;
}

/* === 分组框 === */
QGroupBox {
    border: 1px solid #333333;
    border-radius: 8px;
    margin-top: 16px;
    padding: 16px 10px 10px 10px;
    font-weight: bold;
    font-size: 14px;
    color: #2196F3;
    background-color: #1A1A1A;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
}

/* === 按钮 === */
QPushButton {
    background-color: #2980b9;
    color: white;
    border: none;
    border-radius: 5px;
    font-size: 13px;
    font-weight: bold;
    padding: 8px 16px;
}
QPushButton:hover {
    background-color: #3498db;
}
QPushButton:pressed {
    background-color: #1c6ea4;
}
QPushButton:disabled {
    background-color: #444444;
    color: #777777;
}

/* === 复选框 === */
QCheckBox {
    font-size: 13px;
    font-weight: bold;
    color: #CCCCCC;
    spacing: 8px;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 2px solid #555;
    border-radius: 3px;
    background-color: #1E1E1E;
}
QCheckBox::indicator:checked {
    background-color: #2980b9;
    border-color: #3498db;
}

/* === 多行文本框 === */
QTextEdit, QPlainTextEdit {
    background-color: #0A0A0C;
    color: #00CC66;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 12px;
    border: 1px solid #333333;
    border-radius: 4px;
    padding: 6px;
}

/* === 滚动区域 === */
QScrollArea {
    border: none;
    background: transparent;
}
QScrollBar:vertical {
    background-color: #1A1A1A;
    width: 10px;
    border-radius: 5px;
}
QScrollBar::handle:vertical {
    background-color: #444444;
    border-radius: 5px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover {
    background-color: #555555;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

/* === 分割器 === */
QSplitter::handle {
    background-color: #333333;
    width: 3px;
}
QSplitter::handle:hover {
    background-color: #3498db;
}

/* === 下拉框 === */
QComboBox {
    background-color: #1E1E1E;
    color: #E0E0E0;
    border: 1px solid #444;
    border-radius: 4px;
    padding: 6px 10px;
    font-size: 13px;
    min-width: 120px;
}
QComboBox:hover {
    border: 1px solid #3498db;
}
QComboBox::drop-down {
    border: none;
    width: 24px;
}
QComboBox QAbstractItemView {
    background-color: #1E1E1E;
    color: #E0E0E0;
    selection-background-color: #2980b9;
    border: 1px solid #444;
}

/* === 进度条 === */
QProgressBar {
    background-color: #1E1E1E;
    border: 1px solid #444;
    border-radius: 5px;
    text-align: center;
    font-weight: bold;
    font-size: 12px;
    color: #E0E0E0;
    height: 22px;
}
QProgressBar::chunk {
    background-color: #2980b9;
    border-radius: 4px;
}

/* === 菜单栏 === */
QMenuBar {
    background-color: #1A1A1A;
    color: #CCCCCC;
    border-bottom: 1px solid #333;
    padding: 2px;
}
QMenuBar::item:selected {
    background-color: #2980b9;
}
QMenu {
    background-color: #1E1E1E;
    color: #E0E0E0;
    border: 1px solid #444;
}
QMenu::item:selected {
    background-color: #2980b9;
}

/* === 状态栏 === */
QStatusBar {
    background-color: #1A1A1A;
    color: #999999;
    border-top: 1px solid #333;
    font-size: 12px;
}

/* === 表格 === */
QTableWidget {
    background-color: #1E1E1E;
    color: #E0E0E0;
    border: 1px solid #444;
    gridline-color: #333;
    font-size: 12px;
}
QTableWidget::item:selected {
    background-color: #2980b9;
}
QHeaderView::section {
    background-color: #252525;
    color: #CCCCCC;
    border: 1px solid #444;
    padding: 4px 8px;
    font-weight: bold;
}

/* === 选项卡 === */
QTabWidget::pane {
    border: 1px solid #444;
    background-color: #1A1A1A;
}
QTabBar::tab {
    background-color: #252525;
    color: #999;
    padding: 8px 16px;
    border: 1px solid #333;
    border-bottom: none;
}
QTabBar::tab:selected {
    background-color: #1A1A1A;
    color: #3498db;
    font-weight: bold;
}

/* === 工具提示 === */
QToolTip {
    background-color: #2A2A2A;
    color: #E0E0E0;
    border: 1px solid #555;
    padding: 6px;
    border-radius: 4px;
    font-size: 12px;
}

/* === 列表控件 === */
QListWidget {
    background-color: #1E1E1E;
    color: #E0E0E0;
    border: 1px solid #444;
    border-radius: 4px;
    font-size: 12px;
}
QListWidget::item:selected {
    background-color: #2980b9;
}
"""


def apply_dark_theme(app):
    """将深色主题应用到 QApplication"""
    app.setStyleSheet(DARK_QSS)
