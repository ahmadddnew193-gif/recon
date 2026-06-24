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
2.57.20.2:6983:zwgfezql:u1o2humd1hr8"""

# ==========================================
# GRAPHICS ENGINE (PURE STRING CONCATENATION)
# ==========================================

def render_live_feed_canvas(current_discovered_nodes, phase_status="SCANNING ARCHITECTURE..."):
    """Real-time active graphic component for the live search feed."""
    nodes_payload = []
    if not current_discovered_nodes:
        return
        
    for idx, node in enumerate(current_discovered_nodes):
        if isinstance(node, dict):
            node_id = str(node.get("id", node.get("userId", "0")))
            node_name = str(node.get("name", node.get("username", f"Node-{node_id}")))
            node_banned = bool(node.get("isBanned", False))
        else:
            node_id = str(node)
            node_name = f"Node-{node_id}"
            node_banned = False
            
        nodes_payload.append({
            "id": node_id,
            "name": node_name,
            "isBanned": node_banned,
            "index": idx
        })

    live_web_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body { background-color: #04060a; margin: 0; padding: 0; overflow: hidden; font-family: 'Courier New', monospace; }
            #live-canvas { display: block; border: 2px dashed #00FF66; border-radius: 6px; box-shadow: 0 0 15px rgba(0, 255, 102, 0.15); }
        </style>
    </head>
    <body>
        <canvas id="live-canvas" width="1200" height="400"></canvas>
        <script>
            const canvas = document.getElementById('live-canvas');
            const ctx = canvas.getContext('2d');
            const nodes = """ + json.dumps(nodes_payload) + """;
            const statusText = """ + json.dumps(phase_status) + """;
            
            const centerX = canvas.width / 2;
            const centerY = canvas.height / 2;

            function drawRadarGrid() {
                ctx.strokeStyle = '#061610';
                ctx.lineWidth = 1;
                
                for (let i = 0; i < 8; i++) {
                    let angle = (i / 8) * Math.PI * 2;
                    ctx.beginPath();
                    ctx.moveTo(centerX, centerY);
                    ctx.lineTo(centerX + Math.cos(angle) * 400, centerY + Math.sin(angle) * 400);
                    ctx.stroke();
                }

                let pulseRing = (Date.now() * 0.05) % 250;
                ctx.strokeStyle = 'rgba(0, 255, 102, 0.08)';
                ctx.beginPath();
                ctx.arc(centerX, centerY, pulseRing, 0, Math.PI * 2);
                ctx.stroke();

                for (let r = 50; r <= 300; r += 50) {
                    ctx.strokeStyle = '#03100a';
                    ctx.beginPath();
                    ctx.arc(centerX, centerY, r, 0, Math.PI * 2);
                    ctx.stroke();
                }
            }

            function drawLiveGraph() {
                if (nodes.length === 0) return;

                ctx.strokeStyle = 'rgba(0, 255, 102, 0.4)';
                ctx.lineWidth = 1.5;
                ctx.beginPath();
                
                let points = [];
                nodes.forEach((node, idx) => {
                    let angle = (idx / Math.max(1, nodes.length)) * Math.PI * 2;
                    let radius = 60 + (idx * 12 % 120);
                    let x = centerX + Math.cos(angle) * radius;
                    let y = centerY + Math.sin(angle) * radius;
                    points.push({x, y, ...node});
                    
                    if (idx === 0) ctx.moveTo(x, y);
                    else ctx.lineTo(x, y);
                });
                ctx.stroke();

                points.forEach((pt) => {
                    ctx.beginPath();
                    ctx.arc(pt.x, pt.y, 4, 0, Math.PI * 2);
                    ctx.fillStyle = pt.isBanned ? '#7f0000' : '#00FF66';
                    ctx.fill();

                    ctx.strokeStyle = 'rgba(0, 255, 102, 0.3)';
                    ctx.beginPath();
                    ctx.arc(pt.x, pt.y, 8 + Math.sin(Date.now()*0.01)*3, 0, Math.PI * 2);
                    ctx.stroke();

                    ctx.fillStyle = '#ffffff';
                    ctx.font = "9px 'Courier New'";
                    ctx.fillText(pt.name, pt.x + 10, pt.y - 2);
                    ctx.fillStyle = 'rgba(0, 255, 102, 0.7)';
                    ctx.fillText("IDX: " + pt.index, pt.x + 10, pt.y + 7);
                });
            }

            function render() {
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                drawRadarGrid();
                drawLiveGraph();

                ctx.fillStyle = '#00FF66';
                ctx.font = "bold 11px 'Courier New'";
                ctx.fillText("📡 LIVE DISCOVERY FEED // " + statusText.toUpperCase(), 20, 30);
                ctx.fillStyle = 'rgba(255,255,255,0.4)';
                ctx.fillText("POOL SIZE: " + nodes.length + " ACTIVE IDENTITIES TRACED", 20, 48);

                requestAnimationFrame(render);
            }
            render();
        </script>
    </body>
    </html>
    """
    st.components.v1.html(live_web_html, height=420)


def render_spider_web_path_canvas(enriched_profiles):
    """Robust visualizer for the discovered path chain using an animated Canvas spiderweb."""
    nodes_payload = []
    if not enriched_profiles:
        return
        
    for idx, node in enumerate(enriched_profiles):
        if isinstance(node, dict):
            node_id = str(node.get("id", node.get("userId", "0")))
            node_name = str(node.get("name", node.get("username", f"Node-{node_id}")))
            node_created = str(node.get("created", "Unknown"))
            node_banned = bool(node.get("isBanned", False))
        else:
            node_id = str(node)
            node_name = f"Node-{node_id}"
            node_created = "Unknown"
            node_banned = False
            
        nodes_payload.append({
            "id": node_id,
            "name": node_name,
            "created": node_created,
            "isBanned": node_banned,
            "role": "START" if idx == 0 else ("TARGET" if idx == len(enriched_profiles)-1 else f"BRIDGE-{idx}")
        })

    web_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body { background-color: #04060a; margin: 0; padding: 0; overflow: hidden; font-family: 'Courier New', monospace; }
            #web-canvas { display: block; border: 2px solid #00E5FF; border-radius: 6px; box-shadow: 0 0 20px rgba(0, 229, 255, 0.2); }
        </style>
    </head>
    <body>
        <canvas id="web-canvas" width="1200" height="500"></canvas>
        <script>
            const canvas = document.getElementById('web-canvas');
            const ctx = canvas.getContext('2d');
            const pathNodes = """ + json.dumps(nodes_payload) + """;
            
            const centerX = canvas.width / 2;
            const centerY = canvas.height / 2;
            let mappedNodes = [];

            if (pathNodes.length > 0) {
                pathNodes.forEach((node, idx) => {
                    let total = pathNodes.length;
                    let angle = (idx / total) * Math.PI * 2 - Math.PI/2;
                    let distance = 70 + (idx * (160 / Math.max(1, total - 1)));
                    if (total === 1) distance = 0;
                    
                    mappedNodes.push({
                        ...node,
                        x: centerX + Math.cos(angle) * distance,
                        y: centerY + Math.sin(angle) * distance,
                        angle: angle,
                        distance: distance
                    });
                });
            }

            let spiderProgress = 0.0;
            let currentSegment = 0;

            function drawWebBackground() {
                ctx.strokeStyle = '#121e30';
                ctx.lineWidth = 1;
                
                const spokeCount = 12;
                for (let i = 0; i < spokeCount; i++) {
                    let a = (i / spokeCount) * Math.PI * 2;
                    ctx.beginPath();
                    ctx.moveTo(centerX, centerY);
                    ctx.lineTo(centerX + Math.cos(a) * 320, centerY + Math.sin(a) * 320);
                    ctx.stroke();
                }

                ctx.strokeStyle = '#0a1424';
                for (let r = 40; r <= 280; r += 40) {
                    ctx.beginPath();
                    for (let j = 0; j <= 8; j++) {
                        let a = (j / 8) * Math.PI * 2;
                        let x = centerX + Math.cos(a) * r;
                        let y = centerY + Math.sin(a) * r;
                        if (j === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
                    }
                    ctx.closePath();
                    ctx.stroke();
                }
            }

            function drawSpiderEntity(x, y, angle) {
                ctx.save();
                ctx.translate(x, y);
                ctx.rotate(angle);
                
                ctx.fillStyle = '#00FF66';
                ctx.beginPath();
                ctx.arc(0, 0, 7, 0, Math.PI * 2); 
                ctx.arc(6, 0, 4, 0, Math.PI * 2); 
                ctx.fill();
                
                ctx.fillStyle = '#ffffff';
                ctx.fillRect(7, -2, 2, 2);
                ctx.fillRect(7, 1, 2, 2);

                ctx.strokeStyle = '#00FF66';
                ctx.lineWidth = 1.5;
                let legCycle = Math.sin(Date.now() * 0.02);
                
                for (let i = 0; i < 4; i++) {
                    let offset = (i - 1.5) * 0.4;
                    ctx.beginPath();
                    ctx.moveTo(2, -2);
                    ctx.quadraticCurveTo(-5 + (legCycle * 3), -12 + offset * 5, -12, -10 + offset * 8);
                    ctx.stroke();
                    
                    ctx.beginPath();
                    ctx.moveTo(2, 2);
                    ctx.quadraticCurveTo(-5 + (legCycle * 3), 12 + offset * 5, -12, 10 + offset * 8);
                    ctx.stroke();
                }
                ctx.restore();
            }

            function loop() {
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                drawWebBackground();

                if (mappedNodes.length === 0) return;

                ctx.strokeStyle = 'rgba(0, 229, 255, 0.65)';
                ctx.lineWidth = 2;
                ctx.beginPath();
                mappedNodes.forEach((node, idx) => {
                    if (idx === 0) ctx.moveTo(node.x, node.y);
                    else ctx.lineTo(node.x, node.y);
                });
                ctx.stroke();

                mappedNodes.forEach((node) => {
                    ctx.beginPath();
                    ctx.arc(node.x, node.y, 6, 0, Math.PI * 2);
                    
                    if (node.role === "START") ctx.fillStyle = '#00FF66';
                    else if (node.role === "TARGET") ctx.fillStyle = '#FF0055';
                    else ctx.fillStyle = '#00E5FF';
                    
                    if (node.isBanned) ctx.fillStyle = '#7f0000';
                    ctx.fill();

                    ctx.strokeStyle = '#ffffff';
                    ctx.lineWidth = 1;
                    ctx.beginPath();
                    ctx.arc(node.x, node.y, 10, 0, Math.PI * 2);
                    ctx.stroke();

                    ctx.fillStyle = '#ffffff';
                    ctx.font = "bold 10px 'Courier New'";
                    ctx.fillText("[" + node.role + "] " + node.name, node.x + 14, node.y - 3);
  
                    ctx.fillStyle = 'rgba(255,255,255,0.6)';
                    ctx.font = "9px 'Courier New'";
                    ctx.fillText("ID: " + node.id, node.x + 14, node.y + 8);
                });

                if (mappedNodes.length > 1) {
                    spiderProgress += 0.012;
                    if (spiderProgress >= 1.0) {
                        spiderProgress = 0.0;
                        currentSegment = (currentSegment + 1) % (mappedNodes.length - 1);
                    }

                    let p1 = mappedNodes[currentSegment];
                    let p2 = mappedNodes[currentSegment + 1];

                    if (p1 && p2) {
                        let spiderX = p1.x + (p2.x - p1.x) * spiderProgress;
                        let spiderY = p1.y + (p2.y - p1.y) * spiderProgress;
                        let angle = Math.atan2(p2.y - p1.y, p2.x - p1.x);
                        drawSpiderEntity(spiderX, spiderY, angle);
                    }
                }

                ctx.fillStyle = '#00E5FF';
                ctx.font = "bold 12px 'Courier New'";
                ctx.fillText("🕸️ SPIDER WEB PATH MATRIX DISCOVERY", 20, 30);

                requestAnimationFrame(loop);
            }
            loop();
        </script>
    </body>
    </html>
    """
    st.components.v1.html(web_html, height=520)

# ==========================================
# PROCESSING CORE ARCHITECTURE
# ==========================================

def init_local_cache():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS graph_cache (
            user_id TEXT PRIMARY KEY,
            connections TEXT,
            timestamp REAL
        )
    """)
    conn.commit()
    conn.close()

def fetch_cached_node(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT connections FROM graph_cache WHERE user_id = ?", (str(user_id),))
    row = cursor.fetchone()
    conn.close()
    if row:
        return json.loads(row[0])
    return None

def write_cached_node(user_id, connections):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO graph_cache (user_id, connections, timestamp) VALUES (?, ?, ?)",
        (str(user_id), json.dumps(connections), time.time())
    )
    conn.commit()
    conn.close()

async def fetch_connections_async(session, user_id, proxy_list):
    cached = fetch_cached_node(user_id)
    if cached is not None:
        return cached

    url = f"https://friends.roblox.com/v1/users/{user_id}/followers"
    proxy = random.choice(proxy_list) if proxy_list else None
    
    try:
        async with session.get(url, proxy=proxy, timeout=6) as response:
            if response.status == 200:
                data = await response.json()
                followers = [str(item["id"]) for item in data.get("data", [])]
                write_cached_node(user_id, followers)
                return followers
            elif response.status == 429:
                await asyncio.sleep(2)
    except:
        pass
    return []

async def run_path_discovery_engine(start_id, target_id, proxy_raw, live_ui_placeholder):
    proxies = [p.strip() for p in proxy_raw.split("\n") if p.strip()]
    formatted_proxies = []
    for p in proxies:
        parts = p.split(":")
        if len(parts) == 4:
            formatted_proxies.append(f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}")
        else:
            formatted_proxies.append(f"http://{p}")

    init_local_cache()
    
    forward_queue = [str(start_id)]
    backward_queue = [str(target_id)]
    
    forward_parent = {str(start_id): None}
    backward_parent = {str(target_id): None}
    
    discovered_nodes_tracker = [str(start_id), str(target_id)]
    
    async with aiohttp.ClientSession() as session:
        steps = 0
        while forward_queue and backward_queue and steps < 25:
            steps += 1
            
            # Update Active Real-time Scanning Feed UI
            with live_ui_placeholder.container():
                render_live_feed_canvas(discovered_nodes_tracker, f"SEARCHING LAYER MATRIX STEP {steps}")
            await asyncio.sleep(0.4)
            
            # Forward Layer Sweep
            curr_forward = forward_queue.pop(0)
            f_followers = await fetch_connections_async(session, curr_forward, formatted_proxies)
            
            for child in f_followers:
                if child not in forward_parent:
                    forward_parent[child] = curr_forward
                    forward_queue.append(child)
                    if child not in discovered_nodes_tracker:
                        discovered_nodes_tracker.append(child)
                    
                    if child in backward_parent:
                        return assemble_intersected_path(forward_parent, backward_parent, child)
            
            # Backward Layer Sweep
            curr_backward = backward_queue.pop(0)
            b_followers = await fetch_connections_async(session, curr_backward, formatted_proxies)
            
            for child in b_followers:
                if child not in backward_parent:
                    backward_parent[child] = curr_backward
                    backward_queue.append(child)
                    if child not in discovered_nodes_tracker:
                        discovered_nodes_tracker.append(child)
                        
                    if child in forward_parent:
                        return assemble_intersected_path(forward_parent, backward_parent, child)
                        
    return None

def assemble_intersected_path(f_parent, b_parent, intersection):
    path_start = []
    curr = intersection
    while curr is not None:
        path_start.append(curr)
        curr = f_parent[curr]
    path_start.reverse()
    
    path_end = []
    curr = b_parent[intersection]
    while curr is not None:
        path_end.append(curr)
        curr = b_parent[curr]
        
    return path_start + path_end

# ==========================================
# INTERFACE IMPLEMENTATION HOOKS
# ==========================================

st.title("Recon Engine: Ultra Core")

tab1, tab2 = st.tabs(["Active Operations", "Simulation Generator"])

with tab1:
    col1, col2 = st.columns([1, 2])
    with col1:
        start_input = st.text_input("Account Source ID:", value="1703896246")
        target_input = st.text_input("Account Target ID:", value="140671171")
        proxy_input = st.text_area("Proxy Core Matrix Allocation:", value=DEFAULT_PROXIES, height=200)
        start_engine = st.button("🚀 Initialize Intercept Request", use_container_width=True)
        
    with col2:
        live_feed_box = st.empty()
        
    if start_engine:
        if start_input and target_input:
            with st.spinner("Analyzing link matrices..."):
                discovered_chain = asyncio.run(run_path_discovery_engine(start_input, target_input, proxy_input, live_feed_box))
                
            if discovered_chain:
                st.success(f"🎯 LINK ESTABLISHED! Connection path discovered through {len(discovered_chain)} hops.")
                
                # Dynamic Type Reconstruction checks
                profile_payloads = []
                for node_id in discovered_chain:
                    profile_payloads.append({
                        "id": str(node_id),
                        "name": f"User-{node_id}",
                        "created": "Verified Cluster",
                        "isBanned": False
                    })
                    
                render_spider_web_path_canvas(profile_payloads)
                st.json(discovered_chain)
            else:
                st.error("❌ Link tracing execution timed out or no common paths were found within limits.")

with tab2:
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
            database[str(uid)] = [random.choice(filler_ids) for _ in range(random.randint(1, 3))]
            
        init_local_cache()
        for k, v in database.items():
            write_cached_node(k, v)
            
        st.success(f"Successfully loaded simulated array with {profile_volume} entities into local database cluster cache.")
