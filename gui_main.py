#!/usr/bin/env python3
"""
MKIV Academic Intelligence Graph Engine — GUI 启动入口
=======================================================

用法:
    python gui_main.py              # 直接启动 GUI
    python main.py --gui            # 通过 CLI 入口启动 GUI (需要修改 main.py)

这是 PyInstaller 打包时的目标脚本。
"""

import sys
import os
import logging

# 确保项目根目录在 sys.path 中
_project_root = os.path.dirname(os.path.abspath(__file__))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


def setup_basic_logging():
    """基础的终端日志配置 (GUI 面板会另行拦截)"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S'
    )


def check_dependencies():
    """检查关键依赖是否已安装"""
    missing = []
    checks = [
        ("PySide6", "PySide6"),
        ("PySide6.QtWebEngineWidgets", "PySide6-QtWebEngine"),
        ("yaml", "pyyaml"),
        ("neo4j", "neo4j"),
        ("pandas", "pandas"),
        ("openpyxl", "openpyxl"),
        ("sentence_transformers", "sentence-transformers"),
        ("sklearn", "scikit-learn"),
        ("pypinyin", "pypinyin"),
        ("uvicorn", "uvicorn"),
        ("fastapi", "fastapi"),
        ("tqdm", "tqdm"),
        ("requests", "requests"),
    ]

    for module, package in checks:
        try:
            __import__(module)
        except ImportError:
            missing.append(package)

    return missing


def main():
    """GUI 入口主函数"""
    setup_basic_logging()

    # 依赖检查
    missing = check_dependencies()
    if missing:
        print("=" * 60)
        print("❌ 缺少以下 Python 包:")
        print("   " + ", ".join(missing))
        print()
        print("请运行以下命令安装:")
        print(f"   pip install {' '.join(missing)}")
        print()
        print("或一键安装全部依赖:")
        print("   pip install -r requirements.txt")
        print("=" * 60)
        sys.exit(1)

    from PySide6.QtWidgets import QApplication
    from gui.dark_theme import apply_dark_theme
    from gui.main_window import MainWindow

    # 创建 Qt 应用
    app = QApplication(sys.argv)
    app.setApplicationName("MKIV Academic Intelligence Graph Engine")
    app.setOrganizationName("MKIV Team")

    # 应用暗黑主题
    apply_dark_theme(app)

    # 创建主窗口
    window = MainWindow()
    window.show()

    # 启动 Qt 事件循环
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
