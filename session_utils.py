import copy

import streamlit as st


SESSION_DEFAULTS = {
    "current_hp": 100,
    "current_level": 1,
    "chat_history": [],
    "full_chat_history": [],
    "game_over": False,
    "victory": False,
    "startup_theme": "General SaaS",
    "game_started": False,
    "post_mortem_report": None,
    "post_mortem_outcome": None,
    "awaiting_perk_selection": False,
    "pending_next_level": None,
    "active_perks": {
        "next_round_damage_multiplier": 1.0,
        "shield_charges": 0,
    },
    "perk_history": [],
    "pitch_deck_text": "",
    "pitch_deck_filename": "",
    "pitch_deck_hash": "",
    "pitch_deck_pages": 0,
    "pitch_deck_error": None,
    "player_handle": "",
    "clan_name": "",
    "final_valuation_usd": 0,
    "result_persisted": False,
    "persisted_run_id": None,
    "persistence_notice": "",
    "db_ready": False,
    "db_error": "",
    "db_checked": False,
    "pending_voice_text": "",
    "last_voice_transcript": "",
    "voice_mic_locked": False,
    "voice_mode_active": False,
    "voice_recording": False,
    "voice_recorder_open": False,
    "voice_double_click_deadline": 0.0,
    "voice_lock_prompt": "",
    "voice_last_audio_hash": "",
    "voice_audio_nonce": 0,
    "turn_damage_log": [],
    "max_level_reached": 1,
    "victory_audio_played": False,
    "previous_hp_for_ui": 100,
    "damage_flash_until": 0.0,
    "damage_flash_nonce": 0,
    "local_restore_applied": False,
    "local_restore_checked": False,
    "local_restore_attempts": 0,
    "local_storage_notice": "",
    "local_save_nonce": 0,
}


def ensure_session_state():
    for key, default_value in SESSION_DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = copy.deepcopy(default_value)


def reset_run():
    """Resets one game run while preserving identity, theme, and uploaded deck."""
    st.session_state.current_hp = 100
    st.session_state.current_level = 1
    st.session_state.chat_history = []
    st.session_state.full_chat_history = []
    st.session_state.game_over = False
    st.session_state.victory = False
    st.session_state.game_started = False
    st.session_state.post_mortem_report = None
    st.session_state.post_mortem_outcome = None
    st.session_state.awaiting_perk_selection = False
    st.session_state.pending_next_level = None
    st.session_state.active_perks = {
        "next_round_damage_multiplier": 1.0,
        "shield_charges": 0,
    }
    st.session_state.perk_history = []
    st.session_state.final_valuation_usd = 0
    st.session_state.result_persisted = False
    st.session_state.persisted_run_id = None
    st.session_state.persistence_notice = ""
    st.session_state.pending_voice_text = ""
    st.session_state.last_voice_transcript = ""
    st.session_state.voice_mic_locked = False
    st.session_state.voice_mode_active = False
    st.session_state.voice_recording = False
    st.session_state.voice_recorder_open = False
    st.session_state.voice_double_click_deadline = 0.0
    st.session_state.voice_lock_prompt = ""
    st.session_state.voice_last_audio_hash = ""
    st.session_state.voice_audio_nonce = 0
    st.session_state.turn_damage_log = []
    st.session_state.max_level_reached = 1
    st.session_state.victory_audio_played = False
    st.session_state.previous_hp_for_ui = st.session_state.current_hp
    st.session_state.damage_flash_until = 0.0
    st.session_state.damage_flash_nonce = 0
    st.session_state.local_restore_applied = False
    st.session_state.local_restore_checked = False
    st.session_state.local_restore_attempts = 0
    st.session_state.local_storage_notice = ""
