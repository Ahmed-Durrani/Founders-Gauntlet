import copy
import json
import os
import time

import streamlit as st

try:
    from streamlit_local_storage import LocalStorage
except ImportError:
    LocalStorage = None

STORAGE_KEY = "founders_gauntlet_active_run_v1"

SNAPSHOT_KEYS = (
    "current_hp",
    "current_level",
    "chat_history",
    "full_chat_history",
    "game_over",
    "victory",
    "startup_theme",
    "game_started",
    "awaiting_perk_selection",
    "pending_next_level",
    "active_perks",
    "perk_history",
    "player_handle",
    "clan_name",
    "pending_voice_text",
    "last_voice_transcript",
    "voice_mic_locked",
    "voice_mode_active",
    "voice_recording",
    "voice_recorder_open",
    "voice_double_click_deadline",
    "voice_lock_prompt",
    "voice_last_audio_hash",
    "voice_audio_nonce",
    "turn_damage_log",
    "max_level_reached",
    "victory_audio_played",
    "previous_hp_for_ui",
    "final_valuation_usd",
)


def is_local_storage_available():
    return LocalStorage is not None


def _get_storage():
    if os.getenv("FG_DISABLE_LOCAL_RECOVERY", "").strip() == "1":
        return None
    if LocalStorage is None:
        return None
    try:
        return LocalStorage()
    except Exception:
        return None


def _safe_get_item(storage, item_key, component_key):
    try:
        return storage.getItem(item_key, key=component_key)
    except TypeError:
        try:
            return storage.getItem(item_key)
        except Exception:
            return None
    except Exception:
        return None


def _safe_set_item(storage, item_key, item_value, component_key):
    try:
        storage.setItem(item_key, item_value, key=component_key)
        return True
    except TypeError:
        try:
            storage.setItem(item_key, item_value)
            return True
        except Exception:
            return False
    except Exception:
        return False


def _safe_delete_item(storage, item_key, component_key):
    delete_methods = ("deleteItem", "eraseItem", "removeItem")
    for method_name in delete_methods:
        method = getattr(storage, method_name, None)
        if method is None:
            continue
        try:
            method(item_key, key=component_key)
            return True
        except TypeError:
            try:
                method(item_key)
                return True
            except Exception:
                continue
        except Exception:
            continue
    return _safe_set_item(storage, item_key, "", component_key)


def save_active_run_snapshot():
    """
    Save the active run to browser local storage.
    Returns True if write call succeeded.
    """
    storage = _get_storage()
    if storage is None:
        return False

    snapshot = {key: copy.deepcopy(st.session_state.get(key)) for key in SNAPSHOT_KEYS}
    snapshot["saved_at_epoch"] = int(time.time())
    snapshot["snapshot_version"] = 1

    payload = json.dumps(snapshot, ensure_ascii=True)
    write_key = f"fg_save_snapshot_{st.session_state.local_save_nonce}"
    st.session_state.local_save_nonce += 1
    return _safe_set_item(storage, STORAGE_KEY, payload, write_key)


def clear_active_run_snapshot():
    storage = _get_storage()
    if storage is None:
        return False

    clear_key = f"fg_clear_snapshot_{st.session_state.local_save_nonce}"
    st.session_state.local_save_nonce += 1
    return _safe_delete_item(storage, STORAGE_KEY, clear_key)


def _validate_snapshot(snapshot):
    if not isinstance(snapshot, dict):
        return False
    if "current_hp" not in snapshot or "chat_history" not in snapshot:
        return False
    if not isinstance(snapshot.get("chat_history"), list):
        return False
    return True


def try_restore_active_run_once():
    """
    Attempt to restore run state from local storage.
    Safe to call on every rerun. It exits quickly after successful restore/check.
    """
    if st.session_state.local_restore_applied:
        return "already-restored"

    if st.session_state.local_restore_checked and st.session_state.local_restore_attempts >= 3:
        return "already-checked"

    if st.session_state.game_started or st.session_state.chat_history:
        st.session_state.local_restore_checked = True
        return "active-session-present"

    storage = _get_storage()
    if storage is None:
        st.session_state.local_restore_checked = True
        st.session_state.local_storage_notice = "Install streamlit-local-storage to enable recovery."
        return "storage-unavailable"

    read_key = f"fg_restore_read_{st.session_state.local_restore_attempts}"
    raw_value = _safe_get_item(storage, STORAGE_KEY, read_key)
    st.session_state.local_restore_attempts += 1

    if raw_value in (None, "", "null", "None"):
        if raw_value in ("", "null", "None"):
            st.session_state.local_restore_checked = True
            return "no-snapshot"
        if st.session_state.local_restore_attempts >= 3:
            st.session_state.local_restore_checked = True
            return "no-snapshot"
        return "pending"

    if isinstance(raw_value, str):
        try:
            snapshot = json.loads(raw_value)
        except Exception:
            st.session_state.local_restore_checked = True
            return "invalid-json"
    elif isinstance(raw_value, dict):
        snapshot = raw_value
    else:
        st.session_state.local_restore_checked = True
        return "invalid-type"

    if not _validate_snapshot(snapshot):
        st.session_state.local_restore_checked = True
        return "invalid-payload"

    for key in SNAPSHOT_KEYS:
        if key in snapshot:
            st.session_state[key] = snapshot[key]

    st.session_state.local_restore_applied = True
    st.session_state.local_restore_checked = True
    st.session_state.local_storage_notice = "Recovered active run from local storage."
    return "restored"
