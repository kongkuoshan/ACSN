# MKIV 学术情报图谱引擎 — 文件树与代码引用关系说明 <br> MKIV Academic Intelligence Graph Engine — File Tree & Code Reference Guide

> 本说明只关注**项目相关文件**，已排除 `.git/`、`__pycache__/`、`data/`（运行时产物）、`.claude/` 等非源码/非交付文件。
> This guide covers **project-related files only**, excluding `.git/`, `__pycache__/`, `data/` (runtime artifacts), `.claude/`, etc.

---

## 1. 项目文件树 · Project File Tree

```
MKIV-Academic-Graph/
├── main.py                          # CLI 入口 · CLI entry point
├── gui_main.py                      # GUI 入口 (PyInstaller 打包目标) · GUI entry (PyInstaller target)
├── requirements.txt                 # 核心依赖 · Core dependencies
├── requirements-ml.txt              # 可选 NLP/ML 依赖 (~2GB) · Optional NLP/ML deps
├── mkiv-gui.spec                    # PyInstaller 打包配置 · PyInstaller spec
├── README.md                        # 项目说明 (中英双语) · Project README (bilingual)
├── paper.md                         # JOSS 论文投稿 · JOSS submission
├── LICENSE                          # MIT 许可证 · MIT license
│
├── config/
│   ├── config.example.yaml          # 配置模板 (提交到 Git) · Config template (committed)
│   └── config.yaml                  # 用户配置 (gitignored，首次运行自动生成) · User config (gitignored, auto-generated)
│
├── core/                            # 引擎核心 (10 个模块) · Engine core (10 modules)
│   ├── crawler.py                   # Step 0: OpenAlex REST 爬虫 (带缓存/重试) · REST crawler (cache/retry)
│   ├── author_matcher.py            # Step 0: 导师画像本地匹配 · Author profile local matching
│   ├── cleaner.py                   # Step 1-2: 内部节点打标 + 硬规则清洗 · Node tagging + rule cleaning
│   ├── analyzer.py                  # Step 3: SBERT 聚类 → 排头兵坍缩 · SBERT clustering + vanguard collapse
│   ├── llm_labeler.py               # Step 3.5: LLM 批量预填 + 去重 · LLM batch labeling + dedup
│   ├── assembler.py                 # Step 4: U3 终极组装 + 金钥匙兜底 · Final assembly + golden-key fallback
│   ├── trend_analyzer.py            # Step 4.5: 概念降维 + 演化/雷达/旭日图 · Concept reduction + evolution/radar/sunburst
│   ├── db_importer.py               # Step 5: CSV 导出 + Neo4j LOAD · CSV export + Neo4j LOAD
│   ├── visualizer.py                # Step 6: FastAPI + ECharts 大屏 · FastAPI + ECharts dashboard
│   └── name_processor.py            # 中文名 → 拼音转换 · Chinese → Pinyin conversion
│
├── pipelines/                       # 流水线编排层 · Pipeline orchestration
│   ├── data_pipeline.py             # AcademicPipeline (9 阶段编排) · 9-stage orchestration
│   └── name_pipeline.py             # NameConversionPipeline (姓名转换) · Name conversion
│
├── gui/                             # PySide6 桌面 GUI · Desktop GUI
│   ├── main_window.py               # 主窗口 + 视图切换 · Main window + view switching
│   ├── parameter_panel.py           # 可滚动参数编辑器 (8 组) · Scrollable config editor (8 groups)
│   ├── dashboard_panel.py           # QWebEngineView 大屏包装 · WebEngine dashboard wrapper
│   ├── pipeline_runner.py           # QThread 流水线执行器 · QThread pipeline executor
│   ├── neo4j_manager.py             # Docker Neo4j 生命周期管理 · Docker Neo4j lifecycle
│   ├── startup_wizard.py            # 首次运行 3 页向导 · First-run 3-page wizard
│   ├── dark_theme.py                # 深色 QSS 主题 · Dark QSS theme
│   ├── help_texts.py                # 中文帮助提示字典 · Chinese help tooltips
│   ├── log_handler.py               # logging → Qt Signal 转发 · logging → Qt Signal relay
│   ├── widgets.py                   # 可复用控件工厂 · Reusable widget factories
│   ├── __init__.py                  # 包标记 · Package marker
│   └── resources/.gitkeep           # 资源目录占位 · Resources placeholder
│
├── utils/                           # 通用工具层 · Utilities
│   ├── project_paths.py             # 路径解析 (单一真相来源) · Path resolution (single source of truth)
│   └── file_handler.py              # JSON/Excel 读写 · JSON/Excel I/O
│
├── data/                            # 运行时数据 (gitignored) · Runtime data (gitignored)
│   └── 01_raw/U1.json               # 中间件示例 · Intermediate artifact example
│
└── .github/workflows/build.yml      # CI/CD: Windows + Linux 打包发布 · CI/CD builds & releases
```

---

## 2. 分层架构与引用关系 · Layered Architecture & References

代码按依赖方向自下而上分为 5 层，**上层可引用下层，下层不得反向引用上层**。
The code is organized into 5 layers bottom-up; **upper layers may import lower layers, never the reverse**.

```
┌─────────────────────────────────────────────────────────────────┐
│  入口层 Entry                                                      │
│  main.py ──► pipelines.data_pipeline.AcademicPipeline              │
│  main.py --gui ──► gui_main.main ──► gui.main_window.MainWindow   │
└───────────────┬─────────────────────────────────────────────────┘
                │ 调用 calls
┌───────────────▼─────────────────────────────────────────────────┐
│  编排层 Pipeline                                                   │
│  pipelines/data_pipeline.py  (AcademicPipeline)                    │
│  pipelines/name_pipeline.py  (NameConversionPipeline)              │
└───────────────┬─────────────────────────────────────────────────┘
                │ 调用 (from core.* import ...)
┌───────────────▼─────────────────────────────────────────────────┐
│  引擎层 Core (10 模块，按流水线阶段串联)                             │
│  crawler ─► author_matcher ─► cleaner ─► analyzer                  │
│       ─► llm_labeler ─► assembler ─► trend_analyzer                │
│       ─► db_importer ─► visualizer   (+ name_processor)            │
└───────────────┬─────────────────────────────────────────────────┘
                │ 调用 (from utils.* import ...)
┌───────────────▼─────────────────────────────────────────────────┐
│  工具层 Utils                                                      │
│  utils/project_paths.py   utils/file_handler.py                    │
└─────────────────────────────────────────────────────────────────┘

GUI 层 (PySide6) 横向引用 · GUI layer lateral references:
  gui_main.py ─► gui.main_window.MainWindow
  MainWindow  ─► parameter_panel / dashboard_panel / pipeline_runner
                 neo4j_manager / startup_wizard / log_handler / dark_theme
  pipeline_runner ─► pipelines.data_pipeline.AcademicPipeline
  parameter_panel ─► widgets ─► help_texts
```

### 依赖关系明细 · Import Dependency Matrix (谁 import 谁 / who imports whom)

| 文件 File | 引用的内部模块 Internal imports | 引用的外部库 External libs |
|-----------|-------------------------------|---------------------------|
| `main.py` | `utils.project_paths`、`pipelines.data_pipeline`、`gui_main` | yaml, logging |
| `gui_main.py` | `utils.project_paths`、`gui.dark_theme`、`gui.main_window` | PySide6 |
| `pipelines/data_pipeline.py` | 全部 `core.*`、`utils.file_handler`、`utils.project_paths` | logging |
| `pipelines/name_pipeline.py` | `utils.file_handler`、`core.name_processor` | logging |
| `core/crawler.py` | `utils.file_handler` | requests, urllib3 |
| `core/author_matcher.py` | — | pandas |
| `core/cleaner.py` | — | re, tqdm |
| `core/analyzer.py` | — | sentence_transformers, sklearn |
| `core/llm_labeler.py` | — | requests, pandas |
| `core/assembler.py` | — | pandas, tqdm |
| `core/trend_analyzer.py` | (函数内懒加载 SBERT/sklearn) | tqdm |
| `core/db_importer.py` | — | neo4j, pandas |
| `core/visualizer.py` | `utils.project_paths` | fastapi, neo4j, uvicorn |
| `core/name_processor.py` | — | pypinyin, pandas |
| `utils/project_paths.py` | — | os, sys |
| `utils/file_handler.py` | — | pandas, json |
| `gui/main_window.py` | `gui.{parameter_panel,dashboard_panel,pipeline_runner,neo4j_manager,log_handler,dark_theme,startup_wizard}`、`utils.project_paths` | PySide6 |
| `gui/pipeline_runner.py` | `pipelines.data_pipeline` | PySide6 |
| `gui/parameter_panel.py` | `gui.widgets`、`utils.project_paths` | PySide6, yaml |
| `gui/widgets.py` | `gui.help_texts` | PySide6, openpyxl |
| `gui/neo4j_manager.py` | — | PySide6, subprocess |
| `gui/dashboard_panel.py` | — | PySide6 |
| `gui/startup_wizard.py` | — | PySide6 |
| `gui/log_handler.py` | — | PySide6, logging |
| `gui/dark_theme.py` | — | PySide6 |
| `gui/help_texts.py` | — | (纯数据字典 / pure data dict) |

---

## 3. 各文件作用详解 · File-by-File Roles

### 3.1 入口层 · Entry Layer

| 文件 File | 作用 Role |
|-----------|-----------|
| `main.py` | **CLI 入口**。首次运行自动从模板生成 `config.yaml` → 加载并解析路径 → 实例化 `AcademicPipeline` → 默认执行 `run_dashboard_stage()`（可取消注释其它阶段重跑）。`--gui` 参数跳转到 GUI。**CLI entry**: auto-generates config on first run, loads & resolves paths, instantiates `AcademicPipeline`, runs `run_dashboard_stage()` by default (uncomment other stages to re-run). `--gui` jumps to the GUI. |
| `gui_main.py` | **GUI 入口 / PyInstaller 打包目标**。依赖检查 → 首次运行生成配置 → Linux 下禁用 GPU 修复闪烁 → 应用深色主题 → 创建并显示 `MainWindow`。**GUI entry / PyInstaller target**: dependency check → config generation → GPU disable (Linux flicker fix) → dark theme → show `MainWindow`. |

### 3.2 工具层 · Utilities `utils/`

| 文件 File | 作用 Role |
|-----------|-----------|
| `project_paths.py` | **路径解析单一真相来源**。基于文件物理位置向上查找项目根，不依赖 CWD。提供 `PROJECT_ROOT`、`get_config_path()`、`get_data_path()`、`resolve_all_paths()`、`ensure_in_sys_path()`。**Single source of truth for paths**: locates project root from file location (CWD-independent). |
| `file_handler.py` | **JSON/Excel 读写**。`load_json`/`save_json`/`load_excel`/`save_excel`，统一处理文件不存在、返回类型不一致等边界。**JSON/Excel I/O** with uniform edge-case handling. |

### 3.3 引擎层 · Engine Core `core/`（按流水线阶段 / by pipeline stage）

| 文件 File | 阶段 Stage | 作用 Role |
|-----------|-----------|-----------|
| `crawler.py` | Step 0 | `run_openalex_crawler()`：带缓存、重试、限速的 OpenAlex REST 爬虫，产出 U1.json。Cached/retried/rate-limited crawler → U1.json. |
| `author_matcher.py` | Step 0 | `build_local_database()` / `match_names_locally()`：用已爬取文献建立本地作者库，匹配导师名单。Builds a local author DB to match mentor lists. |
| `cleaner.py` | Step 1-2 | `tag_internal_nodes()`（内部/外部作者打标）、`extract_and_clean_entities()`（去噪 + 提取机构/领域实体）。Tagging + noise removal + entity extraction. |
| `analyzer.py` | Step 3 | `build_cluster_mappings()`（SBERT 语义聚类出"排头兵"）、`apply_vanguard_mapping()`（变体坍缩为标准名）。SBERT clustering → vanguards → collapse variants. |
| `llm_labeler.py` | Step 3.5 | `ask_llm()` / `auto_label_concepts()` / `auto_label_affiliations_batch()` / `deduplicate_standard_names()`：调用 OpenAI 兼容 API 预填映射表并去重。LLM pre-fill via OpenAI-compatible API + dedup. |
| `assembler.py` | Step 4 | `parse_mapping_rules()` / `generate_final_u3()`：读取人工复核后的 Excel 映射，严格过滤 + 金钥匙兜底，产出 U3 黄金数据。Strict filtering + golden-key fallback → U3 gold data. |
| `trend_analyzer.py` | Step 4.5 | `reduce_concept_dimensions()`、`generate_evolution_data()`、`generate_lab_radar_data()`、`generate_topic_distribution()`、`generate_scholar_profile()`：概念降维 + 演化/雷达/旭日图数据。Concept reduction + evolution/radar/sunburst data. |
| `db_importer.py` | Step 5 | `extract_graph_to_csv()`（U3 → CSV）、`Neo4jImporter.execute_load()`（Cypher LOAD 入 Neo4j）。CSV export + Cypher LOAD. |
| `visualizer.py` | Step 6 | FastAPI 应用 + ECharts 两个页面（力导向图 `/`、情报分析 `/analytics`），提供 `start_visualizer_server()` 及后台版本。FastAPI + ECharts (force graph `/`, analytics `/analytics`). |
| `name_processor.py` | 辅助 Aux | `build_name_mapping_dataframe()`：中文名 → 拼音（Western 格式）。Chinese → Pinyin (Western format). |

### 3.4 编排层 · Orchestration `pipelines/`

| 文件 File | 作用 Role |
|-----------|-----------|
| `data_pipeline.py` | **`AcademicPipeline` 类**：将 9 个阶段（Step 0→6）串成完整流水线，每个阶段一个方法，负责读写中间件（U1 → U1.5 → U2 → U2.5 → U3）。Chains 9 stages; each method reads/writes intermediates. |
| `name_pipeline.py` | **`NameConversionPipeline` 类**：两种姓名转换模式（从 Excel / 从纯文本），供独立调用。Two name-conversion modes (Excel / raw text). |

### 3.5 GUI 层 · GUI Layer `gui/`

| 文件 File | 作用 Role |
|-----------|-----------|
| `main_window.py` | `MainWindow`：主窗口，组织菜单栏、中央分栏、日志面板、状态栏，管理视图切换与各面板信号连接。Main window: menus, splitter, log dock, status bar, signal wiring. |
| `parameter_panel.py` | `ParameterPanel`：可滚动配置编辑器，8 个分组（机构/路径/NLP/LLM/数据库/作者匹配/控制/分析），读写 `config.yaml`。Scrollable config editor (8 groups). |
| `dashboard_panel.py` | `DashboardPanel`：`QWebEngineView` 包装，加载大屏 URL，带占位/加载/错误状态与自动重连。WebEngine wrapper with retry/placeholder. |
| `pipeline_runner.py` | `PipelineRunner(QThread)`：后台线程执行 `AcademicPipeline` 各阶段，通过 Qt Signal 回传进度。Background thread executor emitting progress signals. |
| `neo4j_manager.py` | `Neo4jManager`：Docker 容器生命周期管理（deploy/start/stop/restart/remove）+ 连接检测。Docker lifecycle + connection check. |
| `startup_wizard.py` | `StartupWizard`：3 页首次运行向导（欢迎 / 环境检查 / 模式选择），含 `is_first_run()`/`mark_initialized()` 哨兵。3-page first-run wizard with sentinel. |
| `dark_theme.py` | `apply_dark_theme()`：深色 QSS 样式表。Dark QSS stylesheet. |
| `help_texts.py` | `HELP` 字典：每个配置参数对应的中文解释，键与 `config.yaml` 一一对应。Chinese help dict keyed by config param. |
| `log_handler.py` | `LogSignal` / `QLogHandler` / `install_gui_logger()`：把 logging 输出转发为 Qt Signal，驱动 GUI 日志面板。Relays logging to Qt Signals. |
| `widgets.py` | 可复用控件工厂：`create_text_row` / `create_file_row` / `create_int_row` / `create_checkbox_row` / `create_kv_table_row` 等，含帮助按钮。Reusable widget factories with help buttons. |

### 3.6 配置 / 文档 / CI · Config / Docs / CI

| 文件 File | 作用 Role |
|-----------|-----------|
| `config/config.example.yaml` | 配置模板（提交到 Git）。首次运行复制为 `config.yaml`。Config template (committed). |
| `config/config.yaml` | 用户实际配置（gitignored），含机构、路径、NLP、LLM、数据库、分析等节。User config (gitignored). |
| `requirements.txt` | 核心依赖（含 NLP + GUI）。Core deps (incl. NLP + GUI). |
| `requirements-ml.txt` | 可选 NLP/ML 依赖（sentence-transformers、scikit-learn）。Optional NLP/ML deps. |
| `mkiv-gui.spec` | PyInstaller 打包配置。PyInstaller spec. |
| `.github/workflows/build.yml` | CI/CD：打 `v*` tag 自动构建 Windows/Linux 包并发布到 Releases。Builds & releases on `v*` tags. |
| `README.md` / `paper.md` / `LICENSE` | 项目文档 / JOSS 论文 / MIT 许可证。Project docs / JOSS paper / MIT license. |

---

## 4. 数据流转 · Data Flow（中间件链 / Intermediate chain）

```
OpenAlex API
    │  Step 0  crawler.py + author_matcher.py
    ▼
data/01_raw/U1.json ──► Step 1  cleaner.py ──► data/02_analyzed/U1.5.json
    │  Step 2  cleaner.py
    ▼
data/03_cleaned/U2.json + unique.json
    │  Step 3  analyzer.py (SBERT) ──► 映射表 Excel (人工复核 / human review)
    │  Step 3.5 llm_labeler.py (可选 / optional) ──► *_AI预填版.xlsx
    ▼
data/03_cleaned/U2_5.json ──► Step 4  assembler.py ──► data/output/U3.json
    │  Step 4.5 trend_analyzer.py ──► trends.json / lab_radar.json / topic_sunburst.json
    │  Step 5  db_importer.py ──► CSV ──► Neo4j
    ▼
Neo4j ──► Step 6  visualizer.py ──► http://127.0.0.1:8001 (ECharts 大屏 / dashboard)
```

---

## 5. 总结 · TL;DR

- **入口 Entry**：`main.py`（CLI）/ `gui_main.py`（GUI），二者都依赖 `utils/project_paths.py` 定位项目根并加载 `config.yaml`。Both rely on `utils/project_paths.py` to locate the project root and load `config.yaml`.
- **编排 Orchestration**：`pipelines/data_pipeline.py` 是唯一枢纽，串联全部 `core/*` 引擎模块完成 9 阶段流水线。The single hub chaining all `core/*` modules across 9 stages.
- **引擎 Engine**：`core/*` 每个模块对应流水线一个阶段，互相独立、只被 pipeline 调用，且统一通过 `utils/file_handler.py` 读写中间件。Each module maps to one stage, called only by the pipeline, reading/writing intermediates via `utils/file_handler.py`.
- **GUI**：`gui/main_window.py` 是中枢，横向组合参数面板、大屏面板、流水线执行器、Neo4j 管理器等子组件。The hub that laterally composes parameter panel, dashboard panel, pipeline runner, Neo4j manager, etc.
