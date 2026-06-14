import streamlit as st
import requests
import time
from collections import deque

st.set_page_config(page_title="Recon Engine: Fast Path", layout="wide")

st.title("⚡ OSINT Graph Reconnaissance")
st.write("Live bidirectional API traversal. Handles hidden or private profiles automatically.")

# --- Session State ---
if "logs" not in st.session_state:
    st.session_state.logs = []
if "running" not in st.session_state:
    st.session_state.running = False

# --- Helpers ---
def fetch_friends(user_id):
    url = f"https://friends.roblox.com/v1/users/{user_id}/friends"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json().get("data", [])
            return [f["id"] for f in data if not f.get("isDeleted", False)], False
        elif response.status_code == 429:
            return [], True
        return [], False
    except Exception:
        return [], False

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
    st.subheader("Target Parameters")
    s_input = st.text_input("Start ID (You):", "1703896246")
    t_input = st.text_input("Target ID (Kreekcraft):", "140671171")
    delay = st.slider("API Delay (Seconds):", 0.1, 2.0, 0.5, step=0.1)
    
    start_btn = st.button("🚀 Execute Trace", use_container_width=True, type="primary")
    stop_btn = st.button("🛑 Clear Engine", use_container_width=True)

with col2:
    st.subheader("Live Console Output")
    console_placeholder = st.empty()
    status_placeholder = st.empty()

# --- Engine Logic ---
if stop_btn:
    st.session_state.logs = []
    st.session_state.running = False
    st.rerun()

if start_btn and s_input.isdigit() and t_input.isdigit():
    st.session_state.running = True
    st.session_state.logs = ["[SYSTEM] Initializing Bidirectional Engine..."]
    
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
        if len(st.session_state.logs) > 50:
            st.session_state.logs.pop(0)
        console_placeholder.code("\n".join(st.session_state.logs), language="bash")

    log(f"[INFO] Seeding Root Nodes: {s_id} <---> {t_id}")

    # Core Execution Loop
    while st.session_state.running:
        # FIX: Robust directional scheduling logic. 
        # Prevents engine from quitting if target queue drops to zero due to privacy settings.
        if start_queue and (not target_queue or len(start_queue) <= len(target_queue)):
            current_node = start_queue.popleft()
            current_path = start_visited[current_node]
            direction = "FORWARD"
        elif target_queue:
            current_node = target_queue.popleft()
            current_path = target_visited[current_node]
            direction = "REVERSE"
        else:
            log("[ERROR] Search space exhausted. No structural path exists between targets.")
            break

        # Max layer safety limiter
        if len(current_path) > 4:
            continue

        log(f"[{direction}] Scanning UID: {current_node} | Depth: {len(current_path)}")
        api_calls += 1
        status_placeholder.info(f"API Calls Dispatched: {api_calls}")

        friends, hit_limit = fetch_friends(current_node)

        if hit_limit:
            log(f"[WARNING] HTTP 429 Rate Limit Hit. Halting pipeline for 60s...")
            if direction == "FORWARD":
                start_queue.appendleft(current_node)
            else:
                target_queue.appendleft(current_node)
                
            for i in range(60, 0, -1):
                status_placeholder.warning(f"Rate limit cooldown: {i} seconds remaining...")
                time.sleep(1)
            continue 

        # Evaluate intersections cleanly
        for friend in friends:
            if direction == "FORWARD":
                if friend in target_visited:
                    t_path = target_visited[friend]
                    final_chain = current_path + t_path[::-1]
                    path_found = True
                    break
                if friend not in start_visited:
                    start_visited[friend] = current_path + [friend]
                    start_queue.append(friend)
            else:
                if friend in start_visited:
                    s_path = start_visited[friend]
                    final_chain = s_path + current_path[::-1]
                    path_found = True
                    break
                if friend not in target_visited:
                    target_visited[friend] = current_path + [friend]
                    target_queue.append(friend)

        if path_found:
            break

        time.sleep(delay)

    # Resolution Splicing
    if path_found:
        clean_chain = []
        for u in final_chain:
            if not clean_chain or clean_chain[-1] != u:
                clean_chain.append(u)
                
        log(f"[SUCCESS] Target link acquired in {api_calls} queries. Resolving user data handles...")
        names = resolve_usernames(clean_chain)
        
        display = [names.get(uid, f"UID:{uid}") for uid in clean_chain]
        
        st.success("### 🎯 Verified Graph Sequence Map")
        st.info(" ➔ ".join(f"**{n}**" for n in display))
        st.session_state.running = False
