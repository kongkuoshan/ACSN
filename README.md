# MKIV 学术情报图谱引擎 (MKIV Academic Intelligence Graph Engine)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Neo4j](https://img.shields.io/badge/Neo4j-Graph_Database-4caf50.svg)](https://neo4j.com/)
[![OpenAlex](https://img.shields.io/badge/Data_Source-OpenAlex-ff69b4.svg)](https://openalex.org/)
[![PySide6](https://img.shields.io/badge/GUI-PySide6-darkgreen.svg)](https://doc.qt.io/qtforpython-6/)

**MKIV** 是一款面向科研机构的全链路学术情报分析平台。从 OpenAlex 数据爬取、语义聚类清洗、LLM 辅助标注、Neo4j 图数据库入库，到 ECharts 交互式大屏展示——**一条龙自动化**。

**MKIV** is an end-to-end academic intelligence workstation: crawl OpenAlex, clean with NLP clustering, label with LLM assistance, import into Neo4j, and explore via interactive ECharts dashboards.

---

## 核心功能 (Core Features)

| 功能 | 说明 |
|------|------|
| **自动化数据治理** | 容错爬虫 + 正则规则 + SentenceTransformer 聚类 → 将数千种机构/学科变体坍缩为标准"排头兵 (Vanguard)" |
| **人机协同 (HITL)** | LLM 预填映射表 → 人工复核 → 工作量降低 95%+ |
| **情报分析引擎** | 概念维度降维 → ThemeRiver 演化河流图 + 实验室雷达图 + 主题旭日图 |
| **双视角大屏** | 🕸️ 关系星图 (学者合作网络) + 📈 情报分析 (演化趋势/研究倾向) |
| **一键 Docker 部署** | GUI 内置 Neo4j 容器管理，无需手动安装数据库 |
| **桌面 GUI** | PySide6 深色主题，参数面板 + 内嵌 ECharts + 实时日志 + 首次运行向导 |
| **多入口设计** | CLI (开发者) / GUI (用户) / PyInstaller 打包 EXE (零依赖) |

## 系统架构 (System Architecture)

```
                          ┌──────────────────────────────────┐
                          │        OpenAlex API              │
                          └──────────────┬───────────────────┘
                                         │ Step 0: Crawler
                                         ▼
                    ┌────────────────────────────────────────┐
                    │          Data Pipeline (9 Stages)       │
                    │                                        │
                    │  U1 Raw ──► U1.5 Tagged ──► U2 Cleaned │
                    │                     │                   │
                    │   Step 3: NLP Clustering (排头兵 SVP)  │
                    │   Step 3.5: LLM Auto-Label (Optional)  │
                    │   Step 4: Final Assembly ──► U3 Gold   │
                    │   Step 4.5: Intelligence Analytics ◄── │
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

## 文件结构 (Project Structure)

```
MKIV_Academic_Graph/
├── main.py                          # CLI 入口
├── gui_main.py                      # GUI 入口 (PyInstaller 目标)
├── requirements.txt                 # 核心依赖
├── requirements-ml.txt              # 可选 NLP/ML 依赖
├── mkiv-gui.spec                    # PyInstaller 打包配置
│
├── config/
│   ├── config.example.yaml          # 配置模板 (上传 GitHub)
│   └── config.yaml                  # 用户配置 (本地, 不上传)
│
├── core/                            # 核心引擎 (10 模块)
│   ├── crawler.py                   # Step 0: OpenAlex 爬虫 (断点续传)
│   ├── cleaner.py                   # Step 1-2: 机构打标 + 硬规则清洗
│   ├── analyzer.py                  # Step 3: SentenceTransformer 聚类 + 排头兵坍缩
│   ├── llm_labeler.py               # Step 3.5: LLM API 自动预填
│   ├── assembler.py                 # Step 4: 终极清洗 + 真值注入
│   ├── author_matcher.py            # Step 0: 作者画像匹配引擎
│   ├── trend_analyzer.py            # Step 4.5: 概念降维 + 演化/雷达/主题分析
│   ├── db_importer.py               # Step 5: CSV 导出 + Neo4j LOAD
│   ├── visualizer.py                # Step 6: FastAPI + ECharts 大屏
│   └── name_processor.py            # 中文名 → 拼音转换
│
├── pipelines/                       # 流水线编排
│   ├── data_pipeline.py             # 主流水线 (9 阶段编排)
│   └── name_pipeline.py             # 姓名转换流水线
│
├── gui/                             # 桌面 GUI (PySide6)
│   ├── main_window.py               # 主窗口 + 视图切换
│   ├── parameter_panel.py           # 参数配置面板 (8 组)
│   ├── dashboard_panel.py           # WebEngine 大屏嵌入
│   ├── pipeline_runner.py           # QThread 流水线执行器
│   ├── neo4j_manager.py             # Docker Neo4j 生命周期管理
│   ├── startup_wizard.py            # 首次运行 3 页向导
│   ├── dark_theme.py                # 深色 QSS 主题
│   ├── help_texts.py                # 中文帮助文本
│   ├── log_handler.py               # 日志 → Qt 信号
│   └── widgets.py                   # 可复用组件工厂
│
├── utils/
│   └── file_handler.py              # JSON/Excel 读写工具
│
├── data/                            # 运行时数据 (不上传)
│   ├── input/                       # 输入: 导师名单, 映射表
│   └── output/                      # 输出: U3.json, trends.json, 画像表
│
└── .github/workflows/
    └── build.yml                    # CI/CD: Windows + Linux 自动构建
```

## 快速启动 (Quick Start)

### 1. 克隆与安装

```bash
git clone https://github.com/<your-username>/MKIV_Academic_Graph.git
cd MKIV_Academic_Graph
pip install -r requirements.txt

# 如需 NLP 聚类 + LLM 分析 (可选, ~2GB):
pip install -r requirements-ml.txt
```

### 2. 配置

首次运行会自动从 `config/config.example.yaml` 生成 `config/config.yaml`。编辑它：

```yaml
institution:
  email: "youremail@example.com"           # 改为你的邮箱
  target_id: "https://openalex.org/IXXXX"  # 改为你的机构 ID

database:
  password: "修改此密码"                    # ⚠️ 务必修改
```

### 3. 启动 — 三种方式

| 方式 | 命令 | 适用场景 |
|------|------|---------|
| **GUI 桌面** | `python gui_main.py` | 日常使用，参数面板 + 内嵌大屏 |
| **CLI + GUI** | `python main.py --gui` | 开发者，通过命令行切换 |
| **CLI 批处理** | `python main.py` | 服务器 / 无头环境 |
| **打包 EXE** | 双击 `MKIV_Academic_Graph.exe` | 最终用户，无需安装 Python |

### 4. Neo4j 部署

- **方式 A (推荐)**: GUI 内点击 `🐳 一键使用 Docker 部署本地 Neo4j` — 自动拉取镜像、创建容器、挂载导入目录
- **方式 B**: 自行安装 Neo4j，在 GUI 中填写连接 URI

### 5. 流水线运行模式

| 模式 | 执行内容 |
|------|---------|
| **一键启动大屏** | 仅 Step 6 — 直接查看已有数据 |
| **完整流水线** | Step 0→6 全流程 (爬虫→清洗→聚类→入库→大屏) |
| **分步执行** | 手动勾选阶段，灵活调试 |

## 数据流水线 (Pipeline Stages)

| Step | 名称 | 输入 | 输出 | 核心逻辑 |
|------|------|------|------|---------|
| 0 | 数据采集与作者画像 | OpenAlex API | U1.json + 0_画像表 | 全量爬取 + 导师匹配 |
| 1 | 靶向过滤 U1.5 | U1.json | U1.5.json | 机构 ID + 关键词打标 (内部/外部) |
| 2 | 硬规则清洗 U2 | U1.5.json | U2.json + unique.json | 去噪 + 提取唯一实体 |
| 3 | NLP 聚类 U2.5 | unique.json | U2.5.json + Excel 模板 | SBERT 聚类 → 排头兵 → 人工校验 |
| 3.5 | LLM 预填 (可选) | Excel 模板 | _AI预填版.xlsx | 调用 LLM API 自动填表 |
| 4 | 终极组装 U3 | U2.5.json + 人工校验 | U3.json | 严格过滤 + 真值注入 |
| 4.5 | 情报挖掘与演化分析 | U3.json | trends.json + radar.json | 概念降维 + 演化/雷达/主题 |
| 5 | 数据库导入 | U3.json + 0_画像表 | Neo4j | CSV 导出 + Cypher LOAD |
| 6 | 启动大屏 | Neo4j | Web :8000 | FastAPI + ECharts |

## Neo4j 图数据模型

```
(Scholar)-[:CO_WORK {weight}]-(Scholar)
(Scholar)-[:WROTE]->(Paper)
(Scholar)-[:BELONGS_TO]->(Lab)
(Paper)-[:MAPPED_TO]->(Topic)
```

- **Scholar**: 学者 (id, name, role)
- **Paper**: 论文 (id, title, journal, doi)
- **Lab**: 实验室 (name)
- **Topic**: 研究主题 (name)

## 打包分发 (Distribution)

```bash
# 本地构建
pyinstaller mkiv-gui.spec

# 或推送 tag 触发 GitHub Actions 自动构建
git tag v1.0.0
git push origin v1.0.0
```

构建产物自动发布到 GitHub Releases：
- `MKIV-Academic-Graph-Windows.zip` (Windows 10+)
- `MKIV-Academic-Graph-Linux.tar.gz` (Ubuntu 20.04+)

## 用户需要自行准备

| 项目 | 说明 |
|------|------|
| **Docker Desktop** | 一键部署 Neo4j 需要，可从 docker.com 下载 |
| **导师名单 Excel** | `data/input/0_原始导师名单.xlsx` |
| **机构映射表** | Step 3 生成 → 人工填写 → Step 4 使用 |
| **NLP 依赖** | `pip install -r requirements-ml.txt` (如需聚类) |

## 致谢 (Acknowledgments)

- 数据源: [OpenAlex](https://openalex.org/)
- 可视化: [ECharts](https://echarts.apache.org/)
- 图数据库: [Neo4j](https://neo4j.com/)
- AI 协同: 架构设计与核心逻辑由作者与 Claude Code 协同完成

## 许可证 (License)

MIT License — 详见 [LICENSE](LICENSE)
