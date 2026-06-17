import streamlit as st
import asyncio
import aiohttp
import json
import os
import time
import random
from collections import deque

st.set_page_config(page_title="Recon Engine: Game-Scale Core", layout="wide")

st.title("⚡ OSINT Graph Reconnaissance (Database Cache Core)")
st.write("Emulates Roblox game infrastructure by utilizing an optimized local graph cache layer.")

CACHE_FILE = "roblox_graph_map.json"

# --- Graph Database Storage Layer ---
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
    except Exception as e:
        print(f"Cache write error: {e}")

# Load the local graph database
if "global_cache" not in st.session_state:
    st.session_state.global_cache = load_persistent_cache()
if "logs" not in st.session_state:
    st.session_state.logs = []
if "running" not in st.session_state:
    st.session_state.running = False

# --- UI Setup ---
col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("Target Parameters")
    s_input = st.text_input("Start ID:", "1703896246")
    t_input = st.text_input("Target ID:", "140671171")
    batch_size = st.slider("Network Workers (Concurrent Streams):", 10, 100, 40)
    
    st.subheader("🌐 Proxy Routing Panel")
    proxy_input = st.text_area(
        "Paste Proxies (One per line):",
        placeholder="http://user:pass@ip:port",
        height=100
    )
    
    start_btn = st.button("🚀 Execute Swarm Search", use_container_width=True, type="primary")
    stop_btn = st.button("🛑 Stop Engine", use_container_width=True)
    
    st.metric("Locally Indexed Database Profiles", len(st.session_state.global_cache))

with col2:
    st.subheader("Live Graph Processing Engine")
    console_placeholder = st.empty()
    status_placeholder = st.empty()

if stop_btn:
    st.session_state.running = False
    st.rerun()

# --- Hyper-Async Network Handlers ---
async def fetch_friends_async(session, user_id, proxy_list):
    url = f"https://friends.roblox.com/v1/users/{user_id}/friends"
    selected_proxy = random.choice(proxy_list) if proxy_list else None
    try:
        async with session.get(url, proxy=selected_proxy, timeout=5) as response:
            if response.status == 200:
                data = await response.json()
                friends = [f["id"] for f in data.get("data", []) if not f.get("isDeleted", False)]
                return user_id, friends, False
            elif response.status == 429:
                return user_id, [], True
            return user_id, [], False
    except Exception:
        return user_id, [], True

async def resolve_usernames_async(session, id_list, proxy_list):
    if not id_list:
        return {}
    url = "https://users.roblox.com/v1/users"
    selected_proxy = random.choice(proxy_list) if proxy_list else None
    try:
        async with session.post(url, json={"userIds": id_list, "excludeBannedUsers": False}, proxy=selected_proxy, timeout=5) as response:
            if response.status == 200:
                data = await response.json()
                return {u["id"]: u["name"] for u in data.get("data", [])}
        return {}
    except Exception:
        return {}

# --- Execution Engine ---
async def run_engine(s_id, t_id, max_concurrent, proxy_pool):
    start_visited = {s_id: [s_id]}
    start_queue = deque([s_id])
    
    target_visited = {t_id: [t_id]}
    target_queue = deque([t_id])
    
    api_calls = 0
    cache_hits = 0
    path_found = False
    final_chain = []
    new_discoveries = {}

    def log(msg):
        st.session_state.logs.append(msg)
        if len(st.session_state.logs) > 40:
            st.session_state.logs.pop(0)
        console_placeholder.code("\n".join(st.session_state.logs), language="bash")

    log("[START] Mapping network mesh layers...")

    async with aiohttp.ClientSession() as session:
        while st.session_state.running:
            
            # --- PHASE 1: PROCESS FROM LOCAL CACHE INSTANTLY ---
            # Crawl through the queues and instantly resolve anything we already know
            pre_processed = False
            
            for queue, visited, direction in [(start_queue, start_visited, "FORWARD"), (target_queue, target_visited, "REVERSE")]:
                if queue:
                    next_node = queue[0]
                    # Direct check against string and integer formats in the JSON map
                    str_node = str(next_node)
                    if str_node in st.session_state.global_cache:
                        queue.popleft()
                        cached_friends = st.session_state.global_cache[str_node]
                        cache_hits += 1
                        pre_processed = True
                        
                        current_path = visited[next_node]
                        if len(current_path) > 4:
                            continue
                            
                        for friend in cached_friends:
                            if direction == "FORWARD":
                                if friend in target_visited:
                                    final_chain = current_path + target_visited[friend][::-1]
                                    path_found = True
                                    break
                                if friend not in start_visited:
                                    start_visited[friend] = current_path + [friend]
                                    start_queue.append(friend)
                            else:
                                if friend in start_visited:
                                    final_chain = start_visited[friend] + current_path[::-1]
                                    path_found = True
                                    break
                                if friend not in target_visited:
                                    target_visited[friend] = current_path + [friend]
                                    target_queue.append(friend)
                        if path_found:
                            break
            
            if path_found:
                break
                
            # If we were able to pull data instantly from the local database, loop immediately without wasting network time
            if pre_processed:
                if cache_hits % 100 == 0:
                    status_placeholder.success(f"⚡ Local Database Cache Hits: {cache_hits} | No API throttling applied.")
                continue

            # --- PHASE 2: PARALLEL WEB SCROLL SWARM ---
            tasks = []
            directions = []
            
            while len(tasks) < max_concurrent:
                if start_queue and (not target_queue or len(start_queue) <= len(target_queue)):
                    node = start_queue.popleft()
                    if len(start_visited[node]) <= 4:
                        tasks.append(fetch_friends_async(session, node, proxy_pool))
                        directions.append(("FORWARD", node))
                elif target_queue:
                    node = target_queue.popleft()
                    if len(target_visited[node]) <= 4:
                        tasks.append(fetch_friends_async(session, node, proxy_pool))
                        directions.append(("REVERSE", node))
                else:
                    break
            
            if not tasks:
                log("[INFO] Search field terminated. No structural relationship discovered.")
                break

            log(f"[NETWORK] Querying {len(tasks)} live profiles simultaneously...")
            results = await asyncio.gather(*tasks)
            api_calls += len(tasks)
            
            status_placeholder.info(f"API Calls: {api_calls} | Database Hits: {cache_hits} | Total Visited Nodes: {len(start_visited) + len(target_visited)}")
            
            rate_limit_tripped = False

            for (direction, parent_node), (node_id, friends, hit_429) in zip(directions, results):
                if hit_429:
                    rate_limit_tripped = True
                    if direction == "FORWARD":
                        start_queue.appendleft(parent_node)
                    else:
                        target_queue.appendleft(parent_node)
                    continue
                
                # Commit new discovery straight to memory database
                st.session_state.global_cache[str(node_id)] = friends
                new_discoveries[str(node_id)] = friends
                
                current_path = start_visited[parent_node] if direction == "FORWARD" else target_visited[parent_node]
                
                for friend in friends:
                    if direction == "FORWARD":
                        if friend in target_visited:
                            final_chain = current_path + target_visited[friend][::-1]
                            path_found = True
                            break
                        if friend not in start_visited:
                            start_visited[friend] = current_path + [friend]
                            start_queue.append(friend)
                    else:
                        if friend in start_visited:
                            final_chain = start_visited[friend] + current_path[::-1]
                            path_found = True
                            break
                        if friend not in target_visited:
                            target_visited[friend] = current_path + [friend]
                            target_queue.append(friend)
                
                if path_found:
                    break
            
            if path_found:
                break
                
            if rate_limit_tripped and not proxy_pool:
                log("[WARNING] Throttled. Swarm paused for 60s. Add proxies to eliminate this lag.")
                for i in range(60, 0, -1):
                    await asyncio.sleep(1)
                continue

            await asyncio.sleep(0.01)

        # Sync memory modifications out to disk layout
        if new_discoveries:
            save_persistent_cache(st.session_state.global_cache)

        if path_found:
            clean_chain = []
            for u in final_chain:
                if not clean_chain or clean_chain[-1] != u:
                    clean_chain.append(u)
                    
            log("[SUCCESS] Path intercepted! Resolving profile handles...")
            names = await resolve_usernames_async(session, clean_chain, proxy_pool)
            display = [names.get(uid, f"UID:{uid}") for uid in clean_chain]
            
            st.success("### 🎯 Verified Graph Sequence Map")
            st.info(" ➔ ".join(f"**{n}**" for n in display))
            st.session_state.running = False

# --- Entry Point Run ---
if start_btn and s_input.isdigit() and t_input.isdigit():
    st.session_state.running = True
    st.session_state.logs = ["[SYSTEM] Starting Core Database Engine..."]
    
    raw_lines = proxy_input.split("\n")
    cleaned_proxies = [line.strip() for line in raw_lines if line.strip().startswith("http")]
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_engine(int(s_input), int(t_input), batch_size, cleaned_proxies))
