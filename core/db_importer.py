# core/db_importer.py
import os, itertools, re, stat
import pandas as pd
from tqdm import tqdm
from collections import defaultdict, Counter
from neo4j import GraphDatabase
import logging

def _get_clean_id(raw):
    """[内部辅助] 深度清洗 ID"""
    if not raw or str(raw).lower() == 'nan': return None
    clean = str(raw).split("/")[-1].strip()
    clean = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', clean)
    return clean if clean else None

def _safe_text(text):
    """[内部辅助] 文本安全化"""
    if not text or str(text).lower() == 'nan': return "未知"
    return str(text).replace('"', "'").replace('\\', '').strip()

def _rank_counts(counter):
    """[内部辅助] 按 (出现次数降序, 名称升序) 排序, 保证结果跨进程稳定"""
    if not counter: return []
    return sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))

def extract_graph_to_csv(u3_data: list, df_pi: pd.DataFrame, out_dir: str, labels_cfg: dict = None):
    """
    [核心逻辑] 解析 U3 和 0号表，提取点边关系并导出为 CSV。
    同时物化每位学者的主归属/主领域 (primary_lab / primary_topic) 与全部归属 (labs / topics)。
    """
    labels_cfg = labels_cfg or {}
    mentor_role = labels_cfg.get('mentor_role', '导师')
    staff_role = labels_cfg.get('staff_role', '研究员/学生')
    other_unit = labels_cfg.get('other_unit', '其他单元')
    # 兜底「桶」标签: 不参与主归属竞争, 只在本人没有真实机构时兜底
    bucket_labels = {
        labels_cfg.get('external', '外部合作机构'),
        labels_cfg.get('other_dept', '(其他部门)'),
        labels_cfg.get('unknown_dept', '(未知部门)'),
        other_unit,
    }

    logging.info(">> 🧬 正在将 U3 黄金数据解析为图谱网格...")
    
    # 1. 建立导师身份映射 + ID 别名映射 (合并历史分身)
    pi_map = {}
    id_alias_map = {}  # historical_id → primary_id

    if not df_pi.empty:
        # 按姓名分组，识别主号与历史分身
        name_groups = {}
        for _, row in df_pi.iterrows():
            raw_name = str(row.get("原始名单姓名", "")).strip()
            aid = _get_clean_id(row.get("OpenAlex_ID"))
            if not aid or not raw_name:
                continue
            id_status = str(row.get("ID归属状态", ""))
            entry = name_groups.setdefault(raw_name, {"primary": None, "aliases": set()})
            entry["aliases"].add(aid)
            if "主号" in id_status or entry["primary"] is None:
                entry["primary"] = aid

        for name, group in name_groups.items():
            primary = group["primary"]
            if primary:
                pi_map[primary] = name
                # 为所有历史分身建立指向主号的别名映射
                for alias in group["aliases"]:
                    pi_map[alias] = name
                    if alias != primary:
                        id_alias_map[alias] = primary

    nodes_scholar, nodes_paper, nodes_lab, nodes_topic = {}, {}, set(), set()
    rels_wrote, rels_belongs, rels_mapped = set(), set(), set()
    collab_counter = defaultdict(int)
    lab_counter = defaultdict(Counter)     # canonical_id -> Counter(机构名)
    topic_counter = defaultdict(Counter)   # canonical_id -> Counter(主题名)

    # 2. 扫描数据湖同步【组织+领域】
    for work in tqdm(u3_data, desc="织网进度"):
        pid = _get_clean_id(work.get("id"))
        if not pid: continue

        # 论文节点
        p_loc = work.get("primary_location") or {}
        p_src = p_loc.get("source") or {}
        j_name = _safe_text(p_src.get("display_name") or "未知期刊")
        p_doi = work.get("doi") or "" 
        
        nodes_paper[pid] = {"id": pid, "title": _safe_text(work.get("title")), "journal": j_name, "doi": p_doi}
        
        # 领域提取 (同时收集本篇主题, 供学者主领域统计)
        concepts = work.get("concepts") or []
        work_topics = []
        for c in (concepts if isinstance(concepts, list) else []):
            if isinstance(c, dict):
                t_name = _safe_text(c.get("display_name"))
                if t_name != "未知":
                    if t_name not in work_topics:
                        work_topics.append(t_name)
                    nodes_topic.add(t_name)
                    rels_mapped.add((pid, t_name))

        # 学者与关系提取
        p_author_ids = []
        for auth in (work.get("authorships") or []):
            if not auth or not auth.get("is_internal_node"): continue

            a_obj = auth.get("author") or {}
            aid = _get_clean_id(a_obj.get("id"))
            if not aid: continue

            # 别名解析: 历史分身 ID → 主号 ID
            canonical_id = id_alias_map.get(aid, aid)

            s_name = pi_map.get(canonical_id) or pi_map.get(aid) or _safe_text(a_obj.get("display_name"))
            s_role = mentor_role if (canonical_id in pi_map or aid in pi_map) else staff_role

            nodes_scholar[canonical_id] = {"id": canonical_id, "name": s_name, "role": s_role}

            # 为该作者的所有挂靠机构建立 BELONGS_TO 边 (不止第一个)
            aff_strings = auth.get("raw_affiliation_strings") or []
            if not aff_strings:
                fallback = auth.get("raw_affiliation_string") or other_unit
                aff_strings = [fallback]
            for aff in aff_strings:
                lab_name = _safe_text(aff)
                if lab_name != "未知":
                    nodes_lab.add(lab_name)
                    rels_belongs.add((canonical_id, lab_name))
                    lab_counter[canonical_id][lab_name] += 1

            for t_name in work_topics:
                topic_counter[canonical_id][t_name] += 1

            rels_wrote.add((canonical_id, pid))
            p_author_ids.append(canonical_id)
        
        # 合作关系权重
        for u, v in itertools.combinations(p_author_ids, 2):
            collab_counter[tuple(sorted([u, v]))] += 1

    # 3. 物化每人的主归属 / 全部归属
    #    大屏按人着色时只读这些属性, 不再用 Cypher 现算 (现算无法正确取「最常机构」)
    for sid, node in nodes_scholar.items():
        labs = _rank_counts(lab_counter.get(sid))
        real_labs = [n for n, _ in labs if n not in bucket_labels]
        node["labs"] = "|".join(n.replace("|", " ") for n, _ in labs)
        node["primary_lab"] = real_labs[0] if real_labs else (labs[0][0] if labs else other_unit)

        topics = _rank_counts(topic_counter.get(sid))
        node["topics"] = "|".join(n.replace("|", " ") for n, _ in topics)
        node["primary_topic"] = topics[0][0] if topics else ""

    # 4. 导出 CSV
    logging.info(f">> 💾 正在导出 CSV 至 Neo4j Import 目录: {out_dir}")
    os.makedirs(out_dir, exist_ok=True)
    pd.DataFrame(list(nodes_scholar.values())).drop_duplicates('id').to_csv(f"{out_dir}/s.csv", index=False)
    pd.DataFrame(list(nodes_paper.values())).drop_duplicates('id').to_csv(f"{out_dir}/p.csv", index=False)
    pd.DataFrame([{"name": l} for l in nodes_lab]).to_csv(f"{out_dir}/l.csv", index=False)
    pd.DataFrame([{"name": t} for t in nodes_topic]).to_csv(f"{out_dir}/t.csv", index=False)
    pd.DataFrame(list(rels_wrote), columns=["aid","pid"]).to_csv(f"{out_dir}/r_w.csv", index=False)
    pd.DataFrame(list(rels_belongs), columns=["aid","lab"]).to_csv(f"{out_dir}/r_b.csv", index=False)
    pd.DataFrame(list(rels_mapped), columns=["pid","top"]).to_csv(f"{out_dir}/r_m.csv", index=False)
    pd.DataFrame([{"u": k[0], "v": k[1], "w": v} for k, v in collab_counter.items()]).to_csv(f"{out_dir}/r_c.csv", index=False)

    # Cross-platform: ensure CSV files are readable by Neo4j container
    for f in os.listdir(out_dir):
        fp = os.path.join(out_dir, f)
        if os.path.isfile(fp):
            os.chmod(fp, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)

class Neo4jImporter:
    def __init__(self, uri, user, password, connection_timeout=10):
        self.driver = GraphDatabase.driver(
            uri, auth=(user, password),
            connection_timeout=connection_timeout,
            connection_acquisition_timeout=connection_timeout,
        )

    def execute_load(self):
        logging.info(">> 🔗 连接 Neo4j，开始执行全量加载...")
        with self.driver.session() as sess:
            logging.info("   -> 正在建立数据库索引 (首次运行)...")
            try:
                sess.run("CREATE CONSTRAINT s_id_unique IF NOT EXISTS FOR (s:Scholar) REQUIRE s.id IS UNIQUE")
            except Exception:
                pass  # 约束可能已存在
            sess.run("CREATE INDEX p_id_idx IF NOT EXISTS FOR (p:Paper) ON (p.id)")
            sess.run("CREATE INDEX l_name_idx IF NOT EXISTS FOR (l:Lab) ON (l.name)")
            sess.run("CREATE INDEX t_name_idx IF NOT EXISTS FOR (t:Topic) ON (t.name)")

            load_cmds = [
                "LOAD CSV WITH HEADERS FROM 'file:///s.csv' AS row MERGE (s:Scholar {id: row.id}) SET s.name=row.name, s.role=row.role, s.labs=split(row.labs,'|'), s.primary_lab=row.primary_lab, s.topics=split(row.topics,'|'), s.primary_topic=row.primary_topic",
                "LOAD CSV WITH HEADERS FROM 'file:///p.csv' AS row MERGE (p:Paper {id: row.id}) SET p.title=row.title, p.journal=row.journal, p.doi=row.doi",
                "LOAD CSV WITH HEADERS FROM 'file:///l.csv' AS row MERGE (:Lab {name: row.name})",
                "LOAD CSV WITH HEADERS FROM 'file:///t.csv' AS row MERGE (:Topic {name: row.name})",
                "LOAD CSV WITH HEADERS FROM 'file:///r_w.csv' AS row MATCH (s:Scholar {id:row.aid}), (p:Paper {id:row.pid}) MERGE (s)-[:WROTE]->(p)",
                "LOAD CSV WITH HEADERS FROM 'file:///r_b.csv' AS row MATCH (s:Scholar {id:row.aid}), (l:Lab {name:row.lab}) MERGE (s)-[:BELONGS_TO]->(l)",
                "LOAD CSV WITH HEADERS FROM 'file:///r_m.csv' AS row MATCH (p:Paper {id:row.pid}), (t:Topic {name:row.top}) MERGE (p)-[:MAPPED_TO]->(t)",
                "LOAD CSV WITH HEADERS FROM 'file:///r_c.csv' AS row MATCH (s1:Scholar {id:row.u}), (s2:Scholar {id:row.v}) MERGE (s1)-[r:CO_WORK]-(s2) SET r.weight=toInteger(row.w)",
            ]

            logging.info("   -> 清理旧数据...")
            sess.run("MATCH (n) DETACH DELETE n")

            logging.info("   -> 正在织入节点与边...")
            for c in tqdm(load_cmds, desc="执行 Cypher"):
                sess.run(c)

        self.driver.close()
        logging.info("🎉 [MKIV 引擎] 数据已全部载入 Neo4j，可在可视化大屏查看！")