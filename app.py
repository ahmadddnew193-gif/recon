import streamlit as st
import requests
import time
from collections import deque

st.set_page_config(page_title="Lightning Pathfinder", layout="centered")

st.title("⚡ Rapid Meet-in-the-Middle Pathfinder")
st.write("Uses a Bidirectional Search algorithm to locate paths to famous users in under 5 minutes.")

# --- Initialize Advanced Session States ---
if "engine_active" not in st.session_state:
    st.session_state.engine_active = False
if "start_queue" not in st.session_state:
    st.session_state.start_queue = None
if "target_queue" not in st.session_state:
    st.session_state.target_queue = None
if "start_visited" not in st.session_state:
    st.session_state.start_visited = {}
if "target_visited" not in st.session_state:
    st.session_state.target_visited = {}
if "total_requests" not in st.session_state:
    st.session_state.total_requests = 0
if "path_found" not in st.session_state:
    st.session_state.path_found = False
if "final_chain" not in st.session_state:
    st.session_state.final_chain = []

# --- API Layer ---
def fetch_friends_persistent(user_id):
    url = f"https://friends.roblox.com/v1/users/{user_id}/friends"
    try:
        response = requests.get(url)
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
        response = requests.post(url, json={"userIds": id_list, "excludeBannedUsers": False})
        if response.status_code == 200:
            return {u["id"]: u["name"] for u in response.json().get("data", [])}
        return {}
    except Exception:
        return {}

# --- User UI Controls ---
col1, col2 = st.columns(2)
start_input = col1.text_input("Starting User ID (You):", "", disabled=st.session_state.engine_active)
target_input = col2.text_input("Target User ID:", "", disabled=st.session_state.engine_active)

delay = st.slider("Politeness Delay (seconds):", 0.3, 2.0, 0.7, step=0.1)
max_total_depth = st.slider("Max Combined Path Length (Layers):", 2, 8, 4)

# --- Control Buttons ---
if not st.session_state.engine_active:
    if st.button("🚀 Initiate Rapid Traversal", use_container_width=True):
        if start_input.isdigit() and target_input.isdigit():
            s_id = int(start_input)
            t_id = int(target_input)
            
            with st.spinner("Initializing dual-ended graph pipelines..."):
                # Seed Start Side
                s_friends, s_429 = fetch_friends_persistent(s_id)
                st.session_state.total_requests += 1
                
                if s_429:
                    st.error("Roblox API rate limited the initialization. Wait a moment and retry.")
                    st.stop()
                
                st.session_state.start_visited = {s_id: [s_id]}
                st.session_state.start_queue = deque([s_id])
                for f in s_friends:
                    st.session_state.start_visited[f] = [s_id, f]
                    st.session_state.start_queue.append(f)
                
                # Seed Target Side
                t_friends, t_429 = fetch_friends_persistent(t_id)
                st.session_state.total_requests += 1
                
                st.session_state.target_visited = {t_id: [t_id]}
                st.session_state.target_queue = deque([t_id])
                
                if t_friends:
                    for f in t_friends:
                        st.session_state.target_visited[f] = [t_id, f]
                        st.session_state.target_queue.append(f)
                
                # Check for immediate match
                common = set(st.session_state.start_visited.keys()) & set(st.session_state.target_visited.keys())
                if common:
                    intersection_node = common.pop()
                    st.session_state.final_chain = st.session_state.start_visited[intersection_node] + st.session_state.target_visited[intersection_node][::-1][1:]
                    st.session_state.path_found = True
                
                st.session_state.target_id = t_id
                st.session_state.start_id = s_id
                st.session_state.engine_active = True
                st.rerun()
else:
    if st.button("🛑 Force Stop & Clear Engine", use_container_width=True):
        st.session_state.engine_active = False
        st.session_state.start_queue = None
        st.session_state.target_queue = None
        st.session_state.path_found = False
        st.session_state.final_chain = []
        st.rerun()

# --- Core Processing Bidirectional Engine Loop ---
if st.session_state.engine_active and not st.session_state.path_found:
    status_box = st.empty()
    direction_flag = "start"
    nodes_to_process = 15
    
    while (st.session_state.start_queue or st.session_state.target_queue) and nodes_to_process > 0:
        nodes_to_process -= 1
        
        if len(st.session_state.start_queue) <= len(st.session_state.target_queue) and st.session_state.start_queue:
            direction_flag = "start"
            current_node = st.session_state.start_queue.popleft()
            current_path = st.session_state.start_visited[current_node]
        elif st.session_state.target_queue:
            direction_flag = "target"
            current_node = st.session_state.target_queue.popleft()
            current_path = st.session_state.target_visited[current_node]
        else:
            continue
            
        if len(current_path) > (max_total_depth // 2) + 1:
            continue
            
        st.session_state.total_requests += 1
        status_box.info(f"⚡ Scanning Node: {current_node} | Direction: Outward from {direction_flag.upper()} | API Count: {st.session_state.total_requests}")
        
        friends, hit_429 = fetch_friends_persistent(current_node)
        
        if hit_429:
            if direction_flag == "start":
                st.session_state.start_queue.appendleft(current_node)
            else:
                st.session_state.target_queue.appendleft(current_node)
                
            st.error("🚨 Rate Limit Hit (429). Automating Wait Sequence...")
            countdown_bar = st.progress(0)
            for i in range(60, 0, -1):
                status_box.warning(f"⏳ Cooling down... Resuming automated pipeline in {i} seconds.")
                countdown_bar.progress((60 - i) / 60)
                time.sleep(1)
            st.rerun()
            
        for friend_id in friends:
            if direction_flag == "start":
                if friend_id in st.session_state.target_visited:
                    target_branch = st.session_state.target_visited[friend_id]
                    st.session_state.final_chain = current_path + target_branch[::-1]
                    st.session_state.path_found = True
                    break
                if friend_id not in st.session_state.start_visited:
                    st.session_state.start_visited[friend_id] = current_path + [friend_id]
                    st.session_state.start_queue.append(friend_id)
            else:
                if friend_id in st.session_state.start_visited:
                    start_branch = st.session_state.start_visited[friend_id]
                    st.session_state.final_chain = start_branch + current_path[::-1]
                    st.session_state.path_found = True
                    break
                if friend_id not in st.session_state.target_visited:
                    st.session_state.target_visited[friend_id] = current_path + [friend_id]
                    st.session_state.target_queue.append(friend_id)
                    
        if st.session_state.path_found:
            break
            
        time.sleep(delay)

    if st.session_state.path_found:
        st.rerun()
    elif st.session_state.engine_active and not st.session_state.start_queue and not st.session_state.target_queue:
        st.error(f"Search complete. No pathways connect these users within {max_total_depth} layers.")
    elif st.session_state.engine_active:
        st.rerun()

# --- Render Results Outside the Loop ---
if st.session_state.path_found:
    st.success(f"🎯 Connection Map Found Rapidly inside {st.session_state.total_requests} API queries!")
    
    clean_chain = []
    for uid in st.session_state.final_chain:
        if uid not in clean_chain:
            clean_chain.append(uid)
            
    with st.spinner("Resolving username handles across network maps..."):
        names = resolve_usernames(clean_chain)
        
    display_path = [names.get(uid, f"User {uid}") for uid in clean_chain]
    st.write("### 🏁 Verified Connection Chain:")
    st.info(" ➔ ".join(f"**{name}**" for name in display_path))
    
    if st.button("Clear Engine Cache and Start New Search"):
        st.session_state.engine_active = False
        st.session_state.start_queue = None
        st.session_state.target_queue = None
        st.session_state.path_found = False
        st.session_state.final_chain = []
        st.rerun()

# --- Sidebar Realtime Monitor ---
st.sidebar.header("📊 Engine Health")
st.sidebar.metric("API Requests Sent", st.session_state.total_requests)
st.sidebar.metric("Your Front Base Nodes", len(st.session_state.start_queue) if st.session_state.start_queue else 0)
st.sidebar.metric("Target Capture Base Nodes", len(st.session_state.target_queue) if st.session_state.target_queue else 0)
st.sidebar.metric("Total Mapped Users", len(st.session_state.start_visited) + len(st.session_state.target_visited) if ("start_visited" in st.session_state and "target_visited" in st.session_state) else 0)
