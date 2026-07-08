---
title: 'MKIV: A Pipeline Toolkit for Institutional Bibliometric Data Cleaning, Entity Resolution, and Research Trend Visualization'
tags:
  - Python
  - OpenAlex
  - entity-resolution
  - knowledge-graph
  - scientometrics
  - clustering
  - neo4j
  - desktop-gui
authors:
  - name: Your Name
    orcid: 0000-0000-0000-0000
    affiliation: 1
affiliations:
  - name: Your Institution
    index: 1
date: 08 July 2026
bibliography: paper.bib
---

# Summary

MKIV is an open-source Python toolkit that automates the process of building an institutional knowledge graph from OpenAlex bibliographic data. It crawls publication records for a target institution, cleans noisy affiliation strings and research concepts, resolves entity variants through embedding-based clustering with optional LLM-assisted labeling, imports the resulting graph into Neo4j, and serves interactive ECharts dashboards for exploring collaboration networks and research trends.

The system is delivered as both a command-line pipeline and a PySide6 desktop application with a graphical parameter panel, embedded web dashboard, one-click Docker-based Neo4j deployment, and a setup wizard for first-time users. A key design choice is the "vanguard" strategy: rather than sending every raw affiliation string to an LLM or requiring manual review of thousands of variants, the pipeline first clusters similar strings using SentenceTransformer embeddings and agglomerative clustering, then surfaces only the cluster representatives for human or LLM labeling. Verified labels are propagated back to all variants in each cluster. This pattern is applied independently to both institutional affiliations and research concepts, reducing the manual labeling workload from thousands of items to a few dozen.

# Statement of Need

Self-reported affiliation strings in bibliographic databases are notoriously inconsistent. A single research group may appear under dozens of textual variants—different abbreviations, nested organizational hierarchies, translated names, and typographical errors. Cleaning this data typically requires either brittle regular expressions that fail on unseen variants, or exhaustive manual review that does not scale with institutional publication volume. Existing open-source tools for scholarly analytics (e.g., VOSviewer, CiteSpace) focus on citation network visualization and assume pre-cleaned input data, leaving a gap between raw API data and analysis-ready datasets. MKIV fills this gap with an integrated, configurable pipeline that handles the full data lifecycle from acquisition to visualization, and provides a graphical interface accessible to users without programming experience.

# Software Description

MKIV is organized into nine pipeline stages orchestrated by a central `AcademicPipeline` class:

- **Stage 0**: A fault-tolerant REST crawler retrieves works for a given OpenAlex institution ID with configurable year range, using cursor-based pagination and local caching.
- **Stages 1–2**: Authors are tagged as internal or external via institution lineage matching, with configurable keyword fallback. Raw affiliation strings are cleaned by removing emails, postal codes, and country names.
- **Stage 3**: Unique affiliation variants are embedded with `paraphrase-multilingual-MiniLM-L12-v2` and clustered (AgglomerativeClustering or KMeans for large datasets). The shortest string in each cluster becomes its "vanguard" representative. An Excel template is generated for human review.
- **Stage 3.5 (optional)**: An OpenAI-compatible LLM endpoint can batch-label the vanguards with standardized names. Post-processing detects and merges duplicate labels.
- **Stage 4**: Human-verified Excel mappings are parsed. Concepts not present in the mapping are dropped; affiliations are standardized using dictionary lookup with configurable keyword-based fallback (`golden_keys`).
- **Stage 4.5**: Multi-level concepts from the gold dataset undergo a second clustering pass for dimensionality reduction. Three analytics outputs are generated: a year-by-topic evolution matrix, a laboratory-by-topic propensity matrix, and a hierarchical topic tree.
- **Stage 5**: The gold dataset is serialized into CSV node and edge tables (Scholar, Paper, Lab, Topic, and four relationship types) and loaded into Neo4j via `LOAD CSV`.
- **Stage 6**: A FastAPI server serves two ECharts dashboard pages: a force-directed collaboration graph with search and filtering, and an analytics page with ThemeRiver, radar, and Sunburst charts.

The desktop GUI is built with PySide6 (LGPL) and features a dark-themed scrollable parameter panel with per-field help tooltips, a QWebEngineView for embedded dashboard rendering, a real-time log console, a startup wizard with environment detection, and one-click Docker container management for Neo4j. Pipeline execution runs in a QThread to keep the interface responsive.

# Research Use Cases

The primary use case is institutional research profiling: given an OpenAlex institution ID and a list of researcher names, MKIV produces a clean knowledge graph showing who collaborates with whom, which labs they belong to, and what topics they publish on. The analytics module extends this with longitudinal views—showing how an institution's research focus has shifted over time, and comparing research tendencies across laboratories.

MKIV has been tested with data from a Chinese Academy of Sciences institute (approximately 4,000 works, 177 unique concepts, and 3,865 raw affiliation variants reduced to 30 vanguard clusters). The pipeline completed the full crawl-to-dashboard cycle on commodity hardware, with the NLP clustering step running on CPU.

# Acknowledgements

Data is sourced from the OpenAlex API (CC0). The Sentence-BERT model is from Reimers & Gurevych (2019). The graphical interface uses PySide6/Qt. Interactive visualizations use Apache ECharts. AI-assisted programming was used during development of the GUI and pipeline orchestration modules.

# References

- Priem, J., Piwowar, H., & Orr, R. (2022). OpenAlex: A fully-open index of scholarly works, authors, venues, institutions, and concepts. arXiv:2205.01833.
- Reimers, N., & Gurevych, I. (2019). Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks. EMNLP 2019.
- Pedregosa, F., et al. (2011). Scikit-learn: Machine Learning in Python. JMLR, 12, 2825–2830.
