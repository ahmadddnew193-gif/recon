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

# Merged proxy list from user uploads
DEFAULT_PROXIES = """31.59.20.176:6754:qquvrrms:c36jtmb5ca0w
31.56.127.193:7684:qquvrrms:c36jtmb5ca0w
45.38.107.97:6014:qquvrrms:c36jtmb5ca0w
38.154.203.95:5863:qquvrrms:c36jtmb5ca0w
198.105.121.200:6462:qquvrrms:c36jtmb5ca0w
64.137.96.74:6641:qquvrrms:c36jtmb5ca0w
198.23.243.226:6361:qquvrrms:c36jtmb5ca0w
38.154.185.97:6370:qquvrrms:c36jtmb5ca0w
142.111.67.146:5611:qquvrrms:c36jtmb5ca0w
191.96.254.138:6185:qquvrrms:c36jtmb5ca0w
38.154.203.95:5863:zwgfezql:u1o2humd1hr8
198.105.121.200:6462:zwgfezql:u1o2humd1hr8
64.137.96.74:6641:zwgfezql:u1o2humd1hr8
209.127.138.10:5784:zwgfezql:u1o2humd1hr8
38.154.185.97:6370:zwgfezql:u1o2humd1hr8
84.247.60.125:6095:zwgfezql:u1o2humd1hr8
142.111.67.146:5611:zwgfezql:u1o2humd1hr8
191.96.254.138:6185:zwgfezql:u1o2humd1hr8
23.229.19.94:8689:zwgfezql:u1o2humd1hr8
2.57.20.2:6983:zwgfezql:u1o2humd1hr8"""

class ProxyPool:
    def __init__(self, raw_proxy_strings):
        self.proxies = self._parse_proxies(raw_proxy_strings)
        self.registry = {p: {"status": "HEALTHY", "cool_down_until": 0, "failures": 0} for p in self.proxies}
        
    def _parse_proxies(self, text):
        lines = text.split("\n")
        cleaned = []
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"): continue
            if line.count(":") == 3:
                parts = line.split(":")
                cleaned.append(f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}")
        return cleaned

    def get_healthy_proxy(self):
        now = time.time()
        available = [p for p, meta in self.registry.items() 
                     if meta["status"] == "HEALTHY" or (meta["status"] == "COOL_DOWN" and now >= meta["cool_down_until"])]
        if not available: return None
        return random.choice(available)

    def report_status(self, proxy, status_code):
        if proxy not in self.registry: return
        now = time.time()
        if status_code == 200:
            self.registry[proxy]["status"] = "HEALTHY"
            self.registry[proxy]["failures"] = 0
        elif status_code == 429:
            self.registry[proxy]["status"] = "COOL_DOWN"
            self.registry[proxy]["cool_down_until"] = now + 60.0
        else:
            self.registry[proxy]["failures"] += 1
            if self.registry[proxy]["failures"] >= 4: self.registry[proxy]["status"] = "DEAD"
            else:
                self.registry[proxy]["status"] = "COOL_DOWN"
                self.registry[proxy]["cool_down_until"] = now + 15.0

    def get_pool_diagnostics(self):
        healthy = sum(1 for p in self.registry.values() if p["status"] == "HEALTHY")
        cooling = sum(1 for p in self.registry.values() if p["status"] == "COOL_DOWN")
        dead = sum(1 for p in self.registry.values() if p["status"] == "DEAD")
        return healthy, cooling, dead

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS graph (user_id TEXT PRIMARY KEY, friends_list TEXT)")
    conn.commit()
    conn.close()

def load_persistent_cache():
    init_db()
    memory_cache = {}
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, friends_list FROM graph")
        for row in cursor.fetchall(): memory_cache[str(row[0])] = json.loads(row[1])
        conn.close()
    except: pass
    return memory_cache

def save_single_profile_to_db(user_id, friends_list):
    try:
        conn = sqlite3.connect(DB_FILE, timeout=60.0)
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO graph (user_id, friends_list) VALUES (?, ?)", (str(user_id), json.dumps(friends_list)))
        conn.commit()
        conn.close()
    except: pass

if "global_cache" not in st.session_state: st.session_state.global_cache = load_persistent_cache()
if "logs" not in st.session_state: st.session_state.logs = []
if "running" not in st.session_state: st.session_state.running = False
if "final_enriched_path" not in st.session_state: st.session_state.final_enriched_path = None

# --- VISUALIZERS ---
def render_spider_web_path_canvas(enriched_profiles):
    nodes_json = json.dumps([
        {"id": str(n["id"]), "name": str(n["name"]), "isBanned": bool(n["isBanned"])} 
        for n in enriched_profiles
    ])
    
    web_html = f"""
    <!DOCTYPE html>
    <html>
    <body style="margin:0; background:#04060a; overflow:hidden;">
        <canvas id="web-canvas" width="800" height="400"></canvas>
        <script>
            const canvas = document.getElementById('web-canvas');
            const ctx = canvas.getContext('2d');
            const nodes = {nodes_json};
            const centerX = 400, centerY = 200;
            const mappedNodes = nodes.map((n, i) => {{
                const angle = (i / Math.max(1, nodes.length - 1)) * Math.PI * 2;
                const dist = 50 + (i * 30);
                return {{ ...n, x: centerX + Math.cos(angle)*dist, y: centerY + Math.sin(angle)*dist }};
            }});

            let progress = 0;
            let currentNode = 0;

            function animate() {{
                ctx.clearRect(0,0,800,400);
                ctx.strokeStyle = '#1a2b3c';
                ctx.beginPath();
                mappedNodes.forEach(n => {{ ctx.moveTo(centerX, centerY); ctx.lineTo(n.x, n.y); }});
                ctx.stroke();

                mappedNodes.forEach((n, i) => {{
                    ctx.fillStyle = i === 0 ? '#00FF66' : (i === nodes.length-1 ? '#FF0055' : '#00E5FF');
                    ctx.beginPath(); ctx.arc(n.x, n.y, 8, 0, Math.PI*2); ctx.fill();
                }});

                if (currentNode < mappedNodes.length - 1) {{
                    let p1 = mappedNodes[currentNode];
                    let p2 = mappedNodes[currentNode+1];
                    let x = p1.x + (p2.x - p1.x) * progress;
                    let y = p1.y + (p2.y - p1.y) * progress;
                    
                    ctx.fillStyle = '#00FF66';
                    ctx.beginPath(); ctx.arc(x, y, 6, 0, Math.PI*2); ctx.fill();
                    
                    progress += 0.02;
                    if (progress >= 1) {{ progress = 0; currentNode++; }}
                }} else if (mappedNodes.length > 0) {{
                    ctx.fillStyle = '#FF0055';
                    ctx.beginPath(); ctx.arc(mappedNodes[mappedNodes.length-1].x, mappedNodes[mappedNodes.length-1].y, 8, 0, Math.PI*2); ctx.fill();
                }}
                requestAnimationFrame(animate);
            }}
            animate();
        </script>
    </body>
    </html>
    """
    st.components.v1.html(web_html, height=420)

# --- UI ---
with st.sidebar:
    st.header("⚙️ Global Control")
    proxy_input = st.text_area("🌐 Proxies:", value=DEFAULT_PROXIES, height=200)

tab1, tab2, tab3 = st.tabs(["🚀 Engine", "🌍 Harvester", "📦 Seeder"])

with tab1:
    s_input = st.text_input("Start ID:", "1703896246")
    t_input = st.text_input("Target ID:", "140671171")
    if st.button("🚀 Ignite Pipeline"):
        st.session_state.final_enriched_path = None
        st.session_state.running = True
        st.rerun()

    if st.session_state.final_enriched_path:
        render_spider_web_path_canvas(st.session_state.final_enriched_path)
        df = pd.DataFrame(st.session_state.final_enriched_path)
        st.table(df[["name", "id"]])
