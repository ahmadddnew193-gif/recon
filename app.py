import streamlit as st
import requests
import time
from collections import deque

st.set_page_config(page_title="Auto-Resuming Pathfinder", layout="centered")

st.title("🛡️ Autonomous Graph Pathfinder")
st.write("This engine automatically handles rate limits. If blocked, it waits 60s and resumes on its own.")

# --- Initialize Session States ---
if "bfs_queue" not in st.session_state:
    st.session_state.bfs_queue = None
if "visited" not in st.session_state:
    st.session_state.visited = set()
if "total_requests" not in st.session_state:
    st.session_state.total_requests = 0
if "path_found" not in st.session_state:
    st.session_state.path_found = False
if "final_chain" not in st.session_state:
    st.session_state.final_chain = []

# --- API Fetch with Error Handling ---
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
start_input = col1.text_input("Starting User ID:", "", disabled=st.session_state.bfs_queue is not None)
target_input = col2.text_input("Target User ID:", "", disabled=st.session_state.bfs_queue is not None)

delay = st.slider("Request Delay (seconds):", 0.5, 3.0, 1.2, step=0.1)
max_depth = st.slider("Max Search Layers (Degrees of Separation):", 1, 8, 4)

# --- Button logic ---
if st.session_state.bfs_queue is None:
    if st.button("🚀 Start Deep Traversal", use_container_width=True):
        if start_input.isdigit() and target_input.isdigit():
            s_id = int(start_input)
            t_id = int(target_input)
            st.session_state.bfs_queue = deque([(s_id, [s_id])])
            st.session_state.visited = {s_id}
            st.session_state.total_requests = 0
            st.session_state.path_found = False
            st.session_state.target_id = t_id
            st.rerun()
else:
    if st.button("🛑 Stop & Reset Engine", use_container_width=True):
        st.session_state.bfs_queue = None
        st.rerun()

# --- Core Processing Engine Loop ---
if st.session_state.bfs_queue and not st.session_state.path_found:
    status_box = st.empty()
    
    # Process batch to prevent Streamlit timeout
    nodes_to_process_this_turn = 15 
    
    while st.session_state.bfs_queue and nodes_to_process_this_turn > 0:
        current_node, path = st.session_state.bfs_queue.popleft()
        
        if len(path) > max_depth:
            continue
            
        st.session_state.total_requests += 1
        nodes_to_process_this_turn -= 1
        
        status_box.info(f"🔍 Currently Scanning: {current_node} | Total Requests: {st.session_state.total_requests}")
        
        friends, hit_429 = fetch_friends_persistent(current_node)
        
        if hit_429:
            # Put the user back in the front of the queue
            st.session_state.bfs_queue.appendleft((current_node, path))
            
            st.error("🚨 Rate Limit Hit (429). Automating Wait Sequence...")
            countdown_bar = st.progress(0)
            for i in range(60, 0, -1):
                status_box.warning(f"⏳ Cooling down... Resuming in {i} seconds.")
                countdown_bar.progress((60 - i) / 60)
                time.sleep(1)
            st.rerun() # Refresh and try the exact same node again
            
        # Success logic
        if st.session_state.target_id in friends:
            st.session_state.final_chain = path + [st.session_state.target_id]
            st.session_state.path_found = True
            break
            
        # Expand network
        for friend_id in friends:
            if friend_id not in st.session_state.visited:
                st.session_state.visited.add(friend_id)
                st.session_state.bfs_queue.append((friend_id, path + [friend_id]))
        
        time.sleep(delay)

    # Result Handling
    if st.session_state.path_found:
        st.success(f"🎉 Path Found! Processed {st.session_state.total_requests} nodes.")
        with st.spinner("Resolving Usernames..."):
            names = resolve_usernames(st.session_state.final_chain)
        
        display_path = [names.get(uid, f"User {uid}") for uid in st.session_state.final_chain]
        st.write("### Connection Chain:")
        st.info(" ➔ ".join(f"**{name}**" for name in display_path))
        
    elif not st.session_state.bfs_queue:
        st.error(f"Search Finished. No path found within {max_depth} layers.")
    else:
        # Auto-refresh for next batch
        st.rerun()

# --- Sidebar Monitor ---
st.sidebar.header("📊 Engine Health")
st.sidebar.metric("API Calls", st.session_state.total_requests)
st.sidebar.metric("Queue Size", len(st.session_state.bfs_queue) if st.session_state.bfs_queue else 0)
st.sidebar.metric("Discovered Nodes", len(st.session_state.visited))
