"""共享测试夹具 (pytest fixtures)。

设计原则:
  - **离线**: 不联网、不连 Neo4j、不加载 SBERT 模型；所有需要外部资源的路径
    一律用 monkeypatch 替换。
  - **隔离**: 所有落盘操作走 pytest 的 tmp_path，绝不写入项目的 data/。
  - **确定性**: 合成数据由固定随机种子生成，结果可复现。
"""

import os
import sys

import pytest

# 让测试既能 import 项目模块，也能 import scripts/ 下的样本数据生成器
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (PROJECT_ROOT, os.path.join(PROJECT_ROOT, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# tqdm 进度条在测试输出里只是噪音
os.environ.setdefault("TQDM_DISABLE", "1")

# 合成数据统一使用的假机构 ID (与真实机构无关)
TARGET_ID = "I0000000"
FOREIGN_ID = "I9999999"


def _author(name="San Zhang", aid="A1", internal=True,
            affiliations=("Synth Lab Alpha, Beijing 100190, China",)):
    """构造一条 authorship 记录。internal=True 表示挂靠目标机构。"""
    inst_id = f"https://openalex.org/{TARGET_ID if internal else FOREIGN_ID}"
    return {
        "author": {"id": f"https://openalex.org/{aid}", "display_name": name},
        "author_position": "first",
        "institutions": [
            {"id": inst_id, "display_name": "Synthetic Institute", "lineage": [inst_id]}
        ],
        "raw_affiliation_strings": list(affiliations),
    }


def _work(work_id="W1", year=2021, concepts=None, authorships=None,
          journal="Synthetic Journal"):
    """构造一篇最小可用的 U1 文献记录。"""
    if concepts is None:
        concepts = [{"display_name": "Machine Learning", "level": 1, "score": 0.9}]
    if authorships is None:
        authorships = [_author()]
    return {
        "id": f"https://openalex.org/{work_id}",
        "title": f"Synthetic work {work_id}",
        "publication_year": year,
        "doi": f"https://doi.org/10.0000/{work_id}",
        "primary_location": {"source": {"display_name": journal}},
        "concepts": concepts,
        "authorships": authorships,
    }


@pytest.fixture
def make_author():
    """返回 authorship 构造器。"""
    return _author


@pytest.fixture
def make_work():
    """返回文献构造器。"""
    return _work


@pytest.fixture
def target_id():
    return TARGET_ID
