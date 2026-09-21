# core/visualizer.py
import os
import logging
from collections import Counter
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from neo4j import GraphDatabase
import uvicorn

from utils.project_paths import PROJECT_ROOT
from core.constants import DASHBOARD_HOST, DASHBOARD_PORT

# 初始化 FastAPI 应用
app = FastAPI(title="MKIV 学术情报指挥舱")

# 全局数据库驱动，等待流水线启动时注入
driver = None

# Neo4j 连接超时 (秒)
NEO4J_CONNECTION_TIMEOUT = 5

# 图可视化参数 (由 start_visualizer_server 从 config 注入)
DEFAULT_ECHARTS_CDN = "https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"
_graph_cfg = {}

# 固定调色板: 按分类排序后取色, 保证同一分类在任意次启动/请求里颜色一致
_PALETTE = [
    "#5470c6", "#91cc75", "#fac858", "#ee6666", "#73c0de", "#3ba272", "#fc8452", "#9a60b4",
    "#ea7ccc", "#00b4d8", "#e07a5f", "#81b29a", "#f2cc8f", "#3d405b", "#e9c46a", "#2a9d8f",
    "#e76f51", "#6d597a", "#b56576", "#84a59d",
]

def shorten(name):
    """类别名称截断工具"""
    max_len = _graph_cfg.get('shorten_max_len', 16)
    if not name or name in ["Unknown", "待分类", "N/A", "其他"]:
        return "其他单元"
    s = str(name).split(',')[0].split(' -')[0].strip()
    return s[:max_len] + ".." if len(s) > max_len + 2 else s

# ================= 后端 API 接口 =================

@app.get("/api/graph")
def get_graph(view: str = "admin", filter_name: str = ""):
    limit = _graph_cfg.get('max_edges_default', 3000)
    min_w = _graph_cfg.get('min_weight', 1)
    mentor_size = _graph_cfg.get('mentor_symbol_size', 32)
    staff_size = _graph_cfg.get('staff_symbol_size', 12)
    other_unit = "其他单元"

    # 过滤时对合作双方同时生效 → 得到该实验室/主题的「诱导子图」, 不再把外部合作者一并拉进来
    if view == "admin":
        cat_attr = "primary_lab"
    else:
        cat_attr = "primary_topic"

    cypher = f"""
    MATCH (s1:Scholar)
    WHERE $f = '' OR s1.{cat_attr} = $f
    MATCH (s1)-[r:CO_WORK]-(s2:Scholar)
    WHERE r.weight >= {min_w} AND s1.id < s2.id
      AND ($f = '' OR s2.{cat_attr} = $f)
    WITH s1, s2, r
    ORDER BY r.weight DESC LIMIT {limit}
    RETURN s1.id as id1, s1.name as n1, s1.role as r1, s1.{cat_attr} as c1,
           s2.id as id2, s2.name as n2, s2.role as r2, s2.{cat_attr} as c2,
           r.weight as w
    """

    with driver.session() as session:
        res = session.run(cypher, f=filter_name)
        nodes, links, seen_links = {}, [], set()

        for r in res:
            for i in [1, 2]:
                sid = r[f'id{i}']
                if sid not in nodes:
                    is_pi = (r[f'r{i}'] == "导师")
                    nodes[sid] = {
                        "id": sid, "name": r[f'n{i}'],
                        "role": r[f'r{i}'] or "未标注",
                        "category": r[f'c{i}'] or other_unit,
                        "symbol": "diamond" if is_pi else "circle",
                        "symbolSize": mentor_size if is_pi else staff_size,
                        "label": {"show": is_pi, "fontSize": 12, "fontWeight": "bold"}
                    }

            link_hash = tuple(sorted([r['id1'], r['id2']]))
            if link_hash not in seen_links:
                links.append({"source": r['id1'], "target": r['id2'], "value": r['w']})
                seen_links.add(link_hash)

        # 分类按 (人数降序, 名称升序) 排序后固定赋色, 跨进程稳定
        counts = Counter(n["category"] for n in nodes.values())
        ordered = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
        color_of = {name: _PALETTE[i % len(_PALETTE)] for i, (name, _) in enumerate(ordered)}

        categories = [{"name": name, "color": color_of[name], "count": cnt} for name, cnt in ordered]
        for n in nodes.values():
            n["itemStyle"] = {"color": color_of[n["category"]]}

        return {"nodes": list(nodes.values()), "links": links, "categories": categories}

@app.get("/api/categories")
def get_categories(view: str = "admin"):
    cat_attr = "primary_lab" if view == "admin" else "primary_topic"
    query = (f"MATCH (s:Scholar) WHERE s.{cat_attr} IS NOT NULL AND s.{cat_attr} <> '' "
             f"RETURN s.{cat_attr} AS name, count(s) AS cnt ORDER BY cnt DESC")

    with driver.session() as session:
        result = session.run(query)
        return [{"name": r["name"], "count": r["cnt"]} for r in result]

@app.get("/api/details")
def get_details(sid: str):
    # 只用主归属, 避免多机构学者被 OPTIONAL MATCH 笛卡尔展开后取到任意一个机构
    cypher = """
    MATCH (s:Scholar {id: $id})
    OPTIONAL MATCH (s)-[:WROTE]->(p:Paper)
    RETURN s.name as name, s.primary_lab as lab,
           collect(DISTINCT {title: p.title, doi: p.doi, journal: p.journal})[0..15] as papers
    """
    with driver.session() as session:
        res = session.run(cypher, id=sid).single()
        if not res: return {"name": "未知", "lab": "未知", "papers": []}
        return {
            "name": res["name"],
            "lab": shorten(res["lab"]),
            "papers": [p for p in res["papers"] if p['title']]
        }

@app.get("/api/search_exact")
def search_exact(query: str):
    cypher = "MATCH (s:Scholar) WHERE toLower(s.name) CONTAINS toLower($q) OR toLower(s.id) = toLower($q) RETURN s.name as n, s.id as id LIMIT 1"
    with driver.session() as session:
        res = session.run(cypher, q=query).single()
        return {"found": True, "name": res["n"], "id": res["id"]} if res else {"found": False}


# ================= 情报分析 API =================

def _load_analytics_data(filename: str):
    """从磁盘加载分析数据文件"""
    import json
    filepath = os.path.join(PROJECT_ROOT, "data", "output", filename)
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


@app.get("/api/analytics/evolution")
def get_evolution():
    """研究主题演化数据 (Theme River)"""
    data = _load_analytics_data("trends.json")
    if data:
        return data
    # 返回空结构
    return {"years": [], "categories": [], "data": []}


@app.get("/api/analytics/radar")
def get_radar():
    """实验室研究倾向雷达数据"""
    data = _load_analytics_data("lab_radar.json")
    if data:
        return data
    return {"labs": [], "indicators": [], "series": []}


@app.get("/api/analytics/topics")
def get_topics():
    """主题层级分布 (Sunburst)"""
    data = _load_analytics_data("topic_sunburst.json")
    if data:
        return data
    return {"name": "全部研究领域", "children": []}


@app.get("/api/analytics/concept_map")
def get_concept_map():
    """概念维度映射表"""
    data = _load_analytics_data("concept_dim_map.json")
    if data:
        return data
    return {}


# ================= 可视化 UI (原样保留) =================
HTML_CONTENT = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title> 学术情报指挥舱 MKIV</title>
    <script src="__ECHARTS_CDN__"></script>
    <style>
        body { margin: 0; background: #0a0a0c; color: #fff; font-family: 'Segoe UI', sans-serif; overflow: hidden; }
        #main { width: 100vw; height: 100vh; }
        .toolbar { position: absolute; top: 20px; left: 20px; z-index: 999; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; max-width: calc(100vw - 40px); background: rgba(30,30,40,0.85); padding: 10px 12px; border-radius: 12px; backdrop-filter: blur(8px); border: 1px solid #333; box-shadow: 0 4px 15px rgba(0,0,0,0.5); }
        input, select, button { padding: 10px 12px; border-radius: 6px; border: 1px solid #444; background: #1e1e24; color: #fff; outline: none; font-size: 14px;}
        /* 表单控件在 flex 行里没有显式高度时会被拉伸/撑高 (实测一行占 76~108px),
           这里钉住高度, 并让超长的分类名不再把工具条顶出屏幕 */
        .toolbar, .toolbar * { box-sizing: border-box; }
        .toolbar input, .toolbar select, .toolbar button { height: 34px; line-height: 1; padding: 0 12px; }
        .toolbar #filterSelect { max-width: 300px; }
        .toolbar #searchInput { width: 190px; }
        button { background: #3498db; cursor: pointer; border: none; font-weight: bold; transition: 0.2s;}
        button:hover { background: #2980b9; transform: scale(1.02); }
        #sidebar { position: fixed; right: -450px; top: 0; width: 400px; height: 100vh; background: #16161a; transition: 0.4s cubic-bezier(0.4, 0, 0.2, 1); padding: 25px; box-shadow: -10px 0 30px rgba(0,0,0,0.7); z-index: 1000; overflow-y: auto; border-left: 1px solid #333; }
        #sidebar.active { right: 0; }
        .paper-card { background: #25252b; padding: 14px; margin-bottom: 12px; border-radius: 8px; border-left: 5px solid #2ecc71; font-size: 13px; line-height: 1.5; transition: 0.2s; }
        .paper-card:hover { transform: translateX(-5px); }
        .close-btn { float: right; cursor: pointer; font-size: 28px; color: #666; transition: 0.2s;}
        .close-btn:hover { color: #ff4757; }
        #legendPanel { position: fixed; left: 0; right: 0; bottom: 0; z-index: 998; background: rgba(22,22,26,0.94); border-top: 1px solid #333; padding: 6px 14px; max-height: 22vh; overflow-y: auto; font-size: 13px; backdrop-filter: blur(8px); }
        .lg-row { display: flex; align-items: flex-start; gap: 12px; padding: 2px 0; }
        .lg-title { color: #888; min-width: 38px; padding-top: 4px; flex: none; }
        .lg-group { display: flex; flex-wrap: wrap; gap: 4px 14px; }
        .lg-item { display: inline-flex; align-items: center; gap: 6px; cursor: pointer; color: #ddd; padding: 2px 6px; border-radius: 5px; user-select: none; }
        .lg-item:hover { background: #26262c; }
        .lg-item input { accent-color: #3498db; cursor: pointer; width: 13px; height: 13px; }
        .lg-item.off { color: #666; }
        .lg-swatch { width: 12px; height: 12px; border-radius: 3px; display: inline-block; flex: none; }
        .lg-btn { padding: 4px 10px; font-size: 12px; background: #2a2a33; color: #ccc; border: 1px solid #444; border-radius: 5px; cursor: pointer; }
        .lg-btn:hover { border-color: #666; color: #fff; }
        #legendPanel .lg-head { display: flex; align-items: center; gap: 10px; color: #666; font-size: 12px; padding-bottom: 2px; }
    </style>
</head>
<body>
    <div class="toolbar">
        <select id="viewSelect" onchange="updateCategoryList()"><option value="admin">🏛️ 实验室视角</option><option value="topic">🌌 研究主题视角</option></select>
        <select id="filterSelect" onchange="loadGraph()"><option value="">-- 全景星图 --</option></select>
        <input type="text" id="searchInput" placeholder="搜索学者姓名/ID..." onkeypress="if(event.key=='Enter') searchNode()">
        <button onclick="searchNode()">🔍 追踪定位</button>
        <button onclick="location.href='/analytics'" style="background:#2ecc71;">📈 情报分析</button>
    </div>
    <div id="sidebar">
        <span class="close-btn" onclick="closeSidebar()">&times;</span>
        <h2 id="s_name" style="color: #2ecc71; margin-top: 10px; font-size: 28px;">学者姓名</h2>
        <div id="s_lab" style="color: #95a5a6; margin-bottom: 25px; font-weight: 500;">🏢 实验室归属</div>
        <h4 style="border-bottom: 1px solid #333; padding-bottom: 10px; color: #ddd;">📚 核心学术产出</h4>
        <div id="s_papers"></div>
    </div>
    <div id="main"></div>
    <div id="legendPanel"></div>
    <script>
        var myChart = echarts.init(document.getElementById('main'), 'dark');
        var currentGraphData = null;   // 后端返回的完整图 (未经前端勾选过滤)
        var visibleNodes = [];         // 当前勾选后真正显示的点
        var visibleLinks = [];
        var catSelected = {};          // 分类名 -> 是否勾选
        var roleSelected = {};         // 角色名 -> 是否勾选

        async function updateCategoryList() {
            const view = document.getElementById('viewSelect').value;
            const res = await fetch(`/api/categories?view=${view}`);
            const categories = await res.json();
            const sel = document.getElementById('filterSelect');
            sel.innerHTML = '<option value="">-- 全景星图 --</option>';
            categories.forEach(cat => {
                const opt = document.createElement('option');
                opt.value = cat.name; opt.innerText = `${cat.name} (${cat.count})`; sel.appendChild(opt);
            });
            loadGraph();
        }

        async function loadGraph() {
            myChart.showLoading({text: '情报分析中...', maskColor: 'rgba(10, 10, 12, 0.8)'});
            try {
                const view = document.getElementById('viewSelect').value;
                const filter = document.getElementById('filterSelect').value;
                const res = await fetch(`/api/graph?view=${view}&filter_name=${encodeURIComponent(filter)}`);
                currentGraphData = await res.json();

                // 新一批数据: 勾选状态全部重置为「选中」
                catSelected = {};
                currentGraphData.categories.forEach(c => { catSelected[c.name] = true; });
                roleSelected = {};
                currentGraphData.nodes.forEach(n => { roleSelected[n.role] = true; });

                renderLegend();
                applyFilters();
            } catch(e) {
                document.getElementById('legendPanel').innerHTML = '';
                myChart.setOption({ title: { text: '加载失败', subtext: String(e.message || e), left: 'center', top: 'center', textStyle: { color: '#555', fontSize: 20 }, subtextStyle: { color: '#444', fontSize: 14 } } }, true);
            } finally {
                myChart.hideLoading();
            }
        }

        // ============ 自绘图例 (替代 ECharts legend, 可勾选任意分类/角色) ============
        function _mkCheckbox(checked, onChange) {
            const cb = document.createElement('input');
            cb.type = 'checkbox';
            cb.checked = checked;
            cb.addEventListener('change', onChange);
            return cb;
        }

        function renderLegend() {
            const panel = document.getElementById('legendPanel');
            panel.innerHTML = '';
            if (!currentGraphData || currentGraphData.nodes.length === 0) return;

            // 分类行
            const row1 = document.createElement('div'); row1.className = 'lg-row';
            const t1 = document.createElement('span'); t1.className = 'lg-title'; t1.innerText = '分类';
            const g1 = document.createElement('div'); g1.className = 'lg-group';
            row1.appendChild(t1); row1.appendChild(g1);

            const resetBtn = document.createElement('button');
            resetBtn.className = 'lg-btn'; resetBtn.innerText = '重置全部';
            resetBtn.addEventListener('click', resetLegend);
            const headCell = document.createElement('div');
            headCell.style.marginLeft = 'auto'; headCell.appendChild(resetBtn);
            row1.appendChild(headCell);

            currentGraphData.categories.forEach(c => {
                const on = catSelected[c.name] !== false;
                const item = document.createElement('label');
                item.className = 'lg-item' + (on ? '' : ' off');
                item.appendChild(_mkCheckbox(on, ev => {
                    catSelected[c.name] = ev.target.checked;
                    item.classList.toggle('off', !ev.target.checked);
                    applyFilters();
                }));
                const sw = document.createElement('span'); sw.className = 'lg-swatch'; sw.style.background = c.color;
                const tx = document.createElement('span'); tx.innerText = `${c.name} (${c.count})`;
                item.appendChild(sw); item.appendChild(tx);
                g1.appendChild(item);
            });
            panel.appendChild(row1);

            // 角色行
            const roles = Array.from(new Set(currentGraphData.nodes.map(n => n.role)));
            if (roles.length > 0) {
                const row2 = document.createElement('div'); row2.className = 'lg-row';
                const t2 = document.createElement('span'); t2.className = 'lg-title'; t2.innerText = '角色';
                const g2 = document.createElement('div'); g2.className = 'lg-group';
                row2.appendChild(t2); row2.appendChild(g2);
                roles.forEach(r => {
                    const on = roleSelected[r] !== false;
                    const item = document.createElement('label');
                    item.className = 'lg-item' + (on ? '' : ' off');
                    item.appendChild(_mkCheckbox(on, ev => {
                        roleSelected[r] = ev.target.checked;
                        item.classList.toggle('off', !ev.target.checked);
                        applyFilters();
                    }));
                    const tx = document.createElement('span');
                    tx.innerText = `${r === '导师' ? '◆ 导师' : r} (${currentGraphData.nodes.filter(n => n.role === r).length})`;
                    item.appendChild(tx);
                    g2.appendChild(item);
                });
                panel.appendChild(row2);
            }

            const hint = document.createElement('div');
            hint.className = 'lg-head';
            hint.innerText = `当前显示 ${visibleNodes.length} / ${currentGraphData.nodes.length} 位学者 · 连线 ${visibleLinks.length}`;
            hint.id = 'lgHint';
            panel.appendChild(hint);
        }

        function resetLegend() {
            Object.keys(catSelected).forEach(k => catSelected[k] = true);
            Object.keys(roleSelected).forEach(k => roleSelected[k] = true);
            renderLegend();
            applyFilters();
        }

        function buildSeries() {
            return {
                type: 'graph', layout: 'force',
                data: visibleNodes, links: visibleLinks,
                roam: true, layoutAnimation: false,
                label: { position: 'right', color: '#fff', fontSize: 11 },
                force: { repulsion: 300, edgeLength: 60, gravity: 0.1 },
                emphasis: { focus: 'adjacency', lineStyle: { width: 6, opacity: 1 }, label: { show: true, fontWeight: 'bold' } },
                blur: { itemStyle: { opacity: 0.1 }, lineStyle: { opacity: 0.05 } },
                lineStyle: { color: 'source', curveness: 0.1, opacity: 0.4 }
            };
        }

        // 前端本地勾选过滤: 点按分类/角色筛, 边只保留两端都可见的
        function applyFilters() {
            if (!currentGraphData) return;
            visibleNodes = currentGraphData.nodes.filter(n =>
                catSelected[n.category] !== false && roleSelected[n.role] !== false);
            const keep = new Set(visibleNodes.map(n => n.id));
            visibleLinks = currentGraphData.links.filter(l => keep.has(l.source) && keep.has(l.target));
            myChart.setOption({ series: [buildSeries()] }, { replaceMerge: ['series'] });
            const hint = document.getElementById('lgHint');
            if (hint) hint.innerText = `当前显示 ${visibleNodes.length} / ${currentGraphData.nodes.length} 位学者 · 连线 ${visibleLinks.length}`;
        }

        // 把视口平移到目标节点: 直接平移承载 view 变换的 graph group,
        // 与用户拖拽画布是同一条路径 (ECharts 没有移动视口的公开 API,
        // dispatchAction graphRoam 的 update 是 "none", 只发事件不平移)。
        function moveViewToNode(node, onDone) {
            const done = onDone || function(){};
            try {
                const seriesModel = myChart.getModel().getSeriesByIndex(0);
                const view = seriesModel && myChart.getViewOfSeriesModel(seriesModel);
                const group = view && view.group;
                const el = seriesModel.getData().getItemGraphicEl(visibleNodes.indexOf(node));
                const m = el && el.getComputedTransform();   // 含各级父变换的全局矩阵
                if (!group || !m) { done(); return; }
                // 侧栏与底部图例是浮层, 会盖住画布, 按真正可见的区域取中心
                const sideW = document.getElementById('sidebar').offsetWidth || 0;
                const legendH = document.getElementById('legendPanel').offsetHeight || 0;
                const dx = (myChart.getWidth() - sideW) / 2 - m[4];
                const dy = (myChart.getHeight() - legendH) / 2 - m[5];
                if (!dx && !dy) { done(); return; }
                if (group.animateTo) {
                    group.animateTo({ x: group.x + dx, y: group.y + dy },
                                    { duration: 450, easing: 'cubicOut', done: done });
                } else {
                    group.x += dx; group.y += dy; group.dirty(); done();
                }
            } catch (e) { done(); }   // 定位失败不应拖累聚焦与侧栏
        }

        async function searchNode() {
            const query = document.getElementById('searchInput').value.toLowerCase().trim();
            if(!query) return;
            const targetNode = visibleNodes.find(n => n.name.toLowerCase().includes(query) || n.id.toLowerCase() === query);
            if(targetNode) {
                myChart.dispatchAction({ type: 'unfocus', seriesIndex: 0 });
                myChart.dispatchAction({ type: 'focus', seriesIndex: 0, id: targetNode.id });
                showDetails(targetNode.id);
                // 提示框按节点当时的位置定位, 故等平移动画走完再弹
                moveViewToNode(targetNode, function(){
                    myChart.dispatchAction({ type: 'showTip', seriesIndex: 0, dataIndex: visibleNodes.indexOf(targetNode) });
                });
            } else {
                const res = await (await fetch(`/api/search_exact?query=${encodeURIComponent(query)}`)).json();
                if (res.found) {
                    alert(`💡 数据库命中：【${res.name}】\\n由于合作关系低于阈值，已直接调取档案。`);
                    showDetails(res.id);
                } else { alert("⚠️ 查无此人，请确认姓名输入正确。"); }
            }
        }
        async function showDetails(sid) {
            const res = await fetch(`/api/details?sid=${encodeURIComponent(sid)}`);
            const data = await res.json();
            document.getElementById('s_name').innerText = data.name;
            document.getElementById('s_lab').innerText = "🏢 " + data.lab;
            document.getElementById('s_papers').innerHTML = data.papers.map(p => 
                `<div class="paper-card"><b><a href="${p.doi}" target="_blank" style="color:#eee;text-decoration:none;">${p.title}</a></b><br/><div style="color:#f39c12;font-size:11px;margin-top:5px;">📔 ${p.journal}</div></div>`
            ).join('') || '<p style="color:#666;">暂无记录</p>';
            document.getElementById('sidebar').classList.add('active');
        }
        function closeSidebar() { document.getElementById('sidebar').classList.remove('active'); myChart.dispatchAction({ type: 'unfocus', seriesIndex: 0 }); }
        myChart.on('click', e => { if(e.dataType === 'node') showDetails(e.data.id); });
        myChart.getZr().on('click', e => { if(!e.target) closeSidebar(); });
        window.onload = updateCategoryList;
        window.onresize = () => myChart.resize();
    </script>
</body>
</html>
"""

ANALYTICS_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>MKIV 情报分析 — 学术演化与趋势</title>
    <script src="__ECHARTS_CDN__"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { background: #0a0a0c; color: #fff; font-family: 'Segoe UI', sans-serif; overflow: hidden; display: flex; flex-direction: column; height: 100vh; }
        .nav { display: flex; gap: 8px; padding: 12px 20px; background: #121216; border-bottom: 1px solid #222; align-items: center; }
        .nav a { color: #95a5a6; text-decoration: none; padding: 8px 16px; border-radius: 6px; font-size: 13px; font-weight: 600; transition: 0.2s; }
        .nav a:hover { color: #fff; background: #1e1e28; }
        .nav a.active { color: #3498db; background: #1a1a2e; }
        .nav .title { font-size: 16px; font-weight: bold; color: #3498db; margin-right: auto; }
        .tabs { display: flex; gap: 6px; padding: 8px 20px; background: #0d0d12; border-bottom: 1px solid #1a1a1a; }
        .tabs button { padding: 8px 18px; border: 1px solid #333; border-radius: 6px; background: #16161a; color: #aaa; cursor: pointer; font-size: 12px; font-weight: 600; transition: 0.2s; }
        .tabs button:hover { border-color: #555; color: #fff; }
        .tabs button.active { background: #1a2a3a; border-color: #3498db; color: #3498db; }
        .tabs .selector { margin-left: auto; display: flex; align-items: center; gap: 8px; }
        .tabs .selector select { background: #1e1e24; color: #ccc; border: 1px solid #444; padding: 6px 12px; border-radius: 4px; font-size: 12px; }
        #charts { flex: 1; position: relative; }
        .chart { position: absolute; top: 0; left: 0; width: 100%; height: 100%; display: none; }
        .chart.active { display: block; }
        .empty-state { display: flex; justify-content: center; align-items: center; height: 100%; color: #555; font-size: 18px; flex-direction: column; }
        .empty-state .icon { font-size: 64px; margin-bottom: 16px; }
    </style>
</head>
<body>
    <div class="nav">
        <span class="title">MKIV 学术情报分析</span>
        <a href="/">🕸️ 关系星图</a>
        <a href="/analytics" class="active">📈 情报分析</a>
    </div>
    <div class="tabs">
        <button class="active" onclick="switchTab('river')">🌊 主题演化河流</button>
        <button onclick="switchTab('radar')">🎯 实验室研究倾向</button>
        <button onclick="switchTab('sunburst')">☀️ 主题层级分布</button>
        <div class="selector" id="radarSelector" style="display:none;">
            <span style="font-size:12px;color:#888;">对比实验室:</span>
            <select id="labSelect" onchange="updateRadarHighlight()"></select>
        </div>
    </div>
    <div id="charts">
        <div id="river_chart" class="chart active"></div>
        <div id="radar_chart" class="chart"></div>
        <div id="sunburst_chart" class="chart"></div>
    </div>
    <script>
        var riverChart = echarts.init(document.getElementById('river_chart'), 'dark');
        var radarChart = echarts.init(document.getElementById('radar_chart'), 'dark');
        var sunburstChart = echarts.init(document.getElementById('sunburst_chart'), 'dark');
        var radarData = null;

        function switchTab(name) {
            document.querySelectorAll('.tabs button').forEach((b, i) => {
                b.classList.toggle('active', i === ({river:0,radar:1,sunburst:2}[name]));
            });
            document.querySelectorAll('.chart').forEach(c => c.classList.remove('active'));
            document.getElementById(name + '_chart').classList.add('active');
            document.getElementById('radarSelector').style.display = (name === 'radar') ? 'flex' : 'none';
            if (name === 'river') riverChart.resize();
            if (name === 'radar') { radarChart.resize(); if (!radarData) loadRadar(); }
            if (name === 'sunburst') sunburstChart.resize();
        }

        // ==================== Theme River ====================
        async function loadRiver() {
            riverChart.showLoading({text: '加载演化数据...', maskColor: 'rgba(10,10,12,0.8)'});
            try {
                const res = await fetch('/api/analytics/evolution');
                const data = await res.json();
                if (!data.data || data.data.length === 0) {
                    riverChart.hideLoading();
                    showEmpty(riverChart, '暂无演化数据', '请先执行分析流水线 (Step 4.5)');
                    return;
                }
                riverChart.setOption({
                    tooltip: { trigger: 'axis' },
                    legend: { data: data.categories, bottom: 10, textStyle: { color: '#ccc', fontSize: 11 }, type: 'scroll' },
                    singleAxis: { top: 40, bottom: 50, type: 'time', axisLabel: { color: '#aaa' }, axisLine: { lineStyle: { color: '#333' } } },
                    series: [{
                        type: 'themeRiver',
                        emphasis: { itemStyle: { shadowBlur: 20, shadowColor: 'rgba(255,255,255,0.3)' } },
                        data: data.data,
                        label: { show: false }
                    }]
                }, true);
                riverChart.hideLoading();
            } catch(e) {
                riverChart.hideLoading();
                showEmpty(riverChart, '加载失败', e.message);
            }
        }

        // ==================== Radar ====================
        async function loadRadar() {
            radarChart.showLoading({text: '加载实验室数据...', maskColor: 'rgba(10,10,12,0.8)'});
            try {
                const res = await fetch('/api/analytics/radar');
                radarData = await res.json();
                if (!radarData.series || radarData.series.length === 0) {
                    radarChart.hideLoading();
                    showEmpty(radarChart, '暂无实验室数据', '请确认 U3 数据中包含内部实验室信息');
                    return;
                }
                var sel = document.getElementById('labSelect');
                sel.innerHTML = radarData.labs.map((l,i) => '<option value="' + i + '">' + (l.length > 20 ? l.substring(0,18)+'..' : l) + '</option>').join('');
                updateRadarChart();
                radarChart.hideLoading();
            } catch(e) {
                radarChart.hideLoading();
                showEmpty(radarChart, '加载失败', e.message);
            }
        }

        function updateRadarChart(hideOthers) {
            if (!radarData) return;
            var series = radarData.series.map(function(s, i) {
                var show = !hideOthers || i == document.getElementById('labSelect').value;
                return {
                    name: s.name.substring(0, 18),
                    type: 'radar',
                    symbol: 'circle',
                    symbolSize: 4,
                    data: [{ value: s.value, name: s.name.substring(0, 18) }],
                    lineStyle: { opacity: show ? 0.8 : 0.08, width: show ? 2 : 1 },
                    areaStyle: { opacity: show ? 0.15 : 0 },
                    itemStyle: { opacity: show ? 1 : 0 },
                    label: { show: false }
                };
            });
            radarChart.setOption({
                tooltip: { trigger: 'item' },
                legend: { data: radarData.series.map(s => s.name.substring(0,18)), bottom: 10, textStyle: { color: '#ccc', fontSize: 10 }, type: 'scroll' },
                radar: {
                    center: ['50%', '48%'],
                    radius: '65%',
                    indicator: radarData.indicators.map(function(ind) {
                        return { name: ind.length > 10 ? ind.substring(0,9)+'..' : ind, max: 100 };
                    }),
                    axisName: { color: '#aaa', fontSize: 10 }
                },
                series: series
            }, true);
        }

        function updateRadarHighlight() { updateRadarChart(true); }

        // ==================== Sunburst ====================
        async function loadSunburst() {
            sunburstChart.showLoading({text: '加载主题层级...', maskColor: 'rgba(10,10,12,0.8)'});
            try {
                const res = await fetch('/api/analytics/topics');
                const data = await res.json();
                if (!data.children || data.children.length === 0) {
                    sunburstChart.hideLoading();
                    showEmpty(sunburstChart, '暂无主题分布数据', '请先执行分析流水线 (Step 4.5)');
                    return;
                }
                sunburstChart.setOption({
                    tooltip: { trigger: 'item', formatter: '{b}: {c} 篇' },
                    series: [{
                        type: 'sunburst',
                        roam: true,
                        data: data.children,
                        radius: ['20%', '90%'],
                        label: { rotate: 'radial', color: '#ccc', fontSize: 11 },
                        itemStyle: { borderRadius: 4, borderWidth: 2, borderColor: '#0a0a0c' },
                        emphasis: { label: { fontSize: 16, fontWeight: 'bold' } },
                        levels: [{}, { r0: '20%', r: '55%' }, { r0: '55%', r: '65%' }]
                    }]
                }, true);
                sunburstChart.hideLoading();
            } catch(e) {
                sunburstChart.hideLoading();
                showEmpty(sunburstChart, '加载失败', e.message);
            }
        }

        function showEmpty(chart, title, subtitle) {
            chart.setOption({
                title: { text: title, subtext: subtitle, left: 'center', top: 'center',
                         textStyle: { color: '#555', fontSize: 20 }, subtextStyle: { color: '#444', fontSize: 14 } }
            }, true);
        }

        // 初始化加载
        loadRiver();
        loadSunburst();

        window.onresize = function() {
            riverChart.resize();
            radarChart.resize();
            sunburstChart.resize();
        };
    </script>
</body>
</html>
"""


def _render(html: str) -> str:
    """渲染 HTML 模板，注入可配置的 ECharts CDN 地址"""
    return html.replace('__ECHARTS_CDN__', _graph_cfg.get('echarts_cdn', DEFAULT_ECHARTS_CDN))


@app.get("/", response_class=HTMLResponse)
def index():
    return _render(HTML_CONTENT)


@app.get("/analytics", response_class=HTMLResponse)
def analytics():
    return _render(ANALYTICS_HTML)

# ================= 启动器 =================

_server = None
_server_started = False


def start_visualizer_server(db_config: dict, host: str = "0.0.0.0", port: int = DASHBOARD_PORT,
                            graph_cfg: dict = None):
    """
    接收来自 Pipeline 的配置，动态连接 Neo4j 并启动 Web 服务 (阻塞模式, CLI 使用)
    """
    global driver, _graph_cfg
    _graph_cfg = graph_cfg or {}
    logging.info(f">> 📊 正在启动学术情报大屏服务端，连接图数据库...")
    try:
        driver = GraphDatabase.driver(
            db_config['uri'],
            auth=(db_config['user'], db_config['password']),
            connection_timeout=NEO4J_CONNECTION_TIMEOUT,
            connection_acquisition_timeout=NEO4J_CONNECTION_TIMEOUT,
        )
        logging.info(f"   ✅ 图数据库连接成功。")
    except Exception as e:
        logging.error(f"   ❌ 图数据库连接失败: {e}")
        return

    logging.info(f"🚀 MKIV 指挥舱已点火！请在浏览器访问: http://{DASHBOARD_HOST}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="warning")


def start_visualizer_server_background(db_config: dict, host: str = DASHBOARD_HOST, port: int = DASHBOARD_PORT,
                                       graph_cfg: dict = None):
    """
    非阻塞模式：在后台守护线程中启动 FastAPI (GUI 使用)
    """
    import threading
    global driver, _server, _server_started, _graph_cfg
    _graph_cfg = graph_cfg or {}

    logging.info(f">> 📊 正在后台启动学术情报大屏服务端，连接图数据库...")
    try:
        driver = GraphDatabase.driver(
            db_config['uri'],
            auth=(db_config['user'], db_config['password']),
            connection_timeout=NEO4J_CONNECTION_TIMEOUT,
            connection_acquisition_timeout=NEO4J_CONNECTION_TIMEOUT,
        )
        logging.info(f"   ✅ 图数据库连接成功。")
    except Exception as e:
        logging.error(f"   ❌ 图数据库连接失败: {e}")
        return

    config = uvicorn.Config(app=app, host=host, port=port, log_level="warning")
    _server = uvicorn.Server(config=config)
    t = threading.Thread(target=_server.run, daemon=True, name="uvicorn-server")
    t.start()
    _server_started = True
    logging.info(f"🚀 MKIV 指挥舱已后台启动！浏览器访问: http://{host}:{port}")


def stop_visualizer_server():
    """停止后台运行的 FastAPI 服务器并关闭数据库连接"""
    global driver, _server, _server_started
    if _server is not None:
        _server.should_exit = True
        _server = None
        _server_started = False
        logging.info(">> 🛑 可视化服务器已停止。")
    if driver is not None:
        driver.close()
        driver = None
        logging.info(">> 🔌 数据库连接已关闭。")


def is_visualizer_running() -> bool:
    """检查后台服务器是否已启动"""
    return _server_started