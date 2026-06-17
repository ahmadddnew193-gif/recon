import streamlit as st
import asyncio
import aiohttp
import json
import os
import time
import random
from collections import deque

st.set_page_config(page_title="Recon Engine: Free Swarm", layout="wide")

st.title("⚡ OSINT Graph Reconnaissance ($0 Budget Core)")
st.write("Automated live public proxy harvesting with fast-dropping async rotation.")

CACHE_FILE = "roblox_graph_map.json"

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

# --- UI Setup ---
col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("Target Parameters")
    s_input = st.text_input("Start ID (You):", "1703896246")
    t_input = st.text_input("Target ID (Celebrity):", "140671171")
    batch_size = st.slider("Proxy Concurrency (Parallel Workers):", 10, 60, 30)
    
    st.subheader("📊 Engine Statistics")
    st.metric("Cached Profiles in Local DB:", len(st.session_state.global_cache))
    
    start_btn = st.button("🚀 Harvest Proxies & Run Search", use_container_width=True, type="primary")
    stop_btn = st.button("🛑 Stop Engine", use_container_width=True)

with col2:
    st.subheader("Live Graph Processing Engine")
    console_placeholder = st.empty()
    status_placeholder = st.empty()

if stop_btn:
    st.session_state.running = False
    st.rerun()

# --- Automated Free Proxy Harvester ---
async def harvest_free_proxies(session):
    """Scrapes raw open-source repositories for active public proxies"""
    urls = [
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt"
    ]
    harvested = []
    for url in urls:
        try:
            async with session.get(url, timeout=5) as response:
                if response.status == 200:
                    text = await response.text()
                    for line in text.splitlines():
                        line = line.strip()
                        if line and ":" in line:
                            # Standardize into proxy format
                            harvested.append(f"http://{line}")
        except Exception:
            continue
    return list(set(harvested)) # Remove duplicates

# --- Hyper-Async Network Handlers ---
async def fetch_friends_async(session, user_id, proxy_list):
    url = f"https://friends.roblox.com/v1/users/{user_id}/friends"
    
    if not proxy_list:
        return user_id, [], "NO_PROXIES"
        
    proxy = random.choice(proxy_list)
    try:
        # Aggressive 2-second timeout to quickly skip dead/slow free proxies
        async with session.get(url, proxy=proxy, timeout=2) as response:
            if response.status == 200:
                data = await response.json()
                friends = [f["id"] for f in data.get("data", []) if not f.get("isDeleted", False)]
                return user_id, friends, None
            elif response.status == 429:
                return user_id, [], "429"
            return user_id, [], "BAD_STATUS"
    except Exception:
        # If the free proxy times out or drops the connection, flag it to burn it
        return user_id, [], proxy

async def resolve_usernames_async(session, id_list, proxy_list):
    if not id_list:
        return {}
    url = "https://users.roblox.com/v1/users"
    proxy = random.choice(proxy_list) if proxy_list else None
    try:
        async with session.post(url, json={"userIds": id_list, "excludeBannedUsers": False}, proxy=proxy, timeout=4) as response:
            if response.status == 200:
                data = await response.json()
                return {u["id"]: u["name"] for u in data.get("data", [])}
        return {}
    except Exception:
        return {}

# --- Execution Core ---
async def run_engine(s_id, t_id, max_concurrent):
    start_visited = {s_id: [s_id]}
    start_queue = deque([s_id])
    
    target_visited = {t_id: [t_id]}
    target_queue = deque([t_id])
    
    api_calls = 0
    cache_hits = 0
    burned_proxies = 0
    path_found = False
    final_chain = []
    new_discoveries = {}

    def log(msg):
        st.session_state.logs.append(msg)
        if len(st.session_state.logs) > 35:
            st.session_state.logs.pop(0)
        console_placeholder.code("\n".join(st.session_state.logs), language="bash")

    async with aiohttp.ClientSession() as session:
        log("[SYSTEM] Connecting to open-source proxy databases...")
        proxy_pool = await harvest_free_proxies(session)
        log(f"[SUCCESS] Injected {len(proxy_pool)} live free proxies into memory swarm.")

        if not proxy_pool:
            log("[CRITICAL] Failed to harvest free proxies. Aborting run.")
            return

        while st.session_state.running:
            
            # --- PHASE 1: INSTANT CACHE EVALUATION ---
            pre_processed = False
            for queue, visited, direction in [(start_queue, start_visited, "FORWARD"), (target_queue, target_visited, "REVERSE")]:
                if queue:
                    next_node = queue[0]
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
            if pre_processed:
                continue

            # --- PHASE 2: ASYNC SWARM DISPATCH ---
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
                log("[INFO] Tree branches completed. No intersecting relationship found.")
                break

            results = await asyncio.gather(*tasks)
            api_calls += len(tasks)
            
            status_placeholder.info(
                f"Active Proxies: {len(proxy_pool)} | Dead Proxies Removed: {burned_proxies} | "
                f"Cache Hits: {cache_hits} | API Calls: {api_calls}"
            )

            for (direction, parent_node), (node_id, friends, error_flag) in zip(directions, results):
                if error_flag:
                    # If it's an explicit proxy URL that failed/timed out, remove it from our pool permanently
                    if error_flag.startswith("http") and error_flag in proxy_pool:
                        proxy_pool.remove(error_flag)
                        burned_proxies += 1
                    
                    # Return node back to its queue for a retry with a different proxy
                    if direction == "FORWARD":
                        start_queue.appendleft(parent_node)
                    else:
                        target_queue.appendleft(parent_node)
                    continue
                
                # Cache successful lookups so we never hit the web for them again
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
                
            # Keep a tiny delay to allow Streamlit UI loops to render stably
            await asyncio.sleep(0.01)

        if new_discoveries:
            save_persistent_cache(st.session_state.global_cache)

        if path_found:
            clean_chain = []
            for u in final_chain:
                if not clean_chain or clean_chain[-1] != u:
                    clean_chain.append(u)
                    
            log("[SUCCESS] Path link verified! Reconstructing display names...")
            names = await resolve_usernames_async(session, clean_chain, proxy_pool)
            display = [names.get(uid, f"UID:{uid}") for uid in clean_chain]
            
            st.success("### 🎯 Verified Graph Sequence Map")
            st.info(" ➔ ".join(f"**{n}**" for n in display))
            st.session_state.running = False

# --- Trigger ---
if start_btn and s_input.isdigit() and t_input.isdigit():
    st.session_state.running = True
    st.session_state.logs = ["[SYSTEM] Launching Automated Budget Swarm Core..."]
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_engine(int(s_input), int(t_input), batch_size))
