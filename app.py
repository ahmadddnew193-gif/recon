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

# [KEEP ALL YOUR EXISTING IMPORT/CLASS/DB FUNCTIONS HERE - THE REST IS THE UPDATED UI]

# --- RE-ENGINEERED: SPIDER WEB VISUALIZER ---
def render_spider_web_path_canvas(enriched_profiles):
    nodes_payload = [
        {"id": str(n["id"]), "name": str(n["name"]), "isBanned": bool(n["isBanned"])} 
        for n in enriched_profiles
    ]

    # This HTML contains the JS logic for the "Walking Spider"
    web_html = f"""
    <!DOCTYPE html>
    <html>
    <body style="margin:0; background:#04060a;">
        <canvas id="web-canvas" width="800" height="400"></canvas>
        <script>
            const canvas = document.getElementById('web-canvas');
            const ctx = canvas.getContext('2d');
            const nodes = {json.dumps(nodes_payload)};
            
            // Generate web positions
            const centerX = 400;
            const centerY = 200;
            const mappedNodes = nodes.map((n, i) => {{
                const angle = (i / nodes.length) * Math.PI * 2;
                const dist = 50 + (i * 30);
                return {{ ...n, x: centerX + Math.cos(angle)*dist, y: centerY + Math.sin(angle)*dist }};
            }});

            let progress = 0;
            let currentNode = 0;

            function drawWeb() {{
                ctx.strokeStyle = '#1a2b3c';
                // Draw Spoke
                ctx.beginPath();
                for(let n of mappedNodes) {{ ctx.moveTo(centerX, centerY); ctx.lineTo(n.x, n.y); }}
                ctx.stroke();
                // Draw Nodes
                mappedNodes.forEach((n, i) => {{
                    ctx.fillStyle = i === 0 ? '#00FF66' : (i === nodes.length-1 ? '#FF0055' : '#00E5FF');
                    ctx.beginPath(); ctx.arc(n.x, n.y, 8, 0, Math.PI*2); ctx.fill();
                    ctx.fillStyle = 'white'; ctx.fillText(n.name, n.x+10, n.y);
                }});
            }}

            function drawSpider(x, y, angle) {{
                ctx.save();
                ctx.translate(x, y);
                ctx.rotate(angle + Math.PI/2);
                ctx.fillStyle = '#00FF66';
                ctx.beginPath(); ctx.arc(0,0, 6, 0, Math.PI*2); // Body
                ctx.arc(0, -5, 4, 0, Math.PI*2); // Head
                ctx.fill();
                // Legs
                ctx.strokeStyle = '#00FF66';
                for(let i=0; i<4; i++) {{
                    ctx.beginPath();
                    ctx.moveTo(2,0); ctx.lineTo(15 + (i*5), -10+(i*5));
                    ctx.moveTo(-2,0); ctx.lineTo(-15 - (i*5), -10+(i*5));
                    ctx.stroke();
                }}
                ctx.restore();
            }}

            function animate() {{
                ctx.clearRect(0,0,800,400);
                drawWeb();
                
                if (currentNode < mappedNodes.length - 1) {{
                    let p1 = mappedNodes[currentNode];
                    let p2 = mappedNodes[currentNode+1];
                    let spiderX = p1.x + (p2.x - p1.x) * progress;
                    let spiderY = p1.y + (p2.y - p1.y) * progress;
                    let angle = Math.atan2(p2.y - p1.y, p2.x - p1.x);
                    
                    drawSpider(spiderX, spiderY, angle);
                    progress += 0.01;
                    if (progress >= 1) {{ progress = 0; currentNode++; }}
                }} else {{
                    drawSpider(mappedNodes[currentNode].x, mappedNodes[currentNode].y, 0);
                }}
                requestAnimationFrame(animate);
            }}
            animate();
        </script>
    </body>
    </html>
    """
    st.components.v1.html(web_html, height=420)

# --- RE-ENGINEERED: LIVE SWARM MONITOR ---
def render_live_crawler_spider_canvas(recent_nodes, total_scraped):
    # This creates a "Web" pulsing effect in the background
    canvas_html = f"""
    <canvas id="radar" width="800" height="200" style="background:#05070f; border-radius:10px;"></canvas>
    <script>
        const c = document.getElementById('radar');
        const ctx = c.getContext('2d');
        let t = 0;
        function draw() {{
            ctx.clearRect(0,0,800,200);
            ctx.strokeStyle = '#00FF66';
            // Pulsing Web
            for(let i=0; i<5; i++) {{
                ctx.beginPath();
                ctx.arc(400, 100, 20 + i*20 + Math.sin(t)*5, 0, Math.PI*2);
                ctx.stroke();
            }}
            ctx.fillStyle = '#00FF66';
            ctx.fillText("🕸️ SWARM ACTIVE: {total_scraped} PROFILES HARVESTED", 10, 20);
            t+=0.05;
            requestAnimationFrame(draw);
        }}
        draw();
    </script>
    """
    st.components.v1.html(canvas_html, height=210)

# --- APP LOGIC SECTION (Keep your existing tab structure) ---
# ... inside your tab1 implementation ...

    if st.session_state.final_enriched_path:
        st.markdown("### 🕸️ Path Weaving Complete")
        render_spider_web_path_canvas(st.session_state.final_enriched_path)
        
        # Display the result list below the animation
        df_path = pd.DataFrame(st.session_state.final_enriched_path)
        st.table(df_path[["name", "id"]])
    else:
        st.info("Waiting for swarm...")

# --- ENSURE NO AUTO-RESET ---
# Make sure your `master_pipeline_engine` does NOT call st.rerun() 
# inside the loops. Only call st.rerun() after the engine is fully finished.
