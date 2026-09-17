---
title: 'MKIV: Roster-Anchored Entity Resolution for Laboratory-Level Analysis of Institutional Collaboration Networks'
tags:
  - Python
  - OpenAlex
  - entity-resolution
  - author-disambiguation
  - knowledge-graph
  - scientometrics
  - laboratory-analysis
  - neo4j
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

MKIV is an open-source Python toolkit that reconstructs the **internal structure** of a research institution from OpenAlex publication records. A bibliographic index does not know who an institution's people are: OpenAlex assigns global author identifiers that are split across name variants and merged across homonyms, and stores self-reported affiliation strings in which one laboratory appears under dozens of textual forms. MKIV resolves both problems by **anchoring the record to an externally supplied mentorship roster** — a plain list of names, the one piece of institutional knowledge no global index holds. The roster determines which co-authors are principal investigators, which author identifiers belong to the same real person, and therefore which non-roster co-authors are, with high probability, a given mentor's students or shared technical staff. Roster names are supplied as a spreadsheet column and transliterated to pinyin before matching where necessary.

Nine stages then carry the records from a live API to a graph: crawl works for an institution identifier; match them against the roster; tag authors internal or external by institution lineage; clean affiliation strings; collapse the surviving variants by embedding-based clustering into cluster representatives; route those representatives through a human- or LLM-filled mapping spreadsheet; and assemble the result into a Neo4j property graph of Scholars, Papers, Labs, Topics and four relationship types, served to two ECharts dashboards. The techniques are conventional — SentenceTransformer embeddings [@reimers2019sentence], agglomerative clustering [@pedregosa2011scikit], a property graph, force-directed rendering — and no new algorithm is claimed. What is assembled is a reproducible path to a graph in which every internal node carries a role, every laboratory membership is an explicit edge, and every collapse decision traces back to a spreadsheet row a human approved.

The core is an ordinary Python package (about 6,400 lines excluding tests), importable with no graphical interface, database or network access; the PySide6 desktop application and the dashboards are optional frontends over the same pipeline. The repository ships a deterministic synthetic dataset so the pipeline runs end-to-end offline, and a hermetic `pytest` suite of nearly 200 cases runs in CI on every push and pull request. The software is distributed as the repository `ACSN`; MKIV is the engine's internal codename.

# Statement of Need

Affiliation strings are notoriously inconsistent, but for institutional profiling the harder problem is identity. Three failures compound. One real person can hold several OpenAlex author identifiers, while a single identifier can absorb several different people. The index records affiliations, not internal structure: it cannot express that one person supervises another, or that a third belongs to two groups. And neither OpenAlex nor the tools built on top of it know which of an institution's people are its principal investigators — that knowledge lives in an internal roster, not in any database.

MKIV is aimed at the people who hold that roster: research administrators, library and scientometrics staff, and principal investigators who need an accurate picture of an institution's internal collaboration structure and thematic evolution, but who lack the time to build bespoke ETL code. It treats the roster as a first-class input and the mapping table as the pipeline's contract, keeping a human in the loop at the one step where automation is least trustworthy — assigning a canonical name to a cluster of variants — while automating everything else.

# State of the Field

Adjacent tools fall into three layers.

Client libraries expose the OpenAlex REST API. `pyalex` [@pyalex] is a thin, MIT-licensed Python client that tracks the API's own design — entity retrieval, filtering, search, grouping, cursor pagination, retry configuration, and reconstruction of plaintext abstracts. `openalexR` [@openalexr] offers the same access from R. Both are transport: they deliver records faithfully and stop. Neither collapses affiliation variants, resolves author identities, anchors a roster, builds a graph, or visualizes anything, and their affiliation handling is thin — openalexR 2.0.0 removed the per-author `affiliation*` columns in favour of `last_known_institutions`. For a question of the form "clean these few thousand institution-scoped records and tell me who works with whom", the entire data-preparation problem remains with the user.

Science-mapping applications consume pre-processed exports. VOSviewer [@vaneck2010vosviewer] renders co-authorship, co-citation and keyword maps; CiteSpace [@chen2006cite] specialises in emerging-trend and burst detection; bibliometrix and biblioshiny [@aria2017bibliometrix] provide a comprehensive R framework with importers for WoS, Scopus, Dimensions and PubMed, and built-in author and affiliation disambiguation. For whole-corpus science mapping these are more capable than MKIV, but they share two properties that define its niche. Acquisition is outside their scope: they begin from an export the user has already obtained, whereas MKIV begins from an institution identifier and handles pagination, caching and failures itself. And their disambiguation is general-purpose and automatic over the global corpus, whereas the name variants of one laboratory are not those of another's — and the internal hierarchy MKIV is asked about, who supervises whom, is absent from the data entirely, so no global rule set can recover it.

The gap is not a missing algorithm but a missing assembly and a missing anchor: each step is served by mature software, but a maintained, re-runnable path connecting them that knows who the institution's people are is generally unavailable outside bespoke in-house scripts. MKIV is that path — closest in spirit to bibliometrix, but at the raw-record end of the problem, with a queryable graph as the deliverable, an externally supplied roster as the anchor, and a human-arbitrated mapping table as the point of control.

# Software Design

Nine stages are orchestrated by a central `AcademicPipeline` class. Each stage writes a serialized JSON or CSV artefact to disk, so the pipeline is restartable at any stage and failures are diagnosable without re-crawling.

- **Step 0 — acquisition and roster matching.** A fault-tolerant REST crawler retrieves works for an OpenAlex institution ID over a configurable year range, with cursor pagination, a per-page politeness delay, local caching and retries on 429/5xx responses. If a mentorship roster spreadsheet is supplied, the same stage builds a local author-profile database: each internal authorship is keyed by a normalised name fingerprint (case-folded, punctuation and whitespace stripped), Chinese roster names are transliterated to pinyin first, and two-token names are also probed in reversed order. Because one fingerprint can map to several OpenAlex author IDs, the database keeps a per-ID record with publication count, most frequent raw affiliation, top concepts and collaborator set. The stage emits a **profile table** ranking each roster name's candidate identifiers, marking the highest-volume one as primary and the remainder as historical duplicates, and reporting "not found" when a roster name has no internal publication record at all. Every historical identifier is aliased to its primary before graph construction.
- **Step 1 — internal/external tagging.** Authorships are labelled internal when the target institution appears in the author's institution lineage or matches its ID directly, with a case-insensitive keyword-regex fallback over raw affiliation strings for records whose institution linkage OpenAlex has not resolved.
- **Step 2 — physical cleaning and entity extraction.** Emails, postal codes and configured country/city stop-words are stripped from internal affiliation strings; concepts are filtered to a configurable maximum hierarchy level and confidence score. The stage then extracts the two unique-entity sets that drive Step 3: distinct cleaned affiliation variants, and distinct surviving concepts.
- **Step 3 — vanguard clustering and collapse.** Affiliation variants are embedded with a multilingual SentenceTransformer [@reimers2019sentence] and clustered — Ward-linkage agglomerative by default, switching to KMeans above a configurable size threshold to avoid quadratic memory. Each cluster's "vanguard" is its shortest member, on the assumption that the shortest surviving variant is the least contaminated. An Excel template is written listing, per cluster, its size, its vanguard and a truncated reference string for the reviewer; the stage also returns a variant→vanguard dictionary that is applied immediately. This ordering matters: collapse precedes review, so a revised mapping is re-applied rather than re-derived.
- **Step 3.5 — optional LLM prefill.** An OpenAI-compatible endpoint can batch-label the vanguards. Output goes to a separate `*_AI预填版.xlsx` file and never overwrites human work; a post-processing pass merges the duplicate standard names the model produces, first exactly and then by fuzzy string similarity. Templates that already contain human content are never overwritten by the pipeline.
- **Step 4 — mapping application.** The verified spreadsheet is parsed into two dictionaries. Concepts are filtered strictly: a concept absent from the table is dropped, and its original name is preserved on the surviving record so that later views can be two-level (standardised category → original concept). Affiliations resolve through exact mapping, then a case-insensitive substring fallback table of "golden keys", then a configurable catch-all. The mapping source is switchable — auto (prefer prefill, fall back to manual), prefill-only, or manual-only — which makes human and model mappings diffable against each other.
- **Step 4.5 — analytics.** Standardised concepts undergo a second clustering pass with optional LLM naming, unless their number already falls below the target, in which case the mapping is the identity. Three artefacts are produced: a year × topic matrix, a laboratory × topic propensity matrix, and a two-level topic hierarchy.
- **Step 5 — graph assembly.** The assembled dataset is serialized to CSV node and edge tables and loaded into Neo4j with `LOAD CSV`. Scholar nodes carry a role assigned from the roster, and historical identifiers are aliased to their primary. Deliberately, **every** affiliation string on an authorship becomes a `BELONGS_TO` edge rather than only the first, so joint appointments survive as structure instead of being silently discarded. Co-authorship edges are weighted by the number of papers two scholars co-authored.
- **Step 6 — dashboards.** A FastAPI server exposes two ECharts pages. The force-directed graph can be re-cut along two dimensions of the same graph — laboratory view, where categories are labs, and topic view, where categories are topics — with filters, weight thresholding, edge limits and a scholar detail panel. The analytics page renders the Theme River, laboratory radar and topic Sunburst.

Two commitments run through the pipeline. The mapping table is the contract: a spreadsheet a domain expert edits without touching code, and the only place institutional knowledge enters the system, with the pipeline refusing to guess — an unmapped concept is dropped and an unmapped affiliation routed to a configured catch-all rather than silently retained. And every stage communicates through serialized intermediates on disk, which keeps the run restartable and auditable. The PySide6 desktop application (LGPL) wraps the same pipeline with a parameter panel, an embedded dashboard view, a live log console, a first-run environment wizard and one-click Docker management for Neo4j, running the pipeline in a QThread to keep the interface responsive.

# Research Impact Statement

The primary use case is the internal reading of a laboratory or department. Given an OpenAlex institution identifier and a mentorship roster, MKIV produces a graph in which roster members and non-roster co-authors are visually distinct: mentors are rendered as large, labelled, distinctly coloured nodes, and everyone else as small unlabelled circles. That single encoding makes the internal micro-structure legible. A mentor's neighbourhood *is* that mentor's collaboration list. A non-roster scholar who co-publishes with only one mentor is most likely that mentor's student. A non-roster scholar who co-publishes with several mentors, or whose affiliation edges place them in more than one group, is most likely shared engineering or research support staff, or a joint appointment. Reading the network at the level of a laboratory rather than the whole institution is what the tool is for.

These readings are interpretations an analyst makes from an auditable structure, not labels the software assigns. MKIV guarantees the encoding, the roles, the weights and the membership edges, and leaves the inference to the domain expert, who can trace any conclusion back to a weighted edge between identified people. Deriving a probable-role annotation automatically — for instance from the number of roster mentors with whom a non-roster scholar co-publishes — is an explicitly planned extension rather than a current claim.

Three further properties support the use case. Because author identities are repaired from the roster before the graph is built, a collaborator's record is not fragmented across duplicate identifiers. Because laboratory membership is recorded per affiliation rather than per first string, cross-appointment is visible instead of being silently discarded. And because one graph supports both a laboratory view and a topic view, the structural and the thematic question are asked of a single dataset rather than two independently cleaned exports, with the laboratory radar exposing which groups work on what.

MKIV has been exercised end-to-end on data from a research institute: on the order of a few thousand works, several hundred unique concepts, and a few thousand raw affiliation variants reduced to roughly 30 vanguard clusters. The full crawl-to-dashboard cycle completed on commodity hardware, with the NLP clustering step running on CPU.

# AI Usage Disclosure

Generative AI tools were used extensively in producing this software, and their use is disclosed in full. **Tools and models, with the work each performed:** Gemini 3.5 Pro generated the core program body; DeepSeek V4 Pro generated the graphical interface and the pipeline orchestration code; DeepSeek V4.1 Flash drafted the prose in this paper and in the repository documentation. The assistance consisted of code generation, refactoring, test scaffolding, and drafting.

**Human contribution.** The human author framed the problem, decided the decomposition of the workflow into stages, chose the roster-anchored identity resolution and the mapping-table-as-contract design, determined how the pipeline is assembled and which functions are combined, and specified the interfaces between stages. All AI-assisted output — code, tests and prose — was reviewed, validated and edited by the human author, who asserts responsibility for the accuracy, originality, licensing and ethical compliance of every submitted artefact.

Independently of development, MKIV includes an optional runtime component that queries an OpenAI-compatible language model endpoint to pre-fill mapping spreadsheets (Step 3.5). It is disabled by default; when enabled, its suggestions go to a separate spreadsheet for mandatory human review and are never applied without explicit human arbitration. A purely manual path contacts no external model.

# Acknowledgements

Data is sourced from the OpenAlex API (CC0). The Sentence-BERT model is from Reimers & Gurevych (2019). The graphical interface uses PySide6/Qt. Interactive visualizations use Apache ECharts.

# References

- Priem, J., Piwowar, H., & Orr, R. (2022). OpenAlex: A fully-open index of scholarly works, authors, venues, institutions, and concepts. arXiv:2205.01833.
- Reimers, N., & Gurevych, I. (2019). Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks. EMNLP 2019.
- van Eck, N. J., & Waltman, L. (2010). Software survey: VOSviewer, a computer program for bibliometric mapping. Scientometrics, 84(2), 523–538.
- Chen, C. (2006). CiteSpace II: Detecting and visualizing emerging trends and transient patterns in scientific literature. JASIST, 57(3), 359–377.
- Aria, M., & Cuccurullo, C. (2017). bibliometrix: An R-tool for comprehensive science mapping analysis. Journal of Informetrics, 11(4), 959–975.
- Pedregosa, F., et al. (2011). Scikit-learn: Machine Learning in Python. JMLR, 12, 2825–2830.
- pyalex: Python interface to the OpenAlex API. https://github.com/J535D165/pyalex
- openalexR: An R package for collecting and analysing data from OpenAlex. https://docs.ropensci.org/openalexR/
