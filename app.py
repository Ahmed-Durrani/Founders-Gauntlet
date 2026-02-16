# app.py
import streamlit as st
import time
from game_logic import get_ai_response, initialize_ai
from personas import LEVELS
from dotenv import load_dotenv
load_dotenv()

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="The Founder's Gauntlet", page_icon="💼", layout="wide")

# --- CSS FOR STYLING ---
st.markdown("""
<style>
    .stProgress > div > div > div > div {
        background-color: #00FF7F;
    }
    .user-msg {
        text-align: right;
        background-color: #2b313e;
        padding: 10px;
        border-radius: 10px;
        margin: 5px 0;
    }
    .ai-msg {
        text-align: left;
        background-color: #444c56;
        padding: 10px;
        border-radius: 10px;
        margin: 5px 0;
    }
</style>
""", unsafe_allow_html=True)

# --- INITIALIZATION ---
if "initialized" not in st.session_state:
    st.session_state.initialized = True
    st.session_state.current_hp = 100
    st.session_state.current_level = 1
    st.session_state.chat_history = [] # List of {"role": "user/ai", "content": "..."}
    st.session_state.game_over = False
    st.session_state.victory = False

# Check API Key
if not initialize_ai():
    st.error("⚠️ GEMINI_API_KEY not found. Please set it in your environment variables or .env file.")
    st.stop()

# --- SIDEBAR: STATS ---
with st.sidebar:
    st.title("📊 Founder Stats")
    
    # HP Bar Logic
    hp_color = "green" if st.session_state.current_hp > 50 else "orange" if st.session_state.current_hp > 20 else "red"
    st.markdown(f"**Confidence (HP):** {st.session_state.current_hp}/100")
    st.progress(st.session_state.current_hp / 100)
    
    st.divider()
    
    # Level Tracker
    current_lvl_data = LEVELS[st.session_state.current_level] if st.session_state.current_level <= 5 else None
    if current_lvl_data:
        st.subheader(f"📍 {current_lvl_data['title']}")
        st.caption(f"**Opponent:** {current_lvl_data['role']}")
        st.info(f"💡 **Tip:** {current_lvl_data['win_condition']}")
    
    # Reset Button
    if st.button("🔄 Restart Game"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

# --- MAIN GAME AREA ---
st.title("💼 The Founder's Gauntlet")
st.markdown("Pitch your startup. Survive the investors. Don't run out of confidence.")

# 1. HANDLE GAME OVER / VICTORY SCREENS
if st.session_state.game_over:
    st.error("💔 GAME OVER: You ran out of confidence.")
    st.write("Refine your pitch and try again.")
    if st.button("Try Again"):
        st.session_state.current_hp = 100
        st.session_state.game_over = False
        st.session_state.chat_history = []
        st.rerun()
    st.stop()

if st.session_state.victory:
    st.success("🚀 FUNDED! You survived the gauntlet and secured the investment!")
    st.balloons()
    st.stop()

# 2. DISPLAY CHAT HISTORY
chat_container = st.container()
with chat_container:
    if not st.session_state.chat_history:
        # Initial greeting from the first persona
        intro_msg = f"*(Level {st.session_state.current_level} Start)*\n\n**{LEVELS[st.session_state.current_level]['role']}** looks at you."
        st.session_state.chat_history.append({"role": "ai", "content": intro_msg})
    
    for msg in st.session_state.chat_history:
        if msg["role"] == "user":
            st.chat_message("user").write(msg["content"])
        else:
            st.chat_message("assistant").write(msg["content"])

# 3. USER INPUT & GAME LOOP
if user_input := st.chat_input("Type your pitch response here..."):
    # A. Render User Message immediately
    st.session_state.chat_history.append({"role": "user", "content": user_input})
    st.chat_message("user").write(user_input)

    # B. Get AI Response
    with st.spinner("The investor is judging you..."):
        ai_data = get_ai_response(
            user_input, 
            st.session_state.current_level, 
            st.session_state.chat_history
        )

    # C. Process Mechanics
    damage = ai_data.get("damage", 0)
    reply = ai_data.get("reply", "...")
    passed = ai_data.get("level_passed", False)

    # Apply Damage
    if damage < 0:
        st.session_state.current_hp += damage
        st.toast(f"💥 Took {damage} Damage! Reason: Judge didn't like that.", icon="📉")
    
    # Check Death
    if st.session_state.current_hp <= 0:
        st.session_state.current_hp = 0
        st.session_state.game_over = True
        st.rerun()

    # Append AI Reply to History
    st.session_state.chat_history.append({"role": "ai", "content": reply})
    
    # D. Check Level Pass
    if passed:
        st.toast("Level Complete! Moving to next room...", icon="✅")
        time.sleep(1.5) # Slight pause for effect
        
        st.session_state.current_level += 1
        
        # Check Win Condition
        if st.session_state.current_level > 5:
            st.session_state.victory = True
            st.rerun()
        else:
            # Setup next level
            st.session_state.chat_history = [] # Clear chat for new room
            st.rerun()
    else:
        # Just update the chat with the new AI message
        st.rerun()