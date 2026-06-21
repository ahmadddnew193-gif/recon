import os
import json
import streamlit as st
from huggingface_hub import HfApi, snapshot_download

# --- CONFIGURATION ---
HF_TOKEN = st.secrets.get("HF_TOKEN")
REPO_ID = st.secrets.get("HF_REPO_ID")
LOCAL_DATA_DIR = "scraped_chunks"

# Ensure the local data directory exists inside the Streamlit instance
os.makedirs(LOCAL_DATA_DIR, exist_ok=True)

# --- DATABASE LOGIC (SHARDING ENGINE) ---

@st.cache_resource
def sync_database_from_cloud():
    """Downloads the database folder from Hugging Face on application startup."""
    if not HF_TOKEN or not REPO_ID:
        st.warning("⚠️ Cloud tokens missing in secrets.toml. Operating in Local-Only Mode.")
        return False
    try:
        with st.spinner("Synchronizing database from Hugging Face Hub..."):
            # snapshot_download pulls down the entire folder system efficiently
            snapshot_download(
                repo_id=REPO_ID,
                repo_type="dataset",
                token=HF_TOKEN,
                local_dir=LOCAL_DATA_DIR
            )
        st.toast("✅ Database synchronized successfully!", icon="🔥")
        return True
    except Exception as e:
        st.error(f"Cloud Sync failed: {e}. Starting fresh locally.")
        return False

def get_shard_path(user_id: str) -> str:
    """
    Deterministically routes a Roblox User ID to 1 of 100 sub-files.
    This prevents memory spikes by keeping file reads tiny.
    """
    try:
        # Base the shard index on the last two digits of the user ID
        shard_id = int(user_id) % 100
    except ValueError:
        # Fallback for alternative string keys
        shard_id = sum(ord(char) for char in user_id) % 100
    return os.path.join(LOCAL_DATA_DIR, f"shard_{shard_id}.json")

def load_shard(file_path: str) -> dict:
    """Safely loads a JSON shard file from disk."""
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

def save_user_profile(user_id: str, profile_data: dict):
    """Saves or updates an individual user within their designated file chunk."""
    file_path = get_shard_path(user_id)
    shard_data = load_shard(file_path)
    
    # Append or update user details
    shard_data[str(user_id)] = profile_data
    
    # Save the isolated chunk back to disk
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(shard_data, f, indent=2)

def query_user_profile(user_id: str) -> dict:
    """Retrieves an indexed user profile instantly without reading other files."""
    file_path = get_shard_path(user_id)
    shard_data = load_shard(file_path)
    return shard_data.get(str(user_id))

def backup_database_to_cloud():
    """Uploads the local chunk structures back up to Hugging Face."""
    if not HF_TOKEN or not REPO_ID:
        st.error("Backup action halted: Missing credentials.")
        return
    
    try:
        api = HfApi()
        with st.spinner("Uploading modified data chunks to Hugging Face..."):
            # upload_folder calculates file hashes and ONLY transfers files
            # that were actually changed or created during your scraping run!
            api.upload_folder(
                folder_path=LOCAL_DATA_DIR,
                repo_id=REPO_ID,
                repo_type="dataset",
                token=HF_TOKEN,
                commit_message="Automated execution batch database sync"
            )
        st.success("🚀 Backup completed! Remote storage synced successfully.")
    except Exception as e:
        st.error(f"Cloud Backup failed: {e}")

# --- INITIALIZATION ---
# Trigger cloud data retrieval immediately upon execution lifecycle entry
sync_database_from_cloud()


# --- STREAMLIT USER INTERFACE ---
st.title("🛡️ Card-Free 100GB Scalable Database App")
st.write("This instance splits operations across 100 managed JSON blocks synced via Hugging Face.")

tab1, tab2 = st.tabs(["Data Manipulation (Scraper Emulator)", "Data Query Engine"])

with tab1:
    st.header("Simulate Incoming Scraped Data")
    
    input_id = st.text_input("Roblox User ID", placeholder="e.g., 1234567")
    input_username = st.text_input("Username", placeholder="e.g., RobloxPlayer")
    input_friends = st.text_area("Friends Array Data (Comma Separated IDs)", placeholder="45, 9821, 10243")
    
    if st.button("Commit Record to Local Storage"):
        if input_id and input_username:
            # Structuring the payload
            friends_list = [f.strip() for f in input_friends.split(",") if f.strip()]
            payload = {
                "username": input_username,
                "friends_count": len(friends_list),
                "connections": friends_list
            }
            
            # Save data locally
            save_user_profile(input_id, payload)
            st.success(f"Added record to local storage cluster: `{get_shard_path(input_id)}`")
        else:
            st.error("Please provide both a User ID and a Username.")

    st.markdown("---")
    st.subheader("Cloud Synchronization Controls")
    st.write("Because the dataset handles file state checks automatically, only changed blocks are pushed.")
    
    if st.button("Backup Changes to Hugging Face Cloud", type="primary"):
        backup_database_to_cloud()

with tab2:
    st.header("Search Profile Records")
    search_id = st.text_input("Enter target User ID for execution lookup:")
    
    if st.button("Execute Indexed Query"):
        if search_id:
            result = query_user_profile(search_id)
            if result:
                st.metric(label="Target Identity Username", value=result["username"])
                st.metric(label="Total Logged Friends", value=result["friends_count"])
                st.write("#### Tracked Structural Meta-Graph:")
                st.json(result["connections"])
            else:
                st.warning(f"No entry recorded for ID '{search_id}' in partition index `{get_shard_path(search_id)}`.")
        else:
            st.error("Please enter a valid query parameters ID.")
