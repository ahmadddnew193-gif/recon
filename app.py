import streamlit as st
import asyncio
import aiohttp
import json
import os
import time
import random

st.set_page_config(page_title="Recon Engine: Ultimate Core", layout="wide")

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

# Initialize session structures
if "global_cache" not in st.session_state:
    st.session_state.global_cache = load_persistent_cache()
if "logs" not in st.session_state:
    st.session_state.logs = []
if "running" not in st.session_state:
    st.session_state.running = False

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
    st.metric("Database Profiles Loaded In-Memory", len(st.session_state.global_cache))

# --- Navigation Setup via Layout Tabs ---
tab1, tab2 = st.tabs(["🚀 Graph Path Tracer", "📦 Synthetic Database Seeder"])

# ==========================================
# TAB 1: GRAPH PATHFINDER CORE
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
    """Processes known nodes at machine microsecond speeds using direct RAM indexing."""
    g_cache = st.session_state.global_cache
    while not path_found_event.is_set() and st.session_state.running:
        try:
            direction, node = cache_queue.get_nowait()
        except asyncio.QueueEmpty:
            await asyncio.sleep(0.001)  # 1ms ultra-low latency context loop speed
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
    """Network proxy communication task paced specifically to shield datacenter IP ranges from 429 locks."""
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
                    log_func(f"[Worker-{worker_id}] ⚠️ 429 Throttled. Expanding spacing window to {base_delay+0.5}s...")
                    base_delay = min(base_delay + 0.5, 3.5)
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
        if len(st.session_state.logs) > 20:
            st.session_state.logs.pop(0)
        with tab1:
            console_placeholder.code("\n".join(st.session_state.logs), language="bash")

    log("[SYSTEM] Coordinating tracking pipelines. Deploying isolated workers...")

    async with aiohttp.ClientSession() as session:
        workers = []
        workers.append(asyncio.create_task(cache_processor_task(network_queue, cache_queue, start_visited, target_visited, path_found_event, results_container)))
        
        for idx, proxy_url in enumerate(proxies):
            workers.append(asyncio.create_task(proxy_worker_task(idx + 1, proxy_url, network_queue, cache_queue, start_visited, target_visited, session, path_found_event, results_container, log)))

        while not path_found_event.is_set() and st.session_state.running:
            with tab1:
                status_placeholder.info(
                    f"📡 Channels Functional: {len(proxies)} | "
                    f"⚡ Memory Cache Hits: {results_container['cache_hits']} | "
                    f"🌐 Outbound API Calls: {results_container['api_calls']} | "
                    f"📂 Queue Latency Backlog: {network_queue.qsize()}"
                )
            await asyncio.sleep(0.4)

        path_found_event.set()
        await asyncio.gather(*workers, return_exceptions=True)

        if results_container["new_discoveries"]:
            save_persistent_cache(g_cache)

        if results_container["final_chain"]:
            clean_chain = []
            for u in results_container["final_chain"]:
                if not clean_chain or clean_chain[-1] != u:
                    clean_chain.append(u)
                    
            log("[SUCCESS] Connection match mapped! Resolving usernames...")
            names = await resolve_usernames_async(session, clean_chain, proxies)
            display = [names.get(uid, f"UID:{uid}") for uid in clean_chain]
            
            with tab1:
                st.success("### 🎯 Target Chain Intersect Discovered")
                st.info(" ➔ ".join(f"**{n}**" for n in display))
            st.session_state.running = False
        else:
            if not st.session_state.running:
                log("[HALT] Task terminated manually by core command input.")

if start_btn and s_input.isdigit() and t_input.isdigit():
    cleaned_proxies = parse_proxy_input(proxy_input)
    if not cleaned_proxies:
        st.error("❌ Proxy Parser Validation Error. Review string array input.")
    else:
        st.session_state.running = True
        st.session_state.logs = ["[SYSTEM] Initializing processing matrix arrays... Tuning pipelines."]
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(master_pipeline_engine(int(s_input), int(t_input), cleaned_proxies))


# ==========================================
# TAB 2: SYNTHETIC DATABASE SEEDER / GENERATOR
# ==========================================
with tab2:
    st.subheader("📦 Local Database Graph Generator & Stress-Tester")
    st.write("Generates a highly localized, scale-free network mapping to evaluate structural tracing performance instantly.")
    
    gen_c1, gen_c2, gen_c3 = st.columns(3)
    with gen_c1:
        seed_start = st.text_input("Simulate Start ID Custom Entry:", value="1703896246")
    with gen_c2:
        seed_target = st.text_input("Simulate Target ID Custom Entry:", value="140671171")
    with gen_c3:
        profile_volume = st.number_input("Background Density Nodes Volume:", min_value=100, max_value=50000, value=5000, step=500)
        
    generate_btn = st.button("⚡ Execute Mock Database Seeding", use_container_width=True, type="secondary")
    
    if generate_btn and seed_start.isdigit() and seed_target.isdigit():
        progress_bar = st.progress(0.0)
        status_text = st.empty()
        
        status_text.text("⏳ Constructing clean data dictionary arrays...")
        progress_bar.progress(0.1)
        
        # High-Speed Generator Logic
        database = {}
        s_id_int = int(seed_start)
        t_id_int = int(seed_target)
        
        # Establish unique intermediate mock hubs
        hub_a, hub_b, hub_c = 999101, 999102, 999103
        
        database[str(s_id_int)] = [hub_a]
        database[str(hub_a)] = [s_id_int, hub_b]
        database[str(hub_b)] = [hub_a, hub_c]
        database[str(hub_c)] = [hub_b, t_id_int]
        database[str(t_id_int)] = [hub_c]
        
        status_text.text(f"📦 Populating base layers with {profile_volume} background profiles...")
        progress_bar.progress(0.4)
        
        # Optimization: Pre-generate lists via random integer ranges
        filler_ids = [random.randint(2000000, 8000000) for _ in range(int(profile_volume))]
        
        for uid in filler_ids:
            str_uid = str(uid)
            if str_uid not in database:
                database[str_uid] = []
            
            friend_count = random.randint(15, 40)
            picked = random.sample(filler_ids, k=min(friend_count, len(filler_ids)))
            database[str_uid].extend(picked)
            
        status_text.text("🔗 Blending cross-connections into core hidden hubs...")
        progress_bar.progress(0.7)
        
        # Merge background profiles across targets to make the graph dense
        database[str(s_id_int)].extend(random.sample(filler_ids, k=20))
        database[str(hub_a)].extend(random.sample(filler_ids, k=25))
        database[str(hub_b)].extend(random.sample(filler_ids, k=25))
        database[str(hub_c)].extend(random.sample(filler_ids, k=25))
        database[str(t_id_int)].extend(random.sample(filler_ids, k=20))
        
        status_text.text("💾 Stripping duplicate listings and exporting out to disk file...")
        progress_bar.progress(0.85)
        
        # Deduping everything instantly via set mapping
        for key in database:
            database[key] = list(set([int(x) for x in database[key] if int(x) != int(key)]))
            
        # Hot-swap memory cache state so the user doesn't have to restart the script
        st.session_state.global_cache = database
        save_persistent_cache(database)
        
        progress_bar.progress(1.0)
        status_text.text("")
        st.success(f"✅ Seeding Complete! {len(database)} records compiled directly into memory state and '{CACHE_FILE}' storage.")
