# MKIV 学术情报图谱引擎 <br> MKIV Academic Intelligence Graph Engine

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Neo4j](https://img.shields.io/badge/Neo4j-Graph_Database-4caf50.svg)](https://neo4j.com/)
[![OpenAlex](https://img.shields.io/badge/Data_Source-OpenAlex-ff69b4.svg)](https://openalex.org/)
[![PySide6](https://img.shields.io/badge/GUI-PySide6-darkgreen.svg)](https://doc.qt.io/qtforpython-6/)

**中文** | 面向科研机构的学术情报分析平台：从 OpenAlex 抓取、语义聚类清洗、LLM 辅助标注、Neo4j 入库，到 ECharts 交互式大屏——一条龙自动化。

**English** | An end-to-end academic intelligence platform: crawls publication data from OpenAlex, cleans and clusters noisy affiliation strings, optionally labels entities with LLM assistance, imports the result into Neo4j, and serves interactive ECharts dashboards — via both CLI and a desktop GUI.

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
| **多入口** Multi-Entry | CLI / GUI / PyInstaller EXE |

---

## 快速开始 · Quick Start

### 1. 环境准备

- **Python 3.10+**
- **Docker**（用于一键部署 Neo4j；也可连接已有 Neo4j，此时不需要）

### 2. 安装

```bash
git clone https://github.com/<your-username>/MKIV-Academic-Graph.git
cd MKIV-Academic-Graph
pip install -r requirements.txt

# NLP 聚类需要（约 2GB，含 sentence-transformers / scikit-learn）：
pip install -r requirements-ml.txt
```

### 3. 配置

首次运行会自动从 `config/config.example.yaml` 复制生成 `config/config.yaml`（该文件已被 gitignore，不会泄露）。只需填这几项：

```yaml
institution:
  email: "your@email.com"                  # 你的邮箱（OpenAlex 礼貌池需要）
  target_id: "https://openalex.org/IXXXX"  # 目标机构 OpenAlex ID
  start_year: 2021                          # 抓取起始年份
  fallback_keywords: ["Tsinghua", "THU"]   # 内部作者兜底关键词

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

```bash
python gui_main.py     # GUI（推荐，日常使用）
python main.py         # CLI（服务器 / 无头环境）
```

Windows 下也可直接双击 PyInstaller 打包出的 `MKIV_Academic_Graph.exe`。

---

## 核心工作流 · Core Workflow

整个流程只有**第二步需要人工介入**，其余全自动。

### ① 抓数据（Step 0–2，全自动）

爬取目标机构文献 → 标记内部/外部作者 → 清洗噪音。无需人工。

### ② 填映射表（Step 3 → 人工/LLM → Step 4）← 唯一需要你介入的环节

**为什么**：系统把数千个机构变体聚类成约 30 个「排头兵」（每簇选一个代表），把领域概念列成约 179 条，生成两张 Excel 模板，等你把它们翻译成规范中文名。

**两种方式，二选一**：

**A. 人工填写**（不依赖 LLM）：

1. 跑完 Step 3 后，打开 `data/input/` 下的两张表：
   - `1_机构映射表.xlsx` —— 在「填写标准名称」列，给 30 个排头兵填中文实验室名（如「模式识别国家重点实验室」）
   - `2_研究领域映射表.xlsx` —— 在「填写标准大类」列，给 179 个领域填中文大类（人工智能 / 计算机视觉 / 生物与医学 …）
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
| 3 | NLP 聚类 | `unique.json` → `U2.5.json` + 映射表 | SBERT 聚类 → 排头兵 + 空模板 |
| 3.5 | LLM 预填（可选） | 映射表 → `_AI预填版.xlsx` | LLM 批量预填 + 去重 |
| 4 | 终极组装 | `U2.5.json` + 映射表 → `U3.json` | 严格过滤 + 应用人工/LLM 映射 |
| 4.5 | 情报分析 | `U3.json` → trends / radar / sunburst | 概念降维 + 演化/雷达/旭日图 |
| 5 | 数据库导入 | `U3.json` → Neo4j | CSV 导出 + Cypher LOAD |
| 6 | 大屏 | Neo4j → Web :8001 | FastAPI + ECharts |

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
                 │     U2.5 ────► U3 组装 ◄─────┘       │
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
MKIV-Academic-Graph/
├── main.py                          # CLI 入口
├── gui_main.py                      # GUI 入口（PyInstaller 打包目标）
├── requirements.txt                 # 核心依赖
├── requirements-ml.txt              # 可选 NLP/ML 依赖（~2GB）
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
├── models/                          # 本地 NLP 模型（gitignored，运行时下载）
├── data/                            # 运行时数据（gitignored）
├── .github/workflows/build.yml      # CI/CD：Windows/Linux 打包发布
├── README.md
├── paper.md                         # JOSS 论文投稿
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
| Scholar | id, name, role |
| Paper | id, title, journal, doi |
| Lab | name |
| Topic | name |

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
- 开发过程中使用了 AI 辅助编程。

---

## 许可证 · License

MIT — 详见 [LICENSE](LICENSE)
