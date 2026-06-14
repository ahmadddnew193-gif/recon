import streamlit as st
import requests
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed

st.set_page_config(page_title="Recon Engine: Concurrent", layout="wide")

st.title("⚡ OSINT Graph Reconnaissance (Concurrent Engine)")
st.write("Dispatches multi-threaded API worker pools for maximum live throughput.")

# --- Session State ---
if "logs" not in st.session_state:
    st.session_state.logs = []
if "running" not in st.session_state:
    st.session_state.running = False

# --- Core Request Layer ---
def fetch_friends_worker(user_id):
    """Worker function dispatched inside the thread pool"""
    url = f"https://friends.roblox.com/v1/users/{user_id}/friends"
    # PROXY NOTE: To stop 429s completely, buy a proxy pool and add them here:
    # proxies = {"http": "http://user:pass@proxy_ip:port", "https": "http://user:pass@proxy_ip:port"}
    try:
        response = requests.get(url, timeout=4)
        if response.status_code == 200:
            data = response.json().get("data", [])
            return user_id, [f["id"] for f in data if not f.get("isDeleted", False)], False
        elif response.status_code == 429:
            return user_id, [], True
        return user_id, [], False
    except Exception:
        return user_id, [], False

def resolve_usernames(id_list):
    if not id_list:
        return {}
    url = "https://users.roblox.com/v1/users"
    try:
        response = requests.post(url, json={"userIds": id_list, "excludeBannedUsers": False}, timeout=5)
        if response.status_code == 200:
            return {u["id"]: u["name"] for u in response.json().get("data", [])}
        return {}
    except Exception:
        return {}

# --- UI Layout ---
col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("Target Configuration")
    s_input = st.text_input("Start ID:", "1703896246")
    t_input = st.text_input("Target ID:", "140671171")
    concurrency = st.slider("Worker Threads (Simultaneous Calls):", 2, 10, 5)
    
    start_btn = st.button("🚀 Launch Swarm Trace", use_container_width=True, type="primary")
    stop_btn = st.button("🛑 Kill Swarm", use_container_width=True)

with col2:
    st.subheader("Live Swarm Console")
    console_placeholder = st.empty()
    status_placeholder = st.empty()

if stop_btn:
    st.session_state.logs = []
    st.session_state.running = False
    st.rerun()

# --- Multi-Threaded Engine Loop ---
if start_btn and s_input.isdigit() and t_input.isdigit():
    st.session_state.running = True
    st.session_state.logs = ["[SYSTEM] Initializing Concurrent Multi-Threaded Swarm..."]
    
    s_id, t_id = int(s_input), int(t_input)
    
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

    log(f"[INFO] Deploying threads across nodes. Target: {t_id}")

    while st.session_state.running:
        # Collect batch of nodes to scan simultaneously
        batch_nodes = []
        batch_directions = []
        
        while len(batch_nodes) < concurrency:
            if start_queue and (not target_queue or len(start_queue) <= len(target_queue)):
                node = start_queue.popleft()
                if len(start_visited[node]) <= 4:  # Depth check
                    batch_nodes.append(node)
                    batch_directions.append("FORWARD")
            elif target_queue:
                node = target_queue.popleft()
                if len(target_visited[node]) <= 4:
                    batch_nodes.append(node)
                    batch_directions.append("REVERSE")
            else:
                break
                
        if not batch_nodes:
            if not start_queue and not target_queue:
                log("[ERROR] Search queues empty. No path discovered.")
            break

        # Dispatch the thread pool batch
        log(f"[SWARM] Dispatching batch of {len(batch_nodes)} nodes concurrently...")
        rate_limit_triggered = False
        
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = {executor.submit(fetch_friends_worker, nid): (nid, dir_flag) for nid, dir_flag in zip(batch_nodes, batch_directions)}
            
            for future in as_completed(futures):
                nid, dir_flag = futures[future]
                node_id, friends, hit_429 = future.result()
                api_calls += 1
                
                if hit_429:
                    rate_limit_triggered = True
                    # Put it back on the queue
                    if dir_flag == "FORWARD":
                        start_queue.appendleft(node_id)
                    else:
                        target_queue.appendleft(node_id)
                    continue
                    
                # Process discovered networks
                current_path = start_visited[node_id] if dir_flag == "FORWARD" else target_visited[node_id]
                
                for friend in friends:
                    if dir_flag == "FORWARD":
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

        status_placeholder.info(f"API Calls Dispatched: {api_calls} | Mapped Tree Size: {len(start_visited) + len(target_visited)}")
        
        if path_found:
            break
            
        if rate_limit_triggered:
            log("[WARNING] HTTP 429 detected by swarm. Pausing network pool for 60s...")
            for i in range(60, 0, -1):
                status_placeholder.warning(f"Swarm Cool Down: {i} seconds remaining...")
                time.sleep(1)
            continue

        time.sleep(0.2) # Small break between parallel burst cycles

    # Render Results
    if path_found:
        clean_chain = []
        for u in final_chain:
            if not clean_chain or clean_chain[-1] != u:
                clean_chain.append(u)
                
        log(f"[SUCCESS] Intercept track complete. Resolving names...")
        names = resolve_usernames(clean_chain)
        display = [names.get(uid, f"UID:{uid}") for uid in clean_chain]
        
        st.success("### 🎯 Verified Graph Sequence Map")
        st.info(" ➔ ".join(f"**{n}**" for n in display))
        st.session_state.running = False
