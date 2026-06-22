import streamlit as st
import asyncio
import aiohttp
import json
import os
import sqlite3
import random
import time
import pandas as pd
from huggingface_hub import HfApi, hf_hub_download

st.set_page_config(page_title="Recon Engine: Ultra Core", layout="wide")

DB_FILE = "roblox_graph_map.db"
HF_TOKEN = st.secrets.get("HF_TOKEN")
HF_REPO_ID = st.secrets.get("HF_REPO_ID")

# Preserving all 20 proxy configurations
DEFAULT_PROXIES = """38.154.203.95:5863:zwgfezql:u1o2humd1hr8
198.105.121.200:6462:zwgfezql:u1o2humd1hr8
64.137.96.74:6641:zwgfezql:u1o2humd1hr8
209.127.138.10:5784:zwgfezql:u1o2humd1hr8
38.154.185.97:6370:zwgfezql:u1o2humd1hr8
84.247.60.125:6095:zwgfezql:u1o2humd1hr8
142.111.67.146:5611:zwgfezql:u1o2humd1hr8
191.96.254.138:6185:zwgfezql:u1o2humd1hr8
23.229.19.94:8689:zwgfezql:u1o2humd1hr8
2.57.20.2:6983:zwgfezql:u1o2humd1hr8
31.59.20.176:6754:qquvrrms:c36jtmb5ca0w
31.56.127.193:7684:qquvrrms:c36jtmb5ca0w
45.38.107.97:6014:qquvrrms:c36jtmb5ca0w
38.154.203.95:5863:qquvrrms:c36jtmb5ca0w
198.105.121.200:6462:qquvrrms:c36jtmb5ca0w
64.137.96.74:6641:qquvrrms:c36jtmb5ca0w
198.23.243.226:6361:qquvrrms:c36jtmb5ca0w
38.154.185.97:6370:qquvrrms:c36jtmb5ca0w
142.111.67.146:5611:qquvrrms:c36jtmb5ca0w
191.96.254.138:6185:qquvrrms:c36jtmb5ca0w"""

# --- ADVANCED PROXY POOL HEALTH MANAGER ---
class ProxyPool:
    def __init__(self, raw_proxy_strings):
        self.proxies = self._parse_proxies(raw_proxy_strings)
        self.registry = {p: {"status": "HEALTHY", "cool_down_until": 0, "failures": 0} for p in self.proxies}
        
    def _parse_proxies(self, text):
        lines = text.split("\n")
        cleaned = []
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("http://") or line.startswith("https://"):
                cleaned.append(line)
            elif line.count(":") == 3:
                parts = line.split(":")
                cleaned.append(f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}")
        return cleaned

    def get_healthy_proxy(self):
        now = time.time()
        available = []
        for p, meta in self.registry.items():
            if meta["status"] == "DEAD":
                continue
            if meta["status"] == "COOL_DOWN":
                if now >= meta["cool_down_until"]:
                    meta["status"] = "HEALTHY"
                    meta["failures"] = 0
                else:
                    continue
            available.append(p)
        if not available:
            return None
        return random.choice(available)

    def report_status(self, proxy, status_code):
        if proxy not in self.registry:
            return
        now = time.time()
        if status_code == 200:
            self.registry[proxy]["status"] = "HEALTHY"
            self.registry[proxy]["failures"] = 0
        elif status_code == 429:
            self.registry[proxy]["status"] = "COOL_DOWN"
            self.registry[proxy]["cool_down_until"] = now + 60.0
        else:
            self.registry[proxy]["failures"] += 1
            if self.registry[proxy]["failures"] >= 4:
                self.registry[proxy]["status"] = "DEAD"
            else:
                self.registry[proxy]["status"] = "COOL_DOWN"
                self.registry[proxy]["cool_down_until"] = now + 15.0

    def get_pool_diagnostics(self):
        healthy = sum(1 for p in self.registry.values() if p["status"] == "HEALTHY")
        cooling = sum(1 for p in self.registry.values() if p["status"] == "COOL_DOWN")
        dead = sum(1 for p in self.registry.values() if p["status"] == "DEAD")
        return healthy, cooling, dead


def calculate_node_priority(node_id, g_cache):
    str_node = str(node_id)
    if str_node in g_cache:
        friend_count = len(g_cache[str_node])
        return max(10, 200 - friend_count)
    if node_id < 200000000: return 300
    if node_id < 1000000000: return 500
    if node_id > 4000000000: return 1500
    return 1000


# --- SQLITE DATABASE INTEGRITY INFRASTRUCTURE ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS graph (
            user_id TEXT PRIMARY KEY,
            friends_list TEXT
        )
    """)
    conn.commit()
    conn.close()

def load_persistent_cache():
    init_db()
    if HF_TOKEN and HF_REPO_ID:
        try:
            resolved_path = hf_hub_download(repo_id=HF_REPO_ID, filename=DB_FILE, repo_type="dataset", token=HF_TOKEN)
            if os.path.exists(resolved_path):
                with open(resolved_path, "rb") as f_src:
                    with open(DB_FILE, "wb") as f_dst:
                        f_dst.write(f_src.read())
        except Exception as e:
            st.sidebar.error(f"⚠️ Initial Cloud Load Skipped: {str(e)}")
    memory_cache = {}
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, friends_list FROM graph")
        rows = cursor.fetchall()
        for row in rows:
            memory_cache[str(row[0])] = json.loads(row[1])
        conn.close()
    except Exception: pass
    return memory_cache

def save_single_profile_to_db(user_id, friends_list):
    try:
        conn = sqlite3.connect(DB_FILE, timeout=60.0)
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO graph (user_id, friends_list) VALUES (?, ?)", (str(user_id), json.dumps(friends_list)))
        conn.commit()
        conn.close()
    except Exception: pass

def sync_entire_memory_to_sqlite():
    try:
        conn = sqlite3.connect(DB_FILE, timeout=60.0)
        cursor = conn.cursor()
        cursor.execute("BEGIN TRANSACTION")
        for uid, friends in st.session_state.global_cache.items():
            cursor.execute("INSERT OR REPLACE INTO graph (user_id, friends_list) VALUES (?, ?)", (str(uid), json.dumps(friends)))
        conn.commit()
        conn.close()
    except Exception: pass

def upload_cache_to_cloud_blocking():
    if not HF_TOKEN or not HF_REPO_ID: return False, "Configuration credentials missing or invalid."
    sync_entire_memory_to_sqlite()
    if not os.path.exists(DB_FILE): return False, "Target database file absent."
    try:
        api = HfApi()
        api.upload_file(path_or_fileobj=DB_FILE, path_in_repo=DB_FILE, repo_id=HF_REPO_ID, repo_type="dataset", token=HF_TOKEN, commit_message="Automated incremental asynchronous cloud database commit")
        return True, "Success"
    except Exception as e: return False, str(e)

async def upload_cache_to_cloud_async():
    if "cloud_lock" not in st.session_state: st.session_state.cloud_lock = asyncio.Lock()
    async with st.session_state.cloud_lock:
        success, diagnostics = await asyncio.to_thread(upload_cache_to_cloud_blocking)
        if not success: st.session_state.logs.append(f"[CLOUD-WARN] Backup delayed: {diagnostics}")
        return success, diagnostics


if "global_cache" not in st.session_state: st.session_state.global_cache = load_persistent_cache()
if "logs" not in st.session_state: st.session_state.logs = []
if "running" not in st.session_state: st.session_state.running = False
if "harvester_running" not in st.session_state: st.session_state.harvester_running = False
if "seeder_running" not in st.session_state: st.session_state.seeder_running = False


# --- HIGH QUALITY LIVE SPIDER RADAR FEED ---
def render_live_crawler_spider_canvas(recent_nodes, buffer_size, total_scraped, active_status="ACTIVE"):
    payload_nodes = [str(n) for n in recent_nodes]
    canvas_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ background-color: #05070f; margin: 0; padding: 0; overflow: hidden; font-family: 'Courier New', monospace; }}
            #spider-canvas {{ display: block; background: #05070f; border: 2px solid #00FF66; border-radius: 6px; box-shadow: 0 0 15px rgba(0, 255, 102, 0.15); }}
        </style>
    </head>
    <body>
        <canvas id="spider-canvas" width="1200" height="300"></canvas>
        <script>
            const canvas = document.getElementById('spider-canvas');
            const ctx = canvas.getContext('2d');
            ctx.imageSmoothingEnabled = false;

            const recentNodes = {json.dumps(payload_nodes)};
            const bufferSize = {buffer_size};
            const totalScraped = {total_scraped};
            const engineStatus = "{active_status}";

            let radarAngle = 0;
            const coreX = canvas.width / 2;
            const coreY = canvas.height / 2;
            let visualNodes = [];

            recentNodes.forEach((nodeId, index) => {{
                let angle = (index / Math.max(1, recentNodes.length)) * Math.PI * 2 + (Date.now() * 0.0001);
                let distance = 90 + (index * 20) % 80;
                visualNodes.push({{ id: nodeId, x: coreX + Math.cos(angle) * distance, y: coreY + Math.sin(angle) * distance, size: 8, pulse: Math.random() * Math.PI }});
            }});

            function loop() {{
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                
                // Draw background radial grid rows to establish spider web visual anchors
                ctx.strokeStyle = '#0d151f';
                ctx.lineWidth = 1;
                for(let r = 40; r < 300; r += 40) {{
                    ctx.beginPath(); ctx.arc(coreX, coreY, r, 0, Math.PI*2); ctx.stroke();
                }}

                radarAngle += 0.02;
                ctx.strokeStyle = 'rgba(0, 255, 102, 0.08)';
                ctx.beginPath(); ctx.moveTo(coreX, coreY);
                ctx.lineTo(coreX + Math.cos(radarAngle)*600, coreY + Math.sin(radarAngle)*600);
                ctx.stroke();

                visualNodes.forEach((node) => {{
                    node.pulse += 0.05;
                    ctx.strokeStyle = 'rgba(0, 229, 255, 0.4)';
                    ctx.lineWidth = 1;
                    ctx.setLineDash([2, 4]);
                    ctx.beginPath(); ctx.moveTo(coreX, coreY); ctx.lineTo(node.x, node.y); ctx.stroke();
                    ctx.setLineDash([]);

                    ctx.fillStyle = '#00E5FF';
                    ctx.fillRect(node.x - 4, node.y - 4, 8, 8);
                    ctx.fillStyle = '#ffffff';
                    ctx.font = "9px 'Courier New'";
                    ctx.fillText("ID:" + node.id, node.x - 25, node.y + 12);
                }});

                ctx.fillStyle = '#00FF66';
                ctx.fillRect(coreX - 8, coreY - 8, 16, 16);
                ctx.strokeStyle = '#00FF66';
                ctx.strokeRect(coreX - 12, coreY - 12, 24, 24);

                ctx.fillStyle = '#00FF66';
                ctx.font = "bold 11px 'Courier New'";
                ctx.fillText("📡 SWARM MONITOR: [" + engineStatus + "]", 20, 25);
                ctx.fillStyle = '#00E5FF';
                ctx.fillText("📦 CAPTURED: " + totalScraped + " PROFILES | ⚡ BUFFER: " + bufferSize + " TARGETS", 20, 45);
                requestAnimationFrame(loop);
            }}
            loop();
        </script>
    </body>
    </html>
    """
    st.components.v1.html(canvas_html, height=315, scrolling=False)


# --- DYNAMIC CYBER SPIDER WEB PATH VISUALIZER ---
def render_spider_web_path_canvas(enriched_profiles):
    """
    Transforms sequential user connection steps into a multi-tiered tactical 
    cyber spider web canvas. No box shapes. Displays nodes distributed along web layers, 
    with a visual digital spider entity actively crawling through nodes.
    """
    nodes_payload = []
    for idx, node in enumerate(enriched_profiles):
        nodes_payload.append({
            "id": str(node["id"]),
            "name": str(node["name"]),
            "created": str(node["created"]),
            "isBanned": bool(node["isBanned"]),
            "role": "START" if idx == 0 else ("TARGET" if idx == len(enriched_profiles)-1 else f"BRIDGE-{idx}")
        })

    # FIXED: Doubled curly braces inside JS template literals to prevent Python parsing errors
    web_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ background-color: #04060a; margin: 0; padding: 0; overflow: hidden; font-family: 'Courier New', monospace; }}
            #web-canvas {{ display: block; border: 2px solid #00E5FF; border-radius: 6px; box-shadow: 0 0 20px rgba(0, 229, 255, 0.2); }}
        </style>
    </head>
    <body>
        <canvas id="web-canvas" width="1200" height="450"></canvas>
        <script>
            const canvas = document.getElementById('web-canvas');
            const ctx = canvas.getContext('2d');
            ctx.imageSmoothingEnabled = false;

            const pathNodes = {json.dumps(nodes_payload)};
            const centerX = canvas.width / 2;
            const centerY = canvas.height / 2;

            // Mathematical generation mapping positions across a physical spider web spiral matrix
            let mappedNodes = [];
            if (pathNodes.length > 0) {{
                pathNodes.forEach((node, idx) => {{
                    // Evenly distribute spokes radiantly, changing distance layer outwards
                    let total = pathNodes.length;
                    let angle = (idx / total) * Math.PI * 2 - Math.PI/2;
                    let distance = 60 + (idx * (140 / Math.max(1, total - 1)));
                    if (total === 1) distance = 0;
                    
                    mappedNodes.push({{
                        ...node,
                        x: centerX + Math.cos(angle) * distance,
                        y: centerY + Math.sin(angle) * distance,
                        angle: angle,
                        distance: distance
                    }});
                }});
            }}

            // Parameters for tracking the position of the crawling tracking pulse
            let spiderProgress = 0.0;
            let currentSegment = 0;

            function drawWebStructure() {{
                // Draw background radial support web strands
                ctx.strokeStyle = '#101b2b';
                ctx.lineWidth = 1;
                
                // 1. Structural spokes lines radiating from common nexus core
                for (let a = 0; a < Math.PI * 2; a += Math.PI / 4) {{
                    ctx.beginPath(); ctx.moveTo(centerX, centerY);
                    ctx.lineTo(centerX + Math.cos(a)*300, centerY + Math.sin(a)*300);
                    ctx.stroke();
                }}

                // 2. Concentric polygonal ring layers
                for (let r = 50; r <= 250; r += 50) {{
                    ctx.beginPath();
                    for (let i = 0; i <= 8; i++) {{
                        let a = (i / 8) * Math.PI * 2;
                        let x = centerX + Math.cos(a) * r;
                        let y = centerY + Math.sin(a) * r;
                        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
                    }}
                    ctx.closePath(); ctx.stroke();
                }}
            }}

            function loop() {{
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                drawWebStructure();

                if (mappedNodes.length === 0) return;

                // Connect paths sequencially with neon green threads
                ctx.strokeStyle = 'rgba(0, 255, 102, 0.75)';
                ctx.lineWidth = 2;
                ctx.beginPath();
                mappedNodes.forEach((node, idx) => {{
                    if (idx === 0) ctx.moveTo(node.x, node.y);
                    else ctx.lineTo(node.x, node.y);
                }});
                ctx.stroke();

                // Draw Web Intersections (Nodes) as circular vector points
                mappedNodes.forEach((node, idx) => {{
                    ctx.beginPath();
                    ctx.arc(node.x, node.y, 7, 0, Math.PI * 2);
                    
                    if (node.role === "START") ctx.fillStyle = '#00FF66';
                    else if (node.role === "TARGET") ctx.fillStyle = '#FF0055';
                    else ctx.fillStyle = '#00E5FF';
                    
                    if (node.isBanned) ctx.fillStyle = '#7f0000';
                    ctx.fill();

                    // Node Outer Rings
                    ctx.strokeStyle = '#ffffff';
                    ctx.lineWidth = 1.5;
                    ctx.beginPath(); ctx.arc(node.x, node.y, 11, 0, Math.PI*2); ctx.stroke();

                    // Text parameters info boxes
                    ctx.fillStyle = '#ffffff';
                    ctx.font = "bold 10px 'Courier New'";
                    ctx.fillText(`[${{node.role}}] ${{node.name}}`, node.x + 15, node.y - 4);
                    ctx.fillStyle = 'rgba(255,255,255,0.6)';
                    ctx.font = "9px 'Courier New'";
                    ctx.fillText(`ID: ${{node.id}}`, node.x + 15, node.y + 7);
                    if(node.isBanned) {{
                        ctx.fillStyle = '#FF0055';
                        ctx.fillText("🚫 BANNED", node.x + 15, node.y + 18);
                    }}
                }});

                // ANIMATION LOOP: Glowing Tracker Pulse Crawling Across the Web
                if (mappedNodes.length > 1) {{
                    spiderProgress += 0.015;
                    if (spiderProgress >= 1.0) {{
                        spiderProgress = 0.0;
                        currentSegment = (currentSegment + 1) % (mappedNodes.length - 1);
                    }}

                    let p1 = mappedNodes[currentSegment];
                    let p2 = mappedNodes[currentSegment + 1];

                    if (p1 && p2) {{
                        let spiderX = p1.x + (p2.x - p1.x) * spiderProgress;
                        let spiderY = p1.y + (p2.y - p1.y) * spiderProgress;

                        // Draw animated tracing node spider graphic
                        ctx.fillStyle = '#00FF66';
                        ctx.beginPath();
                        ctx.arc(spiderX, spiderY, 6, 0, Math.PI * 2);
                        ctx.fill();

                        ctx.strokeStyle = '#00FF66';
                        ctx.lineWidth = 1;
                        ctx.beginPath(); ctx.arc(spiderX, spiderY, 14 + Math.sin(Date.now()*0.01)*4, 0, Math.PI * 2); ctx.stroke();
                    }}
                }}

                ctx.fillStyle = '#00E5FF';
                ctx.font = "bold 12px 'Courier New'";
                ctx.fillText("🕸️ SPIDER PATH MATRIX LAYER GRAPH", 20, 30);

                requestAnimationFrame(loop);
            }}
            loop();
        </script>
    </body>
    </html>
    """
    st.components.v1.html(web_html, height=465, scrolling=False)


with st.sidebar:
    st.header("⚙️ Global Control Array")
    proxy_input = st.text_area("🌐 Active Webshare Proxies:", value=DEFAULT_PROXIES, height=220)
    st.markdown("---")
    st.metric("Roblox Profiles In Sync DB", len(st.session_state.global_cache))
    
    st.markdown("### ☁️ Cloud Sync Status")
    if HF_TOKEN and HF_REPO_ID:
        st.caption(f"Linked Repo: `{HF_REPO_ID}`")
        if st.button("🔄 Force Push DB to Cloud", use_container_width=True):
            success, error_msg = upload_cache_to_cloud_blocking()
            if success: st.toast("Database backed up successfully!", icon="🚀")
            else: st.error(f"💥 Transfer Dropped: {error_msg}")
    else: st.warning("⚠️ Running in Local-Only Mode.")

tab1, tab2, tab3 = st.tabs(["🚀 Graph Path Tracer & Swarm Feed", "🌍 Real Mass Harvester", "📦 Roblox Backbone Seeder & Tools"])

# ==========================================
# TAB 1: INTEGRATED CORE PIPELINE ENGINE (FIXED PLACEHOLDERS)
# ==========================================
with tab1:
    st.subheader("Dual-Queue Target Analysis Execution (Informed Best-First Engine)")
    
    c1, c2 = st.columns(2)
    with c1: s_input = st.text_input("Start Profile ID:", "1703896246")
    with c2: t_input = st.text_input("Target Profile ID:", "140671171")
        
    btn_col1, btn_col2 = st.columns(2)
    with btn_col1: start_btn = st.button("🚀 Ignite Pipeline Swarm", use_container_width=True, type="primary")
    with btn_col2: stop_btn = st.button("🛑 Kill Pipeline Tasks", use_container_width=True)
        
    if stop_btn:
        st.session_state.running = False
        st.rerun()

    # Dynamic thread-isolated execution placeholders bound to Tab 1
    status_placeholder = st.empty()
    console_placeholder = st.empty()
    group_placeholder = st.empty()
    
    st.markdown("### 📡 Live Feed Discovery Monitor")
    live_feed_placeholder = st.empty()
    
    st.markdown("### 🕸️ Visual Network Web Results")
    graph_placeholder = st.empty()

    # Initial static placeholders state definitions
    live_feed_placeholder.markdown("*(Engine Idle - Launch swarm pipeline to stream metrics data)*")
    graph_placeholder.markdown("*(No active cross-path mapping processed yet)*")

# Background thread logging assistant mapping
def print_thread_safe_log(msg):
    st.session_state.logs.append(msg)
    if len(st.session_state.logs) > 12: st.session_state.logs.pop(0)
    console_placeholder.code("\n".join(st.session_state.logs), language="bash")

async def cache_processor_task(network_queue, cache_queue, start_visited, target_visited, path_found_event, results_container):
    g_cache = st.session_state.global_cache
    while not path_found_event.is_set() and st.session_state.running:
        try: score, (direction, node) = cache_queue.get_nowait()
        except asyncio.QueueEmpty:
            await asyncio.sleep(0.002)
            continue
            
        str_node = str(node)
        friends = g_cache.get(str_node, [])
        results_container["cache_hits"] += 1
        
        current_path = start_visited.get(node) if direction == "FORWARD" else target_visited.get(node)
        if not current_path or len(current_path) >= 5: continue
            
        for friend in friends:
            friend_int = int(friend)
            if direction == "FORWARD":
                if friend_int in target_visited:
                    results_container["final_chain"] = current_path + target_visited[friend_int][::-1]
                    path_found_event.set()
                    break
                if friend_int not in start_visited:
                    start_visited[friend_int] = current_path + [friend_int]
                    f_score = calculate_node_priority(friend_int, g_cache)
                    if str(friend_int) in g_cache: cache_queue.put_nowait((f_score, ("FORWARD", friend_int)))
                    else: network_queue.put_nowait((f_score, ("FORWARD", friend_int)))
            else:
                if friend_int in start_visited:
                    results_container["final_chain"] = start_visited[friend_int] + current_path[::-1]
                    path_found_event.set()
                    break
                if friend_int not in target_visited:
                    target_visited[friend_int] = current_path + [friend_int]
                    f_score = calculate_node_priority(friend_int, g_cache)
                    if str(friend_int) in g_cache: cache_queue.put_nowait((f_score, ("REVERSE", friend_int)))
                    else: network_queue.put_nowait((f_score, ("REVERSE", friend_int)))

async def proxy_worker_task(worker_id, pool_manager, network_queue, cache_queue, start_visited, target_visited, session, path_found_event, results_container):
    g_cache = st.session_state.global_cache
    
    while not path_found_event.is_set() and st.session_state.running:
        proxy = pool_manager.get_healthy_proxy()
        if not proxy:
            await asyncio.sleep(1.5)
            continue
            
        try: score, (direction, node) = network_queue.get_nowait()
        except asyncio.QueueEmpty:
            await asyncio.sleep(0.02)
            continue
            
        str_node = str(node)
        if str_node in g_cache:
            results_container["cache_hits"] += 1
            f_score = calculate_node_priority(node, g_cache)
            cache_queue.put_nowait((f_score, (direction, node)))
            continue
            
        current_path = start_visited.get(node) if direction == "FORWARD" else target_visited.get(node)
        if not current_path or len(current_path) >= 5: continue
            
        url = f"https://friends.roblox.com/v1/users/{node}/friends"
        try:
            async with session.get(url, proxy=proxy, timeout=5) as response:
                results_container["api_calls"] += 1
                pool_manager.report_status(proxy, response.status)
                
                if response.status == 200:
                    data = await response.json()
                    friends = [int(f["id"]) for f in data.get("data", []) if not f.get("isDeleted", False)]
                    
                    g_cache[str_node] = friends
                    save_single_profile_to_db(str_node, friends)
                    results_container["new_discoveries"][str_node] = friends
                    
                    # Store tracking profile arrays for live feed pipeline metrics
                    results_container["rolling_window"].append(node)
                    if len(results_container["rolling_window"]) > 7:
                        results_container["rolling_window"].pop(0)
                    
                    for friend in friends:
                        f_score = calculate_node_priority(friend, g_cache)
                        if direction == "FORWARD":
                            if friend in target_visited:
                                results_container["final_chain"] = current_path + target_visited[friend][::-1]
                                path_found_event.set()
                                break
                            if friend not in start_visited:
                                start_visited[friend] = current_path + [friend]
                                if str(friend) in g_cache: cache_queue.put_nowait((f_score, ("FORWARD", friend)))
                                else: network_queue.put_nowait((f_score, ("FORWARD", friend)))
                        else:
                            if friend in start_visited:
                                results_container["final_chain"] = start_visited[friend] + current_path[::-1]
                                path_found_event.set()
                                break
                            if friend not in target_visited:
                                target_visited[friend] = current_path + [friend]
                                if str(friend) in g_cache: cache_queue.put_nowait((f_score, ("REVERSE", friend)))
                                else: network_queue.put_nowait((f_score, ("REVERSE", friend)))
                    await asyncio.sleep(0.05)
                else:
                    network_queue.put_nowait((score, (direction, node)))
        except Exception:
            pool_manager.report_status(proxy, 0)
            network_queue.put_nowait((score, (direction, node)))

async def fetch_user_groups_async(session, user_id, pool_manager):
    url = f"https://groups.roblox.com/v1/users/{user_id}/groups/roles"
    proxy = pool_manager.get_healthy_proxy()
    try:
        async with session.get(url, proxy=proxy, timeout=5) as response:
            if response.status == 200:
                data = await response.json()
                return {g["group"]["id"]: g["group"]["name"] for g in data.get("data", [])}
    except Exception: pass
    return {}

async def execute_group_intersection_scan(session, s_id, t_id, pool_manager):
    s_groups, t_groups = await asyncio.gather(
        fetch_user_groups_async(session, s_id, pool_manager),
        fetch_user_groups_async(session, t_id, pool_manager)
    )
    if s_groups and t_groups:
        shared_ids = set(s_groups.keys()).intersection(set(t_groups.keys()))
        if shared_ids:
            msg = f"🎯 Shared Roblox Group Intersections Detected ({len(shared_ids)} links):\n"
            for gid in shared_ids: msg += f" • [ID: {gid}] {s_groups[gid]}\n"
            group_placeholder.warning(msg)
            return
    group_placeholder.info("ℹ️ No immediate target intersection discovered in layer-1 groups.")

async def fetch_profile_intel_async(session, user_id, pool_manager):
    user_url = f"https://users.roblox.com/v1/users/{user_id}"
    proxy = pool_manager.get_healthy_proxy()
    try:
        async with session.get(user_url, proxy=proxy, timeout=5) as resp:
            if resp.status == 200:
                data = await resp.json()
                return {"id": user_id, "name": data.get("name", f"UID:{user_id}"), "created": data.get("created", "Unknown")[:10], "isBanned": data.get("isBanned", False)}
    except Exception: pass
    return {"id": user_id, "name": f"UID:{user_id}", "created": "Unknown", "isBanned": False}

async def master_pipeline_engine(s_id, t_id, pool_manager):
    network_queue = asyncio.PriorityQueue()
    cache_queue = asyncio.PriorityQueue()
    start_visited = {s_id: [s_id]}
    target_visited = {t_id: [t_id]}
    
    g_cache = st.session_state.global_cache
    s_score = calculate_node_priority(s_id, g_cache)
    t_score = calculate_node_priority(t_id, g_cache)
    
    if str(s_id) in g_cache: cache_queue.put_nowait((s_score, ("FORWARD", s_id)))
    else: network_queue.put_nowait((s_score, ("FORWARD", s_id)))
    if str(t_id) in g_cache: cache_queue.put_nowait((t_score, ("REVERSE", t_id)))
    else: network_queue.put_nowait((t_score, ("REVERSE", t_id)))
        
    path_found_event = asyncio.Event()
    results_container = {"final_chain": [], "api_calls": 0, "cache_hits": 0, "new_discoveries": {}, "rolling_window": []}

    print_thread_safe_log("[SYSTEM] Re-routing swarm arrays to Thread-Safe placeholders...")

    async with aiohttp.ClientSession() as session:
        asyncio.create_task(execute_group_intersection_scan(session, s_id, t_id, pool_manager))
        
        workers = [asyncio.create_task(cache_processor_task(network_queue, cache_queue, start_visited, target_visited, path_found_event, results_container))]
        for idx in range(8):
            workers.append(asyncio.create_task(proxy_worker_task(idx + 1, pool_manager, network_queue, cache_queue, start_visited, target_visited, session, path_found_event, results_container)))

        while not path_found_event.is_set() and st.session_state.running:
            h, c, d = pool_manager.get_pool_diagnostics()
            q_total = network_queue.qsize() + cache_queue.qsize()
            
            status_placeholder.info(f"🟢 Active Proxies: {h} | 🟡 Cool Down: {c} | 🔴 Dead Pool: {d} | ⚡ Cache Hits: {results_container['cache_hits']} | Outbound Net: {results_container['api_calls']}")
            
            with live_feed_placeholder:
                render_live_crawler_spider_canvas(results_container["rolling_window"], q_total, results_container["cache_hits"] + results_container["api_calls"], active_status="SWARMING")
            await asyncio.sleep(0.2)

        path_found_event.set()
        await asyncio.gather(*workers, return_exceptions=True)

        if results_container["new_discoveries"]:
            await upload_cache_to_cloud_async()

        if results_container["final_chain"]:
            clean_chain = []
            for u in results_container["final_chain"]:
                if not clean_chain or clean_chain[-1] != u: clean_chain.append(u)
                
            print_thread_safe_log(f"[SUCCESS] Linked path connection chain matrix: {clean_chain}")
            intel_tasks = [fetch_profile_intel_async(session, uid, pool_manager) for uid in clean_chain]
            enriched_profiles = await asyncio.gather(*intel_tasks)
            
            with graph_placeholder:
                render_spider_web_path_canvas(enriched_profiles)
        else:
            print_thread_safe_log("[SYSTEM] Processing complete. No link uncovered between targets.")
            graph_placeholder.error("❌ Deep network scan yielded no relational bridge paths.")
        
        st.session_state.running = False

if start_btn and s_input.isdigit() and t_input.isdigit():
    pool_mgr = ProxyPool(proxy_input)
    if pool_mgr.proxies:
        st.session_state.running = True
        st.session_state.harvester_running = False
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(master_pipeline_engine(int(s_input), int(t_input), pool_mgr))
        st.rerun()


# ==========================================
# TAB 2: REAL ROBLOX CRAWLER HARVESTER
# ==========================================
with tab2:
    st.subheader("🌍 Continuous Real-World Social Graph Harvester")
    st.write("Drives automated background harvesting across healthy proxy pipelines.")
    
    hc1, hc2 = st.columns(2)
    with hc1: seed_id_input = st.text_input("Harvester Seed User ID (Start Node):", "1703896246", key="harvest_seed")
    with hc2: max_harvest = st.number_input("Max Users to Scrape Before Auto-Stop:", min_value=100, max_value=100000, value=2000, step=500, key="harvest_max")
        
    hbtn1, hbtn2 = st.columns(2)
    with hbtn1: start_harvest_btn = st.button("⚡ Ignite High-Speed Crawler", use_container_width=True, type="primary", key="harvest_start")
    with hbtn2: stop_harvest_btn = st.button("🛑 Force Stop Harvester", use_container_width=True, key="harvest_stop")
        
    if stop_harvest_btn:
        st.session_state.harvester_running = False
        st.rerun()
        
    harvest_console = st.empty()
    harvest_status = st.empty()

async def harvester_spider_worker(worker_id, pool_manager, harvest_queue, shared_stats, session):
    g_cache = st.session_state.global_cache
    while st.session_state.harvester_running and shared_stats["scraped_count"] < shared_stats["limit"]:
        proxy = pool_manager.get_healthy_proxy()
        if not proxy:
            await asyncio.sleep(2.0)
            continue
        try: user_id = harvest_queue.get_nowait()
        except asyncio.QueueEmpty:
            await asyncio.sleep(0.05)
            continue
            
        str_user = str(user_id)
        if str_user in g_cache:
            for friend in g_cache[str_user]:
                if len(g_cache) < 500000: harvest_queue.put_nowait(friend)
            continue
            
        url = f"https://friends.roblox.com/v1/users/{user_id}/friends"
        try:
            async with session.get(url, proxy=proxy, timeout=5) as response:
                shared_stats["total_api_calls"] += 1
                pool_manager.report_status(proxy, response.status)
                if response.status == 200:
                    data = await response.json()
                    friends = [int(f["id"]) for f in data.get("data", []) if not f.get("isDeleted", False)]
                    
                    g_cache[str_user] = friends
                    save_single_profile_to_db(str_user, friends)
                    
                    shared_stats["scraped_count"] += 1
                    shared_stats["uncommitted_records"] += 1
                    
                    if shared_stats["uncommitted_records"] >= 50:
                        shared_stats["uncommitted_records"] = 0
                        asyncio.create_task(upload_cache_to_cloud_async())
                        
                    for friend in friends:
                        if str(friend) not in g_cache: harvest_queue.put_nowait(friend)
                    await asyncio.sleep(0.1)
                else: harvest_queue.put_nowait(user_id)
        except Exception:
            pool_manager.report_status(proxy, 0)
            harvest_queue.put_nowait(user_id)

async def master_harvester_coordinator(seed_uid, max_profiles, pool_manager):
    harvest_queue = asyncio.Queue()
    harvest_queue.put_nowait(seed_uid)
    shared_stats = {"scraped_count": 0, "limit": max_profiles, "total_api_calls": 0, "uncommitted_records": 0}
    
    async with aiohttp.ClientSession() as session:
        workers = [asyncio.create_task(harvester_spider_worker(idx+1, pool_manager, harvest_queue, shared_stats, session)) for idx in range(6)]
        while st.session_state.harvester_running and shared_stats["scraped_count"] < max_profiles:
            h, c, d = pool_manager.get_pool_diagnostics()
            harvest_status.success(f"🚀 Background Crawl Active | Live Channels: H:{h} C:{c} D:{d} | Profiles Scraped: {shared_stats['scraped_count']} / {max_profiles}")
            harvest_console.code(f"Queue Discovery Buffer Size: {harvest_queue.qsize()} targets waiting.", language="bash")
            await asyncio.sleep(1.0)
            
        st.session_state.harvester_running = False
        await asyncio.gather(*workers, return_exceptions=True)
        await upload_cache_to_cloud_async()

if start_harvest_btn and seed_id_input.isdigit():
    pool_mgr = ProxyPool(proxy_input)
    if pool_mgr.proxies:
        st.session_state.running = False 
        st.session_state.harvester_running = True
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(master_harvester_coordinator(int(seed_id_input), int(max_harvest), pool_mgr))
        st.rerun()


# ==========================================
# TAB 3: ROBLOX BACKBONE SEEDER
# ==========================================
with tab3:
    st.subheader("¼ Live Advanced 2-Layer Backbone Hub Cultivator")
    
    famous_hubs = {
        "Builderman (UID: 1)": 1,
        "Roblox Official (UID: 18)": 18,
        "Shedletsky (UID: 261)": 261,
        "Asimo3089 - Jailbreak (UID: 12551)": 12551,
        "Linkmon99 - Trader (UID: 472911)": 472911,
        "Merely - Limiteds (UID: 2032622)": 2032622
    }
    
    selected_hubs = st.multiselect("Select Core Roblox Hubs to Map:", list(famous_hubs.keys()), default=list(famous_hubs.keys())[:3])
    custom_seed_list = st.text_input("Append Extra Custom Roblox Hub UIDs:", key="seeder_custom")
    max_layer2_nodes = st.number_input("Max Layer-2 Profiles to Swarm:", min_value=10, max_value=2000, value=250, step=50, key="seeder_max")
        
    s_col1, s_col2 = st.columns(2)
    with s_col1: ignite_seed = st.button("🔥 Ignite 2-Layer Backbone Swarm", use_container_width=True, type="primary", key="seeder_start")
    with s_col2: kill_seed = st.button("🛑 Force Stop Seeder Swarm", use_container_width=True, key="seeder_stop")
        
    if kill_seed:
        st.session_state.seeder_running = False
        st.rerun()
        
    seeder_status = st.empty()
    seeder_console = st.empty()

    async def seed_worker_pipeline(uid, pool_manager, session, shared_metrics):
        g_cache = st.session_state.global_cache
        str_uid = str(uid)
        if str_uid in g_cache: return g_cache[str_uid]
            
        proxy = pool_manager.get_healthy_proxy()
        if not proxy: return []
        
        url = f"https://friends.roblox.com/v1/users/{uid}/friends"
        try:
            async with session.get(url, proxy=proxy, timeout=6) as resp:
                shared_metrics["api_calls"] += 1
                pool_manager.report_status(proxy, resp.status)
                if resp.status == 200:
                    data = await resp.json()
                    friends = [int(f["id"]) for f in data.get("data", []) if not f.get("isDeleted", False)]
                    g_cache[str_uid] = friends
                    save_single_profile_to_db(str_uid, friends)
                    shared_metrics["saved_nodes"] += 1
                    return friends
        except Exception: pool_manager.report_status(proxy, 0)
        return []

    async def run_deep_hub_seeder(primary_uids, pool_manager, max_l2):
        shared_metrics = {"api_calls": 0, "saved_nodes": 0, "current_target": "Initializing"}
        g_cache = st.session_state.global_cache
        
        async with aiohttp.ClientSession() as session:
            layer2_queue = []
            for uid in primary_uids:
                if not st.session_state.seeder_running: break
                friends = await seed_worker_pipeline(uid, pool_manager, session, shared_metrics)
                layer2_queue.extend(friends)
                await asyncio.sleep(0.2)
                
            layer2_queue = list(set([uid for uid in layer2_queue if str(uid) not in g_cache]))
            random.shuffle(layer2_queue)
            layer2_targets = layer2_queue[:max_l2]
            
            for idx, l2_uid in enumerate(layer2_targets):
                if not st.session_state.seeder_running: break
                h, c, d = pool_manager.get_pool_diagnostics()
                seeder_status.info(f"⚡ Swarm Working | Channels: H:{h} C:{c} D:{d} | Cached: {shared_metrics['saved_nodes']}")
                seeder_console.code(f"Vector [{idx + 1}/{len(layer2_targets)}]: UID {l2_uid}", language="bash")
                
                await seed_worker_pipeline(l2_uid, pool_manager, session, shared_metrics)
                await asyncio.sleep(0.1)
                if shared_metrics["saved_nodes"] % 25 == 0: await upload_cache_to_cloud_async()
                    
            await upload_cache_to_cloud_async()
            st.session_state.seeder_running = False

    if ignite_seed:
        target_uids = [famous_hubs[name] for name in selected_hubs]
        if custom_seed_list.strip():
            for c_id in custom_seed_list.split(","):
                if c_id.strip().isdigit(): target_uids.append(int(c_id.strip()))
        pool_mgr = ProxyPool(proxy_input)
        if target_uids and pool_mgr.proxies:
            st.session_state.seeder_running = True
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(run_deep_hub_seeder(target_uids, pool_mgr, int(max_layer2_nodes)))
            st.rerun()

    # --- SIMULATED DATA UTILITY ---
    st.markdown("---")
    st.subheader("📦 Fake Local Data Mock-Generator")
    seed_start = st.text_input("Simulate Start ID Entry:", value="1703896246", key="mock_s")
    seed_target = st.text_input("Simulate Target ID Entry:", value="140671171", key="mock_t")
    profile_volume = st.number_input("Background Density Nodes:", min_value=100, max_value=50000, value=5000, step=500, key="mock_vol")
    generate_btn = st.button("⚡ Execute Mock Seeding", use_container_width=True, key="mock_gen")
    
    if generate_btn and seed_start.isdigit() and seed_target.isdigit():
        database = {}
        s_id_int, t_id_int = int(seed_start), int(seed_target)
        hub_a, hub_b, hub_c = 999101, 999102, 999103
        database[str(s_id_int)] = [hub_a]
        database[str(hub_a)] = [s_id_int, hub_b]
        database[str(hub_b)] = [hub_a, hub_c]
        database[str(hub_c)] = [hub_b, t_id_int]
        database[str(t_id_int)] = [hub_c]
        
        filler_ids = [random.randint(2000000, 8000000) for _ in range(int(profile_volume))]
        for uid in filler_ids:
            str_uid = str(uid)
            if str_uid not in database: database[str_uid] = []
            database[str_uid].extend(random.sample(filler_ids, k=min(random.randint(15, 40), len(filler_ids))))
            
        database[str(s_id_int)].extend(random.sample(filler_ids, k=20))
        database[str(hub_a)].extend(random.sample(filler_ids, k=25))
        database[str(hub_b)].extend(random.sample(filler_ids, k=25))
        database[str(hub_c)].extend(random.sample(filler_ids, k=25))
        database[str(t_id_int)].extend(random.sample(filler_ids, k=20))
        
        for key in database: database[key] = list(set([int(x) for x in database[key] if int(x) != int(key)]))
        st.session_state.global_cache = database
        upload_cache_to_cloud_blocking()
        st.success("✅ Mock Database Seeded!")
        st.rerun()
