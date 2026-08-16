"""
Project路径解析器 — 单一真相来源

所有需要定位项目根目录、配置文件、数据文件的模块都应通过此模块获取路径。
不依赖 CWD (current working directory)，而是基于此文件的物理位置向上查找。

支持场景:
  - 终端直接运行: python gui_main.py
  - VS Code 打开父目录: code /parent && python project/gui_main.py
  - 嵌套解压: /home/user/downloads/MKIV-v1.2/MKIV-v1.2/gui_main.py
"""

import os
import sys

# 基于此文件的物理位置，向上查找包含 config/config.yaml 的目录
# 这是唯一可靠的方案，不依赖 CWD
def _discover_project_root():
    """向上遍历目录树，找到包含 config/config.yaml 的项目根目录"""
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
    """返回配置文件的绝对路径"""
    return os.path.join(PROJECT_ROOT, "config", filename)


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
