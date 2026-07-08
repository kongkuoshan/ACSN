---
title: 'MKIV: An Open-Source Analytics Engine for Institutional Knowledge Graph Construction and Multi-Dimensional Research Evolution Mapping'
tags:
  - Python
  - OpenAlex
  - entity-resolution
  - knowledge-graph
  - scientometrics
  - data-governance
  - embedding
  - clustering
  - nlp
  - neo4j
  - desktop-gui
authors:
  - name: MKIV Team
    orcid: 0000-0000-0000-0000
    affiliation: 1
affiliations:
  - name: Institution Name
    index: 1
date: 08 July 2026
bibliography: paper.bib
---

# Summary

The MKIV Academic Intelligence Graph Engine is an open-source, end-to-end analytics workstation designed to transform fragmented bibliographic metadata from [OpenAlex](https://openalex.org/) into structured, actionable institutional intelligence. Unlike traditional rule-based cleaning tools, MKIV introduces a dual-layer **Semantic Vanguard Propagation (SVP)** architecture that applies unsupervised semantic clustering via `SentenceTransformer` embeddings and agglomerative clustering to both institutional affiliations and multi-level research concepts (Levels 0–5). This approach collapses thousands of high-entropy lexical variants into a manageable set of "Vanguard" representatives, enabling efficient truth injection through Large Language Models (LLMs) or domain expert verification. The system automates the full data lifecycle—from fault-tolerant REST API crawling to Neo4j graph database deployment—and provides a desktop-grade graphical interface with embedded ECharts visualizations. Critically, MKIV extends beyond data engineering by integrating an **Intelligence Analytics Module** that performs concept dimensionality reduction and generates temporal evolution maps (ThemeRiver), institutional research-propensity radar charts, and hierarchical topic Sunburst diagrams, making it a comprehensive competitive intelligence platform for scientometricians and institutional analysts.

# Statement of Need

High-precision institutional profiling and research trend analysis are fundamentally hindered by the extreme lexical ambiguity of self-reported metadata in global scholarly databases such as OpenAlex. A single research laboratory or scientific concept may manifest as hundreds of noisy textual variants—varying abbreviations, nested organizational addresses, translated names, and evolving research nomenclature. While LLM-based entity resolution is semantically powerful, processing millions of records directly through large models is computationally prohibitive and cost-ineffective. Furthermore, existing scientometric tools typically address either data cleaning or data visualization in isolation, lacking an integrated pipeline that bridges governance with intelligence. MKIV addresses these challenges by providing: (1) a scalable infrastructure that abstracts data complexity through unsupervised clustering before applying high-level intelligence (AI or human expertise) solely to cluster representatives; and (2) a unified desktop environment that democratizes access to advanced bibliometric analysis for non-programming users through a PySide6 graphical interface with one-click Docker-based database deployment.

# State of the Field

Institutional data governance in scientometrics currently oscillates between static rule-based systems (e.g., regular expression pipelines) and high-cost manual curation. Static systems lack the semantic flexibility to resolve laboratory-level granularity and cross-lingual name variations, while manual curation fails to scale with the exponential growth of global scholarly output. Recent tools have begun incorporating embedding models for entity matching, but they often lack an integrated "propagation" mechanism to broadcast verified ground truths back to all noisy variants. Furthermore, existing open-source platforms for scholarly analytics (e.g., VOSviewer, CiteSpace) focus predominantly on citation network visualization rather than institutional data governance and multi-dimensional research evolution tracking. MKIV advances the state of the field by formalizing the "Vanguard" logic as a reusable ETL paradigm—applied independently to affiliations and to research concepts—and by integrating governance, analytics, and visualization within a single cross-platform desktop application.

# Software Architecture

MKIV adopts a configuration-driven, fully decoupled architecture with multiple entry points supporting diverse user profiles (CLI developer mode, GUI desktop mode, and packaged executable distribution). The system comprises ten core modules orchestrated by a nine-stage pipeline:

1. **Stage 0 — Data Acquisition**: A fault-tolerant REST crawler with exponential backoff and local caching retrieves complete publication records for a target institution from OpenAlex.
2. **Stages 1–2 — Rule-Based Cleaning**: Institutional lineage matching combined with configurable regular expression fallback tags each author as internal or external; hard-rule filters remove email addresses, postal codes, and country names from raw affiliation strings.
3. **Stage 3 — Semantic Vanguard Propagation (SVP)**: Unique affiliation variants and research concepts are embedded using `paraphrase-multilingual-MiniLM-L12-v2`. Agglomerative clustering with a configurable target cluster count identifies "Vanguard" representatives. An Excel mapping template is generated for human verification.
4. **Stage 3.5 — LLM Auto-Labeling (Optional)**: An OpenAI-compatible API endpoint can be invoked to pre-fill the mapping templates, reducing manual workload by over 95%.
5. **Stage 4 — Final Assembly**: Human-verified mapping rules are parsed and applied with strict filtering—concepts not present in the verified mapping are dropped, and affiliations are standardized using both dictionary lookups and hard-coded golden-key fallbacks.
6. **Stage 4.5 — Intelligence Analytics (Novel Contribution)** : Multi-level concepts (Levels 0–5) are re-extracted from the gold dataset. A second SVP pass performs concept dimensionality reduction, clustering hundreds of fine-grained keywords into ~25 macro-categories. Three analytics artifacts are generated: (a) a year-by-topic evolution matrix for ThemeRiver visualization; (b) a laboratory-by-topic propensity matrix for radar chart comparison; and (c) a hierarchical topic tree for Sunburst drill-down.
7. **Stage 5 — Graph Database Import**: The gold dataset is serialized into CSV node and edge tables (Scholar, Paper, Lab, Topic, and four relationship types) and loaded into a Neo4j graph database using Cypher LOAD CSV.
8. **Stage 6 — Visualization Server**: A FastAPI backend serves the ECharts force-graph dashboard and the analytics dashboard over HTTP, consumed by the embedded Chromium WebEngine in the desktop GUI.

The desktop GUI (`gui_main.py`) is implemented with PySide6 (Qt for Python, LGPL-licensed) and features a dark-themed parameter panel with integrated help tooltips for all configuration keys, an embedded QWebEngineView for dashboard rendering, a real-time log console, a three-page first-run setup wizard, and one-click Docker-based Neo4j deployment with cross-platform path normalization for volume mounting. The pipeline executes in a dedicated QThread, ensuring the GUI remains responsive during long-running NLP computations.

# Research Impact

MKIV empowers research institutions and funding agencies to perform deep-dive competitive analysis and talent trajectory tracking with unprecedented efficiency and transparency. By providing a fully auditable, reproducible pipeline from raw API data to interactive dashboards, it facilitates rigorous scientometric studies that can be independently verified. The Intelligence Analytics Module's ability to visualize temporal transitions in research focus—for instance, mapping an institution's evolution from traditional mechanical engineering toward generative AI over a decade—makes MKIV an essential asset for strategic planning, recruitment, and technology forecasting. The packaged executable distribution model (via PyInstaller and GitHub Releases) eliminates technical barriers for non-programming stakeholders, enabling research administrators, librarians, and policy analysts to independently generate institutional intelligence. As an open-source framework with a modular architecture, MKIV invites community contributions for additional data sources (e.g., Scopus, Dimensions), visualization types, and analytical models.

# Acknowledgements

Data is sourced from the OpenAlex API under CC0 license. This project's architectural refactoring, Semantic Vanguard Propagation logic implementation, and graphical user interface were developed with AI-assisted programming. The desktop GUI is built with PySide6/Qt, and all interactive visualizations are rendered using Apache ECharts.

# References

- Priem, J., Piwowar, H., & Orr, R. (2022). OpenAlex: A fully-open index of scholarly works, authors, venues, institutions, and concepts. arXiv preprint arXiv:2205.01833.
- Reimers, N., & Gurevych, I. (2019). Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks. In Proceedings of the 2019 Conference on Empirical Methods in Natural Language Processing (EMNLP).
- Pedregosa, F., et al. (2011). Scikit-learn: Machine Learning in Python. Journal of Machine Learning Research, 12, 2825–2830.
