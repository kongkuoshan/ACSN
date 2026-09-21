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
├── paper.bib                        # 论文参考文献 · BibTeX references
├── LICENSE                          # MIT 许可证 · MIT license
│
├── config/
│   ├── config.example.yaml          # 配置模板 (提交到 Git) · Config template (committed)
│   └── config.yaml                  # 用户配置 (gitignored，首次运行自动生成) · User config (gitignored, auto-generated)
│
├── core/                            # 引擎核心 (11 个模块) · Engine core (11 modules)
│   ├── crawler.py                   # Step 0: OpenAlex REST 爬虫 (带缓存/重试) · REST crawler (cache/retry)
│   ├── author_matcher.py            # Step 0: 导师画像本地匹配 · Author profile local matching
│   ├── cleaner.py                   # Step 1-2: 内部节点打标 + 硬规则清洗 · Node tagging + rule cleaning
│   ├── analyzer.py                  # Step 3: SBERT 聚类 → 排头兵坍缩 · SBERT clustering + vanguard collapse
│   ├── llm_labeler.py               # Step 3.5: LLM 批量预填 + 去重 · LLM batch labeling + dedup
│   ├── assembler.py                 # Step 4: U3 终极组装 + 金钥匙兜底 · Final assembly + golden-key fallback
│   ├── trend_analyzer.py            # Step 4.5: 概念降维 + 演化/雷达/旭日图 · Concept reduction + evolution/radar/sunburst
│   ├── db_importer.py               # Step 5: CSV 导出 + Neo4j LOAD · CSV export + Neo4j LOAD
│   ├── visualizer.py                # Step 6: FastAPI + ECharts 大屏 · FastAPI + ECharts dashboard
│   ├── name_processor.py            # 中文名 → 拼音转换 · Chinese → Pinyin conversion
│   └── constants.py                 # 大屏主机/端口等常量 · Dashboard host/port constants
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
│   └── resources/                   # 资源目录 (app.ico / app.png / .gitkeep) · Resources
│
├── utils/                           # 通用工具层 · Utilities
│   ├── project_paths.py             # 路径解析 (单一真相来源) · Path resolution (single source of truth)
│   ├── file_handler.py              # JSON/Excel 读写 · JSON/Excel I/O
│   └── model_loader.py              # SBERT 模型本地优先加载 · Local-first model loader
│
├── data/                            # 运行时数据 (gitignored) · Runtime data (gitignored)
│   └── input/                       # 用户放置输入 xlsx 的目录 · User input folder
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
│  引擎层 Core (11 模块，按流水线阶段串联)                             │
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
| `core/analyzer.py` | — | (函数内懒加载 sentence_transformers/sklearn) |
| `core/llm_labeler.py` | — | requests, pandas |
| `core/assembler.py` | — | pandas, tqdm |
| `core/trend_analyzer.py` | (函数内懒加载 SBERT/sklearn) | tqdm |
| `core/db_importer.py` | — | neo4j, pandas |
| `core/visualizer.py` | `utils.project_paths` | fastapi, neo4j, uvicorn |
| `core/name_processor.py` | — | pypinyin, pandas |
| `core/constants.py` | — | (纯常量 / pure constants) |
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
| `author_matcher.py` | Step 0 | **导师名单锚定（本项目的核心入口）**。`build_local_database()` 用已爬取文献建立本地作者画像库：内部作者按**姓名指纹**（小写、去 `-`/`.`/空格）聚合，同一个人可对应多个 OpenAlex ID，逐 ID 记录发文量、高频挂靠机构、高频概念与合作者集合；`match_names_locally()` 拿输入名单去匹配，按发文量排序输出 **主号 / 历史分身**，名单里没有的记「查无此人」。中文名先在 `name_processor.py` 转拼音，两段式姓名额外做倒序探测。**Roster anchoring (the project's core entry point)**: `build_local_database()` groups internal authorships by a normalised name fingerprint, keeping a per-OpenAlex-ID record (publication count, top raw affiliation, top concepts, collaborator set); `match_names_locally()` matches the input roster against it and ranks each name's candidate IDs as primary / historical duplicates, or "not found". Chinese names are transliterated first; two-token names are also probed reversed. |
| `cleaner.py` | Step 1-2 | `tag_internal_nodes()`（内部/外部作者打标）、`extract_and_clean_entities()`（去噪 + 提取机构/领域实体）。Tagging + noise removal + entity extraction. |
| `analyzer.py` | Step 3 | `build_cluster_mappings()`（SBERT 语义聚类出"排头兵"，**机构与领域两条通道同款聚类**：默认 Ward 层次聚类，变体数超过 `kmeans_switch_threshold` 时切 KMeans 控内存；每簇取最短串为排头兵，生成两张同构 Excel 模板）、`apply_vanguard_mapping()` / `apply_concept_vanguard_mapping()`（把变体坍缩为排头兵，产出 U2.5；概念的原始名保留在 `original_name`，供旭日图追溯）。**坍缩发生在人工复核之前**，所以映射表被修订后只需重放，不必重跑聚类。SBERT clustering → vanguards → collapse (affiliations *and* concepts); collapse precedes human review, so a revised mapping is re-applied rather than re-derived. |
| `llm_labeler.py` | Step 3.5 | `ask_llm()`（URL 只写到 `/v1` 时自动补 `/chat/completions`）/ `auto_label_concepts()`（**批量** + `concept_target_fields` 白名单校验，未命中留空待人工）/ `auto_label_affiliations_batch()` / `deduplicate_standard_names()`：调用 OpenAI 兼容 API 预填映射表并去重。LLM pre-fill via OpenAI-compatible API + dedup; concept labels are batched and whitelist-validated. |
| `assembler.py` | Step 4 | `parse_mapping_rules()` / `generate_final_u3()`：读取复核后的 Excel 映射，**严格过滤**——不在表中的概念直接剔除（但保留 `original_name` 以支撑两层旭日图），机构按 映射表 → `golden_keys` 子串兜底 → `(其他部门)` 三级解析，产出 U3 黄金数据。映射表来源由 `mapping.source` 决定（auto / ai / manual），因此人工版与 LLM 预填版可以互相**对账**。Strict filtering + golden-key fallback → U3; `mapping.source` makes human and LLM mappings diffable. |
| `trend_analyzer.py` | Step 4.5 | `reduce_concept_dimensions()`、`generate_evolution_data()`、`generate_lab_radar_data()`、`generate_topic_distribution()`、`generate_scholar_profile()`：概念降维 + 演化/雷达/旭日图数据。概念数 ≤ `analytics.concept_clusters` 时**直接返回恒等映射**（跳过聚类与 LLM 命名）。Concept reduction + evolution/radar/sunburst data; falls back to the identity mapping when there are fewer concepts than the cluster target. |
| `db_importer.py` | Step 5 | `extract_graph_to_csv()`（U3 + 画像表 → 节点/边 CSV）、`Neo4jImporter.execute_load()`（建索引 + Cypher `LOAD CSV`）。**身份与角色的落地处**：画像表里的主号/分身先合成 `id_alias_map`，分身 ID 一律归并到主号，避免同一人的合作记录被拆成两个节点；名单内 → `role=导师`，否则 → `研究员/学生`。**每个** `raw_affiliation_strings` 各建一条 `BELONGS_TO` 边（不只第一条），双聘因此保留；`CO_WORK.weight` 为两人共著论文数。**同时物化主归属**：扫描时用 `Counter` 统计每人的机构/主题出现次数，按（次数降序, 名称升序）落成 `labs`/`topics`（`\|` 连接）与 `primary_lab`/`primary_topic`；「外部合作机构/(其他部门)/(未知部门)/其他单元」四个兜底桶不参与主归属竞争，仅当本人无真实机构时才兜底。**Where identity and role land**: historical IDs are aliased to the primary before graph build; role comes from the roster; *every* affiliation string becomes a `BELONGS_TO` edge; co-authorship weight = number of co-authored papers. Primary affiliation/topic are **materialized at import time** so the dashboard never recomputes (and can't get) them wrong. |
| `visualizer.py` | Step 6 | FastAPI 应用 + ECharts 两个页面（力导向图 `/`、情报分析 `/analytics`），提供 `start_visualizer_server()` 及后台版本。图查询走**诱导子图**：过滤时对合作双方同时生效，每个节点读**自己的** `primary_lab`/`primary_topic`，全景与过滤共用同一 `max_edges_default` 上限（过滤后节点数不会反而变多）；配色按分类（人数降序, 名称升序）从固定 `_PALETTE` 取色，跨进程稳定；底部图例为自绘 HTML 勾选列（分类色块+数量 / 角色 / 重置），前端本地过滤点边。FastAPI + ECharts (force graph `/`, analytics `/analytics`); filtering yields an induced subgraph, palette is deterministic across processes, and the legend is a self-drawn HTML checkbox panel. |
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
| `requirements.txt` | 核心依赖（CLI + GUI，不含 NLP/ML）。Core deps (CLI + GUI, no NLP/ML). |
| `requirements-ml.txt` | 可选 NLP/ML 依赖（sentence-transformers、scikit-learn）。Optional NLP/ML deps. |
| `mkiv-gui.spec` | PyInstaller 打包配置。PyInstaller spec. |
| `.github/workflows/build.yml` | CI/CD：打 `v*` tag 自动构建 Windows/Linux 包并发布到 Releases。Builds & releases on `v*` tags. |
| `README.md` / `paper.md` / `LICENSE` | 项目文档 / JOSS 论文 / MIT 许可证。Project docs / JOSS paper / MIT license. |

---

## 4. 数据流转 · Data Flow（中间件链 / Intermediate chain）

```
OpenAlex API
    │  Step 0  crawler.py
    │           └─ data/input/0_原始导师名单.xlsx（可选）→ author_matcher.py → 0_作者匹配画像表.xlsx
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
