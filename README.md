# MKIV 学术情报图谱引擎 <br> MKIV Academic Intelligence Graph Engine

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Neo4j](https://img.shields.io/badge/Neo4j-Graph_Database-4caf50.svg)](https://neo4j.com/)
[![OpenAlex](https://img.shields.io/badge/Data_Source-OpenAlex-ff69b4.svg)](https://openalex.org/)
[![PySide6](https://img.shields.io/badge/GUI-PySide6-darkgreen.svg)](https://doc.qt.io/qtforpython-6/)

**中文** | 面向科研机构的学术情报分析平台：从 OpenAlex 抓取、语义聚类清洗、LLM 辅助标注、Neo4j 入库，到 ECharts 交互式大屏——端到端自动化。

**English** | An end-to-end academic intelligence platform: crawls publication data from OpenAlex, cleans and clusters noisy affiliation strings, optionally labels entities with LLM assistance, imports the result into Neo4j, and serves interactive ECharts dashboards — via both CLI and a desktop GUI.

> **命名说明 · Naming**: 本仓库名为 **`ACSN`**（Academic Search Network）；**`MKIV`** 是引擎的内部代号，源码、EXE、Docker 容器名与界面标题中的 MKIV 都指同一个项目。

---

## 这是什么 · What is MKIV

科研机构的作者挂靠信息（affiliation）在文献数据库里极其混乱——同一个实验室可能有几十种写法（缩写、层级嵌套、翻译、拼写错误）。靠正则或纯人工清洗都不现实。

MKIV 用 **「SBERT 语义聚类 → 排头兵坍缩 → 人工/LLM 复核」** 的方式，把数千个机构/学科变体压成几十个标准名，最终产出一个知识图谱和一套可交互的分析大屏：

- **关系星图**：谁和谁合作、谁属于哪个实验室
- **情报分析**：研究重点如何随时间演化、各实验室研究倾向、主题层级分布

**适用对象**：需要摸清「本机构谁和谁合作、各实验室研究什么、研究方向如何变化」的科研管理部门、课题组、情报分析人员。

---

## 核心功能 · Core Features

| 功能 Feature | 说明 Description |
|-------------|-----------------|
| **数据治理** Data Cleaning | 数千机构/学科变体 → SBERT 聚类坍缩为「排头兵」标准名 |
| **人机协同** Human-in-the-Loop | Step 3 生成映射表 → 人工填写（或 LLM 预填）→ Step 4 应用 |
| **情报分析** Analytics | 主题演化河流图 + 实验室雷达图 + 二层主题旭日图（大类 → 原始概念） |
| **双视角大屏** Dual Dashboard | 关系星图 + 情报分析，网页端双向切换 |
| **一键 Docker** One-Click Deploy | GUI 内置 Neo4j 容器生命周期管理 |
| **桌面 GUI** Desktop App | PySide6 深色主题：参数面板 + 内嵌大屏 + 实时日志 + 首次运行向导 |
| **多入口** Multi-Entry | 源码运行 / CLI→GUI / CLI 流水线 / PyInstaller EXE |

---

## 快速开始 · Quick Start

### 1. 环境准备

- **Python 3.10+**
- **Docker**（用于一键部署 Neo4j；也可连接已有 Neo4j，此时不需要）

### 2. 安装

```bash
git clone https://github.com/kongkuoshan/ACSN.git
cd ACSN

# 核心依赖（CLI + GUI 开箱即用）：
pip install -r requirements.txt

# 可选 —— 仅在需要跑 Step 3 语义聚类时安装（约 2GB，含 sentence-transformers / scikit-learn）：
pip install -r requirements-ml.txt
```

### 3. 配置

首次运行会自动从 `config/config.example.yaml` 复制生成 `config/config.yaml`（该文件已被 gitignore，不会泄露）。只需填这几项：

```yaml
institution:
  email: "your@email.com"                  # 你的邮箱（OpenAlex 礼貌池需要）
  target_id: "https://openalex.org/IXXXX"  # 目标机构 OpenAlex ID
  start_year: 2021                          # 抓取起始年份
  fallback_keywords: ["university", "institute"]  # 内部作者兜底关键词（示例，请按你的机构替换）

database:
  uri: "bolt://localhost:7688"
  user: "neo4j"
  password: "改成8位以上"                    # ⚠️ 必须与 Neo4j 密码一致，且 ≥8 位
```

> **怎么找机构 ID**：在 [openalex.org](https://openalex.org) 搜索你的机构，URL 里的 `Ixxxxx` 就是 `target_id`。

**映射与层级相关配置**（可选，默认即可）：

```yaml
nlp:
  level_threshold: 2        # 概念最大层级：1=仅大类，2=含二级概念（默认 2）

mapping:
  source: auto              # 映射表来源：auto(优先AI预填,回退人工) | ai(仅AI) | manual(仅人工)
  collapse_external: true   # 是否把外部合作机构坍缩为一个节点（false=保留各自名字）
```

- `level_threshold`：决定保留多深的概念层级。设为 1 只保留大类（填表更省事），设为 2 保留二级概念（分析更细，但填表量更大）。
- `mapping.source`：Step 4 读哪份映射表。`auto` 自动优先 AI 预填版、否则人工版；`ai`/`manual` 强制指定。
- `mapping.collapse_external`：`true` 把所有外部合作机构合并成一个「外部合作机构」节点；`false` 则保留各自名字（需在映射表里填各自名称）。

### 4. 启动 Neo4j

**推荐 —— GUI 一键部署**：打开 GUI 后，左侧「数据库」面板点「🐳 一键部署」，自动完成镜像拉取、容器创建、挂载、健康检查。

**或 —— Docker CLI**：

```bash
mkdir -p ./data/import
docker run -d --name mkiv_neo4j \
  -p 7688:7687 -p 7689:7474 \
  -e NEO4J_AUTH=neo4j/your_password \
  -e NEO4J_server_directories_import=/import \
  -v $(pwd)/data/import:/import \
  neo4j:5-community
```

> 容器命令：`docker start/stop/rm -f mkiv_neo4j`。密码必须 ≥8 位，否则容器会循环重启。

### 5. 下载 NLP 模型（国内用户必看）

SBERT 聚类依赖 `paraphrase-multilingual-MiniLM-L12-v2`（约 470MB）。程序**优先从本地 `models/` 目录加载**（完全离线、不发网络请求），找不到才去 HuggingFace 下载。

国内直连 HuggingFace 通常超时，用镜像把模型下到本地即可一劳永逸：

```bash
pip install -U huggingface_hub
HF_ENDPOINT=https://hf-mirror.com huggingface-cli download \
  sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 \
  --local-dir models/paraphrase-multilingual-MiniLM-L12-v2
```

> `models/` 目录已被 gitignore（470MB 不入库）。离线分发时，把整个 `models/` 文件夹一起打包给用户即可。

### 6. 启动

项目提供四种入口，任选其一：

```bash
python gui_main.py       # ① 直接启动 GUI（推荐，日常使用）
python main.py --gui     # ② 通过 CLI 入口启动 GUI（等价）
python main.py           # ③ CLI 运行流水线（默认只执行 Step 6 启动大屏服务）
```

- **④ 源码手动运行**：也可在 IDE（PyCharm / VS Code）中直接 Run `gui_main.py` 或 `main.py`。路径解析基于文件位置、不依赖工作目录，无需额外配置。
- **EXE**：Windows 下双击 PyInstaller 打包出的 `MKIV_Academic_Graph.exe` 即走入口 ①。

> `python main.py` 默认只执行 `run_dashboard_stage()`（启动大屏，要求数据已入库）。要跑完整流水线，请编辑 `main.py` 取消注释对应的前置阶段，或在 GUI 中按阶段执行。

---

## 运行测试 · Running Tests

无需真实数据、无需联网：

```bash
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest tests/ -v
```

测试全程离线：不访问 OpenAlex、不连 Neo4j、不加载 SBERT 模型（编码器用假模型替换），
落盘操作全部走 pytest 的临时目录，不会污染 `data/`。

### 合成演示数据 · Synthetic Demo Dataset

`data/sample/` 里是一份**程序合成的匿名数据**（不对应任何真实机构/学者/论文），
用于徒手复现整条流水线而不接触真实机构数据：

```bash
python scripts/generate_sample_data.py    # 用固定随机种子重新生成演示数据
python scripts/run_sample_pipeline.py     # 一条命令跑通 Step 1 → Step 5（离线）
```

演示流程跳过 Step 5 的 Neo4j 装载；Step 3 会**照常调用流水线自己的聚类与模板生成代码**，
只是把 SBERT 编码器换成按合成真值分组的确定性编码器，生成的映射表再由真值自动填写。
因此**不需要下载模型、不需要数据库**，而「Step 3 出模板 → 人工填写 → Step 4 读表」
这条契约路径仍然被真实地走了一遍。
详见 [`data/sample/README.md`](data/sample/README.md)。

---

## 核心工作流 · Core Workflow

整个流程只有**第二步需要人工介入**，其余全自动。

### ① 抓数据（Step 0–2，全自动）

爬取目标机构文献 → 标记内部/外部作者 → 清洗噪音。无需人工。

如果你把**导师名单**（Excel，列名默认 `导师姓名`）放进 `data/input/0_原始导师名单.xlsx`，Step 0 会额外做一次**作者画像匹配**，输出 `data/output/0_作者匹配画像表.xlsx`：把名单上的名字对到 OpenAlex 作者 ID，并区分**主号 / 历史分身**（同一个人被 OpenAlex 拆成多个 ID 的情况）。中文名会自动转拼音再匹配。不放名单也能跑完流水线，但图谱里就没有「导师」这一角色。详见下方「作者锚定与微观结构」。

### ② 填映射表（Step 3 → 人工/LLM → Step 4）← 唯一需要你介入的环节

**为什么**：系统把数千个机构变体聚类成约 30 个「排头兵」（每簇选一个代表），把数千条领域概念**同样聚类**成若干簇（`nlp.target_con_clusters`），每簇选一个「排头兵」，生成两张**同构**的 Excel 模板，等你把它们翻译成规范中文名。

**两种方式，二选一**：

**A. 人工填写**（不依赖 LLM）：

1. 跑完 Step 3 后，打开 `data/input/` 下的两张表：
   - `1_机构映射表.xlsx` —— 在「填写标准名称」列，给每个排头兵填中文实验室名（如「某某重点实验室」）
   - `2_研究领域映射表.xlsx` —— 在「填写标准大类」列，给每个领域**排头兵**填中文大类（人工智能 / 计算机视觉 / 生物与医学 …）
2. 保存，然后跑 Step 4。

**B. LLM 自动预填**（可选）：

1. `config.yaml` 里设 `llm_assistant.enabled: true` 并配好 `api_url`（OpenAI 兼容接口）。
2. 跑 Step 3.5，生成 `*_AI预填版.xlsx`。
3. Step 4 会**自动优先采用** `_AI预填版`（若存在），否则回退到人工版。

> ⚠️ **填好后不要再重跑 Step 3**——它会重新生成空模板。当前代码已加保护：已填写的表不会被覆盖。

### ③ 出结果（Step 4–6，全自动）

组装（应用你的映射）→ 分析（演化图 / 雷达图 / 旭日图）→ 入库 Neo4j → 大屏展示。

---

## 数据流水线 · Pipeline Stages

| Step | 名称 Name | 输入 → 输出 | 说明 |
|------|----------|-------------|------|
| 0 | 数据采集 | OpenAlex API → `U1.json` | 爬取 + 作者画像匹配 |
| 1 | 靶向过滤 | `U1.json` → `U1.5.json` | 内部/外部作者打标 |
| 2 | 硬规则清洗 | `U1.5.json` → `U2.json` + `unique.json` | 去噪 + 提取机构/领域实体 |
| 3 | NLP 聚类 | `unique.json` → `U2_5.json` + 映射表 | SBERT 聚类 → 排头兵 + 空模板 |
| 3.5 | LLM 预填（可选） | 映射表 → `_AI预填版.xlsx` | LLM 批量预填 + 去重 |
| 4 | 终极组装 | `U2_5.json` + 映射表 → `U3.json` | 严格过滤 + 应用人工/LLM 映射 |
| 4.5 | 情报分析 | `U3.json` → trends / radar / sunburst | 概念降维 + 演化/雷达/旭日图 |
| 5 | 数据库导入 | `U3.json` → Neo4j | CSV 导出 + Cypher LOAD |
| 6 | 大屏 | Neo4j → Web :8001 | FastAPI + ECharts |

### 各阶段详解 · Stage Details

- **Step 0 数据采集** — `crawler.py` 按机构 ID + 年份区间抓取 OpenAlex works：游标分页、逐页限速、本地缓存、429/5xx 重试，产出 `U1.json`。若提供了导师名单，`author_matcher.py` 同时建立本地作者画像库并匹配：按**姓名指纹**（小写、去 `-` / `.` / 空格）聚合内部作者，同一个人可对应多个 OpenAlex ID，逐 ID 记录发文量、高频挂靠机构、高频概念、合作者集合；输出画像表时按发文量排序，最高者为**主号**，其余标记为**历史分身**，名单上有而库里没有的记「查无此人」。中文名先在 `name_processor.py` 转拼音，两段式姓名额外做倒序探测。
- **Step 1 靶向过滤** — `cleaner.tag_internal_nodes()` 按机构 lineage（上级机构树）判定作者是否属于本机构；官方没认出来的记录，用 `institution.fallback_keywords` 做不区分大小写的正则兜底。产出 `U1.5.json`。
- **Step 2 硬规则清洗** — `cleaner.extract_and_clean_entities()` 剔除邮箱、5–7 位邮编、`cleaning.stop_words` 中的国家/城市名；概念只保留 `level ≤ nlp.level_threshold` 且 `score > nlp.score_threshold` 的。同时抽出两个待聚类的唯一实体集合，产出 `U2.json` + `unique.json`。
- **Step 3 NLP 聚类** — `analyzer.build_cluster_mappings()` 用 `paraphrase-multilingual-MiniLM-L12-v2` 编码**机构变体与领域概念**（两条通道同款聚类），默认 Ward 层次聚类；变体数超过 `kmeans_switch_threshold`（默认 3000）自动切 KMeans，避免 O(n²) 内存。每簇取**最短串**为「排头兵」（`vanguard_strategy` 可改为 longest）：机构目标簇数 `nlp.target_aff_clusters`，领域目标簇数 `nlp.target_con_clusters`（默认 100）。生成两张**同构**的 Excel 模板 + 变体→排头兵映射字典，并立即把 U2 坍缩成 `U2_5.json`（概念的原始名保留在 `original_name`，供旭日图追溯）。**坍缩发生在你填表之前**，所以修订映射表只需重跑 Step 4，不必重跑聚类。
- **Step 3.5 LLM 预填（可选）** — `llm_labeler.py` 调 OpenAI 兼容接口批量标注：领域与机构都走**批量**（每批 `llm_assistant.batch_size`，默认 80），领域返回的分类必须命中 `llm_assistant.concept_target_fields` 白名单，否则该行**留空待人工**（绝不把概念原文误当大类）。结果写到**另一份** `*_AI预填版.xlsx`，绝不覆盖人工版。模型产生的重名做两轮合并：先精确同名合并，再用 difflib 按 `similarity_threshold`（默认 0.85）模糊合并跨批次命名不一致。
- **Step 4 终极组装** — `assembler.py` 解析映射表。概念**严格过滤**：表里没有的直接剔除，但原始名保留在 `original_name` 上，供旭日图做二层展开。机构三级解析：映射表精确名 → `institution.golden_keys` 子串兜底（不区分大小写）→ `labels.other_dept` 兜底。读哪份表由 `mapping.source` 决定（`auto` 优先 AI 预填版、否则人工版；`ai` / `manual` 强制指定）。产出 `U3.json`。
- **Step 4.5 情报分析** — `trend_analyzer.py` 对标准名概念再做一次聚类降维（`analytics.concept_clusters`，可选 LLM 命名）；若概念数已不超目标簇数，**直接返回恒等映射**，跳过聚类。产出 `trends.json`（演化河流）、`lab_radar.json`（实验室倾向）、`topic_sunburst.json`（两层旭日：标准大类 → 原始概念）。
- **Step 5 数据库导入** — `db_importer.py` 先把画像表的主号/分身合并成别名表，**分身 ID 一律归并到主号**，同一人的合作记录不会被拆成两个节点；名单命中者 `role=导师`，其余内部作者 `role=研究员/学生`。**每条**机构串都建一条 `BELONGS_TO` 边（不只第一条），双聘因此保留；`CO_WORK.weight` = 两人共著论文数。导出 CSV 后用 Cypher `LOAD CSV` 入库。
- **Step 6 大屏** — `visualizer.py` 起 FastAPI：`/` 是力导向关系星图，可切「实验室视角 / 研究主题视角」——**同一张图按两个维度重切**（按 `BELONGS_TO` 分组，或按 `WROTE→MAPPED_TO` 分组）；`/analytics` 是演化河流 + 实验室雷达 + 主题旭日。

---

## 作者锚定与微观结构 · Roster Anchoring & Micro-Structure

**为什么需要导师名单**：OpenAlex 的作者 ID 是算法推断的，会出两种错——一个人被拆成多个 ID（同一姓名多种写法），或者不同的人被并进一个 ID（同名）。而且它只记录「挂靠机构」，从不记录「谁带谁」。导师名单是唯一持有这层内部知识的输入，也是本工具区别于通用计量工具的地方。

**怎么给**：Excel 放到 `data/input/0_原始导师名单.xlsx`，姓名列默认叫 `导师姓名`（可改 `author_matcher.name_column`）。中文名会自动转拼音。跑完 Step 0 得到 `data/output/0_作者匹配画像表.xlsx`，每行给出：OpenAlex_ID、数据库真实姓名、匹配状态、ID 归属状态（主号 / 历史分身 N）、发文量、高频挂靠实验室、近 5 年主攻领域、合作者规模。

**名单如何进入图谱**：

1. **修身份** — 主号与历史分身的所有论文都归到主号名下，合作记录不再被拆散。
2. **定角色** — 命中名单的节点标记为「导师」，其余内部作者标记为「研究员/学生」。
3. **进可视化** — 大屏里导师是大的红色菱形并常显姓名，非导师是小圆点、不显名。

**怎么读微观结构**：

- **导师的邻居就是他的合作名单**——点开导师节点，右侧栏直接列出其论文。
- **只跟一位导师共著的非名单作者**，大概率是该导师的**学生**。
- **同时跟多位导师共著的非名单作者**，大概率是共享的**工程/研究支撑人员**（或跨组合作者）；若其 `BELONGS_TO` 边同时挂在多个组上，则是**双聘**。

> ⚠️ 上述判断是**你从图里读出来的**，不是程序打的标签。程序只保证角色、权重与归属边正确，每条结论都能回溯到一条带权重的边和一个实名的作者。按「与几位导师共著」自动推断子角色（疑似学生 / 疑似支撑人员）属于**计划中的扩展，当前版本未实现**。

---

## 常见问题 · FAQ

**Q：主题全是英文 / 实验室显示「(其他部门)」？**
A：说明映射表没填（跳过了「② 填映射表」）。补填后重跑 `Step 4 → 4.5 → 5` 即可。不要重跑 Step 3。

**Q：HuggingFace 模型下载一直超时？**
A：用镜像下到本地 `models/`（见「下载 NLP 模型」），或运行前 `export HF_ENDPOINT=https://hf-mirror.com`。

**Q：Neo4j 容器反复重启？**
A：多半是密码 <8 位。改成长于 8 位后重新「一键部署」。

**Q：抓取文献中途超时中断？**
A：爬虫已逐页重试、只缓存完整结果。若频繁超时，建议用你的邮箱在 openalex.org 注册进礼貌池（更快更稳）。

**Q：Step 5 报「权限不够」？**
A：导入目录权限问题已在代码里修复（挂载到 `/import`）。若仍遇到，`sudo chown -R $USER data/import`。

**Q：画像表里某位导师显示「查无此人」？**
A：说明在抓取年份区间内、这个（拼音）写法没有内部文献命中。依次检查：姓名列是否填了拼音/英文写法、`institution.start_year` 是否设得太晚、`institution.fallback_keywords` 是否覆盖该机构的常见写法。

**Q：大屏里为什么很多节点是小圆点而且不显示名字？**
A：只有命中导师名单的作者才是导师（红色菱形 + 常显姓名），其余内部作者统一按 `labels.staff_role`（默认「研究员/学生」）渲染成小圆点。想让更多人被识别为导师，就往 `0_原始导师名单.xlsx` 里加名字后重跑 Step 0。

---

## 系统架构 · Architecture

```
                       ┌──────────────────────────┐
                       │        OpenAlex API      │
                       └───────────┬──────────────┘
                                   │ Step 0 爬虫
                                   ▼
                 ┌─────────────────────────────────────┐
                 │       Data Pipeline（9 阶段）        │
                 │  U1 ─► U1.5 ─► U2 ─► 聚类映射表      │
                 │       │            │    （人工/LLM 填）│
                 │       ▼            ▼         │       │
                 │     U2_5 ────► U3 组装 ◄─────┘       │
                 │                    │                 │
                 │   Step 4.5 分析 ◄──┘                 │
                 │   Step 5 入库 / Step 6 大屏          │
                 └─────────────┬───────────────────────┘
                               ▼
              ┌────────────────────────────────────────┐
              │  Neo4j（Scholar/Paper/Lab/Topic）       │
              │        + FastAPI + ECharts 大屏         │
              │  / 关系星图   /analytics 情报分析        │
              └────────────────────────────────────────┘
```

---

## 文件结构 · Project Structure

```
ACSN/
├── main.py                          # CLI 入口
├── gui_main.py                      # GUI 入口（PyInstaller 打包目标）
├── requirements.txt                 # 核心依赖
├── requirements-ml.txt              # 可选 NLP/ML 依赖（~2GB）
├── requirements-dev.txt             # 开发/测试依赖（pytest 等）
├── pytest.ini                       # pytest 配置
├── .gitignore
├── mkiv-gui.spec                    # PyInstaller 打包配置
│
├── config/
│   ├── config.example.yaml          # 配置模板（提交到 Git）
│   └── config.yaml                  # 用户配置（gitignored，自动生成）
│
├── core/                            # 引擎核心（按流水线阶段）
│   ├── crawler.py                   # Step 0：OpenAlex 爬虫（重试/缓存）
│   ├── author_matcher.py            # Step 0：作者画像匹配
│   ├── cleaner.py                   # Step 1-2：打标 + 清洗 + 实体提取
│   ├── analyzer.py                  # Step 3：SBERT 聚类 + 排头兵坍缩
│   ├── llm_labeler.py               # Step 3.5：LLM 批量预填 + 去重
│   ├── assembler.py                 # Step 4：终极组装 + 金钥匙兜底
│   ├── trend_analyzer.py            # Step 4.5：概念降维 + 演化/雷达/旭日图
│   ├── db_importer.py               # Step 5：CSV 导出 + Neo4j LOAD
│   ├── visualizer.py                # Step 6：FastAPI + ECharts 大屏
│   └── name_processor.py            # 中文名 → 拼音转换
│
├── pipelines/
│   ├── data_pipeline.py             # AcademicPipeline（9 阶段编排）
│   └── name_pipeline.py             # 姓名转换流水线
│
├── gui/                             # PySide6 桌面 GUI
│   ├── main_window.py               # 主窗口 + 视图切换
│   ├── parameter_panel.py           # 可滚动参数编辑器
│   ├── dashboard_panel.py           # QWebEngineView 大屏包装
│   ├── pipeline_runner.py           # QThread 流水线执行器
│   ├── neo4j_manager.py             # Docker Neo4j 生命周期管理
│   ├── startup_wizard.py            # 首次运行向导
│   ├── dark_theme.py                # 深色 QSS 主题
│   ├── help_texts.py                # 中文帮助提示
│   ├── log_handler.py               # logging → Qt Signal 转发
│   └── widgets.py                   # 可复用控件工厂
│
├── utils/
│   ├── file_handler.py              # JSON/Excel 读写
│   ├── model_loader.py              # 模型本地优先加载器
│   └── project_paths.py             # 路径解析（单一真相来源）
│
├── tests/                           # 离线测试套件（不联网 / 不连 Neo4j / 不加载模型）
├── scripts/                         # 合成演示数据与离线复现脚本
│   ├── generate_sample_data.py      # 用固定随机种子生成 data/sample/ 匿名数据
│   └── run_sample_pipeline.py       # 一条命令离线跑通 Step 1 → 5
│
├── models/                          # 本地 NLP 模型（gitignored，运行时下载或手动放置）
├── data/                            # 运行时数据（gitignored）
│   ├── input/                       # ★ 放置你的导师名单等输入 xlsx
│   ├── 01_raw/ … 03_cleaned/        # 流水线中间件（U1 → U2_5）
│   ├── output/                      # 最终结果与图表数据
│   ├── import/                      # Neo4j LOAD CSV 导入目录
│   └── sample/                      # 合成演示数据（提交到 Git，供离线复现）
├── .github/workflows/
│   ├── build.yml                    # CI/CD：Windows/Linux 打包发布
│   └── tests.yml                    # 测试：push / PR 触发（py3.10 / 3.11）
├── README.md
├── paper.md                         # JOSS 论文投稿
├── paper.bib                        # 论文参考文献
└── LICENSE                          # MIT
```

---

## Neo4j 图数据模型 · Graph Schema

```
(Scholar)-[:CO_WORK {weight}]-(Scholar)
(Scholar)-[:WROTE]->(Paper)
(Scholar)-[:BELONGS_TO]->(Lab)
(Paper)-[:MAPPED_TO]->(Topic)
```

| 节点 Node | 属性 Properties |
|-----------|----------------|
| Scholar | id, name, role, `labs[]`, `primary_lab`, `topics[]`, `primary_topic` |
| Paper | id, title, journal, doi |
| Lab | name |
| Topic | name |

> `labs`/`topics` 是**全部**归属（按「出现次数降序、名称升序」），`primary_lab`/`primary_topic` 是发文最多的那一项。四者在 Step 5 入库时物化写入，大屏直接读，不再查询时现算。
> `All` affiliations and the materialized primary one are written at Step 5; the dashboard only reads them.

---

## 维护参考 · Maintenance Reference

> 本节记录对外部接口的实测结论，用于后续升级排查。**最后校准：2026-09**（对照 OpenAlex API 当时返回）。外部接口会变，改动 `core/crawler.py` 前请重新核对。

### OpenAlex Works 接口返回结构

爬虫请求（`core/crawler.py`）：

```
GET https://api.openalex.org/works
    ?filter=authorships.institutions.lineage:{机构ID},publication_year:{起始}-{结束}
    &per-page={单页条数}&cursor=*&mailto={邮箱}
```

返回是一个**信封**，而不是数组：

```jsonc
{
  "meta": {
    "count": 5735,              // 该 filter 命中的总篇数 (全量, 非本页)
    "db_response_time_ms": 42,
    "page": null,                // cursor 分页时恒为 null
    "per_page": 200,
    "next_cursor": "IlsxNjA...", // 空/缺失 = 已取完最后一页
    "groups_count": null,
    "x_query": { "oql": "...", "oqo": { ... }, "url": "..." },
    "cost_usd": 0.0001
  },
  "results": [ /* 每页最多 200 篇 work 对象 */ ]
}
```

**两条分页硬规则**（决定了为什么必须用 cursor）：

| 规则 | 数值 / 行为 |
|------|------------|
| 单页上限 | `per-page` 最大 **200**，超过被静默截断为 200 |
| page 分页上限 | 只能翻到第 **10,000** 条；越界直接报错 `Maximum results size of 10,000 records is exceeded. Cursor pagination is required.` |
| cursor 语义 | `cursor=*` 起步，用上一页的 `meta.next_cursor` 续取；`meta.page` 为 `null` |
| 结束条件 | `meta.next_cursor` 为空 —— 爬虫据此置 `completed`，只有完整抓完才落盘缓存 |

因此本项目走 cursor 全量抓取：本机构 5,735 篇（2022–2026）全部拿得到，不受 1 万条限制。

### `results[]` 里本仓库实际消费的字段

| JSON 路径 | 用途 | 落到哪 |
|-----------|------|--------|
| `id` | work 主键（`https://openalex.org/W…`，取末段） | Paper.id |
| `title` | 论文标题 | Paper.title |
| `doi` | DOI 链接 | Paper.doi |
| `primary_location.source.display_name` | 期刊名 | Paper.journal |
| `concepts[].display_name` | 研究领域（**已标准化为 13 大类**，见映射表） | Topic.name / `MAPPED_TO` |
| `authorships[]` | 作者列表 | Scholar 节点 |
| `authorships[].author.id` | 作者主键 | Scholar.id（**注意：可能为 `null`**，需跳过） |
| `authorships[].author.display_name` | 作者名 | Scholar.name |
| `authorships[].raw_affiliation_strings[]` | 机构原始字符串（**逐条**建边，双聘不丢） | Lab.name / `BELONGS_TO` |
| `authorships[].raw_affiliation_string` | 单值兜底（老字段，仅在数组为空时使用） | 同上 |

> `is_internal_node` **不是** OpenAlex 字段，是 Step 2（`cleaner.py`）按 `authorships[].institutions[].id` / `lineage` 匹配本机构后**自己打**的标记。只有它命中的作者才会成为 Scholar 节点。

### 升级排查 · 三个已知坑

1. **`concepts` 已冻结（2024 起）**。OpenAlex 已转向 `topics` / `primary_topic`（domain → field → subfield → topic 四层）与独立的 `keywords`。本项目仍用 `concepts` + 本地映射表，所以领域分布高度集中在「人工智能」（实测 90.8% 的学者主领域是它，因为映射表把约 47% 的概念实例归到了这一项）。若追求更均衡的领域分布，应迁移到 `primary_topic`。
2. **`affiliations[]` 是 raw string ↔ 归一化机构 ID 的对照表**（`{raw_affiliation_string, institution_ids[]}`）。本项目**目前忽略**它，只用 `raw_affiliation_strings` 原串，靠人工/LLM 映射表归一。想减少人工映射工作量，这里是最现成的切入点。
3. **`authorships[].author.id` 可能为 `null`**（本项目 502 条 authorship 遇到过）。任何 `x.get("id", "")` 的写法都拦不住键存在但值为 `null` 的情况，必须写 `(x.get("id") or "")`，否则 `.split("/")` 会抛 `AttributeError`。

---

## 打包分发 · Distribution

```bash
# 本地打包
pyinstaller mkiv-gui.spec

# 或打 tag 触发 GitHub Actions 自动构建并发布 Release
git tag v1.0.0 && git push origin v1.0.0
```

产物发布到 GitHub Releases：
- `MKIV-Academic-Graph-Windows.zip`（Windows 10+）
- `MKIV-Academic-Graph-Linux.tar.gz`（Ubuntu 20.04+）

> 注意：EXE 默认**不含** NLP 聚类依赖（体积考虑，torch/sentence-transformers 被排除）。需要 NLP 的用户请从源码运行，或把 `models/` 模型目录随包分发。

---

## 致谢 · Acknowledgments

- 数据：[OpenAlex](https://openalex.org/)（CC0）
- 词向量：[Sentence-BERT](https://www.sbert.net/)（Reimers & Gurevych, 2019）
- 可视化：[Apache ECharts](https://echarts.apache.org/)
- 图数据库：[Neo4j](https://neo4j.com/)
- GUI：[PySide6](https://doc.qt.io/qtforpython-6/)（LGPL）

### AI 使用披露 · AI Usage Disclosure

本项目在开发过程中**大量使用生成式 AI**。所用工具、模型与分工如实披露如下。

| 工具 / 模型 | 形态与版本 | 承担的工作 |
|---|---|---|
| Gemini 3.5 Pro | Web 界面 | **核心程序主体**——产出量最大 |
| Claude Code CLI | 本地 CLI（终端 agent 框架） | 代码编写与重构、测试脚手架、文档与提交流程编排 |
| DeepSeek V4 Pro | `deepseek-v4-pro[1m]`，经 Anthropic 兼容端点调用 | GUI（`gui/`）与流水线编排（`pipelines/`）代码 |
| DeepSeek V4.1 Flash | `deepseek-flash`，经 Anthropic 兼容端点调用 | 论文与仓库文档草稿 |

> 表中 Claude Code CLI 是**承载工具**，DeepSeek 两个模型是**经由它调用的后端模型**；Gemini 则通过 Web 界面单独使用。
>
> **关于提交署名**：Claude Code CLI 默认会在 commit 中追加 `Co-Authored-By: Claude Code`。该署名标识的是**工具，不是底层模型**——底层模型是 DeepSeek。因此历史提交里出现该署名**不代表产出比例**，实际产出最多的模型是 Gemini。

**人类作者的贡献**：问题框定、把工作流拆解为各阶段、名单锚定的身份消解与「映射表即契约」的设计、流水线的装配方式与阶段间接口的定义。**所有 AI 产出——代码、测试与文档——均经人类作者复核、验证与修改**，并由其对本项目的准确性、原创性与许可合规承担责任。

**运行时组件**：本工具在 Step 3.5 提供可选的 LLM 映射预填功能（调用用户自行配置的 OpenAI 兼容接口）。它**默认关闭**；启用时结果写入独立表格并强制人工复核，未经人工裁决绝不生效；纯手工路径不接触任何外部模型。

**English.** Generative AI was used extensively in developing this project, and its use is disclosed in full below.

| Tool / model | Form and version | Work performed |
|---|---|---|
| Gemini 3.5 Pro | Web interface | **Core program body** — the largest share of output |
| Claude Code CLI | Local CLI (terminal agent harness) | Code authoring and refactoring, test scaffolding, documentation and commit workflow |
| DeepSeek V4 Pro | `deepseek-v4-pro[1m]`, via an Anthropic-compatible endpoint | GUI (`gui/`) and pipeline orchestration (`pipelines/`) code |
| DeepSeek V4.1 Flash | `deepseek-flash`, via an Anthropic-compatible endpoint | Drafting of the paper and repository documentation |

> Claude Code CLI in the table above is the **harness**; the two DeepSeek models are the **backend models it invokes**. Gemini was used separately through its web interface.
>
> **On commit attribution:** Claude Code CLI appends a `Co-Authored-By: Claude Code` trailer to commits by default. That trailer names **the tool, not the underlying model**, which is DeepSeek. Its presence in the history therefore does not reflect the share of output — Gemini produced the most.

**Human contribution:** the human author framed the problem, decomposed the workflow into stages, chose the roster-anchored identity resolution and the mapping-table-as-contract design, and specified how the pipeline is assembled and how its stages interface. All AI output — code, tests and prose — was reviewed, validated and edited by the human author, who is responsible for the accuracy, originality and licensing compliance of this project.

**Runtime component:** Step 3.5 offers an optional LLM pre-fill for mapping spreadsheets against a user-configured OpenAI-compatible endpoint. It is off by default; when enabled, its output goes to a separate spreadsheet under mandatory human review and is never applied without human arbitration. The manual path contacts no external model.

---

## 许可证 · License

MIT — 详见 [LICENSE](LICENSE)
