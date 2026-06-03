import streamlit as st
import requests
import time
from collections import deque

st.set_page_config(page_title="Deep Connect Tracer", layout="centered")

st.title("🔗 Unlimited Social Graph Pathfinder")
st.write("A true Breadth-First Search (BFS) network engine using politeness delays.")

# --- API Helper Functions ---
def fetch_friend_ids(user_id):
    """Fetches all friend IDs for a given target user."""
    url = f"https://friends.roblox.com/v1/users/{user_id}/friends"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json().get("data", [])
            return [f["id"] for f in data if not f.get("isDeleted", False)]
        elif response.status_code == 429:
            st.error("🚨 Rate limit hit! Increase the delay slider.")
            return []
        return []
    except Exception:
        return []

def resolve_usernames(id_list):
    """Resolves an ordered chain of user IDs into real names in one batch."""
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

# --- User Interface Components ---
col1, col2 = st.columns(2)
start_input = col1.text_input("Starting User ID (You):", "")
target_input = col2.text_input("Target User ID:", "")

# Performance & Politeness Controls
st.sidebar.header("⚙️ Engine Calibration")
delay = st.sidebar.slider("API Request Delay (Seconds)", 0.1, 2.0, 0.4, step=0.1)
max_depth = st.sidebar.slider("Max Degrees of Separation (Layers)", 1, 3, 2)

if st.button("🚀 Begin Graph Traversal", use_container_width=True):
    if start_input.isdigit() and target_input.isdigit():
        start_id = int(start_input)
        target_id = int(target_input)
        
        if start_id == target_id:
            st.warning("Starting point matches the destination target.")
        else:
            # --- BFS Engine Initialization ---
            # The queue stores tuples of: (Current_Node_ID, Path_Taken_To_Get_Here)
            queue = deque([(start_id, [start_id])])
            visited = set([start_id])
            
            path_found = False
            final_chain = []
            
            # Diagnostic Counters for the UI
            total_requests = 0
            status_container = st.empty()
            
            start_time = time.time()
            
            while queue:
                current_node, path = queue.popleft()
                
                # Enforce the depth circuit-breaker safely
                if len(path) > max_depth:
                    continue
                
                total_requests += 1
                status_container.text(f"⏳ Processing API Request #{total_requests} (Scanning node: {current_node})...")
                
                # 1. Fetch current node's friends
                friends = fetch_friend_ids(current_node)
                time.sleep(delay) # The Politeness Delay
                
                # 2. Destination Validation (Short-circuit match check)
                if target_id in friends:
                    final_chain = path + [target_id]
                    path_found = True
                    break
                
                # 3. Graph Expansion
                for friend_id in friends:
                    if friend_id not in visited:
                        visited.add(friend_id)
                        # Append the friend node along with the updated tracking path history
                        queue.append((friend_id, path + [friend_id]))
            
            # --- Rendering Results ---
            elapsed_time = time.time() - start_time
            status_container.empty()
            
            st.sidebar.metric("Execution Time", f"{elapsed_time:.1f}s")
            st.sidebar.metric("API Calls Dispatched", total_requests)
            
            if path_found:
                st.success(f"🎉 Connection Path Found in {total_requests} steps!")
                with st.spinner("Resolving usernames for final graph visualization..."):
                    names = resolve_usernames(final_chain)
                
                display_path = [names.get(uid, f"User {uid}") for uid in final_chain]
                st.info(" ➔ ".join(f"**{name}**" for name in display_path))
                st.metric("Degrees of Separation", f"{len(final_chain) - 1} Step(s)")
            else:
                st.error(f"No connection path found within {max_depth} degrees of separation.")
                st.info("💡 Try increasing the 'Max Degrees' setting in the sidebar if you are searching a wider network.")
    else:
        st.error("Please provide valid numeric User IDs.")
