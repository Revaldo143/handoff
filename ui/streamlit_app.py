import streamlit as st
import httpx
import json
import time
from datetime import datetime

# Set Page Config
st.set_page_config(
    page_title="HANDOFF | Alexa+ Shift Gatekeeper",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

API_URL = "http://127.0.0.1:8000"

def render_html(html_str: str):
    """
    Safely renders custom HTML/CSS into Streamlit with unsafe_allow_html=True.
    Strips leading and trailing whitespace from each line to prevent Markdown
    from misinterpreting 4+ space indented HTML tags as preformatted code blocks.
    """
    clean_lines = [line.strip() for line in html_str.splitlines() if line.strip()]
    st.markdown("\n".join(clean_lines), unsafe_allow_html=True)

# Custom CSS for Premium Command Center Look
CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;700&family=Outfit:wght@500;700;800;900&display=swap');

/* Reset and Global Styles */
html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, sans-serif;
    background-color: #0B0F19 !important;
    color: #E2E8F0 !important;
}

/* Hide default streamlit chrome */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}
.stDeployButton {display: none;}
div[data-testid="stDecoration"] {display: none;}
div[data-testid="stToolbar"] {visibility: hidden;}
.block-container {
    padding-top: 1.2rem !important;
    padding-bottom: 2rem !important;
    padding-left: 2rem !important;
    padding-right: 2rem !important;
    max-width: 100% !important;
}

/* Background Grid Pattern */
.main {
    background: radial-gradient(circle at 50% 0%, rgba(30, 41, 59, 0.45) 0%, rgba(11, 15, 25, 0.95) 75%),
                linear-gradient(rgba(255, 255, 255, 0.02) 1px, transparent 1px),
                linear-gradient(90deg, rgba(255, 255, 255, 0.02) 1px, transparent 1px);
    background-size: 100% 100%, 32px 32px, 32px 32px;
}

/* Top App Header */
.top-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1.2rem 1.8rem;
    background: rgba(17, 24, 39, 0.85);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 16px;
    backdrop-filter: blur(16px);
    margin-bottom: 1.5rem;
    box-shadow: 0 10px 30px -10px rgba(0, 0, 0, 0.6);
}

.brand-wrapper {
    display: flex;
    align-items: center;
    gap: 1.2rem;
}

.logo-symbol {
    width: 48px;
    height: 48px;
    background: linear-gradient(135deg, #10B981 0%, #059669 100%);
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 26px;
    box-shadow: 0 0 25px rgba(16, 185, 129, 0.45);
}

.brand-title {
    font-family: 'Outfit', sans-serif;
    font-size: 2.2rem;
    font-weight: 900;
    letter-spacing: -0.04em;
    background: linear-gradient(135deg, #FFFFFF 30%, #94A3B8 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin: 0;
    line-height: 1;
}

.brand-subtitle {
    font-size: 0.85rem;
    color: #94A3B8;
    margin-top: 0.3rem;
    font-weight: 500;
    letter-spacing: 0.02em;
}

.pulse-badge {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 6px 14px;
    background: rgba(16, 185, 129, 0.12);
    border: 1px solid rgba(16, 185, 129, 0.3);
    border-radius: 9999px;
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 0.06em;
    color: #10B981;
}

.pulse-dot {
    width: 8px;
    height: 8px;
    background-color: #10B981;
    border-radius: 50%;
    animation: pulse 1.8s infinite;
}

@keyframes pulse {
    0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }
    70% { transform: scale(1.15); box-shadow: 0 0 0 8px rgba(16, 185, 129, 0); }
    100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
}

.track-badge {
    padding: 6px 14px;
    background: rgba(59, 130, 246, 0.12);
    border: 1px solid rgba(59, 130, 246, 0.3);
    border-radius: 9999px;
    font-size: 0.75rem;
    font-weight: 700;
    color: #60A5FA;
    letter-spacing: 0.06em;
}

/* Metric Cards Bar */
.metric-row {
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 1rem;
    margin-bottom: 1.5rem;
}

.stat-card {
    background: rgba(17, 24, 39, 0.7);
    border: 1px solid rgba(255, 255, 255, 0.07);
    border-radius: 12px;
    padding: 0.9rem 1.2rem;
    backdrop-filter: blur(10px);
}

.stat-label {
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #94A3B8;
    margin-bottom: 0.3rem;
}

.stat-value {
    font-family: 'Outfit', sans-serif;
    font-size: 1.5rem;
    font-weight: 800;
    color: #F8FAFC;
    line-height: 1.1;
}

/* Voice Channel / Chat Panel */
.panel-header-title {
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: 1rem;
    font-weight: 700;
    letter-spacing: 0.04em;
    color: #F1F5F9;
    margin-bottom: 1rem;
    padding-bottom: 0.6rem;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.waveform {
    display: flex;
    align-items: center;
    gap: 3px;
    height: 18px;
}

.wave-bar {
    width: 3px;
    height: 100%;
    background-color: #10B981;
    border-radius: 2px;
    animation: wave-anim 1.2s ease-in-out infinite alternate;
}

.wave-bar:nth-child(2) { animation-delay: 0.2s; height: 60%; }
.wave-bar:nth-child(3) { animation-delay: 0.4s; height: 90%; }
.wave-bar:nth-child(4) { animation-delay: 0.1s; height: 40%; }
.wave-bar:nth-child(5) { animation-delay: 0.5s; height: 75%; }

@keyframes wave-anim {
    0% { transform: scaleY(0.3); }
    100% { transform: scaleY(1.1); }
}

/* Chat Messages */
.chat-container {
    display: flex;
    flex-direction: column;
    gap: 1.2rem;
    max-height: 480px;
    overflow-y: auto;
    padding-right: 8px;
    margin-bottom: 1.2rem;
}

/* Custom Scrollbar */
::-webkit-scrollbar {
    width: 6px;
    height: 6px;
}
::-webkit-scrollbar-track {
    background: rgba(15, 23, 42, 0.5);
}
::-webkit-scrollbar-thumb {
    background: rgba(71, 85, 105, 0.6);
    border-radius: 4px;
}
::-webkit-scrollbar-thumb:hover {
    background: rgba(100, 116, 139, 0.8);
}

.chat-bubble-user {
    align-self: flex-end;
    max-width: 85%;
    background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%);
    border: 1px solid rgba(59, 130, 246, 0.3);
    border-radius: 14px 14px 2px 14px;
    padding: 0.9rem 1.1rem;
    box-shadow: 0 4px 15px rgba(0, 0, 0, 0.3);
}

.chat-bubble-agent {
    align-self: flex-start;
    max-width: 90%;
    background: rgba(15, 23, 42, 0.85);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 14px 14px 14px 2px;
    padding: 1rem 1.2rem;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
}

.bubble-meta {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.4rem;
    font-size: 0.72rem;
    font-weight: 600;
    color: #94A3B8;
}

.bubble-text {
    font-size: 0.9rem;
    line-height: 1.45;
    color: #F8FAFC;
}

.latency-badge {
    background: rgba(6, 182, 212, 0.15);
    border: 1px solid rgba(6, 182, 212, 0.3);
    color: #38BDF8;
    padding: 2px 6px;
    border-radius: 6px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.7rem;
}

/* Terminal Component */
.terminal-window {
    background: #030712;
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 14px;
    overflow: hidden;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.8);
    margin-bottom: 1.5rem;
}

.terminal-header {
    background: #0D1322;
    padding: 0.6rem 1rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.terminal-controls {
    display: flex;
    gap: 6px;
}

.term-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
}
.term-dot.red { background-color: #EF4444; }
.term-dot.yellow { background-color: #F59E0B; }
.term-dot.green { background-color: #10B981; }

.terminal-title {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.78rem;
    font-weight: 600;
    color: #94A3B8;
    letter-spacing: 0.04em;
}

.terminal-body {
    padding: 1.1rem;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.82rem;
    line-height: 1.6;
    color: #E2E8F0;
    max-height: 230px;
    overflow-y: auto;
}

.term-line {
    display: flex;
    gap: 10px;
    margin-bottom: 5px;
}

.term-time {
    color: #38BDF8;
    flex-shrink: 0;
}

.term-step {
    color: #C084FC;
    font-weight: 700;
    flex-shrink: 0;
}

.term-msg {
    color: #CBD5E1;
}

.term-refused {
    color: #F87171 !important;
    font-weight: 700;
}

.term-verified {
    color: #34D399 !important;
    font-weight: 700;
}

/* Claim Cards */
.claims-grid {
    display: flex;
    flex-direction: column;
    gap: 1rem;
    max-height: 520px;
    overflow-y: auto;
    padding-right: 6px;
}

.claim-card {
    border-radius: 14px;
    padding: 1.2rem 1.4rem;
    position: relative;
    overflow: hidden;
    backdrop-filter: blur(12px);
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.claim-card:hover {
    transform: translateY(-2px);
}

.claim-card.verified {
    background: linear-gradient(135deg, rgba(16, 185, 129, 0.08) 0%, rgba(15, 23, 42, 0.85) 100%);
    border: 1px solid rgba(16, 185, 129, 0.4);
    box-shadow: 0 4px 20px rgba(16, 185, 129, 0.12);
}

.claim-card.refused {
    background: linear-gradient(135deg, rgba(239, 68, 68, 0.08) 0%, rgba(15, 23, 42, 0.85) 100%);
    border: 1px solid rgba(239, 68, 68, 0.4);
    box-shadow: 0 4px 20px rgba(239, 68, 68, 0.12);
}

.claim-card.pending {
    background: linear-gradient(135deg, rgba(245, 158, 11, 0.08) 0%, rgba(15, 23, 42, 0.85) 100%);
    border: 1px solid rgba(245, 158, 11, 0.4);
    box-shadow: 0 4px 20px rgba(245, 158, 11, 0.12);
}

/* Animated Refused Stamp */
.refused-stamp {
    position: absolute;
    right: 18px;
    top: 14px;
    transform: rotate(11deg);
    border: 3px dashed #EF4444;
    color: #EF4444;
    padding: 4px 12px;
    font-family: 'Outfit', sans-serif;
    font-size: 0.95rem;
    font-weight: 900;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    border-radius: 6px;
    background: rgba(239, 68, 68, 0.15);
    box-shadow: 0 0 15px rgba(239, 68, 68, 0.3);
    animation: stamp-drop 0.35s cubic-bezier(0.175, 0.885, 0.32, 1.275);
}

@keyframes stamp-drop {
    0% { transform: scale(2) rotate(-15deg); opacity: 0; }
    100% { transform: scale(1) rotate(11deg); opacity: 1; }
}

.verified-stamp {
    position: absolute;
    right: 18px;
    top: 14px;
    border: 2px solid #10B981;
    color: #10B981;
    padding: 4px 12px;
    font-family: 'Outfit', sans-serif;
    font-size: 0.85rem;
    font-weight: 800;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    border-radius: 6px;
    background: rgba(16, 185, 129, 0.15);
    box-shadow: 0 0 15px rgba(16, 185, 129, 0.3);
}

.pipeline-track {
    display: flex;
    align-items: center;
    gap: 6px;
    margin: 0.8rem 0;
    font-size: 0.72rem;
    font-family: 'JetBrains Mono', monospace;
    font-weight: 600;
}

.pipeline-node {
    padding: 3px 8px;
    border-radius: 4px;
    background: rgba(255, 255, 255, 0.06);
    color: #64748B;
}

.pipeline-node.active-pass {
    background: rgba(16, 185, 129, 0.2);
    color: #34D399;
    border: 1px solid rgba(16, 185, 129, 0.4);
}

.pipeline-node.active-fail {
    background: rgba(239, 68, 68, 0.2);
    color: #F87171;
    border: 1px solid rgba(239, 68, 68, 0.4);
}

.card-title {
    font-size: 1.05rem;
    font-weight: 700;
    color: #F8FAFC;
    margin-bottom: 0.3rem;
}

.card-raw {
    font-style: italic;
    font-size: 0.85rem;
    color: #94A3B8;
    margin-bottom: 0.6rem;
}

.card-body-box {
    background: rgba(0, 0, 0, 0.35);
    border-radius: 8px;
    padding: 0.7rem 0.9rem;
    font-size: 0.82rem;
    line-height: 1.45;
    margin-top: 0.5rem;
    border-left: 3px solid #64748B;
}

.card-body-box.red-border {
    border-left: 3px solid #EF4444;
}

.card-body-box.green-border {
    border-left: 3px solid #10B981;
}

/* Preset Buttons */
div.stButton > button {
    border-radius: 8px !important;
    font-weight: 600 !important;
    font-size: 0.82rem !important;
    transition: all 0.2s ease !important;
}

/* Inputs */
.stTextInput > div > div > input {
    background-color: #0B0F19 !important;
    border: 1px solid rgba(255, 255, 255, 0.15) !important;
    color: #F8FAFC !important;
    border-radius: 10px !important;
}

.stTextInput > div > div > input:focus {
    border-color: #10B981 !important;
    box-shadow: 0 0 10px rgba(16, 185, 129, 0.3) !important;
}
</style>
"""

render_html(CUSTOM_CSS)

# Helper functions to query FastAPI backend
def api_get(endpoint):
    try:
        resp = httpx.get(f"{API_URL}{endpoint}", timeout=2.5)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return None

def api_post(endpoint, data=None):
    try:
        resp = httpx.post(f"{API_URL}{endpoint}", json=data, timeout=3.5)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        return {"error": str(e)}
    return None

# Session state initialization
if "chat_history" not in st.session_state:
    st.session_state.chat_history = [
        {
            "role": "user",
            "claimant": "Night Shift Lead (Ramesh)",
            "text": "Driver claimed he delivered 20 crates of premium mangoes without challan",
            "timestamp": "21:40 IST"
        },
        {
            "role": "agent",
            "state": "REFUSED",
            "text": "Handoff Gatekeeper refused this claim. No purchase order exists for Premium Alphonsos. Duplicate re-order blocked.",
            "latency": 5.1,
            "timestamp": "21:40 IST"
        },
        {
            "role": "user",
            "claimant": "Night Shift Barista (Suresh)",
            "text": "cups empty, we will run out before morning chai rush",
            "timestamp": "22:15 IST"
        },
        {
            "role": "agent",
            "state": "EXECUTED",
            "text": "Verified: Chai Paper Cups 150ml is at 4.0% stock. Restock order for 10 packs has been automatically placed for 5:30 AM delivery.",
            "latency": 4.5,
            "timestamp": "22:15 IST"
        }
    ]

if "latest_trace" not in st.session_state:
    st.session_state.latest_trace = [
        {"time": "+0.4ms", "step": "VOICE_INGESTION", "state": "REPORTED", "msg": "Parsed audio payload: 'cups empty, we will run out before morning chai rush'"},
        {"time": "+1.8ms", "step": "ENTITY_EXTRACTION", "state": "VERIFYING", "msg": "Matched inventory SKU: CUPS-100 (Chai Paper Cups 150ml)"},
        {"time": "+3.4ms", "step": "SQL_STOCK_QUERY", "state": "VERIFYING", "msg": "Table check: current_stock=40, max_stock=1000 -> 4.0% capacity"},
        {"time": "+4.1ms", "step": "GATEKEEPER_EVAL", "state": "VERIFIED", "msg": "RULE MATCH: Stock 4.0% is below critical threshold 10.0%. VERIFIED."},
        {"time": "+4.9ms", "step": "PIPELINE_PREPARE", "state": "PREPARED", "msg": "Drafted Purchase Order PO-AUTOCUPS-99 to National Paper Mills"},
        {"time": "+5.8ms", "step": "AUTO_EXECUTION", "state": "EXECUTED", "msg": "DISPATCHED: Automated supplier confirmation sent. Handoff clean."}
    ]

# Fetch stats and claims
stats_data = api_get("/api/stats") or {
    "total_claims": 2, "refused_count": 1, "verified_count": 1, "pending_handoff": 1, "saved_loss_inr": 14500, "system_gatekeeper_accuracy": "99.8%"
}
claims_resp = api_get("/api/claims") or {"claims": []}
all_claims = claims_resp.get("claims", [])

# Top Header HTML
header_html = f"""
<div class="top-header">
    <div class="brand-wrapper">
        <div class="logo-symbol">🛡️</div>
        <div>
            <h1 class="brand-title">HANDOFF</h1>
            <div class="brand-subtitle">"Every agent acts. This one knows when NOT to."</div>
        </div>
    </div>
    <div style="display: flex; align-items: center; gap: 12px;">
        <span class="track-badge">AMAZON ALEXA+ TRACK</span>
        <div class="pulse-badge">
            <span class="pulse-dot"></span>
            <span>GATEKEEPER KERNEL LIVE</span>
        </div>
    </div>
</div>
"""
render_html(header_html)

# Top Stat Cards
metrics_html = f"""
<div class="metric-row">
    <div class="stat-card">
        <div class="stat-label">Total Claims Handled</div>
        <div class="stat-value">{stats_data.get('total_claims', 0)}</div>
    </div>
    <div class="stat-card" style="border-color: rgba(239, 68, 68, 0.4);">
        <div class="stat-label" style="color: #F87171;">🛑 Refused (False Claims)</div>
        <div class="stat-value" style="color: #EF4444;">{stats_data.get('refused_count', 0)}</div>
    </div>
    <div class="stat-card" style="border-color: rgba(16, 185, 129, 0.4);">
        <div class="stat-label" style="color: #34D399;">✅ Verified & Executed</div>
        <div class="stat-value" style="color: #10B981;">{stats_data.get('verified_count', 0)}</div>
    </div>
    <div class="stat-card" style="border-color: rgba(245, 158, 11, 0.4);">
        <div class="stat-label" style="color: #FBBF24;">⚠️ Pending Morning Review</div>
        <div class="stat-value" style="color: #F59E0B;">{stats_data.get('pending_handoff', 0)}</div>
    </div>
    <div class="stat-card" style="border-color: rgba(56, 189, 248, 0.4);">
        <div class="stat-label" style="color: #38BDF8;">💰 Losses Prevented</div>
        <div class="stat-value" style="color: #38BDF8;">₹{stats_data.get('saved_loss_inr', 0):,}</div>
    </div>
</div>
"""
render_html(metrics_html)

# Layout: Two Columns (Voice Channel vs Mission Control)
col_left, col_right = st.columns([1, 1.25], gap="large")

# ==========================================
# LEFT COLUMN: Voice Channel & Interactive Intake
# ==========================================
with col_left:
    voice_panel_title_html = """
    <div class="panel-header-title">
        <div style="display: flex; align-items: center; gap: 8px;">
            <span>🎙️</span>
            <span>VOICE CHANNEL (SHIFT INTAKE)</span>
        </div>
        <div class="waveform">
            <div class="wave-bar"></div>
            <div class="wave-bar"></div>
            <div class="wave-bar"></div>
            <div class="wave-bar"></div>
            <div class="wave-bar"></div>
        </div>
    </div>
    """
    render_html(voice_panel_title_html)

    # Quick Scenario Presets for Judges
    render_html("<div style='font-size: 0.76rem; font-weight: 700; color: #94A3B8; margin-bottom: 6px;'>⚡ JUDGE DEMO PRESETS (ONE-CLICK):</div>")
    p_col1, p_col2 = st.columns(2)
    
    preset_choice = None
    with p_col1:
        if st.button("🛑 'delivery never arrived' (Will Refuse)", use_container_width=True):
            preset_choice = "the delivery never arrived"
        if st.button("🛑 'milk not received' (No PO)", use_container_width=True):
            preset_choice = "milk delivery not received, vendor didn't show up"
            
    with p_col2:
        if st.button("✅ 'cups are empty' (Will Order)", use_container_width=True):
            preset_choice = "cups are empty"
        if st.button("✅ 'tea stock low' (Will Order)", use_container_width=True):
            preset_choice = "tea stock is running low"

    # Chat Bubbles Stream
    chat_html = ['<div class="chat-container">']
    for msg in st.session_state.chat_history:
        if msg["role"] == "user":
            chat_html.append(f"""
            <div class="chat-bubble-user">
                <div class="bubble-meta">
                    <span>👤 {msg.get('claimant', 'Shift Worker')}</span>
                    <span>{msg.get('timestamp', '')}</span>
                </div>
                <div class="bubble-text">"{msg['text']}"</div>
            </div>
            """)
        else:
            verdict_color = "#10B981" if msg.get("state") in ["VERIFIED", "EXECUTED"] else "#EF4444"
            status_text = "🛡️ REFUSED BY GATEKEEPER" if msg.get("state") == "REFUSED" else "⚡ ACTION EXECUTED"
            chat_html.append(f"""
            <div class="chat-bubble-agent">
                <div class="bubble-meta">
                    <span style="color: {verdict_color}; font-weight: 700;">{status_text}</span>
                    <span class="latency-badge">⚡ {msg.get('latency', 4.2)}ms</span>
                </div>
                <div class="bubble-text">{msg['text']}</div>
            </div>
            """)
    chat_html.append('</div>')
    render_html("".join(chat_html))

    # Input Form
    with st.form("voice_input_form", clear_on_submit=True):
        user_input = st.text_input(
            "Shift Worker Voice Input",
            value=preset_choice if preset_choice else "",
            placeholder="E.g., 'the delivery never arrived' or 'cups are empty'...",
            label_visibility="collapsed"
        )
        f_col1, f_col2 = st.columns([3, 1])
        with f_col1:
            claimant_role = st.selectbox(
                "Role", 
                ["Night Shift Operator", "Night Shift Barista", "Inventory Supervisor", "Kirana Lead"],
                label_visibility="collapsed"
            )
        with f_col2:
            submit_btn = st.form_submit_button("🎙️ Process", use_container_width=True)

    # Processing submission
    if submit_btn and user_input.strip():
        # Call backend
        with st.spinner("Gatekeeper evaluating enterprise database..."):
            res = api_post("/api/voice", {"text": user_input, "claimant": claimant_role})
            if res:
                now_str = datetime.now().strftime("%H:%M IST")
                st.session_state.chat_history.append({
                    "role": "user",
                    "claimant": claimant_role,
                    "text": user_input,
                    "timestamp": now_str
                })
                # Multi-fragment utterances return {"claims": [...]}; single keeps {"claim": {...}}
                items = res.get("claims")
                if items:
                    for it in items:
                        st.session_state.chat_history.append({
                            "role": "agent",
                            "state": it.get("gatekeeper_verdict"),
                            "text": it.get("speech_reply"),
                            "latency": it.get("latency_ms", 0),
                            "timestamp": now_str
                        })
                    merged_trace = []
                    for it in items:
                        for t in it.get("claim", {}).get("timeline", []):
                            merged_trace.append({
                                "time": f"+{t.get('latency_offset_ms', 0)}ms",
                                "step": t.get("step", "EVAL"),
                                "state": t.get("state", "REPORTED"),
                                "msg": t.get("detail", "")
                            })
                    st.session_state.latest_trace = merged_trace
                elif "claim" in res:
                    st.session_state.chat_history.append({
                        "role": "agent",
                        "state": res.get("gatekeeper_verdict"),
                        "text": res.get("speech_reply"),
                        "latency": res.get("latency_ms", 4.5),
                        "timestamp": now_str
                    })
                    # Update trace
                    timeline = res["claim"].get("timeline", [])
                    st.session_state.latest_trace = [
                        {
                            "time": f"+{t.get('latency_offset_ms', 0)}ms",
                            "step": t.get("step", "EVAL"),
                            "state": t.get("state", "REPORTED"),
                            "msg": t.get("detail", "")
                        }
                        for t in timeline
                    ]
                st.rerun()

    # Reset Data button
    render_html("<div style='margin-top: 1rem;'></div>")
    if st.button("🔄 Reset Demo Database to Baseline", use_container_width=True):
        api_post("/api/reset")
        st.session_state.chat_history = [
            {
                "role": "user",
                "claimant": "Night Shift Lead (Ramesh)",
                "text": "Driver claimed he delivered 20 crates of premium mangoes without challan",
                "timestamp": "21:40 IST"
            },
            {
                "role": "agent",
                "state": "REFUSED",
                "text": "Handoff Gatekeeper refused this claim. No purchase order exists for Premium Alphonsos. Duplicate re-order blocked.",
                "latency": 5.1,
                "timestamp": "21:40 IST"
            }
        ]
        st.rerun()

# ==========================================
# RIGHT COLUMN: Mission Control & Claims Status
# ==========================================
with col_right:
    # Top Right: Live Thinking Trace Terminal
    terminal_html = [f"""
    <div class="terminal-window">
        <div class="terminal-header">
            <div class="terminal-controls">
                <div class="term-dot red"></div>
                <div class="term-dot yellow"></div>
                <div class="term-dot green"></div>
            </div>
            <div class="terminal-title">⚡ THINKING TRACE (SUB-MILLISECOND GATEKEEPER ENGINE)</div>
            <div style="font-family: 'JetBrains Mono'; font-size: 0.7rem; color: #10B981;">WAL-MODE SQLite</div>
        </div>
        <div class="terminal-body">
    """]
    
    for item in st.session_state.latest_trace:
        color_class = "term-refused" if item["state"] == "REFUSED" else ("term-verified" if item["state"] in ["VERIFIED", "EXECUTED"] else "")
        terminal_html.append(f"""
            <div class="term-line">
                <span class="term-time">{item['time']}</span>
                <span class="term-step">[{item['step']}]</span>
                <span class="term-msg {color_class}">{item['msg']}</span>
            </div>
        """)
    terminal_html.append("""
        </div>
    </div>
    """)
    render_html("".join(terminal_html))

    # Bottom Right: Claims Status Deck
    render_html("""
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.8rem;">
        <div style="font-weight: 700; font-size: 1rem; color: #F1F5F9; letter-spacing: 0.04em;">
            📋 CLAIMS STATE MACHINE & VERIFICATION DECK
        </div>
    </div>
    """)

    # Filter selector
    filter_choice = st.radio(
        "Filter",
        ["All Claims", "🛑 Refused Only", "✅ Verified / Executed", "⚠️ Pending Morning Review"],
        horizontal=True,
        label_visibility="collapsed"
    )

    filtered_claims = []
    for c in all_claims:
        if filter_choice == "🛑 Refused Only" and c["state"] != "REFUSED":
            continue
        if filter_choice == "✅ Verified / Executed" and c["state"] not in ["VERIFIED", "EXECUTED", "APPROVED", "PREPARED"]:
            continue
        if filter_choice == "⚠️ Pending Morning Review" and c["requires_attention"] != 1:
            continue
        filtered_claims.append(c)

    # Render Cards
    cards_html = ['<div class="claims-grid">']
    for claim in filtered_claims:
        state = claim["state"]
        is_refused = state == "REFUSED"
        is_verified = state in ["VERIFIED", "EXECUTED", "APPROVED", "PREPARED"]
        
        card_class = "refused" if is_refused else ("verified" if is_verified else "pending")
        
        # Stamp
        if is_refused:
            stamp_html = '<div class="refused-stamp">REFUSED</div>'
        elif state == "EXECUTED":
            stamp_html = '<div class="verified-stamp">EXECUTED ⚡</div>'
        else:
            stamp_html = f'<div class="verified-stamp">{state}</div>'

        # Pipeline progress nodes
        nodes = ["REPORTED", "VERIFYING", "DECISION", "EXECUTION"]
        nodes_html = []
        for n in nodes:
            if is_refused and n in ["REPORTED", "VERIFYING", "DECISION"]:
                nodes_html.append(f'<span class="pipeline-node active-fail">{n}</span>')
            elif is_verified:
                nodes_html.append(f'<span class="pipeline-node active-pass">{n}</span>')
            else:
                nodes_html.append(f'<span class="pipeline-node">{n}</span>')
            if n != nodes[-1]:
                nodes_html.append('<span style="color: #475569;">→</span>')

        body_box_class = "red-border" if is_refused else "green-border"
        
        reason_section = ""
        if claim.get("rejection_reason"):
            reason_section = f"""
            <div style="margin-top: 6px; color: #F87171; font-weight: 600;">
                🛡️ Gatekeeper Refusal Reason: <span style="font-weight: 400; color: #FECACA;">{claim['rejection_reason']}</span>
            </div>
            """

        action_section = ""
        if claim.get("action_taken"):
            action_section = f"""
            <div style="margin-top: 6px; color: #34D399; font-weight: 600;">
                ⚡ Action Executed: <span style="font-weight: 400; color: #A7F3D0;">{claim['action_taken']}</span>
            </div>
            """

        cards_html.append(f"""
        <div class="claim-card {card_class}">
            {stamp_html}
            <div style="font-size: 0.72rem; color: #94A3B8; font-weight: 600; text-transform: uppercase;">
                CLAIM #{claim['id']} • {claim.get('claim_type', 'GENERAL')} • {claim.get('claimant', 'Shift Worker')}
            </div>
            <div class="card-title">{claim.get('item_name', 'Item Claim')}</div>
            <div class="card-raw">"{claim.get('raw_text', '')}"</div>
            
            <div class="pipeline-track">
                {''.join(nodes_html)}
            </div>

            <div class="card-body-box {body_box_class}">
                <div style="color: #94A3B8;"><strong>Evidence Cross-Check:</strong> {claim.get('evidence', 'No record')}</div>
                {reason_section}
                {action_section}
            </div>
        </div>
        """)

    cards_html.append('</div>')
    render_html("".join(cards_html))

    # Shift Manager Action Controls
    if filtered_claims:
        render_html("<div style='margin-top: 0.8rem;'></div>")
        m_col1, m_col2, m_col3 = st.columns([2, 1, 1])
        with m_col1:
            selected_claim_id = st.selectbox(
                "Select Claim for Manager Review",
                [c["id"] for c in filtered_claims],
                format_func=lambda x: f"Claim #{x} - {next((c['item_name'] for c in filtered_claims if c['id'] == x), '')}",
                label_visibility="collapsed"
            )
        with m_col2:
            if st.button("✅ Approve", use_container_width=True):
                api_post(f"/api/claims/{selected_claim_id}/approve", {"state": "APPROVED", "note": "Morning Manager manual override approval"})
                st.rerun()
        with m_col3:
            if st.button("🛑 Refuse", use_container_width=True):
                api_post(f"/api/claims/{selected_claim_id}/refuse", {"state": "REFUSED", "note": "Morning Manager affirmed refusal"})
                st.rerun()
