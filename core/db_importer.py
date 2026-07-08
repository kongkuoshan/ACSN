# core/db_importer.py
import os, itertools, re, stat
import pandas as pd
from tqdm import tqdm
from collections import defaultdict
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

def extract_graph_to_csv(u3_data: list, df_pi: pd.DataFrame, out_dir: str):
    """
    [核心逻辑] 解析 U3 和 0号表，提取点边关系并导出为 CSV。
    """
    logging.info(">> 🧬 正在将 U3 黄金数据解析为图谱网格...")
    
    # 1. 建立导师身份映射
    pi_map = {}
    if not df_pi.empty:
        for _, row in df_pi.iterrows():
            aid = _get_clean_id(row.get("OpenAlex_ID"))
            if aid: pi_map[aid] = str(row.get("原始名单姓名", "未知导师")).strip()

    nodes_scholar, nodes_paper, nodes_lab, nodes_topic = {}, {}, set(), set()
    rels_wrote, rels_belongs, rels_mapped = set(), set(), set()
    collab_counter = defaultdict(int)

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
        
        # 领域提取
        concepts = work.get("concepts") or []
        for c in (concepts if isinstance(concepts, list) else []):
            if isinstance(c, dict):
                t_name = _safe_text(c.get("display_name"))
                if t_name != "未知":
                    nodes_topic.add(t_name)
                    rels_mapped.add((pid, t_name))

        # 学者与关系提取
        p_author_ids = []
        for auth in (work.get("authorships") or []):
            if not auth or not auth.get("is_internal_node"): continue
            
            a_obj = auth.get("author") or {}
            aid = _get_clean_id(a_obj.get("id"))
            if not aid: continue
            
            s_name = pi_map[aid] if aid in pi_map else _safe_text(a_obj.get("display_name"))
            s_role = "导师" if aid in pi_map else "研究员/学生"
            lab_name = _safe_text(auth.get("raw_affiliation_string") or "其他单元")

            nodes_scholar[aid] = {"id": aid, "name": s_name, "role": s_role}
            nodes_lab.add(lab_name)
            rels_wrote.add((aid, pid))
            rels_belongs.add((aid, lab_name))
            p_author_ids.append(aid)
        
        # 合作关系权重
        for u, v in itertools.combinations(p_author_ids, 2):
            collab_counter[tuple(sorted([u, v]))] += 1

    # 3. 导出 CSV
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
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def execute_load(self):
        logging.info(">> 🔗 连接 Neo4j，开始执行全量加载...")
        with self.driver.session() as sess:
            logging.info("   -> 清理旧数据...")
            sess.run("MATCH (n) DETACH DELETE n") 
            
            logging.info("   -> 正在建立数据库索引...")
            sess.run("DROP CONSTRAINT s_id_unique IF EXISTS")
            sess.run("CREATE CONSTRAINT s_id_unique IF NOT EXISTS FOR (s:Scholar) REQUIRE s.id IS UNIQUE")
            sess.run("CREATE INDEX p_id_idx IF NOT EXISTS FOR (p:Paper) ON (p.id)")
            sess.run("CREATE INDEX l_name_idx IF NOT EXISTS FOR (l:Lab) ON (l.name)")
            sess.run("CREATE INDEX t_name_idx IF NOT EXISTS FOR (t:Topic) ON (t.name)")
            
            load_cmds = [
                "LOAD CSV WITH HEADERS FROM 'file:///s.csv' AS row MERGE (s:Scholar {id: row.id}) SET s.name=row.name, s.role=row.role",
                "LOAD CSV WITH HEADERS FROM 'file:///p.csv' AS row MERGE (p:Paper {id: row.id}) SET p.title=row.title, p.journal=row.journal, p.doi=row.doi",
                "LOAD CSV WITH HEADERS FROM 'file:///l.csv' AS row MERGE (:Lab {name: row.name})",
                "LOAD CSV WITH HEADERS FROM 'file:///t.csv' AS row MERGE (:Topic {name: row.name})",
                "LOAD CSV WITH HEADERS FROM 'file:///r_w.csv' AS row MATCH (s:Scholar {id:row.aid}), (p:Paper {id:row.pid}) MERGE (s)-[:WROTE]->(p)",
                "LOAD CSV WITH HEADERS FROM 'file:///r_b.csv' AS row MATCH (s:Scholar {id:row.aid}), (l:Lab {name:row.lab}) MERGE (s)-[:BELONGS_TO]->(l)",
                "LOAD CSV WITH HEADERS FROM 'file:///r_m.csv' AS row MATCH (p:Paper {id:row.pid}), (t:Topic {name:row.top}) MERGE (p)-[:MAPPED_TO]->(t)",
                "LOAD CSV WITH HEADERS FROM 'file:///r_c.csv' AS row MATCH (s1:Scholar {id:row.u}), (s2:Scholar {id:row.v}) MERGE (s1)-[r:CO_WORK]-(s2) SET r.weight=toInteger(row.w)"
            ]
            
            logging.info("   -> 正在织入节点与边...")
            for c in tqdm(load_cmds, desc="执行 Cypher"): 
                sess.run(c)
                
        self.driver.close()
        logging.info("🎉 [MKIV 引擎] 数据已全部载入 Neo4j，前端可直接展示！")