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
        return max(10, 200 - len(g_cache[str_node]))
    if node_id < 200000000: return 300
    if node_id < 1000000000: return 500
    if node_id > 4000000000: return 1500
    return 1000

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS graph (user_id TEXT PRIMARY KEY, friends_list TEXT)")
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
            st.sidebar.error(f"⚠️ Cloud Load Skipped: {str(e)}")
    memory_cache = {}
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, friends_list FROM graph")
        for row in cursor.fetchall():
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
    if not HF_TOKEN or not HF_REPO_ID: return False, "Configuration credentials missing."
    sync_entire_memory_to_sqlite()
    if not os.path.exists(DB_FILE): return False, "Target database absent."
    try:
        api = HfApi()
        api.upload_file(path_or_fileobj=DB_FILE, path_in_repo=DB_FILE, repo_id=HF_REPO_ID, repo_type="dataset", token=HF_TOKEN, commit_message="Incremental cloud database commit")
        return True, "Success"
    except Exception as e: return False, str(e)

async def upload_cache_to_cloud_async():
    if "cloud_lock" not in st.session_state: st.session_state.cloud_lock = asyncio.Lock()
    async with st.session_state.cloud_lock:
        await asyncio.to_thread(upload_cache_to_cloud_blocking)

if "global_cache" not in st.session_state: st.session_state.global_cache = load_persistent_cache()
if "logs" not in st.session_state: st.session_state.logs = []
if "running" not in st.session_state: st.session_state.running = False
if "harvester_running" not in st.session_state: st.session_state.harvester_running = False
if "seeder_running" not in st.session_state: st.session_state.seeder_running = False
if "final_enriched_path" not in st.session_state: st.session_state.final_enriched_path = None


# --- UPDATED GRAPHICS: EARTH-42 RADIOACTIVE SPIDER CRAWL VISUALIZERS ---

def render_live_crawler_spider_canvas(recent_nodes, buffer_size, total_scraped, active_status="ACTIVE"):
    payload_nodes = [str(n) for n in recent_nodes]
    canvas_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ background-color: #04060a; margin: 0; padding: 0; overflow: hidden; font-family: 'Courier New', monospace; }}
            #spider-canvas {{ display: block; background: #030508; border: 2px solid #FF0055; border-radius: 6px; box-shadow: 0 0 20px rgba(255, 0, 85, 0.3); }}
        </style>
    </head>
    <body>
        <canvas id="spider-canvas" width="1200" height="300"></canvas>
        <script>
            const canvas = document.getElementById('spider-canvas');
            const ctx = canvas.getContext('2d');
            const recentNodes = {json.dumps(payload_nodes)};
            const bufferSize = {buffer_size};
            const totalScraped = {total_scraped};
            const engineStatus = "{active_status}";
            
            let radarAngle = 0;
            const coreX = canvas.width / 2;
            const coreY = canvas.height / 2;
            let visualNodes = [];

            recentNodes.forEach((nodeId, index) => {{
                let angle = (index / Math.max(1, recentNodes.length)) * Math.PI * 2 + (Date.now() * 0.00005);
                let distance = 100 + (index * 20) % 120;
                visualNodes.push({{ id: nodeId, x: coreX + Math.cos(angle) * distance, y: coreY + Math.sin(angle) * distance }});
            }});

            function drawEarth42Spider(ctx, cx, cy, angle, tick, isMoving) {{
                ctx.save();
                ctx.translate(cx, cy);
                ctx.rotate(angle);
                
                // Chromatic Glitch Aberration
                if (Math.random() < 0.12) {{
                    ctx.translate((Math.random() - 0.5) * 3, (Math.random() - 0.5) * 3);
                }}

                let neonGreen = "#00FF66";
                let spiderPink = "#FF0055";
                let spiderPurple = "#D300C5";

                // ABDOMEN (Pixel Art Style)
                ctx.fillStyle = spiderPink;
                ctx.fillRect(-10, 2, 20, 22);
                ctx.fillStyle = "#04060a";
                ctx.fillRect(-8, 4, 16, 18);

                // Earth-42 Logo Stamp
                ctx.fillStyle = neonGreen;
                ctx.font = "bold 10px monospace";
                ctx.textAlign = "center";
                ctx.textBaseline = "middle";
                ctx.fillText("42", 0, 13);

                // CEPHALOTHORAX (Head)
                ctx.fillStyle = neonGreen;
                ctx.fillRect(-6, -7, 12, 9);
                
                // Multiple Glowing Glowing Eyes
                ctx.fillStyle = "#FFFFFF";
                ctx.fillRect(-4, -6, 2, 2);
                ctx.fillRect(2, -6, 2, 2);
                ctx.fillStyle = spiderPurple;
                ctx.fillRect(-2, -4, 1, 1);
                ctx.fillRect(1, -4, 1, 1);

                // Articulated Bending Legs (Moving with walk-cycle algorithm)
                let wave = Math.sin(tick * (isMoving ? 0.09 : 0.03));
                ctx.lineWidth = 2.5;

                for (let i = 0; i < 4; i++) {{
                    let phase = i * 0.6;
                    let moveOffset = Math.sin(tick * 0.05 + phase) * 6;

                    // Left Legs Joint Calculations
                    ctx.strokeStyle = (i % 2 === 0) ? neonGreen : spiderPink;
                    ctx.beginPath();
                    ctx.moveTo(-5, -4 + (i * 4));
                    let lx1 = -22 - (i * 3) + moveOffset;
                    let ly1 = -16 + (i * 10) - moveOffset * 0.5;
                    let lx2 = -36 - (i * 4);
                    let ly2 = -4 + (i * 12);
                    ctx.lineTo(lx1, ly1);
                    ctx.lineTo(lx2, ly2);
                    ctx.stroke();

                    // Right Legs Joint Calculations
                    ctx.beginPath();
                    ctx.moveTo(5, -4 + (i * 4));
                    let rx1 = 22 + (i * 3) - moveOffset;
                    let ry1 = -16 + (i * 10) + moveOffset * 0.5;
                    let rx2 = 36 + (i * 4);
                    let ry2 = -4 + (i * 12);
                    ctx.lineTo(rx1, ry1);
                    ctx.lineTo(rx2, ry2);
                    ctx.stroke();
                }}
                ctx.restore();
            }}

            function loop() {{
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                
                // Matrix Grid Lines
                ctx.strokeStyle = '#070d14';
                ctx.lineWidth = 1;
                for(let x=0; x<canvas.width; x+=40) {{
                    ctx.beginPath(); ctx.moveTo(x,0); ctx.lineTo(x,canvas.height); ctx.stroke();
                }}
                for(let y=0; y<canvas.height; y+=40) {{
                    ctx.beginPath(); ctx.moveTo(0,y); ctx.lineTo(canvas.width,y); ctx.stroke();
                }}

                let tick = Date.now();

                // Cyber Radioactive Silk Web Infrastructure
                visualNodes.forEach((node) => {{
                    ctx.strokeStyle = (Math.random() < 0.05) ? 'rgba(255, 0, 85, 0.4)' : 'rgba(0, 255, 102, 0.15)';
                    ctx.lineWidth = 1.5;
                    ctx.beginPath(); 
                    ctx.moveTo(coreX, coreY); 
                    ctx.lineTo(node.x, node.y); 
                    ctx.stroke();
                    
                    ctx.fillStyle = '#00E5FF';
                    ctx.fillRect(node.x - 4, node.y - 4, 8, 8);
                }});

                // Dynamic Radar Sweep
                radarAngle += 0.02;
                let rx = coreX + Math.cos(radarAngle)*500;
                let ry = coreY + Math.sin(radarAngle)*500;
                let grad = ctx.createLinearGradient(coreX, coreY, rx, ry);
                grad.addColorStop(0, 'rgba(211, 0, 197, 0.25)');
                grad.addColorStop(1, 'rgba(0,0,0,0)');
                ctx.strokeStyle = grad; ctx.lineWidth = 3;
                ctx.beginPath(); ctx.moveTo(coreX, coreY); ctx.lineTo(rx, ry); ctx.stroke();

                // Render the Living Spider
                drawEarth42Spider(ctx, coreX, coreY, tick * 0.0004, tick, true);

                // Interface Terminal Data Overlay
                ctx.fillStyle = '#00FF66'; ctx.font = "bold 12px 'Courier New'";
                ctx.fillText("📡 ALCHEMEX SWARM MONITOR: [" + engineStatus + "]", 20, 30);
                ctx.fillStyle = '#00E5FF';
                ctx.fillText("📦 NODE DATA: " + totalScraped + " CACHED | ⚡ PIPELINE BUFFER: " + bufferSize + " TARGETS", 20, 50);
                requestAnimationFrame(loop);
            }}
            loop();
        </script>
    </body>
    </html>
    """
    st.components.v1.html(canvas_html, height=315, scrolling=False)


def render_spider_web_path_canvas(enriched_profiles):
    nodes_payload = []
    for idx, node in enumerate(enriched_profiles):
        nodes_payload.append({
            "id": str(node["id"]),
            "name": str(node["name"]),
            "created": str(node["created"]),
            "isBanned": bool(node["isBanned"]),
            "role": "START" if idx == 0 else ("TARGET" if idx == len(enriched_profiles)-1 else f"BRIDGE-{idx}")
        })

    web_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ background-color: #04060a; margin: 0; padding: 0; overflow: hidden; font-family: 'Courier New', monospace; }}
            #web-canvas {{ display: block; border: 2px solid #00E5FF; border-radius: 6px; box-shadow: 0 0 25px rgba(0, 229, 255, 0.2); }}
        </style>
    </head>
    <body>
        <canvas id="web-canvas" width="1200" height="500"></canvas>
        <script>
            const canvas = document.getElementById('web-canvas');
            const ctx = canvas.getContext('2d');

            const pathNodes = {json.dumps(nodes_payload)};
            const centerX = canvas.width / 2;
            const centerY = canvas.height / 2;
            let mappedNodes = [];
            
            if (pathNodes.length > 0) {{
                pathNodes.forEach((node, idx) => {{
                    let total = pathNodes.length;
                    let angle = (idx / total) * Math.PI * 2 - Math.PI/2;
                    let distance = 80 + (idx * (160 / Math.max(1, total - 1)));
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

            let spiderProgress = 0.0;
            let currentSegment = 0;

            function drawWebBackground() {{
                ctx.strokeStyle = 'rgba(211, 0, 197, 0.08)';
                ctx.lineWidth = 1;
                const spokes = 16;
                for (let i = 0; i < spokes; i++) {{
                    let a = (i / spokes) * Math.PI * 2;
                    ctx.beginPath(); ctx.moveTo(centerX, centerY);
                    ctx.lineTo(centerX + Math.cos(a) * 500, centerY + Math.sin(a) * 500);
                    ctx.stroke();
                }}
                for (let r = 60; r <= 360; r += 60) {{
                    ctx.strokeStyle = 'rgba(0, 229, 255, 0.04)';
                    ctx.beginPath();
                    for (let j = 0; j <= spokes; j++) {{
                        let a = (j / spokes) * Math.PI * 2;
                        let x = centerX + Math.cos(a) * r; let y = centerY + Math.sin(a) * r;
                        if (j === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
                    }}
                    ctx.closePath(); ctx.stroke();
                }}
            }}

            function drawEarth42Spider(ctx, cx, cy, angle, tick, isMoving) {{
                ctx.save();
                ctx.translate(cx, cy);
                ctx.rotate(angle);
                
                if (Math.random() < 0.1) {{
                    ctx.translate((Math.random() - 0.5) * 2, (Math.random() - 0.5) * 2);
                }}

                let neonGreen = "#00FF66";
                let spiderPink = "#FF0055";
                let spiderPurple = "#D300C5";

                // ABDOMEN
                ctx.fillStyle = spiderPink;
                ctx.fillRect(-8, 2, 16, 18);
                ctx.fillStyle = "#04060a";
                ctx.fillRect(-6, 4, 12, 14);

                // 42 Logo
                ctx.fillStyle = neonGreen;
                ctx.font = "bold 8px monospace";
                ctx.textAlign = "center";
                ctx.textBaseline = "middle";
                ctx.fillText("42", 0, 11);

                // HEAD
                ctx.fillStyle = neonGreen;
                ctx.fillRect(-5, -6, 10, 8);
                
                ctx.fillStyle = "#FFFFFF";
                ctx.fillRect(-3, -5, 1.5, 1.5);
                ctx.fillRect(1.5, -5, 1.5, 1.5);

                // Moving legs cycle
                let wave = Math.sin(tick * (isMoving ? 0.15 : 0.03));
                ctx.lineWidth = 2;

                for (let i = 0; i < 4; i++) {{
                    let phase = i * 0.5;
                    let legFactor = Math.sin(tick * 0.1 + phase) * 5;

                    ctx.strokeStyle = (i % 2 === 0) ? neonGreen : spiderPink;
                    
                    // Left leg bend
                    ctx.beginPath();
                    ctx.moveTo(-4, -3 + (i * 3.5));
                    ctx.lineTo(-18 - (i * 2) + legFactor, -12 + (i * 8) - legFactor * 0.5);
                    ctx.lineTo(-30 - (i * 3), -2 + (i * 10));
                    ctx.stroke();

                    // Right leg bend
                    ctx.beginPath();
                    ctx.moveTo(4, -3 + (i * 3.5));
                    ctx.lineTo(18 + (i * 2) - legFactor, -12 + (i * 8) + legFactor * 0.5);
                    ctx.lineTo(30 + (i * 3), -2 + (i * 10));
                    ctx.stroke();
                }}
                ctx.restore();
            }}

            function loop() {{
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                drawWebBackground();

                // Draw Path Connection Links
                if (mappedNodes.length > 1) {{
                    ctx.strokeStyle = '#FF0055'; ctx.lineWidth = 3;
                    ctx.beginPath();
                    mappedNodes.forEach((node, idx) => {{
                        if (idx === 0) ctx.moveTo(node.x, node.y);
                        else ctx.lineTo(node.x, node.y);
                    }});
                    ctx.stroke();
                }}

                // Draw User Identity Blueprint Nodes
                mappedNodes.forEach((node) => {{
                    ctx.fillStyle = '#050a12';
                    ctx.fillRect(node.x - 25, node.y - 15, 50, 30);

                    if (node.isBanned) ctx.strokeStyle = '#FF0055';
                    else if (node.role === 'START') ctx.strokeStyle = '#00FF66';
                    else if (node.role === 'TARGET') ctx.strokeStyle = '#00E5FF';
                    else ctx.strokeStyle = '#D300C5';
                    
                    ctx.lineWidth = 2;
                    ctx.strokeRect(node.x - 25, node.y - 15, 50, 30);

                    ctx.fillStyle = '#FFFFFF'; ctx.font = "8px 'Courier New'"; ctx.textAlign = "center";
                    ctx.fillText(node.name.substring(0, 8), node.x, node.y - 2);
                    ctx.fillStyle = 'rgba(0, 229, 255, 0.7)';
                    ctx.fillText(node.id.substring(0, 7), node.x, node.y + 8);
                }});

                // Animate Spider along Node Trace Routes
                if (mappedNodes.length > 1) {{
                    spiderProgress += 0.01;
                    if (spiderProgress >= 1.0) {{
                        spiderProgress = 0.0;
                        currentSegment = (currentSegment + 1) % (mappedNodes.length - 1);
                    }}
                    let p1 = mappedNodes[currentSegment];
                    let p2 = mappedNodes[currentSegment + 1];
                    if (p1 && p2) {{
                        let sx = p1.x + (p2.x - p1.x) * spiderProgress;
                        let sy = p1.y + (p2.y - p1.y) * spiderProgress;
                        let angle = Math.atan2(p2.y - p1.y, p2.x - p1.x);
                        drawEarth42Spider(ctx, sx, sy, angle - Math.PI/2, Date.now(), true);
                    }}
                }}

                ctx.fillStyle = '#FF0055'; ctx.font = "bold 12px 'Courier New'";
                ctx.fillText("🕸️ DIMENSIONAL EARTH-42 TRACEWAY MATRIX NETWORK DISCOVERY", 20, 30);
                requestAnimationFrame(loop);
            }}
            loop();
        </script>
    </body>
    </html>
    """
    st.components.v1.html(web_html, height=515, scrolling=False)

# --- BACKEND PIPELINE WORKFLOW LOGIC (UNTOUCHED) ---

async def proxy_worker_task(worker_id, pool_manager, network_queue, cache_queue, start_visited, target_visited, path_found_event, results_container, session):
    g_cache = st.session_state.global_cache
    while not path_found_event.is_set() and st.session_state.running:
        try:
            priority, item = network_queue.get_nowait()
        except asyncio.QueueEmpty:
            await asyncio.sleep(0.05)
            continue
        direction, node = item
        str_node = str(node)
        proxy = pool_manager.get_healthy_proxy()
        if not proxy:
            await asyncio.sleep(0.5)
            network_queue.put_nowait((priority, item))
            continue
        friends_url = f"https://friends.roblox.com/v1/users/{node}/friends"
        try:
            async with session.get(friends_url, proxy=proxy, timeout=6) as resp:
                results_container["total_api_calls"] += 1
                if resp.status == 200:
                    pool_manager.report_status(proxy, 200)
                    data = await resp.json()
                    friends_list = [f["id"] for f in data.get("data", [])]
                    g_cache[str_node] = friends_list
                    save_single_profile_to_db(str_node, friends_list)
                    results_container["uncommitted_records"] += 1
                    current_path = start_visited.get(node) if direction == "FORWARD" else target_visited.get(node)
                    if not current_path or len(current_path) >= 5: continue
                    for friend in friends_list:
                        friend_int = int(friend)
                        if direction == "FORWARD":
                            if friend_int in target_visited:
                                results_container["final_chain"] = current_path + target_visited[friend_int][::-1]
                                path_found_event.set()
                                break
                            if friend_int not in start_visited:
                                start_visited[friend_int] = current_path + [friend_int]
                                f_score = calculate_node_priority(friend_int, g_cache)
                                cache_queue.put_nowait((f_score, ("FORWARD", friend_int)))
                        else:
                            if friend_int in start_visited:
                                results_container["final_chain"] = start_visited[friend_int] + current_path[::-1]
                                path_found_event.set()
                                break
                            if friend_int not in target_visited:
                                target_visited[friend_int] = current_path + [friend_int]
                                f_score = calculate_node_priority(friend_int, g_cache)
                                cache_queue.put_nowait((f_score, ("REVERSE", friend_int)))
                elif resp.status == 429:
                    pool_manager.report_status(proxy, 429)
                    network_queue.put_nowait((priority + 50, item))
                else:
                    pool_manager.report_status(proxy, resp.status)
                    network_queue.put_nowait((priority + 20, item))
        except Exception:
            pool_manager.report_status(proxy, 500)
            network_queue.put_nowait((priority + 20, item))

async def execute_group_intersection_scan(session, s_id, t_id, pool_manager):
    s_groups = await fetch_user_groups_async(session, s_id, pool_manager)
    t_groups = await fetch_user_groups_async(session, t_id, pool_manager)
    if s_groups and t_groups:
        shared_ids = set(s_groups.keys()).intersection(set(t_groups.keys()))
        if shared_ids:
            msg = f"🎯 Shared Roblox Group Intersections Detected ({len(shared_ids)} links):\n"
            for gid in shared_ids: msg += f" • [ID: {gid}] {s_groups[gid]}\n"
            group_placeholder.warning(msg)
            return
    group_placeholder.info("ℹ️ No immediate target intersection discovered in layer-1 groups.")

async def fetch_user_groups_async(session, user_id, pool_manager):
    url = f"https://groups.roblox.com/v2/users/{user_id}/groups/roles"
    proxy = pool_manager.get_healthy_proxy()
    try:
        async with session.get(url, proxy=proxy, timeout=5) as resp:
            if resp.status == 200:
                data = await resp.json()
                return {g["group"]["id"]: g["group"]["name"] for g in data.get("data", [])}
    except Exception: pass
    return {}

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
    path_found_event = asyncio.Event()
    results_container = {"final_chain": None, "total_api_calls": 0, "cache_hits": 0, "uncommitted_records": 0}
    g_cache = st.session_state.global_cache
    
    if str(s_id) in g_cache: cache_queue.put_nowait((0, ("FORWARD", s_id)))
    else: network_queue.put_nowait((0, ("FORWARD", s_id)))
    if str(t_id) in g_cache: cache_queue.put_nowait((0, ("REVERSE", t_id)))
    else: network_queue.put_nowait((0, ("REVERSE", t_id)))
        
    engine_status.info("🚀 Bi-Directional Graph Swarm Engine Ignited...")
    async with aiohttp.ClientSession() as session:
        asyncio.create_task(execute_group_intersection_scan(session, s_id, t_id, pool_manager))
        workers = [asyncio.create_task(proxy_worker_task(i, pool_manager, network_queue, cache_queue, start_visited, target_visited, path_found_event, results_container, session)) for i in range(12)]
        recent_nodes_buffer = []
        
        while not path_found_event.is_set() and st.session_state.running:
            while not cache_queue.empty() and not path_found_event.is_set():
                try: priority, (direction, node) = cache_queue.get_nowait()
                except asyncio.QueueEmpty: break
                recent_nodes_buffer.append(node)
                if len(recent_nodes_buffer) > 15: recent_nodes_buffer.pop(0)
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
            
            h, c, d = pool_manager.get_pool_diagnostics()
            engine_metrics_banner.markdown(f"**Swarm Diagnostics:** Healthy Proxies: `{h}` | Cooldown: `{c}` | Dead: `{d}` | Cache Hits: `{results_container['cache_hits']}` | API Requests: `{results_container['total_api_calls']}`")
            with live_canvas_wrapper:
                render_live_crawler_spider_canvas(recent_nodes_buffer, network_queue.qsize() + cache_queue.qsize(), len(g_cache), "SEARCHING")
            await asyncio.sleep(0.4)
            
        st.session_state.running = False
        path_found_event.set()
        await asyncio.gather(*workers, return_exceptions=True)
        
        if results_container["final_chain"]:
            engine_status.success(f"🎯 CHAIN DETECTED IN SOCIAL MOVEMENT GRAPH: {results_container['final_chain']}")
            enriched_profiles = []
            for uid in results_container["final_chain"]:
                p_intel = await fetch_profile_intel_async(session, uid, pool_manager)
                enriched_profiles.append(p_intel)
            st.session_state.final_enriched_path = enriched_profiles
            await upload_cache_to_cloud_async()
            st.rerun()
        else:
            engine_status.error("❌ Scan complete. No linkage trace remains between items.")

# --- SIDEBAR CONTROL PANEL ---
with st.sidebar:
    st.header("⚙️ Global Control Array")
    proxy_input = st.text_area("🌐 Proxy Configuration String (IP:Port:User:Pass):", value=DEFAULT_PROXIES, height=240)
    st.subheader("☁️ HuggingFace Dataset Syncer")
    if st.button("📤 Forces Cloud Commit Now", use_container_width=True):
        with st.spinner("Pushing local SQLite layer to cloud dataset repository..."):
            ok, response = upload_cache_to_cloud_blocking()
            if ok: st.sidebar.success("Database uploaded successfully!")
            else: st.sidebar.error(f"Sync Aborted: {response}")
    st.markdown("---")
    st.info(f"📁 Local Cache Layer Volume: `{len(st.session_state.global_cache)}` Roblox social records.")

# --- APPLICATION WINDOW TAB DIRECTORY ---
tab1, tab2, tab3 = st.tabs(["🚀 Engine Framework", "🌍 Real-World Harvester", "📦 Backbone Seeder"])

with tab1:
    st.title("🎯 Bidirectional Path Engine")
    ec1, ec2 = st.columns(2)
    with ec1: s_id_input = st.text_input("Source Node User ID:", "1703896246")
    with ec2: t_id_input = st.text_input("Target Node User ID:", "140671171")
    btn_col1, btn_col2 = st.columns(2)
    with btn_col1:
        start_engine_btn = st.button("⚡ Ignite Bi-Directional Swarm", use_container_width=True, type="primary")
    with btn_col2:
        stop_engine_btn = st.button("🛑 Force Stop Engine", use_container_width=True)
        if stop_engine_btn:
            st.session_state.running = False
            st.rerun()
            
    engine_status = st.empty()
    group_placeholder = st.empty()
    engine_metrics_banner = st.empty()
    live_canvas_wrapper = st.empty()
    
    if st.session_state.final_enriched_path:
        st.subheader("🕸️ Active Linked Sequence Traversal Visualizer")
        render_spider_web_path_canvas(st.session_state.final_enriched_path)
        st.subheader("📋 Enriched Sequence Profile Data Frame")
        st.dataframe(pd.DataFrame(st.session_state.final_enriched_path), use_container_width=True)
        
    if start_engine_btn and s_id_input.isdigit() and t_id_input.isdigit():
        pool_mgr = ProxyPool(proxy_input)
        if pool_mgr.proxies:
            st.session_state.final_enriched_path = None
            st.session_state.running = True
            st.session_state.harvester_running = False
            st.session_state.seeder_running = False
            asyncio.run(master_pipeline_engine(int(s_id_input), int(t_id_input), pool_mgr))
        else: st.error("No valid proxies detected in global config array.")

with tab2:
    st.title("🌍 Real-World Social Graph Harvester")
    hc1, hc2 = st.columns(2)
    with hc1: seed_id_input = st.text_input("Harvester Seed User ID:", "1703896246", key="harvest_seed")
    with hc2: max_harvest = st.number_input("Max Users to Scrape:", min_value=100, max_value=100000, value=2000, key="harvest_max")
    hbtn1, hbtn2 = st.columns(2)
    with hbtn1: start_harvest_btn = st.button("⚡ Ignite Crawler", use_container_width=True, type="primary", key="harvest_start")
    with hbtn2: stop_harvest_btn = st.button("🛑 Stop Harvester", use_container_width=True, key="harvest_stop")
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
            if str_user in g_cache: friends = g_cache[str_user]
            else:
                friends_url = f"https://friends.roblox.com/v1/users/{user_id}/friends"
                try:
                    async with session.get(friends_url, proxy=proxy, timeout=6) as resp:
                        shared_stats["total_api_calls"] += 1
                        if resp.status == 200:
                            pool_manager.report_status(proxy, 200)
                            data = await resp.json()
                            friends = [f["id"] for f in data.get("data", [])]
                            g_cache[str_user] = friends
                            save_single_profile_to_db(str_user, friends)
                            shared_stats["scraped_count"] += 1
                        elif resp.status == 429:
                            pool_manager.report_status(proxy, 429)
                            harvest_queue.put_nowait(user_id)
                            await asyncio.sleep(1.0)
                            continue
                        else:
                            pool_manager.report_status(proxy, resp.status)
                            harvest_queue.put_nowait(user_id)
                            continue
                except Exception:
                    pool_manager.report_status(proxy, 500)
                    harvest_queue.put_nowait(user_id)
                    continue
            for f in friends:
                if str(f) not in g_cache: harvest_queue.put_nowait(f)

    async def master_harvester_coordinator(seed_uid, max_profiles, pool_manager):
        harvest_queue = asyncio.Queue()
        harvest_queue.put_nowait(seed_uid)
        shared_stats = {"scraped_count": 0, "limit": max_profiles, "total_api_calls": 0, "uncommitted_records": 0}
        async with aiohttp.ClientSession() as session:
            workers = [asyncio.create_task(harvester_spider_worker(idx+1, pool_manager, harvest_queue, shared_stats, session)) for idx in range(6)]
            while st.session_state.harvester_running and shared_stats["scraped_count"] < max_profiles:
                h, c, d = pool_manager.get_pool_diagnostics()
                harvest_status.success(f"🚀 Crawler Active |\nH:{h} C:{c} D:{d} | Profiles Scraped: {shared_stats['scraped_count']} / {max_profiles}")
                harvest_console.code(f"Queue Size: {harvest_queue.qsize()} targets waiting.", language="bash")
                await asyncio.sleep(1.0)
            st.session_state.harvester_running = False
            await asyncio.gather(*workers, return_exceptions=True)
            await upload_cache_to_cloud_async()

    if start_harvest_btn and seed_id_input.isdigit():
        pool_mgr = ProxyPool(proxy_input)
        if pool_mgr.proxies:
            st.session_state.running = False
            st.session_state.harvester_running = True
            st.session_state.seeder_running = False
            st.rerun()

    if st.session_state.harvester_running:
        pool_mgr = ProxyPool(proxy_input)
        asyncio.run(master_harvester_coordinator(int(seed_id_input), int(max_harvest), pool_mgr))

with tab3:
    st.subheader("📦 Roblox Backbone Seeder & Tools")
    seed_start = st.text_input("Simulate Start ID:", value="1703896246")
    seed_target = st.text_input("Simulate Target ID:", value="140671171")
    profile_volume = st.number_input("Background Density Nodes:", min_value=100, max_value=50000, value=1500)
    generate_btn = st.button("⚡ Execute Mock Seeding", use_container_width=True)
    
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
            database[str(uid)] = [random.choice(filler_ids) for _ in range(random.randint(2, 5))]
            
        st.session_state.global_cache.update(database)
        sync_entire_memory_to_sqlite()
        st.success(f"Successfully seeded `{profile_volume}+5` paths into database memory!")
