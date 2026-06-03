import streamlit as st
import requests
import time
from collections import deque

st.set_page_config(page_title="Unstoppable Pathfinder", layout="centered")

st.title("🛡️ Persistent Graph Pathfinder")
st.write("This engine saves its state. If rate-limited, you can pause and resume without losing progress.")

# --- Initialize Session States ---
# This keeps data alive even when the page re-renders or hits an error
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
            return [], True  # Trigger Rate Limit Flag
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

delay = st.slider("Delay between API requests (seconds):", 0.5, 3.0, 1.5, step=0.1)
max_depth = st.slider("Max Layers to Search:", 1, 4, 3)

# --- Button logic ---
button_placeholder = st.empty()

# If we haven't started a search yet, show "Start"
if st.session_state.bfs_queue is None:
    if button_placeholder.button("🚀 Start Deep Traversal", use_container_width=True):
        if start_input.isdigit() and target_input.isdigit():
            s_id = int(start_input)
            t_id = int(target_input)
            
            # Setup the engine state
            st.session_state.bfs_queue = deque([(s_id, [s_id])])
            st.session_state.visited = {s_id}
            st.session_state.total_requests = 0
            st.session_state.path_found = False
            st.session_state.target_id = t_id
            st.rerun()
else:
    # If a search is currently paused or active, show "Resume"
    if button_placeholder.button("🔄 Resume Search Pipeline", use_container_width=True):
        st.session_state.rate_limited = False # Clear the flag to try again
        st.rerun()

# --- Core Processing Engine Loop ---
if st.session_state.bfs_queue and not st.session_state.path_found:
    status_box = st.empty()
    progress_bar = st.progress(0)
    
    rate_limit_tripped = False
    
    # Process up to 20 nodes per button click to prevent web timeouts
    nodes_to_process_this_turn = 20 
    
    while st.session_state.bfs_queue and nodes_to_process_this_turn > 0:
        current_node, path = st.session_state.bfs_queue.popleft()
        
        # Stop if we exceed maximum depth limits
        if len(path) > max_depth:
            continue
            
        st.session_state.total_requests += 1
        nodes_to_process_this_turn -= 1
        
        status_box.text(f"Scanning node: {current_node} | Total API calls: {st.session_state.total_requests}")
        
        # Run API Fetch
        friends, hit_429 = fetch_friends_persistent(current_node)
        time.sleep(delay)
        
        if hit_429:
            # Re-queue the current node so we don't lose it!
            st.session_state.bfs_queue.appendleft((current_node, path))
            rate_limit_tripped = True
            break
            
        # Target Match Checking
        if st.session_state.target_id in friends:
            st.session_state.final_chain = path + [st.session_state.target_id]
            st.session_state.path_found = True
            break
            
        # Queue expansion
        for friend_id in friends:
            if friend_id not in st.session_state.visited:
                st.session_state.visited.add(friend_id)
                st.session_state.bfs_queue.append((friend_id, path + [friend_id]))

    # Loop evaluation
    if st.session_state.path_found:
        st.success(f"🎉 Connection Located successfully after {st.session_state.total_requests} lookups!")
        with st.spinner("Resolving user profiles..."):
            names = resolve_usernames(st.session_state.st.session_state.final_chain if "final_chain" in st.session_state else st.session_state.final_chain)
            # Fallback mapping context
            names = resolve_usernames(st.session_state.final_chain)
        display_path = [names.get(uid, f"User {uid}") for uid in st.session_state.final_chain]
        st.info(" ➔ ".join(f"**{name}**" for name in display_path))
        
        # Reset button to allow clear operations
        if st.button("Clear Engine Cache"):
            st.session_state.bfs_queue = None
            st.rerun()
            
    elif rate_limit_tripped:
        st.error("🚨 Roblox API Rate Limit Hit (HTTP 429)!")
        st.warning("Your current progress has been saved securely in the dashboard state. Please wait 60 seconds for the API limits to clear, then click 'Resume Search Pipeline' above.")
        
    elif not st.session_state.bfs_queue:
        st.error(f"Search concluded. No active connections found within {max_depth} layers.")
        if st.button("Reset Engine"):
            st.session_state.bfs_queue = None
            st.rerun()
    else:
        # If we finished our 20-node batch safely but haven't hit a wall or target, auto-refresh to keep going
        st.rerun()

# --- Sidebar Realtime Monitor ---
st.sidebar.header("📊 Live Engine Telemetry")
st.sidebar.metric("Total API Calls Run", st.session_state.total_requests)
st.sidebar.metric("Nodes Awaiting Scan", len(st.session_state.bfs_queue) if st.session_state.bfs_queue else 0)
st.sidebar.metric("Unique Profiles Mapped", len(st.session_state.visited))
