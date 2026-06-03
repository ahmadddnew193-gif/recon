import streamlit as st
import requests
import time

st.set_page_config(page_title="BloxConnect Tracer", layout="centered")

st.title("🔗 Social Graph Path Finder")
st.write("Trace the exact chain of mutual connections linking any two players together.")

# 1. Helper Function: Fetch Friend IDs
def fetch_friend_ids(user_id):
    """Fetches up to the first 200 friend IDs for a given user."""
    url = f"https://friends.roblox.com/v1/users/{user_id}/friends"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            friends_data = response.json().get("data", [])
            # Filter out deleted accounts, return a clean list of IDs
            return [friend["id"] for friend in friends_data if not friend.get("isDeleted", False)]
        return []
    except Exception:
        return []

# 2. Helper Function: Convert IDs to Real Usernames efficiently
def resolve_usernames(id_list):
    """Takes a list of IDs and resolves usernames in a single batch POST request."""
    if not id_list:
        return {}
    url = "https://users.roblox.com/v1/users"
    payload = {"userIds": id_list, "excludeBannedUsers": False}
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            user_data = response.json().get("data", [])
            return {user["id"]: user["name"] for user in user_data}
        return {}
    except Exception:
        return {}

# --- UI Layout Elements ---
col1, col2 = st.columns(2)
start_id = col1.text_input("Starting User ID (You):", value="")
target_id = col2.text_input("Target User ID (e.g., 156 for Builderman):", value="")

if st.button("🗺️ Trace Connection Path", use_container_width=True):
    if start_id.isdigit() and target_id.isdigit():
        s_id = int(start_id)
        t_id = int(target_id)
        
        if s_id == t_id:
            st.warning("The starting player and the target player are the same user!")
        else:
            with st.spinner("Analyzing public friendship graphs..."):
                
                # Step 1: Scan Tier 1 (Direct Friends)
                st.write("🔍 Scanning your direct friend list...")
                tier_1_friends = fetch_friend_ids(s_id)
                
                path_found = False
                final_chain = []
                
                if t_id in tier_1_friends:
                    # Direct Match Found immediately
                    final_chain = [s_id, t_id]
                    path_found = True
                else:
                    # Step 2: Scan Tier 2 (Friends of Friends)
                    st.write("🔄 Target not found in direct friends. Scanning mutual connections...")
                    
                    # To prevent hitting rate limits, we limit scanning to the top 30 friends
                    scan_limit = tier_1_friends[:30]
                    
                    for index, mutual_id in enumerate(scan_limit):
                        # Add a tiny internal delay to stay safe from API rate limits
                        time.sleep(0.1)
                        
                        sub_friends = fetch_friend_ids(mutual_id)
                        if t_id in sub_friends:
                            final_chain = [s_id, mutual_id, t_id]
                            path_found = True
                            break
                
                # Render results to the website interface
                if path_found:
                    st.success("🎉 Connection Path Discovered!")
                    
                    # Resolve IDs to readable names for the web display
                    name_map = resolve_usernames(final_chain)
                    
                    # Format output visuals
                    display_chain = [name_map.get(uid, f"User {uid}") for uid in final_chain]
                    
                    st.subheader("🎯 Path Blueprint:")
                    # Display the steps cleanly across the screen
                    st.info(" ➔ ".join(f"**{name}**" for name in display_chain))
                    st.metric(label="Degrees of Separation", value=f"{len(final_chain) - 1} Step(s) Away")
                else:
                    st.error("No close connection found within a 2-degree limit, or the target's friend settings are private.")
                    st.caption("Note: To avoid security rate-limiting on web requests, this scanner checks up to 30 mutual nodes.")
    else:
        st.error("Please ensure both inputs are numeric Roblox User IDs.")
