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

# Combined Proxy Array: Merging both authentication pools seamlessly
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


# --- HEURISTIC INTELLIGENCE WEIGHTING ENGINE ---

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
            resolved_path = hf_hub_download(
                repo_id=HF_REPO_ID,
                filename=DB_FILE,
                repo_type="dataset",
                token=HF_TOKEN
            )
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
    except Exception:
        pass
    return memory_cache

def save_single_profile_to_db(user_id, friends_list):
    try:
        # High timeout value prevents file-locking drops during background crawls
        conn = sqlite3.connect(DB_FILE, timeout=60.0)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO graph (user_id, friends_list) VALUES (?, ?)",
            (str(user_id), json.dumps(friends_list))
        )
        conn.commit()
        conn.close()
    except Exception:
        pass

def sync_entire_memory_to_sqlite():
    try:
        conn = sqlite3.connect(DB_FILE, timeout=60.0)
        cursor = conn.cursor()
        cursor.execute("BEGIN TRANSACTION")
        for uid, friends in st.session_state.global_cache.items():
            cursor.execute(
                "INSERT OR REPLACE INTO graph (user_id, friends_list) VALUES (?, ?)",
                (str(uid), json.dumps(friends))
            )
        conn.commit()
        conn.close()
    except Exception:
        pass

# --- THREAD-ISOLATED CLOUD LOCK ENGINE ---

def upload_cache_to_cloud_blocking():
    if not HF_TOKEN or not HF_REPO_ID:
        return False, "Configuration credentials missing or invalid."
    sync_entire_memory_to_sqlite()
    if not os.path.exists(DB_FILE):
        return False, "Target database file absent."
    try:
        api = HfApi()
        api.upload_file(
            path_or_fileobj=DB_FILE,
            path_in_repo=DB_FILE,
            repo_id=HF_REPO_ID,
            repo_type="dataset",
            token=HF_TOKEN,
            commit_message="Automated incremental asynchronous cloud database commit"
        )
        return True, "Success"
    except Exception as e:
        return False, str(e)

async def upload_cache_to_cloud_async():
    if "cloud_lock" not in st.session_state:
        st.session_state.cloud_lock = asyncio.Lock()
        
    async with st.session_state.cloud_lock:
        success, diagnostics = await asyncio.to_thread(upload_cache_to_cloud_blocking)
        if not success:
            # Safely logs to dashboard console output stream instead of breaking runtimes
            st.session_state.logs.append(f"[CLOUD-WARN] Backup delayed: {diagnostics}")
        return success, diagnostics


if "global_cache" not in st.session_state:
    st.session_state.global_cache = load_persistent_cache()
if "logs" not in st.session_state:
    st.session_state.logs = []
if "running" not in st.session_state:
    st.session_state.running = False
if "harvester_running" not in st.session_state:
    st.session_state.harvester_running = False
if "seeder_running" not in st.session_state:
    st.session_state.seeder_running = False

def render_cyber_graph_ui(enriched_nodes):
    html_elements = ""
    for idx, node in enumerate(enriched_nodes):
        is_endpoint = (idx == 0 or idx == len(enriched_nodes) - 1)
        bg_color = "#111625" if is_endpoint else "#201612"
        border_color = "#00E5FF" if is_endpoint else "#FF6D00"
        text_color = "#E0E0E0"
        
        created_year = node["created"][:4]
        is_suspected_alt = str(created_year) in ["2025", "2026"] and not is_endpoint
        alt_badge = """<div style="color: #FF3D00; font-size: 10px; margin-top: 4px; font-weight: bold;">⚠️ SUSPECTED ALT</div>""" if is_suspected_alt else ""
        banned_badge = """<div style="color: #FF1744; font-size: 10px; margin-top: 4px; font-weight: bold;">🚫 BANNED</div>""" if node["isBanned"] else ""

        role_label = "START TARGET" if idx == 0 else ("END TARGET" if idx == len(enriched_nodes) - 1 else f"BRIDGE NODE {idx}")

        html_elements += f"""
        <div style="display: flex; align-items: center; margin: 10px 0;">
            <div style="background-color: {bg_color}; border: 1px solid {border_color}; 
                        padding: 14px; border-radius: 6px; color: {text_color}; 
                        font-family: 'Courier New', monospace; min-width: 170px; text-align: left;">
                <div style="font-size: 9px; color: {border_color}; font-weight: bold; letter-spacing: 1px;">{role_label}</div>
                <div style="font-size: 14px; margin-top: 4px; font-weight: bold; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{node['name']}</div>
                <div style="font-size: 11px; opacity: 0.6; margin-top: 2px;">ID: {node['id']}</div>
                <div style="font-size: 10px; opacity: 0.5; margin-top: 4px;">Born: {node['created']}</div>
                {alt_badge}
                {banned_badge}
            </div>
        """
        if idx < len(enriched_nodes) - 1:
            html_elements += """<div style="padding: 0 12px; color: #00E5FF; font-size: 20px; font-weight: bold; font-family: monospace;">➔</div>"""
            
    full_container = f"""<div style="display: flex; flex-wrap: wrap; align-items: center; padding: 15px; background-color: #070913; border-radius: 8px; border: 1px solid #1A1F35; margin-bottom: 20px;">{html_elements}</div>"""
    st.components.v1.html(full_container, height=160, scrolling=True)


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
            if success:
                st.toast("Database backed up successfully!", icon="🚀")
                st.rerun()
            else:
                st.error(f"💥 Transfer Dropped: {error_msg}")
    else:
        st.warning("⚠️ Running in Local-Only Mode.")

tab1, tab2, tab3 = st.tabs(["🚀 Graph Path Tracer", "🌍 Real Mass Harvester", "📦 Roblox Backbone Seeder & Tools"])

# ==========================================
# TAB 1: GRAPH PATHFINDER CORE
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

    console_placeholder = st.empty()
    status_placeholder = st.empty()
    group_placeholder = st.empty()

async def cache_processor_task(network_queue, cache_queue, start_visited, target_visited, path_found_event, results_container):
    g_cache = st.session_state.global_cache
    while not path_found_event.is_set() and st.session_state.running:
        try:
            score, (direction, node) = cache_queue.get_nowait()
        except asyncio.QueueEmpty:
            await asyncio.sleep(0.001)
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

async def proxy_worker_task(worker_id, pool_manager, network_queue, cache_queue, start_visited, target_visited, session, path_found_event, results_container, log_func):
    g_cache = st.session_state.global_cache
    
    while not path_found_event.is_set() and st.session_state.running:
        proxy = pool_manager.get_healthy_proxy()
        if not proxy:
            await asyncio.sleep(2.0)
            continue
            
        try:
            score, (direction, node) = network_queue.get_nowait()
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
                    await asyncio.sleep(0.1)
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

async def execute_group_intersection_scan(session, s_id, t_id, pool_manager, placeholder):
    shared_ids = set()
    s_groups, t_groups = await asyncio.gather(
        fetch_user_groups_async(session, s_id, pool_manager),
        fetch_user_groups_async(session, t_id, pool_manager)
    )
    if s_groups and t_groups:
        shared_ids = set(s_groups.keys()).intersection(set(t_groups.keys()))
    with placeholder:
        if shared_ids:
            st.warning(f"🎯 Direct Group Vector Detected! Found {len(shared_ids)} shared groups:")
            for gid in shared_ids:
                st.markdown(f"• **Group:** {s_groups[gid]} `(ID: {gid})` ➔ [View](https://www.roblox.com/groups/{gid})")
        else:
            st.info("ℹ️ No directly shared structural Roblox Group vectors identified.")

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
    results_container = {"final_chain": [], "api_calls": 0, "cache_hits": 0, "new_discoveries": {}}

    def log(msg):
        st.session_state.logs.append(msg)
        if len(st.session_state.logs) > 20: st.session_state.logs.pop(0)
        with tab1: console_placeholder.code("\n".join(st.session_state.logs), language="bash")

    log("[SYSTEM] Coordinating proxy health pools. Swarming pipeline arrays...")

    async with aiohttp.ClientSession() as session:
        asyncio.create_task(execute_group_intersection_scan(session, s_id, t_id, pool_manager, group_placeholder))
        
        workers = [asyncio.create_task(cache_processor_task(network_queue, cache_queue, start_visited, target_visited, path_found_event, results_container))]
        for idx in range(8):
            workers.append(asyncio.create_task(proxy_worker_task(idx + 1, pool_manager, network_queue, cache_queue, start_visited, target_visited, session, path_found_event, results_container, log)))

        while not path_found_event.is_set() and st.session_state.running:
            h, c, d = pool_manager.get_pool_diagnostics()
            with tab1:
                status_placeholder.info(
                    f"🟢 Healthy Proxies: {h} | 🟡 Cooling: {c} | 🔴 Dead: {d} | "
                    f"⚡ Cache Hits: {results_container['cache_hits']} | 🌐 Total Outbound Requests: {results_container['api_calls']}"
                )
            await asyncio.sleep(0.2)

        path_found_event.set()
        await asyncio.gather(*workers, return_exceptions=True)

        if results_container["new_discoveries"]:
            await upload_cache_to_cloud_async()

        if results_container["final_chain"]:
            clean_chain = []
            for u in results_container["final_chain"]:
                if not clean_chain or clean_chain[-1] != u: clean_chain.append(u)
                
            log("[SUCCESS] Path mapping linked. Compiling targets...")
            intel_tasks = [fetch_profile_intel_async(session, uid, pool_manager) for uid in clean_chain]
            enriched_profiles = await asyncio.gather(*intel_tasks)
            with tab1:
                st.success("### 🎯 Target Chain Intersect Discovered")
                render_cyber_graph_ui(enriched_profiles)
        else:
            log("[SYSTEM] Swarm complete. No path uncovered.")
        st.session_state.running = False

if start_btn and s_input.isdigit() and t_input.isdigit():
    pool_mgr = ProxyPool(proxy_input)
    if pool_mgr.proxies:
        st.session_state.running = True
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(master_pipeline_engine(int(s_input), int(t_input), pool_mgr))


# ==========================================
# TAB 2: REAL ROBLOX CRAWLER HARVESTER
# ==========================================
with tab2:
    st.subheader("🌍 Continuous Real-World Social Graph Harvester")
    st.write("Drives automated background harvesting across healthy proxy pipelines.")
    
    hc1, hc2 = st.columns(2)
    with hc1: seed_id_input = st.text_input("Harvester Seed User ID (Start Node):", "1703896246")
    with hc2: max_harvest = st.number_input("Max Users to Scrape Before Auto-Stop:", min_value=100, max_value=100000, value=2000, step=500)
        
    hbtn1, hbtn2 = st.columns(2)
    with hbtn1: start_harvest_btn = st.button("⚡ Ignite High-Speed Crawler", use_container_width=True, type="primary")
    with hbtn2: stop_harvest_btn = st.button("🛑 Force Stop Harvester", use_container_width=True)
        
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
            
        try:
            user_id = harvest_queue.get_nowait()
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
                else:
                    harvest_queue.put_nowait(user_id)
        except Exception:
            pool_manager.report_status(proxy, 0)
            harvest_queue.put_nowait(user_id)

async def master_harvester_coordinator(seed_uid, max_profiles, pool_manager):
    harvest_queue = asyncio.Queue()
    harvest_queue.put_nowait(seed_uid)
    shared_stats = {"scraped_count": 0, "limit": max_profiles, "total_api_calls": 0, "uncommitted_records": 0}
    
    async with aiohttp.ClientSession() as session:
        workers = []
        for idx in range(6):
            workers.append(asyncio.create_task(harvester_spider_worker(idx+1, pool_manager, harvest_queue, shared_stats, session)))
            
        while st.session_state.harvester_running and shared_stats["scraped_count"] < max_profiles:
            h, c, d = pool_manager.get_pool_diagnostics()
            with tab2:
                harvest_status.success(
                    f"🚀 Crawl Active | Live Channels: H:{h} C:{c} D:{d} | "
                    f"📂 Profiles Scraped: {shared_stats['scraped_count']} / {max_profiles}"
                )
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
    st.subheader("📥 Live Advanced 2-Layer Backbone Hub Cultivator")
    
    famous_hubs = {
        "Builderman (UID: 1)": 1,
        "Roblox Official (UID: 18)": 18,
        "Shedletsky (UID: 261)": 261,
        "Asimo3089 - Jailbreak (UID: 12551)": 12551,
        "Linkmon99 - Trader (UID: 472911)": 472911,
        "Merely - Limiteds (UID: 2032622)": 2032622
    }
    
    selected_hubs = st.multiselect("Select Core Roblox Hubs to Map:", list(famous_hubs.keys()), default=list(famous_hubs.keys())[:3])
    custom_seed_list = st.text_input("Append Extra Custom Roblox Hub UIDs:")
    max_layer2_nodes = st.number_input("Max Layer-2 Profiles to Swarm:", min_value=10, max_value=2000, value=250, step=50)
        
    s_col1, s_col2 = st.columns(2)
    with s_col1: ignite_seed = st.button("🔥 Ignite 2-Layer Backbone Swarm", use_container_width=True, type="primary")
    with s_col2: kill_seed = st.button("🛑 Force Stop Seeder Swarm", use_container_width=True)
        
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
        except Exception:
            pool_manager.report_status(proxy, 0)
        return []

    async def run_deep_hub_seeder(primary_uids, pool_manager, max_l2):
        shared_metrics = {"api_calls": 0, "saved_nodes": 0, "current_target": "Initializing"}
        g_cache = st.session_state.global_cache
        
        async with aiohttp.ClientSession() as session:
            shared_metrics["current_target"] = f"Mapping {len(primary_uids)} core seeds..."
            layer2_queue = []
            
            for uid in primary_uids:
                if not st.session_state.seeder_running: break
                friends = await seed_worker_pipeline(uid, pool_manager, session, shared_metrics)
                layer2_queue.extend(friends)
                await asyncio.sleep(0.2)
                
            layer2_queue = list(set([uid for uid in layer2_queue if str(uid) not in g_cache]))
            random.shuffle(layer2_queue)
            layer2_targets = layer2_queue[:max_l2]
            
            shared_metrics["current_target"] = f"Cascading down to {len(layer2_targets)} secondary targets..."
            
            for idx, l2_uid in enumerate(layer2_targets):
                if not st.session_state.seeder_running: break
                h, c, d = pool_manager.get_pool_diagnostics()
                with tab3:
                    seeder_status.info(f"⚡ Swarm Working | Channels: H:{h} C:{c} D:{d} | Cached: {shared_metrics['saved_nodes']}")
                    seeder_console.code(f"Phase: {shared_metrics['current_target']}\nVector [{idx + 1}/{len(layer2_targets)}]: UID {l2_uid}", language="bash")
                
                await seed_worker_pipeline(l2_uid, pool_manager, session, shared_metrics)
                await asyncio.sleep(0.1)
                
                if shared_metrics["saved_nodes"] % 25 == 0:
                    await upload_cache_to_cloud_async()
                    
            await upload_cache_to_cloud_async()
            st.session_state.seeder_running = False
            st.success("🎉 Deep Social Highway established completely!")

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

    # --- SYNTHETIC SEEDER PANEL ---
    st.markdown("---")
    st.subheader("📦 Fake Local Data Mock-Generator")
    seed_start = st.text_input("Simulate Start ID Entry:", value="1703896246")
    seed_target = st.text_input("Simulate Target ID Entry:", value="140671171")
    profile_volume = st.number_input("Background Density Nodes:", min_value=100, max_value=50000, value=5000, step=500)
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

    # --- DATABASE MAINTENANCE PANELS ---
    st.markdown("---")
    st.subheader("🧹 Database Maintenance & Purge Utilities")
    m_col1, m_col2 = st.columns(2)
    with m_col1:
        wipe_all_btn = st.button("💥 Wipe Entire Cache File & Memory", use_container_width=True, type="secondary")
        if wipe_all_btn:
            st.session_state.global_cache = {}
            if os.path.exists(DB_FILE):
                try: os.remove(DB_FILE)
                except Exception: pass
            init_db()
            upload_cache_to_cloud_blocking()
            st.success("💥 Database dropped!")
            st.rerun()
            
    with m_col2:
        purge_hubs_btn = st.button("🧩 Scrub Mock Tracing Hubs Only", use_container_width=True)
        if purge_hubs_btn:
            g_cache = st.session_state.global_cache
            mock_hubs = ["999101", "999102", "999103"]
            nodes_altered = 0
            for h_id in mock_hubs:
                if h_id in g_cache: del g_cache[h_id]; nodes_altered += 1
            for key in list(g_cache.keys()):
                orig_list = g_cache[key]
                cleaned_list = [x for x in orig_list if str(x) not in mock_hubs]
                if len(cleaned_list) != len(orig_list): g_cache[key] = cleaned_list; nodes_altered += 1
            upload_cache_to_cloud_blocking()
            st.success(f"✅ Scrubbed reference matrices! Removed {nodes_altered} links.")
            st.rerun()
