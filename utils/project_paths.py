"""
Project路径解析器 — 单一真相来源

所有需要定位项目根目录、配置文件、数据文件的模块都应通过此模块获取路径。
不依赖 CWD (current working directory)，而是基于此文件的物理位置向上查找。

支持场景:
  - 终端直接运行: python gui_main.py
  - VS Code 打开父目录: code /parent && python project/gui_main.py
  - 嵌套解压: /home/user/downloads/MKIV-v1.2/MKIV-v1.2/gui_main.py
  - PyInstaller 打包后: 以可执行文件所在目录为项目根，config/ data/ 与 exe 同级
"""

import os
import sys


def _is_frozen() -> bool:
    """是否运行在 PyInstaller 打包产物中"""
    return getattr(sys, "frozen", False)


def _bundle_dir() -> str:
    """PyInstaller 解包目录 (onefile 为临时目录)；非打包时返回项目根。

    打包进包内的只读资源 (如 config.example.yaml) 位于此目录。
    """
    return getattr(sys, "_MEIPASS", PROJECT_ROOT)


# 基于此文件的物理位置，向上查找包含 config/config.yaml 的目录
# 这是唯一可靠的方案，不依赖 CWD
def _discover_project_root():
    """定位项目根目录。

    打包后: 以可执行文件所在目录为根，保证 config/、data/ 与可执行文件同级、用户可读写。
    源码运行: 从本文件位置向上查找包含 config/ 的目录，不依赖 CWD。
    """
    if _is_frozen():
        return os.path.dirname(os.path.abspath(sys.executable))

    # 起始点: 此文件所在目录的父目录 (utils/ -> 项目根)
    candidate = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # 安全检查: 遍历最多 5 层
    for _ in range(5):
        if os.path.isfile(os.path.join(candidate, "config", "config.yaml")):
            return candidate
        # 也检查 config.example.yaml
        if os.path.isfile(os.path.join(candidate, "config", "config.example.yaml")):
            return candidate
        parent = os.path.dirname(candidate)
        if parent == candidate:
            break
        candidate = parent

    # 回退: 如果遍历失败，返回基于此文件位置的默认路径
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


PROJECT_ROOT = _discover_project_root()


def get_config_path(filename: str = "config.yaml") -> str:
    """返回配置文件的绝对路径。

    打包运行时，若用户目录下不存在该文件、但包内内置了同名模板，
    则回退到包内资源 (只读)。首次运行会用该模板生成用户可写的 config.yaml。
    """
    target = os.path.join(PROJECT_ROOT, "config", filename)
    if not os.path.exists(target):
        bundled = os.path.join(_bundle_dir(), "config", filename)
        if os.path.exists(bundled):
            return bundled
    return target


def get_data_path(relative_path: str) -> str:
    """将 config.yaml 中的相对路径解析为基于项目根的绝对路径

    如果传入的路径已经是绝对路径，直接返回。
    相对路径 (如 ./data/01_raw/U1.json) 会被解析为基于 PROJECT_ROOT 的绝对路径。
    """
    if os.path.isabs(relative_path):
        return relative_path
    # 去掉 ./ 前缀
    clean = relative_path.lstrip("./")
    return os.path.join(PROJECT_ROOT, clean)


def resolve_all_paths(config: dict) -> dict:
    """遍历配置中 paths 节的所有路径值，将它们全部解析为绝对路径

    这确保所有 core/pipelines 模块拿到的是绝对路径，无论谁怎么设置了 CWD。
    原地修改并返回 config 引用。
    """
    paths_section = config.get("paths", {})
    for key, value in list(paths_section.items()):
        if isinstance(value, str):
            paths_section[key] = get_data_path(value)
    return config


def ensure_in_sys_path():
    """将项目根目录加入 sys.path（对直接运行的脚本和打包后都安全）"""
    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)
