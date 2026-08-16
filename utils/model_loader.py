# utils/model_loader.py
"""SentenceTransformer 模型加载器 — 本地优先，离线可用。

背景:
    SentenceTransformer(model_name) 传 HuggingFace 模型 ID 时，每次都会走
    huggingface_hub 的「查缓存 → 发 HEAD 请求校验远程」流程，网络不通时会卡住。
    本模块优先从项目内的 models/ 目录加载模型 (完全离线，不发任何网络请求)，
    找不到时才回退到 HuggingFace Hub。
"""
import os
import logging

from utils.project_paths import PROJECT_ROOT


def resolve_model_path(model_name: str):
    """若 model_name 能对应到一个存在的本地目录，返回其绝对路径；否则返回 None。

    依次尝试:
      1. model_name 本身是存在的目录 (绝对路径或相对当前工作目录)
      2. 相对项目根目录
      3. 项目根目录下的 models/<basename>
    """
    if not model_name:
        return None

    if os.path.isdir(model_name):
        return os.path.abspath(model_name)

    candidate = os.path.join(PROJECT_ROOT, model_name)
    if os.path.isdir(candidate):
        return candidate

    base = os.path.basename(str(model_name).rstrip('/\\'))
    candidate = os.path.join(PROJECT_ROOT, 'models', base)
    if os.path.isdir(candidate):
        return candidate

    return None


def load_sentence_transformer(model_name: str):
    """优先从本地目录加载模型 (离线)，否则回退到 HuggingFace Hub。"""
    from sentence_transformers import SentenceTransformer

    local = resolve_model_path(model_name)
    if local:
        logging.info(f"   📦 从本地加载模型 (离线): {local}")
        return SentenceTransformer(local)

    logging.info(f"   📦 从 HuggingFace Hub 加载模型: {model_name}")
    logging.info("      💡 网络受限时: export HF_ENDPOINT=https://hf-mirror.com")
    return SentenceTransformer(model_name)
