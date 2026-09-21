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


def build_affiliation_ground_truth():
    """清洗后的机构串 → 标准课题组名。这是合成数据的**真值**。

    它有两个用途，都不需要手工维护一张映射表：
      1. `run_sample_pipeline` 用它构造确定性编码器，让流水线**自己的**
         Step 3 聚类 + 模板生成代码原样跑起来 (无需下载 SBERT 模型)；
      2. 生成出来的模板，其「填写标准名称」列由这份真值自动填写。
    真值只有 LABS 这一个来源，改了 LABS 不会与任何表格失配。
    """
    ground_truth = {}
    for canonical, variants in LABS.items():
        for raw in variants:
            cleaned = _clean_noise(raw)
            if cleaned:
                ground_truth[cleaned] = canonical
    return ground_truth


def build_concept_ground_truth():
    """原始领域名 → 标准大类 (TOPICS 的展开)。"""
    return {original: category
            for category, originals in TOPICS.items()
            for original in originals}


SAMPLE_README = """# data/sample — 合成演示数据 (SYNTHETIC / 匿名)

**这里的全部内容都是程序合成的假数据，不对应任何真实机构、学者或论文。**
本目录存在的唯一目的，是让任何人在不接触真实机构数据的前提下复现完整流水线。

| 文件 | 对应流水线阶段 |
|------|----------------|
| `U1_SYNTHETIC.json` | Step 0 抓取产物 (结构与 OpenAlex `/works` 返回一致) |
| `0_原始导师名单_SYNTHETIC.xlsx` | Step 0 作者画像匹配的输入名单 |

数据由 `scripts/generate_sample_data.py` 以固定随机种子生成，可完全复现：

```bash
python scripts/generate_sample_data.py
```

一条命令跑通 Step 1 → Step 5 (离线，不需要联网 / Neo4j / HuggingFace 模型)：

```bash
python scripts/run_sample_pipeline.py
```

**映射表不在这里，而是由流水线自己生成**：`run_sample_pipeline.py` 把 Step 3 的
SBERT 编码器换成按合成真值分组的确定性编码器（因此不必下载 500MB 模型），
然后调用流水线**自己的** `build_cluster_mappings()` 生成簇模板，再按同一份真值
自动填写标准名称列，写出到 `data/sample/_run/`。这样「Step 3 出模板 → Step 4
读表」这条契约路径在演示里是真的被走了一遍，而不是拿一张手填的表糊过去。

真实使用时唯一的变化是：编码器换成 `paraphrase-multilingual-MiniLM-L12-v2`，
标准名称列由人工 (或 Step 3.5 的 LLM 预填) 填写。

### 演示数据里能看到什么

三个合成课题组各写了 3 种脏写法 (缩写 / 邮箱 / 中英混排 / 带邮编国名)，清洗后得到
9 条不同的机构串。Step 3 把它们聚成 3 簇，每簇选一个「排头兵」，Step 4 再坍缩成
3 个标准名 —— 跑完可以打开 `_run/1_机构映射表.xlsx` 对照簇编号与变体数。

进度条走 stderr，不影响产物正确性。
"""


def write_sample_dataset(out_dir=None, seed=0, n_works=60):
    """生成并写出完整演示数据集，返回输出目录。"""
    out_dir = out_dir or os.path.join(PROJECT_ROOT, "data", "sample")
    os.makedirs(out_dir, exist_ok=True)

    save_json(build_works(n_works=n_works, seed=seed),
              os.path.join(out_dir, "U1_SYNTHETIC.json"))
    save_excel(build_mentor_dataframe(),
               os.path.join(out_dir, "0_原始导师名单_SYNTHETIC.xlsx"))

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
