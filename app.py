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
bg_top = "#ffffff"
bg_mid = "#ffffff"
bg_bottom = "#ffffff"
bg_vignette = "#ffffff"

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
        background: #ffffff !important;
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
        background: #ffffff !important;
        border-right: 1px solid #e5e7eb;
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
        color: #111111 !important;
    }
    [data-testid="stMetric"], .stAlert, .stChatMessage, [data-testid="stDataFrame"], [data-testid="stExpander"] {
        backdrop-filter: blur(3px);
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
        color: #111111 !important;
    }
    [data-testid="stAppViewContainer"] > .main {
        color: #111111 !important;
    }
    [data-testid="stAppViewContainer"] > .main h1,
    [data-testid="stAppViewContainer"] > .main h2,
    [data-testid="stAppViewContainer"] > .main h3,
    [data-testid="stAppViewContainer"] > .main p,
    [data-testid="stAppViewContainer"] > .main li,
    [data-testid="stAppViewContainer"] > .main label,
    [data-testid="stAppViewContainer"] > .main [data-testid="stMarkdownContainer"],
    [data-testid="stAppViewContainer"] > .main [data-testid="stCaptionContainer"] {
        color: #111111 !important;
        text-shadow: none !important;
    }
    [data-testid="stAppViewContainer"] > .main [data-testid="stCaptionContainer"] {
        color: #111111 !important;
    }
    [data-testid="stAppViewContainer"] > .main [data-testid="stHeading"] * {
        color: #111111 !important;
    }
    [data-testid="stChatMessageContent"] * {
        color: #111111 !important;
    }
    [data-testid="stAppViewContainer"] > .main .block-container *:not(button):not(input):not(textarea) {
        color: #111111 !important;
    }
    .stButton > button {
        background: #ffffff !important;
        color: #111111 !important;
        border: 1px solid #d1d5db !important;
        border-radius: 14px;
        min-height: 44px;
        width: 100%;
        font-weight: 700;
        transition: transform 120ms ease, box-shadow 120ms ease, opacity 120ms ease;
        box-shadow: 0 2px 6px rgba(0, 0, 0, 0.08);
    }
    .stButton > button:hover {
        background: #f8fafc !important;
        color: #111111 !important;
        opacity: 0.97;
    }
    .stButton > button:active {
        transform: scale(0.95);
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.25);
    }
    [data-testid="stTextInput"] div[data-baseweb="input"] {
        background: #ffffff !important;
        border: 1px solid #94a3b8 !important;
        border-radius: 10px !important;
        box-shadow: none !important;
    }
    [data-testid="stTextInput"] div[data-baseweb="input"]:focus-within {
        border-color: #111827 !important;
        box-shadow: 0 0 0 2px rgba(17, 24, 39, 0.12) !important;
    }
    [data-testid="stTextInput"] input {
        color: #111111 !important;
        caret-color: #111111 !important;
    }
    .st-key-fg_chat_mic_anchor {
        height: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
    }
    .st-key-fg_open_voice_mode {
        position: fixed;
        right: 7.2rem;
        bottom: 1.15rem;
        z-index: 10020;
        margin: 0 !important;
        width: 42px !important;
    }
    .st-key-fg_open_voice_mode button {
        width: 42px !important;
        min-height: 42px !important;
        border-radius: 999px !important;
        padding: 0 !important;
        background: #ffffff !important;
        border: 1px solid #d1d5db !important;
        color: #111111 !important;
        font-size: 0.82rem !important;
        font-weight: 800 !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.14) !important;
    }
    .st-key-fg_open_voice_mode button:hover {
        background: #f8fafc !important;
        color: #111111 !important;
        opacity: 0.95 !important;
        transform: scale(0.96);
    }
    .st-key-fg_voice_bar_shell {
        background: #ffffff !important;
        border: 1px solid #d1d5db;
        border-radius: 24px;
        padding: 0.55rem 0.65rem 0.65rem 0.65rem;
        margin-top: 0.25rem;
        margin-bottom: 0.35rem;
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.08);
    }
    .st-key-fg_voice_bar_shell [data-testid="stCaptionContainer"] {
        color: #111111 !important;
        margin-bottom: 0.2rem;
    }
    .st-key-fg_voice_mic_button button,
    .st-key-fg_voice_lock_button button,
    .st-key-fg_voice_unlock_button button,
    .st-key-fg_voice_stop_button button {
        width: 56px !important;
        min-height: 56px !important;
        border-radius: 999px !important;
        padding: 0 !important;
        font-weight: 800 !important;
        font-size: 0.8rem !important;
    }
    .st-key-fg_voice_mic_button button {
        background: #ffffff !important;
        border: 1px solid #d1d5db !important;
        color: #111111 !important;
    }
    .st-key-fg_voice_lock_button button {
        background: #ffffff !important;
        border: 1px solid #d1d5db !important;
        color: #111111 !important;
    }
    .st-key-fg_voice_unlock_button button {
        background: #ffffff !important;
        border: 1px solid #d1d5db !important;
        color: #111111 !important;
    }
    .st-key-fg_voice_stop_button button {
        background: #ffffff !important;
        border: 1px solid #d1d5db !important;
        color: #111111 !important;
    }
    .st-key-fg_voice_exit_mode button {
        min-height: 56px !important;
        border-radius: 999px !important;
        background: #ffffff !important;
        border: 1px solid #d1d5db !important;
        color: #111111 !important;
        font-weight: 800 !important;
        font-size: 0.88rem !important;
    }
    @keyframes fgVoiceDotPulse {
        0% { transform: scale(0.9); opacity: 0.45; }
        50% { transform: scale(1.4); opacity: 1; }
        100% { transform: scale(0.9); opacity: 0.45; }
    }
    @keyframes fgVoiceBars {
        0%, 100% { transform: scaleY(0.3); opacity: 0.48; }
        50% { transform: scaleY(1); opacity: 1; }
    }
    .st-key-fg_voice_bar_shell .fg-voice-wave {
        margin-top: 0.35rem;
        border-radius: 999px;
        background: #f8fafc;
        border: 1px solid #d1d5db;
        padding: 0.32rem 0.58rem;
        display: flex;
        align-items: center;
        gap: 0.45rem;
    }
    .st-key-fg_voice_bar_shell .fg-wave-dot {
        width: 8px;
        height: 8px;
        border-radius: 999px;
        background: #64748b;
        flex: 0 0 auto;
    }
    .st-key-fg_voice_bar_shell .is-recording .fg-wave-dot {
        background: #ff6d7a;
        animation: fgVoiceDotPulse 920ms ease-in-out infinite;
    }
    .st-key-fg_voice_bar_shell .fg-wave-text {
        color: #111111;
        font-size: 0.84rem;
        font-weight: 650;
        white-space: nowrap;
    }
    .st-key-fg_voice_bar_shell .fg-wave-bars {
        margin-left: auto;
        display: flex;
        align-items: flex-end;
        gap: 3px;
        height: 16px;
    }
    .st-key-fg_voice_bar_shell .fg-wave-bars i {
        width: 3px;
        height: 14px;
        border-radius: 999px;
        background: #475569;
        transform-origin: center bottom;
        display: inline-block;
    }
    .st-key-fg_voice_bar_shell .is-recording .fg-wave-bars i {
        animation: fgVoiceBars 900ms ease-in-out infinite;
    }
    .st-key-fg_voice_bar_shell .is-recording .fg-wave-bars i:nth-child(2) { animation-delay: 80ms; }
    .st-key-fg_voice_bar_shell .is-recording .fg-wave-bars i:nth-child(3) { animation-delay: 150ms; }
    .st-key-fg_voice_bar_shell .is-recording .fg-wave-bars i:nth-child(4) { animation-delay: 220ms; }
    .st-key-fg_voice_bar_shell .is-recording .fg-wave-bars i:nth-child(5) { animation-delay: 300ms; }
    .st-key-fg_voice_bar_shell .is-idle .fg-wave-bars i {
        transform: scaleY(0.38);
        opacity: 0.4;
    }
    [data-testid="stFileUploader"] {
        background: #ffffff;
        border-radius: 14px;
        padding: 0.25rem;
    }
    section[data-testid="stFileUploaderDropzone"] {
        background: #ffffff !important;
        border: 1px dashed #cbd5e1 !important;
        border-radius: 14px !important;
        color: #111111 !important;
    }
    section[data-testid="stFileUploaderDropzone"] * {
        color: #111111 !important;
    }
    [data-testid="stFileUploaderDropzoneInstructions"] {
        color: #111111 !important;
    }
    [data-testid="stFileUploaderDropzoneInstructions"] small,
    [data-testid="stFileUploaderDropzoneInstructions"] span {
        color: #111111 !important;
    }
    [data-testid="stFileUploaderFileName"] {
        color: #111111 !important;
        background: #f8fafc;
        border-radius: 8px;
        padding: 0.2rem 0.35rem;
    }
    [data-testid="stFileUploader"] button,
    section[data-testid="stFileUploaderDropzone"] button {
        background: #ffffff !important;
        color: #111111 !important;
        border: 1px solid #d1d5db !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08) !important;
    }
    [data-testid="stFileUploader"] button:hover,
    section[data-testid="stFileUploaderDropzone"] button:hover {
        background: #f8fafc !important;
        color: #111111 !important;
        border-color: #cbd5e1 !important;
        opacity: 0.97 !important;
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
