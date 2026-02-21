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
if hp >= 30:
    stress = (100 - hp) / 70.0
    bg_top = _blend("#f4f7ff", "#fff2f3", stress * 0.36)
    bg_mid = _blend("#e8efff", "#ffdfe3", stress * 0.52)
    bg_bottom = _blend("#d6e1f5", "#b07f88", stress * 0.62)
    bg_vignette = _blend("#4b6fa8", "#8f2233", stress * 0.48)
else:
    critical = (30 - hp) / 30.0
    bg_top = _blend("#ffe8ea", "#2b1518", critical * 0.84)
    bg_mid = _blend("#f5b8bf", "#1d0f13", critical * 0.95)
    bg_bottom = _blend("#ab5c6c", "#12080c", critical)
    bg_vignette = _blend("#7e1f2f", "#0a0506", critical)

global_css = """
<style>
    :root {
        --fg-bg-top: __BG_TOP__;
        --fg-bg-mid: __BG_MID__;
        --fg-bg-bottom: __BG_BOTTOM__;
        --fg-bg-vignette: __BG_VIGNETTE__;
    }
    @keyframes fgAuroraShift {
        0% { transform: translate3d(-4%, -3%, 0) scale(1); opacity: 0.38; }
        50% { transform: translate3d(4%, 3%, 0) scale(1.12); opacity: 0.62; }
        100% { transform: translate3d(-4%, -3%, 0) scale(1); opacity: 0.38; }
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
        background:
            radial-gradient(120% 82% at 50% -12%, rgba(255, 255, 255, 0.55) 0%, rgba(255, 255, 255, 0) 60%),
            radial-gradient(150% 120% at 50% 112%, var(--fg-bg-vignette) 0%, transparent 67%),
            linear-gradient(180deg, var(--fg-bg-top) 0%, var(--fg-bg-mid) 54%, var(--fg-bg-bottom) 100%);
        background-size: 170% 170%, 170% 170%, 100% 100%;
        animation: fgBackdropShift 16s ease-in-out infinite;
        transition: background 420ms ease;
    }
    [data-testid="stAppViewContainer"]::after {
        content: "";
        position: fixed;
        inset: -18%;
        pointer-events: none;
        background:
            radial-gradient(45% 54% at 16% 24%, rgba(84, 129, 194, 0.34) 0%, rgba(84, 129, 194, 0) 74%),
            radial-gradient(50% 56% at 84% 74%, rgba(187, 69, 86, 0.26) 0%, rgba(187, 69, 86, 0) 76%);
        filter: blur(12px);
        animation: fgAuroraShift 12s ease-in-out infinite;
        z-index: 0;
    }
    [data-testid="stAppViewContainer"]::before {
        content: "";
        position: fixed;
        inset: 0;
        pointer-events: none;
        background-image:
            repeating-linear-gradient(
                135deg,
                rgba(255, 255, 255, 0.05) 0px,
                rgba(255, 255, 255, 0.05) 2px,
                rgba(255, 255, 255, 0.01) 2px,
                rgba(255, 255, 255, 0.01) 8px
            );
        opacity: 0.22;
        mix-blend-mode: soft-light;
        animation: fgGridDrift 12s linear infinite;
        z-index: 0;
    }
    [data-testid="stAppViewContainer"] > .main::before {
        content: "";
        position: fixed;
        inset: -24%;
        pointer-events: none;
        background:
            conic-gradient(
                from 40deg at 50% 50%,
                rgba(124, 178, 255, 0.26) 0deg,
                rgba(124, 178, 255, 0) 80deg,
                rgba(255, 132, 132, 0.22) 170deg,
                rgba(255, 132, 132, 0) 260deg,
                rgba(124, 178, 255, 0.26) 360deg
            );
        mix-blend-mode: screen;
        animation: fgOrbitalGlow 22s linear infinite;
        z-index: 0;
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
        background: linear-gradient(180deg, rgba(17, 25, 43, 0.92) 0%, rgba(18, 23, 37, 0.95) 100%);
        border-right: 1px solid rgba(255, 255, 255, 0.08);
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
        color: #f2f4ff;
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
    }
    .stButton > button {
        background: linear-gradient(180deg, #1f2a44 0%, #182237 100%) !important;
        color: #f2f6ff !important;
        border: 1px solid rgba(255, 255, 255, 0.14) !important;
        border-radius: 14px;
        min-height: 44px;
        width: 100%;
        font-weight: 700;
        transition: transform 120ms ease, box-shadow 120ms ease, opacity 120ms ease;
        box-shadow: 0 5px 14px rgba(0, 0, 0, 0.2);
    }
    .stButton > button:hover {
        background: linear-gradient(180deg, #1f2a44 0%, #182237 100%) !important;
        color: #f2f6ff !important;
        opacity: 0.97;
    }
    .stButton > button:active {
        transform: scale(0.95);
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.25);
    }
    [data-testid="stFileUploader"] {
        background: rgba(12, 20, 36, 0.34);
        border-radius: 14px;
        padding: 0.25rem;
    }
    section[data-testid="stFileUploaderDropzone"] {
        background: linear-gradient(180deg, rgba(25, 35, 58, 0.95) 0%, rgba(18, 27, 45, 0.95) 100%) !important;
        border: 1px dashed rgba(180, 208, 255, 0.45) !important;
        border-radius: 14px !important;
        color: #f2f6ff !important;
    }
    section[data-testid="stFileUploaderDropzone"] * {
        color: #f2f6ff !important;
    }
    [data-testid="stFileUploaderDropzoneInstructions"] {
        color: #d9e6ff !important;
    }
    [data-testid="stFileUploaderDropzoneInstructions"] small,
    [data-testid="stFileUploaderDropzoneInstructions"] span {
        color: #b4c5e6 !important;
    }
    [data-testid="stFileUploaderFileName"] {
        color: #f2f6ff !important;
        background: rgba(10, 16, 29, 0.45);
        border-radius: 8px;
        padding: 0.2rem 0.35rem;
    }
    [data-testid="stFileUploader"] button,
    section[data-testid="stFileUploaderDropzone"] button {
        background: linear-gradient(180deg, #1f2a44 0%, #182237 100%) !important;
        color: #f2f6ff !important;
        border: 1px solid rgba(255, 255, 255, 0.14) !important;
        box-shadow: 0 5px 14px rgba(0, 0, 0, 0.2) !important;
    }
    [data-testid="stFileUploader"] button:hover,
    section[data-testid="stFileUploaderDropzone"] button:hover {
        background: linear-gradient(180deg, #1f2a44 0%, #182237 100%) !important;
        color: #f2f6ff !important;
        border-color: rgba(255, 255, 255, 0.2) !important;
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
            opacity: 0.16;
        }
        [data-testid="stAppViewContainer"]::after {
            filter: blur(13px);
            opacity: 0.95;
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
        [data-testid="stSidebar"] {
            width: 100vw !important;
            min-width: 100vw !important;
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

navigation = st.navigation(pages, position="sidebar", expanded=True)
navigation.run()
