import streamlit as st
import asyncio
import aiohttp
import json
import os
import sqlite3
import random
import time
import pandas as pd
from huggingface_hub import HfApi, hf_hub_download

st.set_page_config(page_title="Recon Engine: Ultra Core", layout="wide")

DB_FILE = "roblox_graph_map.db"
HF_TOKEN = st.secrets.get("HF_TOKEN")
HF_REPO_ID = st.secrets.get("HF_REPO_ID")

DEFAULT_PROXIES = """38.154.203.95:5863:zwgfezql:u1o2humd1hr8
198.105.121.200:6462:zwgfezql:u1o2humd1hr8
64.137.96.74:6641:zwgfezql:u1o2humd1hr8
209.127.138.10:5784:zwgfezql:u1o2humd1hr8
38.154.185.97:6370:zwgfezql:u1o2humd1hr8
84.247.60.125:6095:zwgfezql:u1o2humd1hr8
142.111.67.146:5611:zwgfezql:u1o2humd1hr8"""

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS graph (
            uid TEXT PRIMARY KEY,
            friends TEXT,
            last_updated REAL
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def load_all_uids():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT uid FROM graph")
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows]

def get_db_connection():
    return sqlite3.connect(DB_FILE)

def parse_proxies(raw_text):
    lines = [l.strip() for l in raw_text.strip().split("\n") if l.strip()]
    formatted = []
    for line in lines:
        parts = line.split(":")
        if len(parts) == 4:
            ip, port, user, pwd = parts
            formatted.append(f"http://{user}:{pwd}@{ip}:{port}")
        elif len(parts) == 2:
            ip, port = parts
            formatted.append(f"http://{ip}:{port}")
    return formatted

def sync_download_from_hf():
    if not HF_TOKEN or not HF_REPO_ID:
        return False, "HF credentials missing in st.secrets"
    try:
        api = HfApi(token=HF_TOKEN)
        files = api.list_repo_files(repo_id=HF_REPO_ID, repo_type="dataset")
        if DB_FILE in files:
            path = hf_hub_download(repo_id=HF_REPO_ID, filename=DB_FILE, repo_type="dataset", token=HF_TOKEN)
            import shutil
            shutil.copy(path, DB_FILE)
            return True, "Database synced down successfully from Hugging Face!"
        else:
            return False, "Database file not found in HF repository."
    except Exception as e:
        return False, f"Sync Down Failed: {str(e)}"

def sync_upload_to_hf():
    if not HF_TOKEN or not HF_REPO_ID:
        return False, "HF credentials missing in st.secrets"
    if not os.path.exists(DB_FILE):
        return False, "Local database file does not exist to upload."
    try:
        api = HfApi(token=HF_TOKEN)
        api.upload_file(
            path_or_fileobj=DB_FILE,
            path_in_repo=DB_FILE,
            repo_id=HF_REPO_ID,
            repo_type="dataset"
        )
        return True, "Database pushed up successfully to Hugging Face!"
    except Exception as e:
        return False, f"Sync Up Failed: {str(e)}"

async def fetch_friends(session, uid, proxy_list, retries=2):
    url = f"https://friends.roblox.com/v1/users/{uid}/friends"
    for attempt in range(retries + 1):
        proxy = random.choice(proxy_list) if proxy_list else None
        try:
            async with session.get(url, proxy=proxy, timeout=6) as response:
                if response.status == 200:
                    data = await response.json()
                    return [str(f['id']) for f in data.get('data', [])]
                elif response.status == 403:
                    await asyncio.sleep(0.5)
                elif response.status == 429:
                    await asyncio.sleep(1.5)
        except:
            await asyncio.sleep(0.3)
    return None

async def worker(queue, session, proxy_list, progress_box, stats_box, total_targets):
    processed = 0
    while True:
        uid = await queue.get()
        if uid is None:
            queue.task_done()
            break
        
        friends = await fetch_friends(session, uid, proxy_list)
        conn = get_db_connection()
        c = conn.cursor()
        
        if friends is not None:
            friends_json = json.dumps(friends)
            c.execute("INSERT OR REPLACE INTO graph (uid, friends, last_updated) VALUES (?, ?, ?)",
                      (uid, friends_json, time.time()))
            conn.commit()
            processed += 1
            stats_box.markdown(f"**⚡ Current Batch Performance:** Success response saved for UID `{uid}`.")
        else:
            c.execute("SELECT uid FROM graph WHERE uid=?", (uid,))
            if not c.fetchone():
                c.execute("INSERT OR REPLACE INTO graph (uid, friends, last_updated) VALUES (?, ?, ?)",
                          (uid, "[]", time.time()))
                conn.commit()
            stats_box.markdown(f"**⚠️ Notice:** UID `{uid}` timed out or profile restricted. Saved dummy node.")
            processed += 1
            
        conn.close()
        progress_box.progress(min(processed / max(total_targets, 1), 1.0), text=f"Crawling Node Array Graph Queue: {processed}/{total_targets}")
        queue.task_done()

async def run_crawler_async(uids_to_scrape, proxies, progress_box, stats_box, concurrency):
    queue = asyncio.Queue()
    for uid in uids_to_scrape:
        await queue.put(uid)
    for _ in range(concurrency):
        await queue.put(None)
        
    async with aiohttp.ClientSession() as session:
        tasks = []
        for _ in range(concurrency):
            task = asyncio.create_task(worker(queue, session, proxies, progress_box, stats_box, len(uids_to_scrape)))
            tasks.append(task)
        await asyncio.gather(*tasks)

def find_shortest_path_db(start_uid, target_uid):
    if start_uid == target_uid:
        return [start_uid]
        
    conn = get_db_connection()
    c = conn.cursor()
    
    queue = [[start_uid]]
    visited = {start_uid}
    
    while queue:
        path = queue.pop(0)
        node = path[-1]
        
        c.execute("SELECT friends FROM graph WHERE uid=?", (node,))
        row = c.fetchone()
        if row and row[0]:
            try:
                friends = json.loads(row[0])
            except:
                friends = []
            for friend in friends:
                if friend == target_uid:
                    conn.close()
                    return path + [target_uid]
                if friend not in visited:
                    visited.add(friend)
                    queue.append(path + [friend])
    conn.close()
    return None

st.title("🛰️ Recon Engine: Ultra Core Graph Mapping")
st.markdown("### Specialized Structural Intelligence Engine for Mapping & Path-Finding")

st.sidebar.header("☁️ Cloud Sync (Hugging Face)")
if st.sidebar.button("⬇️ Pull Database from Cloud", use_container_width=True):
    with st.spinner("Downloading database instance..."):
        success, msg = sync_download_from_hf()
        if success:
            st.sidebar.success(msg)
        else:
            st.sidebar.error(msg)

if st.sidebar.button("⬆️ Push Database to Cloud", use_container_width=True):
    with st.spinner("Uploading local architecture configuration..."):
        success, msg = sync_upload_to_hf()
        if success:
            st.sidebar.success(msg)
        else:
            st.sidebar.error(msg)

# ADDED "Database Management" TAB AT THE END OF THE TABS LIST
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🎯 Targeted Crawler", 
    "📈 Network Infrastructure Explorer", 
    "🔮 Map Simulation Sandbox", 
    "🗄️ Master Node Explorer",
    "🗂️ Database Management"
])

with tab1:
    st.header("Node Discovery & Scan Layer")
    col_inputs, col_proxies = st.columns([2, 1])
    
    with col_inputs:
        input_uids = st.text_area("Input Base Scrape UIDs (Comma or Line Separated):", value="140671171, 1703896246")
        concurrency_slider = st.slider("Asynchronous Concurrency Pool:", min_value=5, max_value=200, value=50, step=5)
        deep_scan = st.checkbox("Deep Scan Layer 2 (Automatically queue all discovered connections)", value=False)
        
    with col_proxies:
        proxy_input = st.text_area("Rotating HTTP Proxies (ip:port:user:pass):", value=DEFAULT_PROXIES, height=180)
        
    if st.button("🚀 Initialize Network Intercept Phase", use_container_width=True):
        raw_uids = [u.strip() for u in input_uids.replace("\n", ",").split(",") if u.strip()]
        parsed_proxies = parse_proxies(proxy_input)
        
        if not raw_uids:
            st.error("Target Matrix Array cannot be blank.")
        else:
            p_box = st.progress(0, text="Initializing Pipeline Queue...")
            s_box = st.empty()
            
            st.subheader("Executing Phase 1 Mapping...")
            asyncio.run(run_crawler_async(raw_uids, parsed_proxies, p_box, s_box, concurrency_slider))
            
            if deep_scan:
                st.subheader("Executing Deep Scan Phase 2 Connection Mapping...")
                conn = get_db_connection()
                c = conn.cursor()
                all_discovered = set()
                for uid in raw_uids:
                    c.execute("SELECT friends FROM graph WHERE uid=?", (uid,))
                    r = c.fetchone()
                    if r and r[0]:
                        try:
                            all_discovered.update(json.loads(r[0]))
                        except:
                            pass
                conn.close()
                
                secondary_targets = list(all_discovered)[:400]
                if secondary_targets:
                    p_box_2 = st.progress(0, text=f"Deep Scan Active: Crawling {len(secondary_targets)} child nodes...")
                    s_box_2 = st.empty()
                    asyncio.run(run_crawler_async(secondary_targets, parsed_proxies, p_box_2, s_box_2, concurrency_slider))
                    
            st.success("🏁 Core Sweep Phase Completed. Matrix Nodes Updated.")

with tab2:
    st.header("Real-Time Database Pathfinding & Extraction")
    col_s, col_t = st.columns(2)
    start_node = col_s.text_input("Source Node Identity (UID):")
    target_node = col_t.text_input("Destination Node Identity (UID):")
    
    if st.button("🎛️ Trace Path Vectors", use_container_width=True):
        if not start_node or not target_node:
            st.error("Both network vertices must be defined.")
        else:
            with st.spinner("Calculating absolute vector tracking route optimization..."):
                route = find_shortest_path_db(start_node.strip(), target_node.strip())
                if route:
                    st.success(f"🎯 Connection Route Discovered via {len(route)-1} Hops!")
                    st.code(" -> ".join(route), language="text")
                else:
                    st.error("🚫 Connection Map Gap: No connection route maps these nodes in the current local cache database.")

with tab3:
    st.header("Virtual Sandbox Engine Data Generator")
    seed_start = st.text_input("Simulate Start ID:", value="1703896246")
    seed_target = st.text_input("Simulate Target ID:", value="140671171")
    profile_volume = st.number_input("Background Density Nodes:", min_value=100, max_value=50000, value=1500)
    generate_btn = st.button("⚡ Execute Mock Seeding", use_container_width=True)
    
    if generate_btn and seed_start.isdigit() and seed_target.isdigit():
        database = {}
        s_id_int, t_id_int = int(seed_start), int(seed_target)
        hub_a, hub_b, hub_c = 999101, 999102, 999103
        database[str(s_id_int)] = [hub_a]
        database[str(hub_a)] = [s_id_int, hub_b]
        database[str(hub_b)] = [hub_a, hub_c]
        database[str(hub_c)] = [hub_b, t_id_int]
        database[str(t_id_int)] = [hub_c]
        
        filler_ids = [random.randint(2000000, 8000000) for _ in range(int(profile_volume))]
        for uid in filler_ids:
            database[str(uid)] = [random.randint(2000000, 8000000) for _ in range(random.randint(2, 8))]
            
        conn = get_db_connection()
        c = conn.cursor()
        for k, v in database.items():
            c.execute("INSERT OR REPLACE INTO graph (uid, friends, last_updated) VALUES (?, ?, ?)",
                      (k, json.dumps([str(x) for x in v]), time.time()))
        conn.commit()
        conn.close()
        st.success(f"Successfully simulated and stored structural connections data matrices for {profile_volume} entities inside local cache.")

with tab4:
    st.header("Node Repository Storage Viewer")
    if st.button("🔄 Refresh Structural Map Repositories View", use_container_width=True):
        conn = get_db_connection()
        df = pd.read_sql_query("SELECT uid, friends, last_updated FROM graph", conn)
        conn.close()
        
        if df.empty:
            st.info("System storage records are empty.")
        else:
            st.metric("Total Active Cached Node Matrix Frameworks", len(df))
            st.dataframe(df, use_container_width=True)

# IMPLEMENTATION OF THE REQUESTED DELETE FEATURES
with tab5:
    st.header("🗂️ Database Management Controls")
    st.markdown("Use this panel to manage structural records or wipe data assets to restart clean.")
    
    st.subheader("🗑️ Delete Specific Node Player")
    delete_uid_input = st.text_input("Enter target Player UID to remove:")
    if st.button("❌ Terminate Specific UID Record", use_container_width=True):
        if delete_uid_input.strip():
            conn = get_db_connection()
            c = conn.cursor()
            c.execute("SELECT uid FROM graph WHERE uid=?", (delete_uid_input.strip(),))
            row = c.fetchone()
            if row:
                c.execute("DELETE FROM graph WHERE uid=?", (delete_uid_input.strip(),))
                conn.commit()
                st.success(f"Successfully removed Player UID `{delete_uid_input.strip()}` from database.")
            else:
                st.warning(f"No records found for Player UID `{delete_uid_input.strip()}`.")
            conn.close()
        else:
            st.error("Please provide a valid UID string input.")
            
    st.write("---")
    
    st.subheader("🚨 Wipe Whole Database Infrastructure")
    st.markdown("Warning: Clicking this action will clear out all tracked profiles permanently.")
    confirm_wipe = st.checkbox("I verify that I want to completely format and drop all stored index maps.")
    
    if st.button("🔥 Purge Complete Database File Data", use_container_width=True):
        if confirm_wipe:
            conn = get_db_connection()
            c = conn.cursor()
            c.execute("DELETE FROM graph")
            conn.commit()
            conn.close()
            st.success("Database format executed. Total data values dropped back to zero configuration setup.")
        else:
            st.error("Action denied. Check the confirmation checkbox before executing database wipe operations.")
