#!/usr/bin/env python
"""生成**合成/匿名**演示数据集 (data/sample/)。

为什么需要它
------------
真实机构数据位于 data/ (已 gitignore)，其中含机构 ID、邮箱、导师真名，
不能进版本库。但 JOSS 评审需要「可复现的 example usage」——审稿人必须能
在一条命令内跑通全流程。因此这里用固定随机种子合成一份结构与 OpenAlex
返回完全一致的匿名数据，任何人都可以离线复现。

**数据是合成的，不代表任何真实机构、学者或论文。**

用法:
    python scripts/generate_sample_data.py            # 输出到 data/sample/
    python scripts/generate_sample_data.py --out DIR  # 自定义输出目录
"""

import argparse
import os
import random
import sys

# 允许以 `python scripts/generate_sample_data.py` 直接运行
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd  # noqa: E402

from core.cleaner import _clean_noise  # noqa: E402
from utils.file_handler import save_excel, save_json  # noqa: E402
from utils.project_paths import PROJECT_ROOT  # noqa: E402

# 假机构 (与任何真实 OpenAlex ID 无关)
SYNTH_INSTITUTION_ID = "https://openalex.org/I0000000"
SYNTH_INSTITUTION_NAME = "Synthetic Institute of Technology"
FOREIGN_INSTITUTION_ID = "https://openalex.org/I9999999"

# 三个课题组，每个课题组的机构串有多种脏写法 (缩写/嵌套/邮箱/邮编/国名)
LABS = {
    "Synthetic Brain Lab": [
        "Synthetic Brain Lab, Beijing 100190, China",
        "Synthetics Brain Lab (SBL), Beijing, China",
        "sbl.admin@synth.example Synthetic Brain Lab",
        "Brain Lab, Synthetic Institute of Technology, PRC",
    ],
    "Synthetic Vision Lab": [
        "Synthetic Vision Lab, Beijing 100190, China",
        "Synth. Vision Lab (SVL), People's Republic of China",
        "Vision Lab, Synthetic Institute of Technology",
    ],
    "Synthetic Robotics Lab": [
        "Synthetic Robotics Lab, Beijing, China",
        "Synth Robotics Lab (SRL), Beijing 100190, China",
        "Robotics Group, Synthetic Institute of Technology, P.R. China",
    ],
}

# 研究领域：原始概念 → 标准大类 (Step 4 的映射关系)
TOPICS = {
    "人工智能": ["Deep Learning", "Machine Learning", "Neural Networks"],
    "计算机视觉": ["Computer Vision", "Image Segmentation"],
    "机器人学": ["Robotics", "Robot Manipulation"],
}

# 导师名单 (合成姓名)
MENTORS = ["Alice Chen", "Bob Liu", "Carol Wang", "David Zhao"]

# 内部人员 → OpenAlex ID 列表。Alice Chen 故意挂两个 ID，
# 用于演示 Step 5 的「历史分身合并」(同一真名下多个作者号归并到主号)。
AUTHOR_IDS = {
    "Alice Chen": ["A100", "A101"],
    "Bob Liu": ["A200"],
    "Carol Wang": ["A300"],
    "David Zhao": ["A400"],
    "Eve Sun": ["A500"],
    "Frank Ma": ["A600"],
    "Grace Hu": ["A700"],
    "Henry Xu": ["A800"],
    "Ivy Luo": ["A900"],
    "Jack Deng": ["A110"],
    "Kelly Fang": ["A120"],
    "Leo Qiu": ["A130"],
}

INTERNAL_NAMES = list(AUTHOR_IDS)
EXTERNAL_NAMES = [
    "Mona Patel", "Nick Brown", "Olga Ivanova", "Paul Garcia",
    "Quinn Miller", "Rita Sato", "Sam Okafor", "Tina Novak",
]

JOURNALS = [
    "Journal of Synthetic Systems",
    "Synthetic Transactions on Intelligence",
    "Proceedings of the Synthetic Society",
]


def _openalex_id(prefix, value):
    """拼出 OpenAlex 风格的完整 URL (prefix 为空时 value 已含字母)。"""
    return f"https://openalex.org/{prefix}{value}"


def build_works(n_works=60, seed=0):
    """构造 n_works 篇合成文献 (U1 结构，与 OpenAlex 返回一致)。

    确定性: 同一 seed 永远得到同一份数据。
    """
    rng = random.Random(seed)
    works = []

    for i in range(1, n_works + 1):
        # 1-3 个内部作者 (多为课题组成员)，0-2 个外部合作者
        n_internal = rng.randint(1, 3)
        n_external = rng.randint(0, 2)

        authorships = []
        for name in rng.sample(INTERNAL_NAMES, min(n_internal, len(INTERNAL_NAMES))):
            _lab, variants = rng.choice(list(LABS.items()))
            authorships.append({
                "author": {"id": _openalex_id("", rng.choice(AUTHOR_IDS[name])),
                           "display_name": name},
                "author_position": "first",
                "institutions": [{
                    "id": SYNTH_INSTITUTION_ID,
                    "display_name": SYNTH_INSTITUTION_NAME,
                    "lineage": [SYNTH_INSTITUTION_ID],
                }],
                "raw_affiliation_strings": [rng.choice(variants)],
            })
        for name in rng.sample(EXTERNAL_NAMES, n_external):
            authorships.append({
                "author": {"id": _openalex_id("AX", name.replace(" ", "")),
                           "display_name": name},
                "author_position": "middle",
                "institutions": [{
                    "id": FOREIGN_INSTITUTION_ID,
                    "display_name": "Foreign Synthetic University",
                    "lineage": [FOREIGN_INSTITUTION_ID],
                }],
                "raw_affiliation_strings": ["Foreign Synthetic University, USA"],
            })

        # 概念: 只保留 level<=2 且 score>0.4 的才会活到 U2 (与 nlp 阈值一致)
        concepts = []
        for category, originals in TOPICS.items():
            if rng.random() < 0.45:
                concepts.append({
                    "display_name": rng.choice(originals),
                    "level": 1,
                    "score": round(rng.uniform(0.5, 0.99), 2),
                })

        works.append({
            "id": _openalex_id("W", i),
            "title": f"Synthetic study {i} on {rng.choice(list(TOPICS))}",
            "publication_year": rng.randint(2018, 2025),
            "doi": f"https://doi.org/10.0000/synth.{i}",
            "primary_location": {"source": {"display_name": rng.choice(JOURNALS)}},
            "concepts": concepts,
            "authorships": authorships,
        })

    return works


def build_mentor_dataframe():
    """合成导师名单 (Step 0 的输入 Excel)。"""
    return pd.DataFrame({"导师姓名": MENTORS})


def _cleaned_variants():
    """把每个课题组的所有脏写法清洗成 Step 4 里实际出现的排头兵字符串。"""
    mapping = {}
    for canonical, variants in LABS.items():
        for raw in variants:
            cleaned = _clean_noise(raw)
            if cleaned:
                mapping[cleaned] = canonical
    return mapping


def build_affiliation_mapping():
    """预填好的机构映射表 (替代 Step 3 的 SBERT 聚类 + 人工填写)。

    真实使用中这张表由 Step 3 生成模板、人工或 LLM 填写；
    演示数据里直接给出答案，好让审稿人无需下载 500MB 模型即可跑通 Step 4。
    """
    rows = [{
        "簇编号": i,
        "包含变体数": 1,
        "🤖 AI 提取的【排头兵】": cleaned,
        "🧑‍🔧 填写标准名称 (抄左边/填中文/不认识留空)": canonical,
        "🔍 辅助参考 (可忽略)": "",
    } for i, (cleaned, canonical) in enumerate(_cleaned_variants().items())]
    return pd.DataFrame(rows)


def build_concept_mapping():
    """预填好的研究领域映射表。"""
    rows = [{
        "原始领域名称": original,
        "填写标准大类 (如：人工智能)": category,
    } for category, originals in TOPICS.items() for original in originals]
    return pd.DataFrame(rows)


SAMPLE_README = """# data/sample — 合成演示数据 (SYNTHETIC / 匿名)

**这里的全部内容都是程序合成的假数据，不对应任何真实机构、学者或论文。**
本目录存在的唯一目的，是让任何人在不接触真实机构数据的前提下复现完整流水线。

| 文件 | 对应流水线阶段 |
|------|----------------|
| `U1_SYNTHETIC.json` | Step 0 抓取产物 (结构与 OpenAlex `/works` 返回一致) |
| `0_原始导师名单_SYNTHETIC.xlsx` | Step 0 作者画像匹配的输入名单 |
| `1_机构映射表_SYNTHETIC_已填.xlsx` | Step 4 机构映射 (已填好，跳过人工填写) |
| `2_研究领域映射表_SYNTHETIC_已填.xlsx` | Step 4 领域映射 (已填好) |

数据由 `scripts/generate_sample_data.py` 以固定随机种子生成，可完全复现：

```bash
python scripts/generate_sample_data.py
```

一条命令跑通 Step 1 → Step 5 (离线，不需要联网 / Neo4j / HuggingFace 模型)：

```bash
python scripts/run_sample_pipeline.py
```

> 说明：演示流程**跳过 Step 3 的 SBERT 语义聚类**（样本量太小，聚类的意义不大），
> 改用恒等映射 + 预填映射表，从而不必下载 500MB 模型。
> 真实使用时 Step 3 会调用 `paraphrase-multilingual-MiniLM-L12-v2` 自动生成排头兵。

### 运行时会看到的告警（属正常现象）

跑演示时会打印若干条 `⚠️ 重名冲突: ...都映射为...`。这是**预期行为**：
演示数据故意让同一个课题组的 3–4 种脏写法都收敛到同一个标准名，
Step 4 发现多个「排头兵」指向同一标准名时就会提示合并。

在真实数据上这类告警值得人工核对（它意味着两个不同实体被合并了）；
在演示数据里它正是「坍缩生效」的证据。
进度条与告警走 stderr，不影响产物正确性。
"""


def write_sample_dataset(out_dir=None, seed=0, n_works=60):
    """生成并写出完整演示数据集，返回输出目录。"""
    out_dir = out_dir or os.path.join(PROJECT_ROOT, "data", "sample")
    os.makedirs(out_dir, exist_ok=True)

    save_json(build_works(n_works=n_works, seed=seed),
              os.path.join(out_dir, "U1_SYNTHETIC.json"))
    save_excel(build_mentor_dataframe(),
               os.path.join(out_dir, "0_原始导师名单_SYNTHETIC.xlsx"))
    save_excel(build_affiliation_mapping(),
               os.path.join(out_dir, "1_机构映射表_SYNTHETIC_已填.xlsx"))
    save_excel(build_concept_mapping(),
               os.path.join(out_dir, "2_研究领域映射表_SYNTHETIC_已填.xlsx"))

    with open(os.path.join(out_dir, "README.md"), "w", encoding="utf-8") as f:
        f.write(SAMPLE_README)

    return out_dir


def main():
    parser = argparse.ArgumentParser(description="生成合成演示数据集")
    parser.add_argument("--out", default=None, help="输出目录 (默认 data/sample/)")
    parser.add_argument("--works", type=int, default=60, help="合成文献数量")
    parser.add_argument("--seed", type=int, default=0, help="随机种子 (保证可复现)")
    args = parser.parse_args()

    out_dir = write_sample_dataset(args.out, seed=args.seed, n_works=args.works)
    print(f"✅ 合成演示数据已生成: {out_dir}")
    print(f"   机构: {SYNTH_INSTITUTION_NAME} ({SYNTH_INSTITUTION_ID})")
    print(f"   课题组: {len(LABS)} 个 / 研究大类: {len(TOPICS)} 个 / 文献: {args.works} 篇")
    print("   ⚠️  全部为合成数据，不代表任何真实机构或学者。")


if __name__ == "__main__":
    main()
