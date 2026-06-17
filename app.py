import streamlit as st
import asyncio
import aiohttp
import json
import os
import time
import random

st.set_page_config(page_title="Recon Engine: Hyper-Speed Core", layout="wide")

st.title("⚡ OSINT Graph Reconnaissance (Dedicated Pipeline Core)")
st.write("Utilizes a high-throughput multi-worker queue bound to private authenticated proxies.")

CACHE_FILE = "roblox_graph_map.json"

# Default pre-loaded Webshare proxy pool from configuration credentials
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

# --- UI Sidebar ---
col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("Target Parameters")
    s_input = st.text_input("Start ID:", "1703896246")
    t_input = st.text_input("Target ID:", "140671171")
    
    st.subheader("🌐 Proxy Routing Array")
    proxy_input = st.text_area(
        "Webshare Authenticated Gateway List:",
        value=DEFAULT_PROXIES,
        height=220
    )
    
    start_btn = st.button("🚀 Ignite Pipeline Swarm", use_container_width=True, type="primary")
    stop_btn = st.button("🛑 Kill Pipeline Tasks", use_container_width=True)
    
    st.metric("Profiles Currently Cached in DB", len(st.session_state.global_cache))

with col2:
    st.subheader("Live Continuous Tracking Engine")
    console_placeholder = st.empty()
    status_placeholder = st.empty()

if stop_btn:
    st.session_state.running = False
    st.rerun()

# --- Dedicated Worker Interface ---
async def proxy_worker_task(worker_id, proxy, start_queue, target_queue, start_visited, target_visited, session, path_found_event, results_container, log_func):
    """An isolated loop bound exclusively to one proxy, maintaining continuous execution flow."""
    cooldowns = 0
    while not path_found_event.is_set() and st.session_state.running:
        try:
            # Balance the search tree by choosing to pull from the smaller queue
            if len(start_visited) <= len(target_visited):
                if not start_queue.empty():
                    node = start_queue.get_nowait()
                    direction = "FORWARD"
                elif not target_queue.empty():
                    node = target_queue.get_nowait()
                    direction = "REVERSE"
                else:
                    await asyncio.sleep(0.05)
                    continue
            else:
                if not target_queue.empty():
                    node = target_queue.get_nowait()
                    direction = "REVERSE"
                elif not start_queue.empty():
                    node = start_queue.get_nowait()
                    direction = "FORWARD"
                else:
                    await asyncio.sleep(0.05)
                    continue
        except asyncio.QueueEmpty:
            await asyncio.sleep(0.05)
            continue

        # Step 1: Instantly bypass network lookups if data exists inside the Local DB
        str_node = str(node)
        if str_node in st.session_state.global_cache:
            friends = st.session_state.global_cache[str_node]
            results_container["cache_hits"] += 1
            
            # Fast check intersection path
            current_path = start_visited[node] if direction == "FORWARD" else target_visited[node]
            if len(current_path) >= 5:
                continue
                
            for friend in friends:
                if direction == "FORWARD":
                    if friend in target_visited:
                        results_container["final_chain"] = current_path + target_visited[friend][::-1]
                        path_found_event.set()
                        break
                    if friend not in start_visited:
                        start_visited[friend] = current_path + [friend]
                        await start_queue.put(friend)
                else:
                    if friend in start_visited:
                        results_container["final_chain"] = start_visited[friend] + current_path[::-1]
                        path_found_event.set()
                        break
                    if friend not in target_visited:
                        target_visited[friend] = current_path + [friend]
                        await target_queue.put(friend)
            continue

        # Step 2: Outbound network request pipeline via the dedicated proxy
        url = f"https://friends.roblox.com/v1/users/{node}/friends"
        try:
            async with session.get(url, proxy=proxy, timeout=5) as response:
                results_container["api_calls"] += 1
                
                if response.status == 200:
                    data = await response.json()
                    friends = [f["id"] for f in data.get("data", []) if not f.get("isDeleted", False)]
                    
                    # Update Memory DB
                    st.session_state.global_cache[str_node] = friends
                    results_container["new_discoveries"][str_node] = friends
                    
                    current_path = start_visited[node] if direction == "FORWARD" else target_visited[node]
                    if len(current_path) >= 5:
                        continue
                        
                    for friend in friends:
                        if direction == "FORWARD":
                            if friend in target_visited:
                                results_container["final_chain"] = current_path + target_visited[friend][::-1]
                                path_found_event.set()
                                break
                            if friend not in start_visited:
                                start_visited[friend] = current_path + [friend]
                                await start_queue.put(friend)
                        else:
                            if friend in start_visited:
                                results_container["final_chain"] = start_visited[friend] + current_path[::-1]
                                path_found_event.set()
                                break
                            if friend not in target_visited:
                                target_visited[friend] = current_path + [friend]
                                await target_queue.put(friend)
                                
                    # Maintain steady throughput pacing to prevent rate limiting
                    await asyncio.sleep(0.25)
                    
                elif response.status == 429:
                    # Put node back in the queue line for another worker to try
                    if direction == "FORWARD":
                        await start_queue.put(node)
                    else:
                        await target_queue.put(node)
                    
                    cooldowns += 1
                    log_func(f"[Worker-{worker_id}] 429 Throttled. Isolating proxy pathway for 6 seconds...")
                    await asyncio.sleep(6.0)
                else:
                    if direction == "FORWARD":
                        await start_queue.put(node)
                    else:
                        await target_queue.put(node)
                    await asyncio.sleep(1.0)
        except Exception:
            if direction == "FORWARD":
                await start_queue.put(node)
            else:
                await target_queue.put(node)
            await asyncio.sleep(1.0)

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

# --- Control Core Assembly ---
async def master_pipeline_engine(s_id, t_id, proxies):
    start_queue = asyncio.Queue()
    target_queue = asyncio.Queue()
    
    await start_queue.put(s_id)
    await target_queue.put(t_id)
    
    start_visited = {s_id: [s_id]}
    target_visited = {t_id: [t_id]}
    
    path_found_event = asyncio.Event()
    
    results_container = {
        "final_chain": [],
        "api_calls": 0,
        "cache_hits": 0,
        "new_discoveries": {}
    }

    def log(msg):
        st.session_state.logs.append(msg)
        if len(st.session_state.logs) > 30:
            st.session_state.logs.pop(0)
        console_placeholder.code("\n".join(st.session_state.logs), language="bash")

    log(f"[SYSTEM] Spinning up {len(proxies)} dedicated asynchronous pipeline streams...")

    async with aiohttp.ClientSession() as session:
        # Initialize one persistent background task wrapper per proxy route
        workers = []
        for idx, proxy_url in enumerate(proxies):
            workers.append(
                asyncio.create_task(
                    proxy_worker_task(
                        idx + 1, proxy_url, start_queue, target_queue,
                        start_visited, target_visited, session,
                        path_found_event, results_container, log
                    )
                )
            )

        # Keep UI informed as workers crunch background queues asynchronously
        while not path_found_event.is_set() and st.session_state.running:
            status_placeholder.info(
                f"🚀 Active Network Channels: {len(proxies)} | "
                f"Local Database Cache Hits: {results_container['cache_hits']} | "
                f"Outbound API Calls Traversed: {results_container['api_calls']} | "
                f"Discovered Profiles: {len(start_visited) + len(target_visited)}"
            )
            await asyncio.sleep(0.4)

        # Signal completion state to remaining threads
        path_found_event.set()
        await asyncio.gather(*workers, return_exceptions=True)

        if results_container["new_discoveries"]:
            save_persistent_cache(st.session_state.global_cache)

        if results_container["final_chain"]:
            clean_chain = []
            for u in results_container["final_chain"]:
                if not clean_chain or clean_chain[-1] != u:
                    clean_chain.append(u)
                    
            log("[SUCCESS] Match link discovered! Reconstructing identity handles...")
            names = await resolve_usernames_async(session, clean_chain, proxies)
            display = [names.get(uid, f"UID:{uid}") for uid in clean_chain]
            
            st.success("### 🎯 Verified Graph Sequence Map")
            st.info(" ➔ ".join(f"**{n}**" for n in display))
            st.session_state.running = False

# --- Trigger Router ---
if start_btn and s_input.isdigit() and t_input.isdigit():
    cleaned_proxies = parse_proxy_input(proxy_input)
    
    if not cleaned_proxies:
        st.error("❌ Critical: Proxy formatting verification failed. Verify configuration data input.")
    else:
        st.session_state.running = True
        st.session_state.logs = ["[SYSTEM] Synchronizing dedicated pipeline cores... Wait for tracking channels to ignite."]
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(master_pipeline_engine(int(s_input), int(t_input), cleaned_proxies))
