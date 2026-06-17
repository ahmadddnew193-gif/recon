import streamlit as st
import asyncio
import aiohttp
import json
import os
import time
import random

st.set_page_config(page_title="Recon Engine: Split-Queue Core", layout="wide")

st.title("⚡ OSINT Graph Reconnaissance (Split-Queue Engine)")
st.write("Hyper-optimized dual-queue pipeline splitting local database tracking from proxy paths.")

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
        if not line:
            continue
        if line.startswith("http://") or line.startswith("https://"):
            cleaned.append(line)
        elif line.count(":") == 3:
            parts = line.split(":")
            cleaned.append(f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}")
    return cleaned

# --- Streamlit UI Setup ---
col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("Target Parameters")
    s_input = st.text_input("Start ID:", "1703896246")
    t_input = st.text_input("Target ID:", "140671171")
    
    st.subheader("🌐 Authenticated Gateways")
    proxy_input = st.text_area("Webshare Routing Array Lines:", value=DEFAULT_PROXIES, height=220)
    
    start_btn = st.button("🚀 Ignite Split Swarm", use_container_width=True, type="primary")
    stop_btn = st.button("🛑 Kill Pipeline Tasks", use_container_width=True)
    
    st.metric("Profiles Currently Cached in DB", len(st.session_state.global_cache))

with col2:
    st.subheader("Live Continuous Tracking Engine")
    console_placeholder = st.empty()
    status_placeholder = st.empty()

if stop_btn:
    st.session_state.running = False
    st.rerun()

# --- Worker 1: Ultra-Fast Local Cache Sweeper ---
async def cache_processor_task(network_queue, cache_queue, start_visited, target_visited, path_found_event, results_container):
    """Processes known nodes at machine speed using local database memory without consuming network bandwidth."""
    while not path_found_event.is_set() and st.session_state.running:
        try:
            direction, node = cache_queue.get_nowait()
        except asyncio.QueueEmpty:
            await asyncio.sleep(0.02)
            continue
            
        str_node = str(node)
        friends = st.session_state.global_cache.get(str_node, [])
        results_container["cache_hits"] += 1
        
        current_path = start_visited.get(node) if direction == "FORWARD" else target_visited.get(node)
        if not current_path or len(current_path) >= 5:
            continue
            
        for friend in friends:
            if direction == "FORWARD":
                if friend in target_visited:
                    results_container["final_chain"] = current_path + target_visited[friend][::-1]
                    path_found_event.set()
                    break
                if friend not in start_visited:
                    start_visited[friend] = current_path + [friend]
                    if str(friend) in st.session_state.global_cache:
                        await cache_queue.put(("FORWARD", friend))
                    else:
                        await network_queue.put(("FORWARD", friend))
            else:
                if friend in start_visited:
                    results_container["final_chain"] = start_visited[friend] + current_path[::-1]
                    path_found_event.set()
                    break
                if friend not in target_visited:
                    target_visited[friend] = current_path + [friend]
                    if str(friend) in st.session_state.global_cache:
                        await cache_queue.put(("REVERSE", friend))
                    else:
                        await network_queue.put(("REVERSE", friend))

# --- Worker 2: Smart Adaptive Proxy Network Channels ---
async def proxy_worker_task(worker_id, proxy, network_queue, cache_queue, start_visited, target_visited, session, path_found_event, results_container, log_func):
    """Paces requests cleanly to avoid detection limits. Dynamically steps back if firewalls challenge the IP."""
    base_delay = 1.4  # Optimal safe interval for datacenter proxy ranges
    
    while not path_found_event.is_set() and st.session_state.running:
        try:
            direction, node = network_queue.get_nowait()
        except asyncio.QueueEmpty:
            await asyncio.sleep(0.05)
            continue
            
        str_node = str(node)
        if str_node in st.session_state.global_cache:
            results_container["cache_hits"] += 1
            await cache_queue.put((direction, node))
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
                    friends = [f["id"] for f in data.get("data", []) if not f.get("isDeleted", False)]
                    
                    st.session_state.global_cache[str_node] = friends
                    results_container["new_discoveries"][str_node] = friends
                    
                    for friend in friends:
                        if direction == "FORWARD":
                            if friend in target_visited:
                                results_container["final_chain"] = current_path + target_visited[friend][::-1]
                                path_found_event.set()
                                break
                            if friend not in start_visited:
                                start_visited[friend] = current_path + [friend]
                                if str(friend) in st.session_state.global_cache:
                                    await cache_queue.put(("FORWARD", friend))
                                else:
                                    await network_queue.put(("FORWARD", friend))
                        else:
                            if friend in start_visited:
                                results_container["final_chain"] = start_visited[friend] + current_path[::-1]
                                path_found_event.set()
                                break
                            if friend not in target_visited:
                                target_visited[friend] = current_path + [friend]
                                if str(friend) in st.session_state.global_cache:
                                    await cache_queue.put(("REVERSE", friend))
                                else:
                                    await network_queue.put(("REVERSE", friend))
                                    
                    # Drift delay back down slightly over stable connections
                    base_delay = max(base_delay - 0.05, 1.2)
                    await asyncio.sleep(base_delay)
                    
                elif response.status == 429:
                    await network_queue.put((direction, node))
                    log_func(f"[Worker-{worker_id}] ⚠️ Throttled. Pacing adjusted to {base_delay+0.5}s. Cooling pathway down...")
                    base_delay = min(base_delay + 0.5, 3.5)
                    await asyncio.sleep(12.0)  # Safe lockout recovery window
                else:
                    await asyncio.sleep(1.0)
                    
        except Exception:
            await network_queue.put((direction, node))
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

# --- Engine Master Orchestration Loop ---
async def master_pipeline_engine(s_id, t_id, proxies):
    network_queue = asyncio.Queue()
    cache_queue = asyncio.Queue()
    
    start_visited = {s_id: [s_id]}
    target_visited = {t_id: [t_id]}
    
    # Pre-sort targets into respective processing queues
    if str(s_id) in st.session_state.global_cache:
        await cache_queue.put(("FORWARD", s_id))
    else:
        await network_queue.put(("FORWARD", s_id))
        
    if str(t_id) in st.session_state.global_cache:
        await cache_queue.put(("REVERSE", t_id))
    else:
        await network_queue.put(("REVERSE", t_id))
        
    path_found_event = asyncio.Event()
    results_container = {
        "final_chain": [],
        "api_calls": 0,
        "cache_hits": 0,
        "new_discoveries": {}
    }

    def log(msg):
        st.session_state.logs.append(msg)
        if len(st.session_state.logs) > 25:
            st.session_state.logs.pop(0)
        console_placeholder.code("\n".join(st.session_state.logs), language="bash")

    log("[SYSTEM] Spinning up coordinated dual-queue optimization architecture...")

    async with aiohttp.ClientSession() as session:
        workers = []
        
        # Fire up the hyper-speed local cache analyzer
        workers.append(asyncio.create_task(cache_processor_task(network_queue, cache_queue, start_visited, target_visited, path_found_event, results_container)))
        
        # Deploy network channels bound directly to dedicated proxy IPs
        for idx, proxy_url in enumerate(proxies):
            workers.append(asyncio.create_task(proxy_worker_task(idx + 1, proxy_url, network_queue, cache_queue, start_visited, target_visited, session, path_found_event, results_container, log)))

        while not path_found_event.is_set() and st.session_state.running:
            status_placeholder.info(
                f"📡 Channels Live: {len(proxies)} | "
                f"⚡ Memory Cache Hits: {results_container['cache_hits']} | "
                f"🌐 Outbound API Calls: {results_container['api_calls']} | "
                f"📂 Network Queue Backlog: {network_queue.qsize()}"
            )
            await asyncio.sleep(0.5)

        path_found_event.set()
        await asyncio.gather(*workers, return_exceptions=True)

        if results_container["new_discoveries"]:
            save_persistent_cache(st.session_state.global_cache)

        if results_container["final_chain"]:
            clean_chain = []
            for u in results_container["final_chain"]:
                if not clean_chain or clean_chain[-1] != u:
                    clean_chain.append(u)
                    
            log("[SUCCESS] Path trace complete! Parsing target names...")
            names = await resolve_usernames_async(session, clean_chain, proxies)
            display = [names.get(uid, f"UID:{uid}") for uid in clean_chain]
            
            st.success("### 🎯 Verified Graph Sequence Map")
            st.info(" ➔ ".join(f"**{n}**" for n in display))
            st.session_state.running = False

# --- UI Trigger Routers ---
if start_btn and s_input.isdigit() and t_input.isdigit():
    cleaned_proxies = parse_proxy_input(proxy_input)
    
    if not cleaned_proxies:
        st.error("❌ Configuration Failure: Unable to clean data structures.")
    else:
        st.session_state.running = True
        st.session_state.logs = ["[SYSTEM] Synchronizing tracking matrices... Threads operational."]
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(master_pipeline_engine(int(s_input), int(t_input), cleaned_proxies))
