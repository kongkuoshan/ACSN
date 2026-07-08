# core/visualizer.py
import os
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from neo4j import GraphDatabase
import uvicorn
import logging

# 初始化 FastAPI 应用
app = FastAPI(title="MKIV 学术情报指挥舱")

# 全局数据库驱动，等待流水线启动时注入
driver = None

def shorten(name):
    """前端类别名称截断工具"""
    if not name or name in ["Unknown", "待分类", "N/A", "其他"]:
        return "其他单元"
    s = str(name).split(',')[0].split(' -')[0].strip()
    return s[:16] + ".." if len(s) > 18 else s

# ================= 后端 API 接口 =================

@app.get("/api/graph")
def get_graph(view: str = "admin", filter_name: str = ""):
    limit = 3000 if filter_name == "" else 5000
    min_w = 1

    if view == "admin":
        cypher = f"""
        MATCH (s1:Scholar)
        WHERE $f = '' OR EXISTS((s1)-[:BELONGS_TO]->(:Lab {{name: $f}}))
        MATCH (s1)-[r:CO_WORK]-(s2:Scholar)
        WHERE r.weight >= {min_w} AND s1.id < s2.id 
        WITH s1, s2, r
        ORDER BY r.weight DESC LIMIT {limit}
        OPTIONAL MATCH (s1)-[:BELONGS_TO]->(lab:Lab)
        WITH s1, s2, r, collect(DISTINCT lab.name)[0] as cat
        RETURN s1.id as id1, s1.name as n1, s1.role as r1, 
               s2.id as id2, s2.name as n2, s2.role as r2, 
               coalesce(cat, "其他单元") as cat, r.weight as w
        """
    else:
        cypher = f"""
        MATCH (s1:Scholar)
        WHERE $f = '' OR EXISTS((s1)-[:WROTE]->(:Paper)-[:MAPPED_TO]->(:Topic {{name: $f}}))
        MATCH (s1)-[r:CO_WORK]-(s2:Scholar)
        WHERE r.weight >= {min_w} AND s1.id < s2.id
        WITH s1, s2, r
        ORDER BY r.weight DESC LIMIT {limit}
        OPTIONAL MATCH (s1)-[:WROTE]->()-[:MAPPED_TO]->(t:Topic)
        WITH s1, s2, r, collect(DISTINCT t.name)[0] as cat
        RETURN s1.id as id1, s1.name as n1, s1.role as r1, 
               s2.id as id2, s2.name as n2, s2.role as r2, 
               coalesce(cat, "其他单元") as cat, r.weight as w
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
                        "category": shorten(r['cat']),
                        "symbol": "diamond" if is_pi else "circle",
                        "symbolSize": 32 if is_pi else 12,
                        "itemStyle": {"color": "#e74c3c" if is_pi else None},
                        "label": {"show": is_pi, "fontSize": 12, "fontWeight": "bold"}
                    }

            link_hash = tuple(sorted([r['id1'], r['id2']]))
            if link_hash not in seen_links:
                links.append({"source": r['id1'], "target": r['id2'], "value": r['w']})
                seen_links.add(link_hash)
        
        unique_cats = list(set([n["category"] for n in nodes.values()]))
        return {"nodes": list(nodes.values()), "links": links, "categories": [{"name": c} for c in unique_cats]}

@app.get("/api/categories")
def get_categories(view: str = "admin"):
    if view == "admin":
        query = "MATCH (s:Scholar)-[:BELONGS_TO]->(c:Lab) RETURN c.name AS name, count(DISTINCT s) as cnt ORDER BY cnt DESC"
    else:
        query = "MATCH (p:Paper)-[:MAPPED_TO]->(c:Topic) RETURN c.name AS name, count(DISTINCT p) as cnt ORDER BY cnt DESC"
        
    with driver.session() as session:
        result = session.run(query)
        return [{"raw": r["name"], "short": shorten(r["name"])} for r in result]

@app.get("/api/details")
def get_details(sid: str):
    cypher = """
    MATCH (s:Scholar {id: $id})
    OPTIONAL MATCH (s)-[:BELONGS_TO]->(l:Lab)
    OPTIONAL MATCH (s)-[:WROTE]->(p:Paper)
    RETURN s.name as name, l.name as lab, 
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
    filepath = os.path.join("data", "output", filename)
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


# ================= 前端 UI (原样保留) =================
HTML_CONTENT = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title> 学术情报指挥舱 MKIV</title>
    <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
    <style>
        body { margin: 0; background: #0a0a0c; color: #fff; font-family: 'Segoe UI', sans-serif; overflow: hidden; }
        #main { width: 100vw; height: 100vh; }
        .toolbar { position: absolute; top: 20px; left: 20px; z-index: 999; display: flex; gap: 10px; background: rgba(30,30,40,0.85); padding: 15px; border-radius: 12px; backdrop-filter: blur(8px); border: 1px solid #333; box-shadow: 0 4px 15px rgba(0,0,0,0.5); }
        input, select, button { padding: 10px 12px; border-radius: 6px; border: 1px solid #444; background: #1e1e24; color: #fff; outline: none; font-size: 14px;}
        button { background: #3498db; cursor: pointer; border: none; font-weight: bold; transition: 0.2s;}
        button:hover { background: #2980b9; transform: scale(1.02); }
        #sidebar { position: fixed; right: -450px; top: 0; width: 400px; height: 100vh; background: #16161a; transition: 0.4s cubic-bezier(0.4, 0, 0.2, 1); padding: 25px; box-shadow: -10px 0 30px rgba(0,0,0,0.7); z-index: 1000; overflow-y: auto; border-left: 1px solid #333; }
        #sidebar.active { right: 0; }
        .paper-card { background: #25252b; padding: 14px; margin-bottom: 12px; border-radius: 8px; border-left: 5px solid #2ecc71; font-size: 13px; line-height: 1.5; transition: 0.2s; }
        .paper-card:hover { transform: translateX(-5px); }
        .close-btn { float: right; cursor: pointer; font-size: 28px; color: #666; transition: 0.2s;}
        .close-btn:hover { color: #ff4757; }
    </style>
</head>
<body>
    <div class="toolbar">
        <select id="viewSelect" onchange="updateCategoryList()"><option value="admin">🏛️ 实验室视角</option><option value="topic">🌌 研究主题视角</option></select>
        <select id="filterSelect" onchange="loadGraph()"><option value="">-- 全景星图 --</option></select>
        <input type="text" id="searchInput" placeholder="搜索学者姓名/ID..." onkeypress="if(event.key=='Enter') searchNode()">
        <button onclick="searchNode()">🔍 追踪定位</button>
    </div>
    <div id="sidebar">
        <span class="close-btn" onclick="closeSidebar()">&times;</span>
        <h2 id="s_name" style="color: #2ecc71; margin-top: 10px; font-size: 28px;">学者姓名</h2>
        <div id="s_lab" style="color: #95a5a6; margin-bottom: 25px; font-weight: 500;">🏢 实验室归属</div>
        <h4 style="border-bottom: 1px solid #333; padding-bottom: 10px; color: #ddd;">📚 核心学术产出</h4>
        <div id="s_papers"></div>
    </div>
    <div id="main"></div>
    <script>
        var myChart = echarts.init(document.getElementById('main'), 'dark');
        var currentGraphData = null;
        async function updateCategoryList() {
            const view = document.getElementById('viewSelect').value;
            const res = await fetch(`/api/categories?view=${view}`);
            const categories = await res.json();
            const sel = document.getElementById('filterSelect');
            sel.innerHTML = '<option value="">-- 全景星图 --</option>';
            categories.forEach(cat => {
                const opt = document.createElement('option');
                opt.value = cat.raw; opt.innerText = cat.short; sel.appendChild(opt);
            });
            loadGraph();
        }
        async function loadGraph() {
            myChart.showLoading({text: '情报分析中...', maskColor: 'rgba(10, 10, 12, 0.8)'});
            const view = document.getElementById('viewSelect').value;
            const filter = document.getElementById('filterSelect').value;
            const res = await fetch(`/api/graph?view=${view}&filter_name=${encodeURIComponent(filter)}`);
            currentGraphData = await res.json();
            myChart.setOption({
                legend: { data: currentGraphData.categories.map(c => c.name), bottom: 15, type: 'scroll' },
                tooltip: { trigger: 'item', formatter: '{b}' },
                series: [{
                    type: 'graph', layout: 'force',
                    data: currentGraphData.nodes, links: currentGraphData.links, categories: currentGraphData.categories,
                    roam: true, layoutAnimation: false, label: { position: 'right', color: '#fff', fontSize: 11 }, 
                    force: { repulsion: 300, edgeLength: 60, gravity: 0.1 },                       
                    emphasis: { focus: 'adjacency', lineStyle: { width: 6, opacity: 1 }, label: { show: true, fontWeight: 'bold' } },                    
                    blur: { itemStyle: { opacity: 0.1 }, lineStyle: { opacity: 0.05 } },
                    lineStyle: { color: 'source', curveness: 0.1, opacity: 0.4 }
                }]
            }, true);
            myChart.hideLoading();
        }
        async function searchNode() {
            const query = document.getElementById('searchInput').value.toLowerCase().trim();
            if(!query) return;
            const targetNode = currentGraphData.nodes.find(n => n.name.toLowerCase().includes(query) || n.id.toLowerCase() === query);
            if(targetNode) {
                myChart.dispatchAction({ type: 'unfocus', seriesIndex: 0 });
                myChart.dispatchAction({ type: 'focus', seriesIndex: 0, id: targetNode.id });
                myChart.dispatchAction({ type: 'showTip', seriesIndex: 0, dataIndex: currentGraphData.nodes.indexOf(targetNode) });
                showDetails(targetNode.id);
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
    <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
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
        <a href="/" class="active">🕸️ 关系星图</a>
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


@app.get("/", response_class=HTMLResponse)
def index():
    return HTML_CONTENT


@app.get("/analytics", response_class=HTMLResponse)
def analytics():
    return ANALYTICS_HTML

# ================= 启动器 =================

_server = None
_server_started = False


def start_visualizer_server(db_config: dict, host: str = "0.0.0.0", port: int = 8000):
    """
    接收来自 Pipeline 的配置，动态连接 Neo4j 并启动 Web 服务 (阻塞模式, CLI 使用)
    """
    global driver
    logging.info(f">> 📊 正在启动学术情报大屏服务端，连接图数据库...")
    try:
        driver = GraphDatabase.driver(db_config['uri'], auth=(db_config['user'], db_config['password']))
        logging.info(f"   ✅ 图数据库连接成功。")
    except Exception as e:
        logging.error(f"   ❌ 图数据库连接失败: {e}")
        return

    logging.info(f"🚀 MKIV 指挥舱已点火！请在浏览器访问: http://127.0.0.1:{port}")
    uvicorn.run(app, host=host, port=port, log_level="warning")


def start_visualizer_server_background(db_config: dict, host: str = "127.0.0.1", port: int = 8000):
    """
    非阻塞模式：在后台守护线程中启动 FastAPI (GUI 使用)
    """
    import threading
    global driver, _server, _server_started

    logging.info(f">> 📊 正在后台启动学术情报大屏服务端，连接图数据库...")
    try:
        driver = GraphDatabase.driver(db_config['uri'], auth=(db_config['user'], db_config['password']))
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
    """停止后台运行的 FastAPI 服务器"""
    global _server, _server_started
    if _server is not None:
        _server.should_exit = True
        _server = None
        _server_started = False
        logging.info(">> 🛑 可视化服务器已停止。")


def is_visualizer_running() -> bool:
    """检查后台服务器是否已启动"""
    return _server_started