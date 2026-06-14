import streamlit as st
import asyncio
import aiohttp
import time
from collections import deque

st.set_page_config(page_title="Recon Engine: Hyper-Async", layout="wide")

st.title("⚡ OSINT Graph Reconnaissance (Hyper-Async Engine)")
st.write("Overhauled Event-Loop Core utilizing non-blocking asynchronous I/O multiplexing.")

# --- Session State ---
if "logs" not in st.session_state:
    st.session_state.logs = []
if "running" not in st.session_state:
    st.session_state.running = False

# --- UI Layout ---
col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("Target Configuration")
    s_input = st.text_input("Start ID:", "1703896246")
    t_input = st.text_input("Target ID:", "140671171")
    batch_size = st.slider("Micro-Batch Size (Concurrent Tasks):", 5, 50, 20)
    
    start_btn = st.button("🚀 Launch Async Swarm", use_container_width=True, type="primary")
    stop_btn = st.button("🛑 Terminate Loop", use_container_width=True)

with col2:
    st.subheader("Live Event-Loop Console")
    console_placeholder = st.empty()
    status_placeholder = st.empty()

if stop_btn:
    st.session_state.logs = []
    st.session_state.running = False
    st.rerun()

# --- Async Network Workers ---
async def fetch_friends_async(session, user_id):
    """Fires non-blocking network calls multiplexed over a single TCP connection pool"""
    url = f"https://friends.roblox.com/v1/users/{user_id}/friends"
    
    # 🔴 PROXY HOOK: Paste your proxy address here to completely bypass 429 rate limits!
    # example: proxy = "http://username:password@proxy_host:proxy_port"
    proxy = None 
    
    try:
        async with session.get(url, proxy=proxy, timeout=5) as response:
            if response.status == 200:
                data = await response.json()
                friends = [f["id"] for f in data.get("data", []) if not f.get("isDeleted", False)]
                return user_id, friends, False
            elif response.status == 429:
                return user_id, [], True
            return user_id, [], False
    except Exception:
        return user_id, [], False

async def resolve_usernames_async(session, id_list):
    if not id_list:
        return {}
    url = "https://users.roblox.com/v1/users"
    try:
        async with session.post(url, json={"userIds": id_list, "excludeBannedUsers": False}, timeout=5) as response:
            if response.status == 200:
                data = await response.json()
                return {u["id"]: u["name"] for u in data.get("data", [])}
        return {}
    except Exception:
        return {}

# --- Core Async Engine Execution ---
async def run_engine(s_id, t_id, max_concurrent):
    start_visited = {s_id: [s_id]}
    start_queue = deque([s_id])
    
    target_visited = {t_id: [t_id]}
    target_queue = deque([t_id])
    
    api_calls = 0
    path_found = False
    final_chain = []

    def log(msg):
        st.session_state.logs.append(msg)
        if len(st.session_state.logs) > 40:
            st.session_state.logs.pop(0)
        console_placeholder.code("\n".join(st.session_state.logs), language="bash")

    log(f"[INFO] Initializing Async Engine. Concurrent Batch Windows: {max_concurrent}")

    async with aiohttp.ClientSession() as session:
        while st.session_state.running:
            tasks = []
            directions = []
            
            # Fill the batch frame concurrently
            while len(tasks) < max_concurrent:
                if start_queue and (not target_queue or len(start_queue) <= len(target_queue)):
                    node = start_queue.popleft()
                    if len(start_visited[node]) <= 4:
                        tasks.append(fetch_friends_async(session, node))
                        directions.append(("FORWARD", node))
                elif target_queue:
                    node = target_queue.popleft()
                    if len(target_visited[node]) <= 4:
                        tasks.append(fetch_friends_async(session, node))
                        directions.append(("REVERSE", node))
                else:
                    break
            
            if not tasks:
                log("[ERROR] Search infrastructure exhausted. No reachable connection link exists.")
                break

            # Fire the entire batch over the async loop simultaneously
            log(f"[EVENT-LOOP] Executing bundle of {len(tasks)} parallel tracking frames...")
            results = await asyncio.gather(*tasks)
            api_calls += len(tasks)
            status_placeholder.info(f"API Calls Dispatched: {api_calls} | Nodes Mapped: {len(start_visited) + len(target_visited)}")
            
            rate_limit_tripped = False

            # Process responses instantly
            for (direction, parent_node), (node_id, friends, hit_429) in zip(directions, results):
                if hit_429:
                    rate_limit_tripped = True
                    if direction == "FORWARD":
                        start_queue.appendleft(parent_node)
                    else:
                        target_queue.appendleft(parent_node)
                    continue
                
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
                
            if rate_limit_tripped:
                log("[CRITICAL 429] IP Address throttled by target host. Pausing Event-Loop for 60s...")
                for i in range(60, 0, -1):
                    status_placeholder.warning(f"Throttling Cool Down: {i}s remaining... Hook up proxies to eliminate this wait.")
                    await asyncio.sleep(1)
                continue

            # Tiny adaptive sleep to let Streamlit paint UI steps smoothly
            await asyncio.sleep(0.05)

        # Resolve usernames asynchronously at the end
        if path_found:
            clean_chain = []
            for u in final_chain:
                if not clean_chain or clean_chain[-1] != u:
                    clean_chain.append(u)
                    
            log(f"[SUCCESS] Intercept chain confirmed. Resolving public handles...")
            names = await resolve_usernames_async(session, clean_chain)
            display = [names.get(uid, f"UID:{uid}") for uid in clean_chain]
            
            st.success("### 🎯 Verified Graph Sequence Map")
            st.info(" ➔ ".join(f"**{n}**" for n in display))
            st.session_state.running = False

# --- Trigger Handler ---
if start_btn and s_input.isdigit() and t_input.isdigit():
    st.session_state.running = True
    st.session_state.logs = ["[SYSTEM] Initializing Async IO Event Loop Architecture..."]
    
    # Safe Streamlit async wrapper execution
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_engine(int(s_input), int(t_input), batch_size))
