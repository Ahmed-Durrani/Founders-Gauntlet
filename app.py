import streamlit as st
from dotenv import load_dotenv

from database import initialize_database
from game_logic import initialize_ai
from session_utils import ensure_session_state
from views.dashboard import render_dashboard_view
from views.game import render_game_view
from views.leaderboard import render_leaderboard_view

load_dotenv()

st.set_page_config(page_title="The Founder's Gauntlet", page_icon="💼", layout="wide")

def _hex_to_rgb(hex_color):
    value = hex_color.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))


def _rgb_to_hex(rgb_tuple):
    r, g, b = [max(0, min(255, int(v))) for v in rgb_tuple]
    return f"#{r:02x}{g:02x}{b:02x}"


def _blend(hex_a, hex_b, t):
    t = max(0.0, min(1.0, float(t)))
    a = _hex_to_rgb(hex_a)
    b = _hex_to_rgb(hex_b)
    mixed = (
        a[0] + (b[0] - a[0]) * t,
        a[1] + (b[1] - a[1]) * t,
        a[2] + (b[2] - a[2]) * t,
    )
    return _rgb_to_hex(mixed)


ensure_session_state()

hp = max(0, min(100, int(st.session_state.current_hp)))
bg_top = "#0a0e17"
bg_mid = "#0a0e17"
bg_bottom = "#0a0e17"
bg_vignette = "#0a0e17"

global_css = """
<style>
    :root {
        --fg-bg-top: __BG_TOP__;
        --fg-bg-mid: __BG_MID__;
        --fg-bg-bottom: __BG_BOTTOM__;
        --fg-bg-vignette: __BG_VIGNETTE__;
    }
    @keyframes fgAuroraShift {
        0% { transform: translate3d(-4%, -3%, 0) scale(1); opacity: 0.2; }
        50% { transform: translate3d(4%, 3%, 0) scale(1.12); opacity: 0.38; }
        100% { transform: translate3d(-4%, -3%, 0) scale(1); opacity: 0.2; }
    }
    @keyframes fgGridDrift {
        0% { background-position: 0 0; opacity: 0.2; }
        50% { background-position: 34px 26px; opacity: 0.3; }
        100% { background-position: 0 0; opacity: 0.2; }
    }
    @keyframes fgOrbitalGlow {
        0% { transform: rotate(0deg) scale(1.02); opacity: 0.12; }
        50% { transform: rotate(180deg) scale(1.12); opacity: 0.24; }
        100% { transform: rotate(360deg) scale(1.02); opacity: 0.12; }
    }
    @keyframes fgBackdropShift {
        0% { background-position: 50% 0%, 50% 100%, 0 0; }
        50% { background-position: 58% 5%, 42% 96%, 0 0; }
        100% { background-position: 50% 0%, 50% 100%, 0 0; }
    }
    @keyframes fgFadeInUp {
        0% { opacity: 0; transform: translateY(16px); }
        100% { opacity: 1; transform: translateY(0); }
    }
    @keyframes fgSubtleFloat {
        0% { transform: translateY(0); }
        50% { transform: translateY(-3px); }
        100% { transform: translateY(0); }
    }
    html, body, [data-testid="stAppViewContainer"], [data-testid="stAppViewContainer"] * {
        touch-action: manipulation;
    }
    html, body {
        height: 100% !important;
        overflow: hidden !important;
    }
    [data-testid="stAppViewContainer"] {
        position: relative;
        height: 100dvh !important;
        overflow: hidden !important;
        background: #0a0e17 !important;
        animation: none !important;
        transition: none !important;
    }
    [data-testid="stAppViewContainer"]::after {
        display: none !important;
        content: none !important;
    }
    [data-testid="stAppViewContainer"]::before {
        display: none !important;
        content: none !important;
    }
    [data-testid="stAppViewContainer"] > .main::before {
        display: none !important;
        content: none !important;
    }
    [data-testid="stAppViewContainer"] > .main {
        height: 100dvh !important;
        overflow-y: auto !important;
        overflow-x: hidden !important;
        scrollbar-width: none !important;
        background: transparent !important;
    }
    [data-testid="stAppViewContainer"] > .main::-webkit-scrollbar {
        width: 0 !important;
        height: 0 !important;
    }
    [data-testid="stAppViewContainer"] > .main,
    [data-testid="stAppViewContainer"] > .main * {
        position: relative;
        z-index: 1;
    }
    [data-testid="stSidebar"] {
        background: #0f1419 !important;
        border-right: 1px solid #1e2a3a;
        overflow: hidden !important;
    }
    [data-testid="stSidebar"] > div:first-child {
        height: 100dvh !important;
        max-height: 100dvh !important;
        overflow-y: auto !important;
        overflow-x: hidden !important;
        -webkit-overflow-scrolling: touch !important;
        overscroll-behavior: contain;
    }
    [data-testid="stSidebar"] * {
        color: #e8eaed !important;
    }
    [data-testid="stMetric"], .stAlert, .stChatMessage, [data-testid="stDataFrame"], [data-testid="stExpander"] {
        backdrop-filter: blur(12px);
        background: rgba(255, 255, 255, 0.05) !important;
        border: 1px solid rgba(255,255,255,0.10) !important;
        border-radius: 16px;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
        animation: fgFadeInUp 0.5s ease-out both;
    }
    .stChatMessage {
        animation: fgSubtleFloat 6s ease-in-out infinite;
    }
    [data-testid="stChatInput"] {
        background: rgba(255,255,255,0.92) !important;
        border: 1px solid rgba(255,255,255,0.20) !important;
        border-radius: 14px !important;
        backdrop-filter: blur(8px);
    }
    [data-testid="stChatInput"] textarea {
        color: #111111 !important;
        caret-color: #111111 !important;
    }
    [data-testid="stChatInput"] textarea::placeholder {
        color: #6b7280 !important;
    }
    [data-testid="stChatInput"] button {
        color: #111111 !important;
        transition: all 200ms ease !important;
    }
    [data-testid="stChatInput"] button:active {
        background: rgba(0, 0, 0, 0.25) !important;
        transform: scale(0.94) !important;
        box-shadow: inset 0 2px 6px rgba(0, 0, 0, 0.3) !important;
    }
    #MainMenu, footer, [data-testid="stDecoration"] {
        visibility: hidden;
        display: none !important;
    }
    header[data-testid="stHeader"] {
        background: transparent !important;
        border-bottom: none !important;
        height: auto !important;
    }
    [data-testid="collapsedControl"] {
        display: flex !important;
        visibility: visible !important;
        opacity: 1 !important;
        z-index: 10000 !important;
    }
    [data-testid="stAppViewContainer"] > .main .block-container {
        padding-top: 0.8rem;
        padding-bottom: 1rem;
        color: #e8eaed !important;
    }
    [data-testid="stAppViewContainer"] > .main {
        color: #e8eaed !important;
    }
    [data-testid="stAppViewContainer"] > .main h1,
    [data-testid="stAppViewContainer"] > .main h2,
    [data-testid="stAppViewContainer"] > .main h3,
    [data-testid="stAppViewContainer"] > .main p,
    [data-testid="stAppViewContainer"] > .main li,
    [data-testid="stAppViewContainer"] > .main label,
    [data-testid="stAppViewContainer"] > .main [data-testid="stMarkdownContainer"],
    [data-testid="stAppViewContainer"] > .main [data-testid="stCaptionContainer"] {
        color: #e8eaed !important;
        text-shadow: none !important;
    }
    [data-testid="stAppViewContainer"] > .main [data-testid="stCaptionContainer"] {
        color: #9ca3af !important;
    }
    [data-testid="stAppViewContainer"] > .main [data-testid="stHeading"] * {
        color: #ffffff !important;
    }
    [data-testid="stChatMessageContent"] * {
        color: #e8eaed !important;
    }
    [data-testid="stAppViewContainer"] > .main .block-container *:not(button):not(input):not(textarea) {
        color: #e8eaed !important;
    }
    /* ── Metric widget ── */
    [data-testid="stMetricValue"] {
        color: #ffffff !important;
    }
    [data-testid="stMetricLabel"] {
        color: #9ca3af !important;
    }
    [data-testid="stMetricDelta"] svg {
        fill: currentColor !important;
    }
    /* ── DataFrames & tables ── */
    [data-testid="stDataFrame"],
    [data-testid="stDataFrame"] * {
        color: #e8eaed !important;
    }
    [data-testid="stDataFrame"] [role="columnheader"] {
        color: #ffffff !important;
        font-weight: 700 !important;
    }
    [data-testid="stTable"],
    [data-testid="stTable"] th,
    [data-testid="stTable"] td {
        color: #e8eaed !important;
        border-color: rgba(255,255,255,0.08) !important;
    }
    /* ── Expanders ── */
    [data-testid="stExpander"] summary,
    [data-testid="stExpander"] summary span,
    [data-testid="stExpander"] summary p {
        color: #e8eaed !important;
    }
    [data-testid="stExpander"] svg {
        fill: #e8eaed !important;
    }
    /* ── Info / Warning / Error boxes ── */
    .stAlert p, .stAlert span, .stAlert div {
        color: #e8eaed !important;
    }
    [data-testid="stNotification"] p {
        color: #e8eaed !important;
    }
    /* ── Tabs ── */
    [data-testid="stTab"],
    button[data-baseweb="tab"] {
        color: #9ca3af !important;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        color: #ffffff !important;
    }
    /* ── Text area ── */
    [data-testid="stTextArea"] textarea {
        color: #e8eaed !important;
        background: rgba(255,255,255,0.05) !important;
        border-color: rgba(255,255,255,0.12) !important;
    }
    /* ── Selectbox / multiselect ── */
    [data-baseweb="select"] * {
        color: #e8eaed !important;
    }
    [data-baseweb="popover"] [role="listbox"] {
        background: #1a1f2e !important;
    }
    [data-baseweb="popover"] [role="option"] {
        color: #e8eaed !important;
    }
    [data-baseweb="popover"] [role="option"]:hover {
        background: rgba(255,255,255,0.08) !important;
    }
    .stButton > button {
        background: rgba(255,255,255,0.06) !important;
        color: #e8eaed !important;
        border: 1px solid rgba(255,255,255,0.12) !important;
        border-radius: 14px;
        min-height: 44px;
        width: 100%;
        font-weight: 700;
        transition: all 280ms cubic-bezier(0.4, 0, 0.2, 1);
        box-shadow: 0 2px 6px rgba(0, 0, 0, 0.2);
        backdrop-filter: blur(8px);
    }
    .stButton > button:hover {
        background: rgba(255,255,255,0.10) !important;
        color: #ffffff !important;
        transform: scale(1.02) translateY(-1px);
        box-shadow: 0 6px 24px rgba(59, 130, 246, 0.2), 0 0 0 1px rgba(59, 130, 246, 0.15);
        border-color: rgba(59, 130, 246, 0.3) !important;
    }
    .stButton > button:active {
        transform: scale(0.97);
        box-shadow: 0 2px 8px rgba(59, 130, 246, 0.25);
    }
    [data-testid="stTextInput"] div[data-baseweb="input"] {
        background: rgba(255,255,255,0.05) !important;
        border: 1px solid rgba(255,255,255,0.12) !important;
        border-radius: 10px !important;
        box-shadow: none !important;
        transition: all 300ms cubic-bezier(0.4, 0, 0.2, 1);
    }
    [data-testid="stTextInput"] div[data-baseweb="input"]:focus-within {
        border-color: rgba(59, 130, 246, 0.5) !important;
        box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.15), 0 0 20px rgba(59, 130, 246, 0.1) !important;
    }
    [data-testid="stTextInput"] input {
        color: #e8eaed !important;
        caret-color: #e8eaed !important;
    }
    .st-key-fg_chat_mic_anchor {
        height: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
    }
    .st-key-fg_mic_btn {
        position: fixed;
        right: 7.2rem;
        bottom: 1.15rem;
        z-index: 10020;
        margin: 0 !important;
        width: 42px !important;
    }
    .st-key-fg_mic_btn button {
        width: 42px !important;
        min-height: 42px !important;
        border-radius: 999px !important;
        padding: 0 !important;
        background: rgba(255,255,255,0.10) !important;
        border: 1px solid rgba(255,255,255,0.20) !important;
        color: #e8eaed !important;
        font-size: 1.1rem !important;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3), inset 0 1px 0 rgba(255,255,255,0.08) !important;
        backdrop-filter: blur(12px) !important;
        transition: all 280ms cubic-bezier(0.4, 0, 0.2, 1) !important;
    }
    .st-key-fg_mic_btn button:hover {
        background: rgba(59, 130, 246, 0.15) !important;
        color: #ffffff !important;
        transform: scale(1.08) !important;
        box-shadow: 0 0 24px rgba(59, 130, 246, 0.3), 0 0 0 2px rgba(59, 130, 246, 0.2), 0 4px 16px rgba(0, 0, 0, 0.3) !important;
        border-color: rgba(59, 130, 246, 0.4) !important;
    }
    /* Hidden helper buttons for JS bridge */
    .st-key-fg_mic_lock, .st-key-fg_mic_stop {
        height: 0 !important;
        overflow: hidden !important;
        margin: 0 !important;
        padding: 0 !important;
        opacity: 0 !important;
        pointer-events: none !important;
    }
    /* Recording overlay */
    @keyframes fgRecDotPulse {
        0% { transform: scale(0.8); opacity: 0.5; }
        50% { transform: scale(1.3); opacity: 1; }
        100% { transform: scale(0.8); opacity: 0.5; }
    }
    .fg-recording-overlay {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.5rem 1rem;
        background: rgba(239, 68, 68, 0.12);
        border: 1px solid rgba(239, 68, 68, 0.25);
        border-radius: 12px;
        margin: 0.35rem 0;
    }
    .fg-rec-dot {
        width: 10px;
        height: 10px;
        border-radius: 999px;
        background: #ef4444;
        animation: fgRecDotPulse 1s ease-in-out infinite;
    }
    .fg-rec-text {
        color: #fca5a5;
        font-size: 0.85rem;
        font-weight: 600;
    }
    [data-testid="stFileUploader"] {
        background: rgba(255,255,255,0.03);
        border-radius: 14px;
        padding: 0.25rem;
    }
    section[data-testid="stFileUploaderDropzone"] {
        background: rgba(255,255,255,0.04) !important;
        border: 1px dashed rgba(255,255,255,0.15) !important;
        border-radius: 14px !important;
        color: #e8eaed !important;
    }
    section[data-testid="stFileUploaderDropzone"] * {
        color: #e8eaed !important;
    }
    [data-testid="stFileUploaderDropzoneInstructions"] {
        color: #e8eaed !important;
    }
    [data-testid="stFileUploaderDropzoneInstructions"] small,
    [data-testid="stFileUploaderDropzoneInstructions"] span {
        color: #9ca3af !important;
    }
    [data-testid="stFileUploaderFileName"] {
        color: #e8eaed !important;
        background: rgba(255,255,255,0.06);
        border-radius: 8px;
        padding: 0.2rem 0.35rem;
    }
    [data-testid="stFileUploader"] button,
    section[data-testid="stFileUploaderDropzone"] button {
        background: rgba(255,255,255,0.08) !important;
        color: #e8eaed !important;
        border: 1px solid rgba(255,255,255,0.15) !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2) !important;
    }
    [data-testid="stFileUploader"] button:hover,
    section[data-testid="stFileUploaderDropzone"] button:hover {
        background: rgba(255,255,255,0.14) !important;
        color: #ffffff !important;
        border-color: rgba(255,255,255,0.2) !important;
        opacity: 1 !important;
    }
    [data-testid="stFileUploader"] button:active,
    section[data-testid="stFileUploaderDropzone"] button:active {
        transform: scale(0.95);
    }

    @media (max-width: 768px) {
        html, body {
            margin: 0 !important;
            padding: 0 !important;
            overflow: hidden !important;
            max-width: 100vw !important;
        }
        [data-testid="stAppViewContainer"]::before {
            display: none !important;
        }
        [data-testid="stAppViewContainer"]::after {
            display: none !important;
        }
        [data-testid="stAppViewContainer"] {
            max-width: 100vw !important;
            overflow: hidden !important;
        }
        [data-testid="stAppViewContainer"] > .main {
            padding: 0 !important;
        }
        [data-testid="stAppViewContainer"] > .main .block-container {
            padding-top: 0.35rem !important;
            padding-right: 0 !important;
            padding-bottom: 0.5rem !important;
            padding-left: 0 !important;
            max-width: 100vw !important;
        }
        [data-testid="stSidebar"][aria-expanded="false"] {
            transform: translateX(-100%) !important;
            margin-left: 0 !important;
        }
        [data-testid="stSidebar"][aria-expanded="true"] {
            transform: translateX(0) !important;
        }
        [data-testid="stSidebar"] > div:first-child {
            height: 100dvh !important;
            max-height: 100dvh !important;
        }
        [data-testid="collapsedControl"] {
            top: 0.5rem !important;
            right: 0.5rem !important;
            left: auto !important;
            z-index: 10000 !important;
        }
        .stButton > button {
            min-height: 58px !important;
            font-size: 1.05rem !important;
            border-radius: 16px !important;
            width: 100% !important;
        }
        .st-key-fg_open_voice_mode button {
            width: 46px !important;
            min-height: 46px !important;
            border-radius: 999px !important;
            font-size: 0.78rem !important;
        }
        .st-key-fg_open_voice_mode {
            right: 5.4rem !important;
            bottom: 0.95rem !important;
            width: 46px !important;
        }
        .st-key-fg_voice_mic_button button,
        .st-key-fg_voice_lock_button button,
        .st-key-fg_voice_unlock_button button,
        .st-key-fg_voice_stop_button button {
            width: 62px !important;
            min-height: 62px !important;
            border-radius: 999px !important;
            font-size: 0.8rem !important;
        }
        .st-key-fg_voice_exit_mode button {
            min-height: 62px !important;
            border-radius: 999px !important;
            font-size: 0.9rem !important;
        }
    }
</style>
"""
global_css = (
    global_css
    .replace("__BG_TOP__", bg_top)
    .replace("__BG_MID__", bg_mid)
    .replace("__BG_BOTTOM__", bg_bottom)
    .replace("__BG_VIGNETTE__", bg_vignette)
)
st.markdown(global_css, unsafe_allow_html=True)

# ── Animated SVG constellation background ──────────────────────────────
# Represents the startup ecosystem: nodes = founders/investors/ideas,
# lines = connections, pulsing glow = the pressure of the pitch.
_svg_bg = """
<div id="fg-constellation-bg" style="
  position:fixed; inset:0; z-index:0; pointer-events:none;
  overflow:hidden; background:transparent;
">
<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%"
     viewBox="0 0 1440 900" preserveAspectRatio="xMidYMid slice"
     style="position:absolute;inset:0;width:100%;height:100%;">
  <defs>
    <!-- Gradient blobs -->
    <radialGradient id="blob-a" cx="50%" cy="50%" r="50%"><stop offset="0%" stop-color="#3b82f6" stop-opacity="0.12"/><stop offset="100%" stop-color="#3b82f6" stop-opacity="0"/></radialGradient>
    <radialGradient id="blob-b" cx="50%" cy="50%" r="50%"><stop offset="0%" stop-color="#8b5cf6" stop-opacity="0.10"/><stop offset="100%" stop-color="#8b5cf6" stop-opacity="0"/></radialGradient>
    <radialGradient id="blob-c" cx="50%" cy="50%" r="50%"><stop offset="0%" stop-color="#06b6d4" stop-opacity="0.08"/><stop offset="100%" stop-color="#06b6d4" stop-opacity="0"/></radialGradient>
    <!-- Node glows -->
    <radialGradient id="ng1"><stop offset="0%" stop-color="#3b82f6" stop-opacity="0.5"/><stop offset="100%" stop-color="#3b82f6" stop-opacity="0"/></radialGradient>
    <radialGradient id="ng2"><stop offset="0%" stop-color="#8b5cf6" stop-opacity="0.4"/><stop offset="100%" stop-color="#8b5cf6" stop-opacity="0"/></radialGradient>
    <radialGradient id="ng3"><stop offset="0%" stop-color="#06b6d4" stop-opacity="0.4"/><stop offset="100%" stop-color="#06b6d4" stop-opacity="0"/></radialGradient>
    <filter id="soften"><feGaussianBlur stdDeviation="0.8"/></filter>
  </defs>

  <!-- Layer 1: Large animated gradient blobs (Vercel/Stripe vibe) -->
  <ellipse cx="320" cy="250" rx="400" ry="300" fill="url(#blob-a)" opacity="0.08">
    <animate attributeName="cx" values="320;420;280;320" dur="20s" repeatCount="indefinite"/>
    <animate attributeName="cy" values="250;320;200;250" dur="16s" repeatCount="indefinite"/>
    <animate attributeName="opacity" values="0.06;0.12;0.06" dur="12s" repeatCount="indefinite"/>
  </ellipse>
  <ellipse cx="1100" cy="350" rx="350" ry="280" fill="url(#blob-b)" opacity="0.07">
    <animate attributeName="cx" values="1100;1020;1150;1100" dur="18s" repeatCount="indefinite"/>
    <animate attributeName="cy" values="350;280;400;350" dur="14s" repeatCount="indefinite"/>
    <animate attributeName="opacity" values="0.05;0.10;0.05" dur="15s" repeatCount="indefinite"/>
  </ellipse>
  <ellipse cx="700" cy="700" rx="380" ry="260" fill="url(#blob-c)" opacity="0.06">
    <animate attributeName="cx" values="700;780;650;700" dur="19s" repeatCount="indefinite"/>
    <animate attributeName="cy" values="700;640;750;700" dur="17s" repeatCount="indefinite"/>
    <animate attributeName="opacity" values="0.05;0.09;0.05" dur="13s" repeatCount="indefinite"/>
  </ellipse>

  <!-- Layer 2: Neural network lines (thin, pulsing) -->
  <g stroke-width="0.5" fill="none" filter="url(#soften)">
    <line x1="140" y1="120" x2="380" y2="260" stroke="#3b82f6" opacity="0.08"><animate attributeName="opacity" values="0.04;0.12;0.04" dur="9s" repeatCount="indefinite"/></line>
    <line x1="380" y1="260" x2="620" y2="160" stroke="#8b5cf6" opacity="0.07"><animate attributeName="opacity" values="0.03;0.10;0.03" dur="11s" repeatCount="indefinite"/></line>
    <line x1="620" y1="160" x2="900" y2="320" stroke="#06b6d4" opacity="0.06"><animate attributeName="opacity" values="0.03;0.09;0.03" dur="13s" repeatCount="indefinite"/></line>
    <line x1="900" y1="320" x2="1180" y2="180" stroke="#3b82f6" opacity="0.07"><animate attributeName="opacity" values="0.04;0.11;0.04" dur="10s" repeatCount="indefinite"/></line>
    <line x1="1180" y1="180" x2="1360" y2="400" stroke="#8b5cf6" opacity="0.06"><animate attributeName="opacity" values="0.03;0.09;0.03" dur="12s" repeatCount="indefinite"/></line>
    <line x1="220" y1="520" x2="460" y2="640" stroke="#06b6d4" opacity="0.06"><animate attributeName="opacity" values="0.03;0.09;0.03" dur="14s" repeatCount="indefinite"/></line>
    <line x1="460" y1="640" x2="740" y2="500" stroke="#3b82f6" opacity="0.07"><animate attributeName="opacity" values="0.04;0.10;0.04" dur="9s" repeatCount="indefinite"/></line>
    <line x1="740" y1="500" x2="1040" y2="680" stroke="#8b5cf6" opacity="0.06"><animate attributeName="opacity" values="0.03;0.09;0.03" dur="15s" repeatCount="indefinite"/></line>
    <line x1="1040" y1="680" x2="1320" y2="560" stroke="#06b6d4" opacity="0.05"><animate attributeName="opacity" values="0.03;0.08;0.03" dur="11s" repeatCount="indefinite"/></line>
    <!-- Cross-links for depth -->
    <line x1="140" y1="120" x2="220" y2="520" stroke="#3b82f6" opacity="0.04"><animate attributeName="opacity" values="0.02;0.07;0.02" dur="16s" repeatCount="indefinite"/></line>
    <line x1="620" y1="160" x2="740" y2="500" stroke="#8b5cf6" opacity="0.04"><animate attributeName="opacity" values="0.02;0.06;0.02" dur="18s" repeatCount="indefinite"/></line>
    <line x1="900" y1="320" x2="1040" y2="680" stroke="#06b6d4" opacity="0.04"><animate attributeName="opacity" values="0.02;0.06;0.02" dur="14s" repeatCount="indefinite"/></line>
  </g>

  <!-- Layer 3: Floating nodes with glow halos -->
  <circle cx="140" cy="120" r="2.5" fill="#3b82f6" opacity="0.5"><animate attributeName="cy" values="120;108;126;120" dur="18s" repeatCount="indefinite"/><animate attributeName="opacity" values="0.35;0.65;0.35" dur="5s" repeatCount="indefinite"/></circle>
  <circle cx="140" cy="120" r="12" fill="url(#ng1)" opacity="0.2"><animate attributeName="cy" values="120;108;126;120" dur="18s" repeatCount="indefinite"/><animate attributeName="r" values="10;16;10" dur="5s" repeatCount="indefinite"/></circle>

  <circle cx="380" cy="260" r="2" fill="#8b5cf6" opacity="0.45"><animate attributeName="cx" values="380;370;390;380" dur="20s" repeatCount="indefinite"/><animate attributeName="opacity" values="0.3;0.6;0.3" dur="6s" repeatCount="indefinite"/></circle>
  <circle cx="380" cy="260" r="10" fill="url(#ng2)" opacity="0.18"><animate attributeName="cx" values="380;370;390;380" dur="20s" repeatCount="indefinite"/></circle>

  <circle cx="620" cy="160" r="2" fill="#06b6d4" opacity="0.4"><animate attributeName="cx" values="620;632;614;620" dur="22s" repeatCount="indefinite"/><animate attributeName="cy" values="160;150;168;160" dur="16s" repeatCount="indefinite"/></circle>
  <circle cx="620" cy="160" r="10" fill="url(#ng3)" opacity="0.15"><animate attributeName="cx" values="620;632;614;620" dur="22s" repeatCount="indefinite"/></circle>

  <circle cx="900" cy="320" r="3" fill="#3b82f6" opacity="0.45"><animate attributeName="cy" values="320;308;328;320" dur="19s" repeatCount="indefinite"/><animate attributeName="opacity" values="0.3;0.6;0.3" dur="7s" repeatCount="indefinite"/></circle>
  <circle cx="900" cy="320" r="14" fill="url(#ng1)" opacity="0.18"><animate attributeName="cy" values="320;308;328;320" dur="19s" repeatCount="indefinite"/><animate attributeName="r" values="12;18;12" dur="7s" repeatCount="indefinite"/></circle>

  <circle cx="1180" cy="180" r="2" fill="#8b5cf6" opacity="0.4"><animate attributeName="cy" values="180;170;188;180" dur="17s" repeatCount="indefinite"/></circle>
  <circle cx="1180" cy="180" r="10" fill="url(#ng2)" opacity="0.15"><animate attributeName="cy" values="180;170;188;180" dur="17s" repeatCount="indefinite"/></circle>

  <circle cx="1360" cy="400" r="1.8" fill="#06b6d4" opacity="0.35"><animate attributeName="cy" values="400;388;408;400" dur="20s" repeatCount="indefinite"/></circle>

  <circle cx="220" cy="520" r="2" fill="#06b6d4" opacity="0.4"><animate attributeName="cx" values="220;230;214;220" dur="21s" repeatCount="indefinite"/></circle>
  <circle cx="220" cy="520" r="10" fill="url(#ng3)" opacity="0.15"><animate attributeName="cx" values="220;230;214;220" dur="21s" repeatCount="indefinite"/></circle>

  <circle cx="460" cy="640" r="1.8" fill="#3b82f6" opacity="0.35"><animate attributeName="cx" values="460;470;452;460" dur="23s" repeatCount="indefinite"/></circle>

  <circle cx="740" cy="500" r="2.2" fill="#8b5cf6" opacity="0.4"><animate attributeName="cx" values="740;730;750;740" dur="19s" repeatCount="indefinite"/><animate attributeName="cy" values="500;490;508;500" dur="15s" repeatCount="indefinite"/></circle>
  <circle cx="740" cy="500" r="10" fill="url(#ng2)" opacity="0.15"><animate attributeName="cx" values="740;730;750;740" dur="19s" repeatCount="indefinite"/></circle>

  <circle cx="1040" cy="680" r="2" fill="#06b6d4" opacity="0.35"><animate attributeName="cx" values="1040;1050;1032;1040" dur="18s" repeatCount="indefinite"/></circle>
  <circle cx="1320" cy="560" r="1.5" fill="#3b82f6" opacity="0.3"><animate attributeName="cy" values="560;550;568;560" dur="16s" repeatCount="indefinite"/></circle>

  <!-- Ambient particles -->
  <circle cx="80" cy="780" r="1" fill="#3b82f6" opacity="0.15"><animate attributeName="opacity" values="0.08;0.22;0.08" dur="8s" repeatCount="indefinite"/></circle>
  <circle cx="520" cy="40" r="1" fill="#8b5cf6" opacity="0.12"><animate attributeName="opacity" values="0.06;0.18;0.06" dur="10s" repeatCount="indefinite"/></circle>
  <circle cx="1100" cy="80" r="1" fill="#06b6d4" opacity="0.12"><animate attributeName="opacity" values="0.06;0.18;0.06" dur="9s" repeatCount="indefinite"/></circle>
  <circle cx="300" cy="380" r="0.8" fill="#3b82f6" opacity="0.1"><animate attributeName="opacity" values="0.05;0.15;0.05" dur="7s" repeatCount="indefinite"/></circle>
  <circle cx="1280" cy="760" r="0.8" fill="#8b5cf6" opacity="0.1"><animate attributeName="opacity" values="0.05;0.15;0.05" dur="12s" repeatCount="indefinite"/></circle>
</svg>
</div>
"""
st.markdown(_svg_bg, unsafe_allow_html=True)

if not initialize_ai():
    st.error("GEMINI_API_KEY not found. Please set it in your environment variables or .env file.")
    st.stop()

if not st.session_state.db_checked:
    db_ready, db_error = initialize_database()
    st.session_state.db_ready = db_ready
    st.session_state.db_error = db_error or ""
    st.session_state.db_checked = True

pages = [
    st.Page(render_game_view, title="Game", icon="🎮", url_path="game", default=True),
    st.Page(render_leaderboard_view, title="Leaderboards", icon="🏆", url_path="leaderboards"),
    st.Page(render_dashboard_view, title="Dashboard", icon="📊", url_path="dashboard"),
]

navigation = st.navigation(pages, position="sidebar", expanded=False)
navigation.run()
