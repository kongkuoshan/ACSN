# gui/widgets.py
"""
可复用的 GUI 组件工厂函数
"""

import os
from PySide6.QtWidgets import (
    QPushButton, QHBoxLayout, QLabel, QMessageBox, QFileDialog,
    QLineEdit, QToolButton
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon

from gui.help_texts import HELP


def make_help_btn(param_key: str, parent=None):
    """
    创建一个圆形 ? 帮助按钮。
    点击后弹出包含中文帮助文本的对话框。

    参数:
        param_key: 在 HELP 字典中的键名
        parent: 父级 widget
    """
    btn = QToolButton(parent)
    btn.setText("?")
    btn.setFixedSize(22, 22)
    btn.setToolTip("点击查看帮助说明")
    btn.setStyleSheet("""
        QToolButton {
            border-radius: 11px;
            background-color: #444444;
            color: white;
            font-weight: bold;
            font-size: 12px;
            padding: 0;
            border: none;
        }
        QToolButton:hover {
            background-color: #3498db;
        }
    """)
    btn.setCursor(Qt.PointingHandCursor)

    help_text = HELP.get(param_key, f"暂无帮助信息: {param_key}")
    title = param_key.split(".")[-1]

    def show_help():
        QMessageBox.information(parent, f"帮助 — {title}", help_text)

    btn.clicked.connect(show_help)
    return btn


def create_text_row(label_text: str, default: str = "", param_key: str = "",
                    placeholder: str = "", password: bool = False, parent=None):
    """
    创建标准文本输入行: [Label] [Input] [?]

    返回: (row_layout, line_edit, help_btn)
    """
    layout = QHBoxLayout()
    layout.setContentsMargins(0, 2, 0, 2)

    label = QLabel(label_text)
    label.setMinimumWidth(130)
    layout.addWidget(label)

    line_edit = QLineEdit(default)
    if placeholder:
        line_edit.setPlaceholderText(placeholder)
    if password:
        line_edit.setEchoMode(QLineEdit.Password)
    line_edit.setMinimumHeight(28)
    layout.addWidget(line_edit, 1)

    if param_key and param_key in HELP:
        btn = make_help_btn(param_key, parent)
        layout.addWidget(btn)

    return layout, line_edit


def create_file_row(label_text: str, default: str = "", param_key: str = "",
                    file_filter: str = "All Files (*)", parent=None):
    """
    创建文件选择行: [Label] [Path Input] [Browse...] [?]

    返回: (row_layout, line_edit, browse_btn)
    """
    layout = QHBoxLayout()
    layout.setContentsMargins(0, 2, 0, 2)

    label = QLabel(label_text)
    label.setMinimumWidth(130)
    layout.addWidget(label)

    line_edit = QLineEdit(default)
    line_edit.setMinimumHeight(28)
    line_edit.setPlaceholderText("点击右侧浏览按钮选择文件...")
    layout.addWidget(line_edit, 1)

    def browse():
        path, _ = QFileDialog.getOpenFileName(parent, f"选择 {label_text}", os.path.dirname(default) if default else os.getcwd(), file_filter)
        if path:
            line_edit.setText(path)

    browse_btn = QPushButton("浏览...")
    browse_btn.setFixedWidth(60)
    browse_btn.clicked.connect(browse)
    layout.addWidget(browse_btn)

    if param_key and param_key in HELP:
        btn = make_help_btn(param_key, parent)
        layout.addWidget(btn)

    return layout, line_edit


def create_dir_row(label_text: str, default: str = "", param_key: str = "", parent=None):
    """
    创建目录选择行: [Label] [Path Input] [Browse...] [?]
    """
    layout = QHBoxLayout()
    layout.setContentsMargins(0, 2, 0, 2)

    label = QLabel(label_text)
    label.setMinimumWidth(130)
    layout.addWidget(label)

    line_edit = QLineEdit(default)
    line_edit.setMinimumHeight(28)
    line_edit.setPlaceholderText("点击右侧浏览按钮选择目录...")
    layout.addWidget(line_edit, 1)

    def browse():
        path = QFileDialog.getExistingDirectory(parent, f"选择 {label_text}", default if default else os.getcwd())
        if path:
            line_edit.setText(path)

    browse_btn = QPushButton("浏览...")
    browse_btn.setFixedWidth(60)
    browse_btn.clicked.connect(browse)
    layout.addWidget(browse_btn)

    if param_key and param_key in HELP:
        btn = make_help_btn(param_key, parent)
        layout.addWidget(btn)

    return layout, line_edit


def create_int_row(label_text: str, default: int = 0, param_key: str = "",
                   min_val: int = 0, max_val: int = 999999, parent=None):
    """
    创建整数输入行: [Label] [SpinBox] [?]
    """
    from PySide6.QtWidgets import QSpinBox

    layout = QHBoxLayout()
    layout.setContentsMargins(0, 2, 0, 2)

    label = QLabel(label_text)
    label.setMinimumWidth(130)
    layout.addWidget(label)

    spin = QSpinBox()
    spin.setRange(min_val, max_val)
    spin.setValue(default)
    spin.setMinimumHeight(28)
    layout.addWidget(spin, 1)

    if param_key and param_key in HELP:
        btn = make_help_btn(param_key, parent)
        layout.addWidget(btn)

    return layout, spin


def create_checkbox_row(label_text: str, default: bool = False,
                        param_key: str = "", parent=None):
    """
    创建复选框行: [CheckBox (label)] [?]
    """
    from PySide6.QtWidgets import QCheckBox

    layout = QHBoxLayout()
    layout.setContentsMargins(0, 2, 0, 2)

    checkbox = QCheckBox(label_text)
    checkbox.setChecked(default)
    layout.addWidget(checkbox, 1)

    if param_key and param_key in HELP:
        btn = make_help_btn(param_key, parent)
        layout.addWidget(btn)

    return layout, checkbox


def create_textarea_row(label_text: str, default: str = "", param_key: str = "",
                        rows: int = 3, parent=None):
    """
    创建多行文本输入行: [Label] [TextEdit] [?]
    """
    from PySide6.QtWidgets import QTextEdit

    layout = QHBoxLayout()
    layout.setContentsMargins(0, 2, 0, 2)

    label = QLabel(label_text)
    label.setMinimumWidth(130)
    label.setAlignment(Qt.AlignTop)
    layout.addWidget(label)

    text_edit = QTextEdit()
    text_edit.setPlainText(default)
    text_edit.setMaximumHeight(rows * 28)
    text_edit.setMinimumHeight(60)
    layout.addWidget(text_edit, 1)

    if param_key and param_key in HELP:
        btn = make_help_btn(param_key, parent)
        layout.addWidget(btn)

    return layout, text_edit


def create_kv_table_row(label_text: str, data: dict = None, param_key: str = "",
                        key_header: str = "关键字", val_header: str = "值", parent=None):
    """
    创建键值对表格编辑行: [Label] [Table + Add/Del buttons] [?]

    返回: (row_layout, table_widget)
    """
    from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView
    from PySide6.QtCore import Qt as QtCore

    layout = QHBoxLayout()
    layout.setContentsMargins(0, 2, 0, 2)

    label = QLabel(label_text)
    label.setMinimumWidth(130)
    label.setAlignment(QtCore.AlignTop)
    layout.addWidget(label)

    # 表格 + 按钮容器
    table_container = QVBoxLayout()
    table_container.setSpacing(4)

    table = QTableWidget(0, 2)
    table.setHorizontalHeaderLabels([key_header, val_header])
    table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
    table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
    table.setMaximumHeight(150)
    table.setMinimumHeight(80)
    table.setStyleSheet("""
        QTableWidget { background-color: #1E1E1E; color: #E0E0E0; border: 1px solid #444; }
        QTableWidget::item { padding: 2px; }
        QHeaderView::section { background-color: #252525; color: #CCC; border: 1px solid #444; padding: 2px; }
    """)

    # 初始数据
    if data:
        for k, v in data.items():
            if k:
                table.insertRow(table.rowCount())
                table.setItem(table.rowCount() - 1, 0, QTableWidgetItem(str(k)))
                table.setItem(table.rowCount() - 1, 1, QTableWidgetItem(str(v)))

    table_container.addWidget(table)

    # 增删按钮
    btn_row = QHBoxLayout()
    btn_add = QPushButton("+ 添加行")
    btn_add.setFixedHeight(24)
    btn_add.setStyleSheet("font-size: 11px; padding: 2px 8px;")
    btn_del = QPushButton("- 删除选中行")
    btn_del.setFixedHeight(24)
    btn_del.setStyleSheet("font-size: 11px; padding: 2px 8px; background-color: #c0392b;")

    def add_row():
        table.insertRow(table.rowCount())
        table.setItem(table.rowCount() - 1, 0, QTableWidgetItem(""))
        table.setItem(table.rowCount() - 1, 1, QTableWidgetItem(""))

    def del_row():
        row = table.currentRow()
        if row >= 0:
            table.removeRow(row)

    btn_add.clicked.connect(add_row)
    btn_del.clicked.connect(del_row)
    btn_row.addWidget(btn_add)
    btn_row.addWidget(btn_del)
    btn_row.addStretch()
    table_container.addLayout(btn_row)

    layout.addLayout(table_container, 1)

    if param_key and param_key in HELP:
        btn = make_help_btn(param_key, parent)
        layout.addWidget(btn)

    return layout, table
