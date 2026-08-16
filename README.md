# MKIV 学术情报图谱引擎 <br> MKIV Academic Intelligence Graph Engine

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Neo4j](https://img.shields.io/badge/Neo4j-Graph_Database-4caf50.svg)](https://neo4j.com/)
[![OpenAlex](https://img.shields.io/badge/Data_Source-OpenAlex-ff69b4.svg)](https://openalex.org/)
[![PySide6](https://img.shields.io/badge/GUI-PySide6-darkgreen.svg)](https://doc.qt.io/qtforpython-6/)

**中文** | MKIV 是一款面向科研机构的学术情报分析平台。从 OpenAlex 数据爬取、语义聚类清洗、LLM 辅助标注、Neo4j 入库，到 ECharts 交互式大屏展示——一条龙自动化。

**English** | MKIV is an end-to-end academic intelligence platform. It crawls publication data from OpenAlex, cleans and clusters noisy affiliation strings, optionally labels entities with LLM assistance, imports structured data into Neo4j, and serves interactive ECharts dashboards — all automated in a single pipeline, with both CLI and desktop GUI interfaces.

---

## 核心功能 · Core Features

| Feature | 说明 · Description |
|---------|---------------------|
| **数据治理** Data Cleaning | 数千种机构/学科变体 → 聚类坍缩为"排头兵"标准名。Thousands of raw variants collapsed into standard "vanguard" names via SBERT clustering. |
| **人机协同** Human-in-the-Loop | LLM 预填映射表 → 人工复核。LLM pre-fills mapping templates, human reviews and corrects. |
| **情报分析** Analytics | 概念降维 → ThemeRiver 演化图 + 实验室雷达图 + 主题旭日图。Dimensionality reduction → evolution, radar, and sunburst charts. |
| **双视角大屏** Dual Dashboard | 关系星图 (合作网络) + 情报分析 (演化趋势)。Force graph (collaboration) + analytics (trends). |
| **一键 Docker** One-Click Deploy | GUI 内置 Neo4j 容器管理。Built-in Docker container lifecycle for Neo4j. |
| **桌面 GUI** Desktop App | PySide6 深色主题，参数面板 + 内嵌 ECharts + 实时日志 + 向导。Dark theme, embedded browser, real-time log. |
| **多入口** Multi-Entry | CLI / GUI / PyInstaller EXE。 |

## 系统架构 · Architecture

```
                          ┌──────────────────────────────────┐
                          │        OpenAlex API              │
                          └──────────────┬───────────────────┘
                                         │ Step 0: Crawler
                                         ▼
                    ┌────────────────────────────────────────┐
                    │          Data Pipeline (9 stages)       │
                    │                                        │
                    │  U1 Raw ──► U1.5 Tagged ──► U2 Cleaned │
                    │                     │                   │
                    │   Step 3: SBERT Clustering (vanguards) │
                    │   Step 3.5: LLM Auto-Label (optional)  │
                    │   Step 4: Final Assembly ──► U3 Gold   │
                    │   Step 4.5: Analytics ◄──              │
                    │   Step 5: Neo4j Import                 │
                    │   Step 6: Dashboard Server             │
                    └──────────────────┬─────────────────────┘
                                       │
                    ┌──────────────────┼──────────────────────┐
                    │                  ▼                       │
                    │  ┌──────────────────────────────┐       │
                    │  │    Neo4j Graph Database       │       │
                    │  │  Scholar │ Paper │ Lab │ Topic│       │
                    │  │  CO_WORK │ WROTE │ BELONGS_TO  │    │
                    │  └──────────────┬───────────────┘       │
                    │                 │                        │
                    │  ┌──────────────▼───────────────┐       │
                    │  │  FastAPI + ECharts Dashboard │       │
                    │  │  / (Force Graph)              │       │
                    │  │  /analytics (ThemeRiver/Radar)│       │
                    │  └──────────────────────────────┘       │
                    └──────────────────────────────────────────┘
```

## 文件结构 · Project Structure

```
MKIV-Academic-Graph/
├── main.py                          # CLI entry point
├── gui_main.py                      # GUI entry point (PyInstaller target)
├── requirements.txt                 # Core dependencies
├── requirements-ml.txt              # Optional NLP/ML (~2 GB)
├── mkiv-gui.spec                    # PyInstaller spec
│
├── config/
│   ├── config.example.yaml          # Template (committed)
│   └── config.yaml                  # User config (gitignored, auto-generated)
│
├── core/                            # 10 engine modules
│   ├── crawler.py                   # Step 0: REST crawler with caching
│   ├── cleaner.py                   # Step 1-2: institution tagging + rule cleaning
│   ├── analyzer.py                  # Step 3: SBERT clustering + vanguard collapse
│   ├── llm_labeler.py               # Step 3.5: LLM batch labeling + dedup
│   ├── assembler.py                 # Step 4: final assembly + golden-key fallback
│   ├── author_matcher.py            # Step 0: author profile matching
│   ├── trend_analyzer.py            # Step 4.5: concept reduction + evolution/radar/sunburst
│   ├── db_importer.py               # Step 5: CSV export + Neo4j LOAD
│   ├── visualizer.py                # Step 6: FastAPI + ECharts (2 pages)
│   └── name_processor.py            # Chinese → Pinyin conversion
│
├── pipelines/                       # Pipeline orchestration
│   ├── data_pipeline.py             # 9-stage AcademicPipeline
│   └── name_pipeline.py             # Name conversion pipeline
│
├── gui/                             # PySide6 desktop GUI
│   ├── main_window.py               # Main window + view switching
│   ├── parameter_panel.py           # Scrollable config editor (8 groups)
│   ├── dashboard_panel.py           # QWebEngineView wrapper
│   ├── pipeline_runner.py           # QThread pipeline executor
│   ├── neo4j_manager.py             # Docker Neo4j lifecycle (deploy/start/stop/restart)
│   ├── startup_wizard.py            # 3-page first-run wizard
│   ├── dark_theme.py                # Dark QSS stylesheet
│   ├── help_texts.py                # Chinese help tooltips
│   ├── log_handler.py               # logging → Qt Signal relay
│   └── widgets.py                   # Reusable widget factories
│
├── utils/
│   └── file_handler.py              # JSON/Excel I/O
│
├── data/                            # Runtime data (gitignored)
├── .github/workflows/build.yml      # CI/CD: Windows + Linux builds
├── README.md
├── paper.md                         # JOSS submission
└── LICENSE                          # MIT
```

## 快速启动 · Quick Start

### 1. 安装 · Install

```bash
git clone https://github.com/<your-username>/MKIV-Academic-Graph.git
cd MKIV_Academic_Graph
pip install -r requirements.txt

# Optional: NLP clustering + LLM analysis (~2 GB)
pip install -r requirements-ml.txt
```

### 2. 配置 · Configure

On first run, `config/config.yaml` is auto-generated from the template. Edit it:

```yaml
institution:
  email: "your@email.com"                  # Your email (required by OpenAlex)
  target_id: "https://openalex.org/IXXXX"  # Your institution's OpenAlex ID
  fallback_keywords: ["Tsinghua", "THU"]   # Keywords to match internal authors
  golden_keys:                             # Last-resort keyword → standard name
    "CS Dept": "Department of Computer Science"

database:
  password: "change-me"                    # ⚠️ Change this
```

### 3. 启动 · Launch

#### Windows

| Method | Command | For |
|--------|---------|-----|
| **GUI** | `python gui_main.py` | Daily use |
| **CLI→GUI** | `python main.py --gui` | Developers |
| **CLI** | `python main.py` | Server / headless |
| **EXE** | Double-click `MKIV_Academic_Graph.exe` | Zero-dependency end users |

> GPU acceleration remains enabled on Windows (DirectX).

#### Linux

| Method | Command | Notes |
|--------|---------|-------|
| **GUI** | `python gui_main.py` | GPU auto-disabled to prevent flicker |
| **CLI→GUI** | `python main.py --gui` | Same as above |
| **CLI** | `python main.py` | Recommended for servers |
| **Binary** | `./MKIV_Academic_Graph` | PyInstaller build |

> Linux automatically sets `QTWEBENGINE_CHROMIUM_FLAGS='--disable-gpu'` for stable rendering.

### 4. 启动 Neo4j · Start Neo4j

Neo4j must be running before the dashboard can display data.

**A: GUI one-click (recommended)** — Click `🐳 Deploy` in the database panel. The GUI handles image pull, container creation, volume mounting, and health checks.

**B: Docker CLI** —
```bash
mkdir -p ./data/import
docker run -d --name mkiv_neo4j \
  -p 7688:7687 -p 7689:7474 \
  -e NEO4J_AUTH=neo4j/your_password \
  -e NEO4J_server_directories_import=/import \
  -v $(pwd)/data/import:/import \
  neo4j:5-community
```

**C: Manual install** — Download from [neo4j.com](https://neo4j.com/), set password, configure `database.uri` in config.yaml.

```bash
# Container lifecycle
docker stop mkiv_neo4j      # Stop
docker start mkiv_neo4j     # Start
docker rm -f mkiv_neo4j     # Remove
```

### 5. 运行模式 · Run Modes

| Mode | Stages | Use case |
|------|--------|----------|
| **Dashboard only** | Step 6 | View existing data |
| **Full pipeline** | Step 0→6 | First-time run: crawl to dashboard |
| **Step-by-step** | User-selected | Debugging / re-running specific stages |

## 数据流水线 · Pipeline Stages

| Step | Name | Input → Output | Description |
|------|------|----------------|-------------|
| 0 | Data Acquisition | OpenAlex API → U1.json | Crawl + author matching |
| 1 | Tagging U1.5 | U1.json → U1.5.json | Internal/external author tagging |
| 2 | Cleaning U2 | U1.5.json → U2.json | Noise removal + unique entity extraction |
| 3 | NLP Clustering | unique.json → U2.5.json + Excel | SBERT cluster → vanguards → human review |
| 3.5 | LLM Label (opt.) | Excel → _AI_prefilled.xlsx | Batch LLM labeling + dedup |
| 4 | Final Assembly | U2.5 + reviewed Excel → U3.json | Strict filtering + golden-key fallback |
| 4.5 | Analytics | U3.json → trends/radar/sunburst | Concept reduction + evolution analysis |
| 5 | DB Import | U3.json + profile table → Neo4j | CSV export + Cypher LOAD |
| 6 | Dashboard | Neo4j → Web :8001 | FastAPI + ECharts (2 pages) |

## Neo4j 图数据模型 · Graph Schema

```
(Scholar)-[:CO_WORK {weight}]-(Scholar)
(Scholar)-[:WROTE]->(Paper)
(Scholar)-[:BELONGS_TO]->(Lab)
(Paper)-[:MAPPED_TO]->(Topic)
```

| Node | Properties |
|------|------------|
| Scholar | id, name, role |
| Paper | id, title, journal, doi |
| Lab | name |
| Topic | name |

## 打包分发 · Distribution

```bash
# Local build
pyinstaller mkiv-gui.spec

# Or push a tag to trigger GitHub Actions CI/CD
git tag v1.0.0 && git push origin v1.0.0
```

Build artifacts are published to GitHub Releases:
- `MKIV-Academic-Graph-Windows.zip` (Windows 10+)
- `MKIV-Academic-Graph-Linux.tar.gz` (Ubuntu 20.04+)

## 用户自行准备 · User-Provided

| Item | Description |
|------|-------------|
| **Docker Desktop** | Required for one-click Neo4j deploy |
| **Mentor name list** | `data/input/0_原始导师名单.xlsx` |
| **Mapping tables** | Generated at Step 3, reviewed by human before Step 4 |
| **NLP deps** | `pip install -r requirements-ml.txt` (if clustering needed) |

## 致谢 · Acknowledgments

- Data: [OpenAlex](https://openalex.org/) (CC0)
- Embeddings: [Sentence-BERT](https://www.sbert.net/) (Reimers & Gurevych, 2019)
- Visualization: [Apache ECharts](https://echarts.apache.org/)
- Graph DB: [Neo4j](https://neo4j.com/)
- GUI: [PySide6](https://doc.qt.io/qtforpython-6/) (LGPL)
- AI assistance used during GUI and pipeline development.

## 许可证 · License

MIT — see [LICENSE](LICENSE)
