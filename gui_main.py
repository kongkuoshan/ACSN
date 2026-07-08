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
    """检查关键依赖。返回 (required_missing, optional_missing)"""
    required_missing = []
    optional_missing = []

    required = [
        ("PySide6", "PySide6"),
        ("PySide6.QtWebEngineWidgets", "PySide6 (QtWebEngine)"),
        ("yaml", "pyyaml"),
        ("neo4j", "neo4j"),
        ("pandas", "pandas"),
        ("openpyxl", "openpyxl"),
        ("pypinyin", "pypinyin"),
        ("uvicorn", "uvicorn"),
        ("fastapi", "fastapi"),
        ("tqdm", "tqdm"),
        ("requests", "requests"),
    ]

    optional = [
        ("sentence_transformers", "sentence-transformers (NLP聚类需要)"),
        ("sklearn", "scikit-learn (NLP聚类需要)"),
    ]

    for module, package in required:
        try:
            __import__(module)
        except ImportError:
            required_missing.append(package)

    for module, package in optional:
        try:
            __import__(module)
        except ImportError:
            optional_missing.append(package)

    return required_missing, optional_missing


def ensure_config():
    """首次运行时自动从模板生成 config.yaml"""
    config_path = os.path.join(_project_root, "config", "config.yaml")
    example_path = os.path.join(_project_root, "config", "config.example.yaml")

    if not os.path.exists(config_path):
        if not os.path.exists(example_path):
            print("❌ 致命错误: config.example.yaml 也丢失了！请重新克隆项目。")
            sys.exit(1)
        import shutil
        shutil.copy(example_path, config_path)
        print("📋 首次运行: 已从 config.example.yaml 生成 config/config.yaml")
        print("   请编辑 config/config.yaml 填入你的机构 ID、邮箱和数据库密码。")
        print()


def main():
    """GUI 入口主函数"""
    setup_basic_logging()
    ensure_config()

    # 依赖检查
    required_missing, optional_missing = check_dependencies()
    if required_missing:
        print("=" * 60)
        print("❌ 缺少以下必需 Python 包:")
        print("   " + ", ".join(required_missing))
        print()
        print("请运行: pip install -r requirements.txt")
        print("=" * 60)
        sys.exit(1)

    if optional_missing:
        print("=" * 60)
        print("⚠️  缺少以下可选 Python 包 (NLP聚类/LLM分析需要):")
        print("   " + ", ".join(optional_missing))
        print()
        print("如需NLP功能请运行: pip install sentence-transformers scikit-learn")
        print("=" * 60)

    # ⚠️ 必须在导入 Qt 之前设置，否则不会生效
    # 禁用 GPU 加速 — 修复 Linux 上 QWebEngineView 闪烁/穿透问题
    if sys.platform == 'linux':
        os.environ['QTWEBENGINE_CHROMIUM_FLAGS'] = '--disable-gpu --disable-software-rasterizer'
        os.environ['QT_QUICK_BACKEND'] = 'software'
        print("💡 Linux 环境: 已禁用 WebEngine GPU 加速以避免闪烁")

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
