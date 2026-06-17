import streamlit as st
import asyncio
import aiohttp
import json
import os
import time
import random
import pandas as pd

st.set_page_config(page_title="Recon Engine: Ultra Core", layout="wide")

CACHE_FILE = "roblox_graph_map.json"

# Pre-loaded verified Webshare proxy configuration
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

@st.cache_resource
def load_persistent_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_persistent_cache(cache_data):
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump(cache_data, f)
    except Exception:
        pass

# Initialize unified session structures
if "global_cache" not in st.session_state:
    st.session_state.global_cache = load_persistent_cache()
if "logs" not in st.session_state:
    st.session_state.logs = []
if "running" not in st.session_state:
    st.session_state.running = False
if "harvester_running" not in st.session_state:
    st.session_state.harvester_running = False

def parse_proxy_input(raw_text):
    lines = raw_text.split("\n")
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

# --- Sidebar Configuration Control Array ---
with st.sidebar:
    st.header("⚙️ Global Control Array")
    proxy_input = st.text_area("🌐 Webshare Proxy Gateways:", value=DEFAULT_PROXIES, height=220)
    st.markdown("---")
    st.metric("Roblox Profiles In Local DB", len(st.session_state.global_cache))

# --- Navigation Setup via Layout Tabs ---
tab1, tab2, tab3 = st.tabs(["🚀 Graph Path Tracer", "🌍 Real Mass Harvester", "📦 Roblox Backbone Seeder & Tools"])

# ==========================================
# TAB 1: GRAPH PATHFINDER CORE (REAL SCANS)
# ==========================================
with tab1:
    st.subheader("Dual-Queue Target Analysis Execution")
    
    c1, c2 = st.columns(2)
    with c1:
        s_input = st.text_input("Start Profile ID:", "1703896246")
    with c2:
        t_input = st.text_input("Target Profile ID:", "140671171")
        
    btn_col1, btn_col2 = st.columns(2)
    with btn_col1:
        start_btn = st.button("🚀 Ignite Pipeline Swarm", use_container_width=True, type="primary")
    with btn_col2:
        stop_btn = st.button("🛑 Kill Pipeline Tasks", use_container_width=True)
        
    if stop_btn:
        st.session_state.running = False
        st.rerun()

    console_placeholder = st.empty()
    status_placeholder = st.empty()

# --- Pathfinder Worker Components ---
async def cache_processor_task(network_queue, cache_queue, start_visited, target_visited, path_found_event, results_container):
    g_cache = st.session_state.global_cache
    while not path_found_event.is_set() and st.session_state.running:
        try:
            direction, node = cache_queue.get_nowait()
        except asyncio.QueueEmpty:
            await asyncio.sleep(0.001)
            continue
            
        str_node = str(node)
        friends = g_cache.get(str_node, [])
        results_container["cache_hits"] += 1
        
        current_path = start_visited.get(node) if direction == "FORWARD" else target_visited.get(node)
        if not current_path or len(current_path) >= 5:
            continue
            
        for friend in friends:
            friend_int = int(friend)
            if direction == "FORWARD":
                if friend_int in target_visited:
                    results_container["final_chain"] = current_path + target_visited[friend_int][::-1]
                    path_found_event.set()
                    break
                if friend_int not in start_visited:
                    start_visited[friend_int] = current_path + [friend_int]
                    if str(friend_int) in g_cache:
                        cache_queue.put_nowait(("FORWARD", friend_int))
                    else:
                        network_queue.put_nowait(("FORWARD", friend_int))
            else:
                if friend_int in start_visited:
                    results_container["final_chain"] = start_visited[friend_int] + current_path[::-1]
                    path_found_event.set()
                    break
                if friend_int not in target_visited:
                    target_visited[friend_int] = current_path + [friend_int]
                    if str(friend_int) in g_cache:
                        cache_queue.put_nowait(("REVERSE", friend_int))
                    else:
                        network_queue.put_nowait(("REVERSE", friend_int))

async def proxy_worker_task(worker_id, proxy, network_queue, cache_queue, start_visited, target_visited, session, path_found_event, results_container, log_func):
    base_delay = 1.3
    g_cache = st.session_state.global_cache
    
    while not path_found_event.is_set() and st.session_state.running:
        try:
            direction, node = network_queue.get_nowait()
        except asyncio.QueueEmpty:
            await asyncio.sleep(0.05)
            continue
            
        str_node = str(node)
        if str_node in g_cache:
            results_container["cache_hits"] += 1
            cache_queue.put_nowait((direction, node))
            continue
            
        current_path = start_visited.get(node) if direction == "FORWARD" else target_visited.get(node)
        if not current_path or len(current_path) >= 5:
            continue
            
        url = f"https://friends.roblox.com/v1/users/{node}/friends"
        try:
            async with session.get(url, proxy=proxy, timeout=6) as response:
                results_container["api_calls"] += 1
                
                if response.status == 200:
                    data = await response.json()
                    friends = [int(f["id"]) for f in data.get("data", []) if not f.get("isDeleted", False)]
                    
                    g_cache[str_node] = friends
                    results_container["new_discoveries"][str_node] = friends
                    
                    for friend in friends:
                        if direction == "FORWARD":
                            if friend in target_visited:
                                results_container["final_chain"] = current_path + target_visited[friend][::-1]
                                path_found_event.set()
                                break
                            if friend not in start_visited:
                                start_visited[friend] = current_path + [friend]
                                if str(friend) in g_cache:
                                    cache_queue.put_nowait(("FORWARD", friend))
                                else:
                                    network_queue.put_nowait(("FORWARD", friend))
                        else:
                            if friend in start_visited:
                                results_container["final_chain"] = start_visited[friend] + current_path[::-1]
                                path_found_event.set()
                                break
                            if friend not in target_visited:
                                target_visited[friend] = current_path + [friend]
                                if str(friend) in g_cache:
                                    cache_queue.put_nowait(("REVERSE", friend))
                                else:
                                    network_queue.put_nowait(("REVERSE", friend))
                                    
                    base_delay = max(base_delay - 0.05, 1.1)
                    await asyncio.sleep(base_delay)
                    
                elif response.status == 429:
                    network_queue.put_nowait((direction, node))
                    log_func(f"[Worker-{worker_id}] ⚠️ Throttled. Adjusting pace window...")
                    await asyncio.sleep(12.0)
                else:
                    network_queue.put_nowait((direction, node))
                    await asyncio.sleep(1.0)
        except Exception:
            network_queue.put_nowait((direction, node))
            await asyncio.sleep(1.5)

async def resolve_usernames_async(session, id_list, proxy_list):
    if not id_list:
        return {}
    url = "https://users.roblox.com/v1/users"
    proxy = random.choice(proxy_list) if proxy_list else None
    try:
        async with session.post(url, json={"userIds": id_list, "excludeBannedUsers": False}, proxy=proxy, timeout=5) as response:
            if response.status == 200:
                data = await response.json()
                return {u["id"]: u["name"] for u in data.get("data", [])}
        return {}
    except Exception:
        return {}

async def master_pipeline_engine(s_id, t_id, proxies):
    network_queue = asyncio.Queue()
    cache_queue = asyncio.Queue()
    start_visited = {s_id: [s_id]}
    target_visited = {t_id: [t_id]}
    
    g_cache = st.session_state.global_cache
    if str(s_id) in g_cache:
        cache_queue.put_nowait(("FORWARD", s_id))
    else:
        network_queue.put_nowait(("FORWARD", s_id))
        
    if str(t_id) in g_cache:
        cache_queue.put_nowait(("REVERSE", t_id))
    else:
        network_queue.put_nowait(("REVERSE", t_id))
        
    path_found_event = asyncio.Event()
    results_container = {"final_chain": [], "api_calls": 0, "cache_hits": 0, "new_discoveries": {}}

    def log(msg):
        st.session_state.logs.append(msg)
        if len(st.session_state.logs) > 20: st.session_state.logs.pop(0)
        with tab1: console_placeholder.code("\n".join(st.session_state.logs), language="bash")

    log("[SYSTEM] Coordinating tracking pipelines. Deploying isolated workers...")

    async with aiohttp.ClientSession() as session:
        workers = [asyncio.create_task(cache_processor_task(network_queue, cache_queue, start_visited, target_visited, path_found_event, results_container))]
        for idx, proxy_url in enumerate(proxies):
            workers.append(asyncio.create_task(proxy_worker_task(idx + 1, proxy_url, network_queue, cache_queue, start_visited, target_visited, session, path_found_event, results_container, log)))

        while not path_found_event.is_set() and st.session_state.running:
            with tab1:
                status_placeholder.info(
                    f"📡 Channels Functional: {len(proxies)} | ⚡ Memory Cache Hits: {results_container['cache_hits']} | "
                    f"🌐 Outbound API Calls: {results_container['api_calls']} | 📂 Queue Backlog: {network_queue.qsize()}"
                )
            await asyncio.sleep(0.4)

        path_found_event.set()
        await asyncio.gather(*workers, return_exceptions=True)

        if results_container["new_discoveries"]:
            save_persistent_cache(g_cache)

        if results_container["final_chain"]:
            clean_chain = []
            for u in results_container["final_chain"]:
                if not clean_chain or clean_chain[-1] != u: clean_chain.append(u)
            log("[SUCCESS] Connection match mapped! Resolving usernames...")
            names = await resolve_usernames_async(session, clean_chain, proxies)
            display = [names.get(uid, f"UID:{uid}") for uid in clean_chain]
            with tab1:
                st.success("### 🎯 Target Chain Intersect Discovered")
                st.info(" ➔ ".join(f"**{n}**" for n in display))
            st.session_state.running = False

if start_btn and s_input.isdigit() and t_input.isdigit():
    cleaned_proxies = parse_proxy_input(proxy_input)
    if cleaned_proxies:
        st.session_state.running = True
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(master_pipeline_engine(int(s_input), int(t_input), cleaned_proxies))

# ==========================================
# TAB 2: REAL ROBLOX CRAWLER HARVESTER
# ==========================================
with tab2:
    st.subheader("🌍 Continuous Real-World Social Graph Harvester")
    st.write("Harvests thousands of genuine profiles into your database by running an asynchronous spider walk through friends lists.")
    
    hc1, hc2 = st.columns(2)
    with hc1:
        seed_id_input = st.text_input("Harvester Seed User ID (Start Node):", "1703896246")
    with hc2:
        max_harvest = st.number_input("Max Users to Scrape Before Auto-Stop:", min_value=100, max_value=100000, value=2000, step=500)
        
    hbtn1, hbtn2 = st.columns(2)
    with hbtn1:
        start_harvest_btn = st.button("⚡ Ignite High-Speed Crawler", use_container_width=True, type="primary")
    with hbtn2:
        stop_harvest_btn = st.button("🛑 Force Stop Harvester", use_container_width=True)
        
    if stop_harvest_btn:
        st.session_state.harvester_running = False
        st.rerun()
        
    harvest_console = st.empty()
    harvest_status = st.empty()

# --- Harvester Async Implementation ---
async def harvester_spider_worker(worker_id, proxy, harvest_queue, shared_stats, session, proxies_list):
    g_cache = st.session_state.global_cache
    base_delay = 1.3
    
    while st.session_state.harvester_running and shared_stats["scraped_count"] < shared_stats["limit"]:
        try:
            user_id = harvest_queue.get_nowait()
        except asyncio.QueueEmpty:
            await asyncio.sleep(0.1)
            continue
            
        str_user = str(user_id)
        if str_user in g_cache:
            for friend in g_cache[str_user]:
                if len(g_cache) < 500000:
                    harvest_queue.put_nowait(friend)
            continue
            
        url = f"https://friends.roblox.com/v1/users/{user_id}/friends"
        try:
            async with session.get(url, proxy=proxy, timeout=6) as response:
                shared_stats["total_api_calls"] += 1
                
                if response.status == 200:
                    data = await response.json()
                    friends = [int(f["id"]) for f in data.get("data", []) if not f.get("isDeleted", False)]
                    
                    g_cache[str_user] = friends
                    shared_stats["scraped_count"] += 1
                    shared_stats["uncommitted_records"] += 1
                    
                    if shared_stats["uncommitted_records"] >= 50:
                        save_persistent_cache(g_cache)
                        shared_stats["uncommitted_records"] = 0
                        
                    for friend in friends:
                        if str(friend) not in g_cache:
                            harvest_queue.put_nowait(friend)
                            
                    base_delay = max(base_delay - 0.05, 1.1)
                    await asyncio.sleep(base_delay)
                    
                elif response.status == 429:
                    harvest_queue.put_nowait(user_id)
                    shared_stats["throttles"] += 1
                    await asyncio.sleep(12.0)
                else:
                    await asyncio.sleep(1.0)
        except Exception:
            harvest_queue.put_nowait(user_id)
            await asyncio.sleep(1.5)

async def master_harvester_coordinator(seed_uid, max_profiles, proxies):
    harvest_queue = asyncio.Queue()
    harvest_queue.put_nowait(seed_uid)
    shared_stats = {"scraped_count": 0, "limit": max_profiles, "total_api_calls": 0, "throttles": 0, "uncommitted_records": 0}
    
    async with aiohttp.ClientSession() as session:
        workers = []
        for idx, p_url in enumerate(proxies):
            workers.append(asyncio.create_task(harvester_spider_worker(idx+1, p_url, harvest_queue, shared_stats, session, proxies)))
            
        while st.session_state.harvester_running and shared_stats["scraped_count"] < max_profiles:
            with tab2:
                harvest_status.success(
                    f"🚀 Crawl Active | 📂 Real Profiles Added This Session: {shared_stats['scraped_count']} / {max_profiles} | "
                    f"🌐 Outbound Connection Enquiries: {shared_stats['total_api_calls']} | ⚠️ Firewall Throttles: {shared_stats['throttles']}"
                )
                harvest_console.code(
                    f"Queue Discovery Buffer Size: {harvest_queue.qsize()} profiles pending tracking.\n"
                    f"RAM Cache buffer uncommitted rows: {shared_stats['uncommitted_records']}/50\n"
                    f"Status: Ingesting verified friend network sequences...", language="bash"
                )
            await asyncio.sleep(1.5)
            
        st.session_state.harvester_running = False
        await asyncio.gather(*workers, return_exceptions=True)
        save_persistent_cache(st.session_state.global_cache)

if start_harvest_btn and seed_id_input.isdigit():
    cleaned_proxies = parse_proxy_input(proxy_input)
    if cleaned_proxies:
        st.session_state.harvester_running = True
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(master_harvester_coordinator(int(seed_id_input), int(max_harvest), cleaned_proxies))
        st.rerun()

# ==========================================
# TAB 3: ROBLOX BACKBONE SEEDER & MANAGEMENT
# ==========================================
with tab3:
    st.subheader("📥 Live Roblox Backbone Hub Pre-Seeder")
    st.write("Build a real-world Roblox dataset inside your cache instantly. Select high-density infrastructure hubs (Admins, Devs, Traders) to fetch their active live friend circles.")
    
    famous_hubs = {
        "Builderman (UID: 1)": 1,
        "Roblox Official (UID: 18)": 18,
        "Shedletsky / Telamon (UID: 261)": 261,
        "Asimo3089 - Jailbreak Creator (UID: 12551)": 12551,
        "Linkmon99 - Top Trader (UID: 472911)": 472911,
        "Merely - Limiteds Collector (UID: 2032622)": 2032622,
        "Badcc - Scripting Legend (UID: 1981245)": 1981245
    }
    
    selected_hubs = st.multiselect("Select Core Roblox Hubs to Map:", list(famous_hubs.keys()), default=list(famous_hubs.keys()))
    custom_seed_list = st.text_input("Append Extra Custom Roblox Hub UIDs (Comma-separated):", placeholder="e.g. 1703896246, 140671171")
    
    ignite_seed = st.button("🔥 Run Asynchronous Roblox Seed Swarm", use_container_width=True, type="primary")
    
    # Core Seeding Scraper Logic
    async def seed_worker(uid, proxy, session, log_box):
        g_cache = st.session_state.global_cache
        url = f"https://friends.roblox.com/v1/users/{uid}/friends"
        try:
            async with session.get(url, proxy=proxy, timeout=7) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    friends = [int(f["id"]) for f in data.get("data", []) if not f.get("isDeleted", False)]
                    g_cache[str(uid)] = friends
                    return len(friends)
        except Exception:
            pass
        return 0

    async def run_hub_seeder(id_list, proxies):
        status_box = st.empty()
        async with aiohttp.ClientSession() as session:
            tasks = []
            for i, uid in enumerate(id_list):
                p = proxies[i % len(proxies)] if proxies else None
                tasks.append(seed_worker(uid, p, session, status_box))
            results = await asyncio.gather(*tasks)
            save_persistent_cache(st.session_state.global_cache)
            st.success(f"🎉 Backbone construction completed! Successfully populated real connection matrices for selected Roblox hubs.")

    if ignite_seed:
        target_uids = [famous_hubs[name] for name in selected_hubs]
        if custom_seed_list.strip():
            for c_id in custom_seed_list.split(","):
                if c_id.strip().isdigit(): target_uids.append(int(c_id.strip()))
                
        cleaned_proxies = parse_proxy_input(proxy_input)
        if target_uids and cleaned_proxies:
            with st.spinner("Swarming Roblox servers to assemble real-world native backbone..."):
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(run_hub_seeder(target_uids, cleaned_proxies))
                st.rerun()

    # --- SYNTHETIC SEEDER BACKUP PANEL ---
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
        for key in database:
            database[key] = list(set([int(x) for x in database[key] if int(x) != int(key)]))
        st.session_state.global_cache = database
        save_persistent_cache(database)
        st.success("✅ Mock Database Seeded!")
        st.rerun()

    # --- DATABASE MAINTENANCE PANELS ---
    st.markdown("---")
    st.subheader("🧹 Database Maintenance & Purge Utilities")
    st.write("Safely erase structural entries from your system to toggle cleanly between synthetic testing and actual tracking jobs.")
    
    m_col1, m_col2 = st.columns(2)
    
    with m_col1:
        st.markdown("**Option A: The Complete Clean Slate**")
        wipe_all_btn = st.button("💥 Wipe Entire Cache File & Memory", use_container_width=True, type="secondary")
        if wipe_all_btn:
            st.session_state.global_cache = {}
            if os.path.exists(CACHE_FILE):
                try: os.remove(CACHE_FILE)
                except Exception: pass
            st.success("💥 Database dropped! Reset to 0 records.")
            st.rerun()
            
    with m_col2:
        st.markdown("**Option B: Scrub Injected Bridge Hubs Only**")
        purge_hubs_btn = st.button("🧩 Scrub Mock Tracing Hubs Only", use_container_width=True)
        if purge_hubs_btn:
            g_cache = st.session_state.global_cache
            mock_hubs = ["999101", "999102", "999103"]
            nodes_altered = 0
            for h_id in mock_hubs:
                if h_id in g_cache:
                    del g_cache[h_id]
                    nodes_altered += 1
            for key in list(g_cache.keys()):
                orig_list = g_cache[key]
                cleaned_list = [x for x in orig_list if str(x) not in mock_hubs]
                if len(cleaned_list) != len(orig_list):
                    g_cache[key] = cleaned_list
                    nodes_altered += 1
            save_persistent_cache(g_cache)
            st.success(f"✅ Scrubbed reference matrices! Removed {nodes_altered} link dependencies.")
            st.rerun()
