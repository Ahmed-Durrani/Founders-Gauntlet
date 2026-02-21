import hashlib
import io
import time

import streamlit as st
import streamlit.components.v1 as components

from database import save_run_result
from feedback_fx import play_hidden_sound, trigger_haptic_feedback
from game_logic import (
    get_post_mortem_analysis,
    get_turn_judgment,
    stream_investor_reply,
    transcribe_pitch_audio,
)
from local_recovery import (
    clear_active_run_snapshot,
    is_local_storage_available,
    save_active_run_snapshot,
    try_restore_active_run_once,
)
from personas import LEVELS, THEMES
from session_utils import reset_run
from ui_helpers import compute_vc_valuation, format_currency, load_leaderboards, render_post_mortem_report

PERKS = {
    "charisma": {
        "name": "Charisma Buff",
        "description": "Reduce damage by 50 percent on your next round.",
    },
    "tech_shield": {
        "name": "Technical Cofounder Shield",
        "description": "Block the next incoming damage event completely.",
    },
    "none": {
        "name": "No Perk",
        "description": "Proceed with no temporary advantage.",
    },
}


def extract_pitch_deck_text(pdf_bytes):
    """
    Extracts text from an uploaded PDF.
    Returns: (text, page_count)
    """
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("pypdf is not installed. Add `pypdf` to requirements and install it.") from exc

    reader = PdfReader(io.BytesIO(pdf_bytes))
    page_text = []
    for page in reader.pages:
        page_text.append((page.extract_text() or "").strip())

    combined = "\n\n".join(page_text).strip()
    if not combined:
        raise ValueError("No readable text found in this PDF.")

    max_chars = 120_000
    if len(combined) > max_chars:
        combined = combined[:max_chars]

    return combined, len(reader.pages)


def clear_pitch_deck_state(clear_error=True):
    st.session_state.pitch_deck_text = ""
    st.session_state.pitch_deck_filename = ""
    st.session_state.pitch_deck_hash = ""
    st.session_state.pitch_deck_pages = 0
    if clear_error:
        st.session_state.pitch_deck_error = None


def _hp_fill_style(hp_value):
    if hp_value > 50:
        return "linear-gradient(90deg, #00c853 0%, #31e981 100%)"
    if hp_value > 20:
        return "linear-gradient(90deg, #f6d365 0%, #f39c12 100%)"
    return "linear-gradient(90deg, #ff4d4f 0%, #ff7875 100%)"


def render_animated_hp_bar():
    current_hp = max(0, min(100, int(st.session_state.current_hp)))
    previous_hp = max(0, min(100, int(st.session_state.previous_hp_for_ui)))
    bar_color = _hp_fill_style(current_hp)
    anim_id = f"hpAnim{int(time.time() * 1000)}"

    st.markdown(
        f"""
<style>
@keyframes {anim_id} {{
  0% {{ width: {previous_hp}%; }}
  100% {{ width: {current_hp}%; }}
}}
.hp-track {{
  width: 100%;
  height: 16px;
  border-radius: 999px;
  background: rgba(255,255,255,0.12);
  border: 1px solid rgba(255,255,255,0.12);
  overflow: hidden;
}}
.hp-fill {{
  height: 100%;
  width: {current_hp}%;
  border-radius: 999px;
  background: {bar_color};
  animation: {anim_id} 420ms ease-out forwards;
}}
</style>
<div class="hp-track"><div class="hp-fill"></div></div>
""",
        unsafe_allow_html=True,
    )
    st.session_state.previous_hp_for_ui = current_hp


def render_damage_flash_overlay():
    now = time.time()
    if st.session_state.damage_flash_until <= now:
        return

    flash_id = f"damageFlash{st.session_state.damage_flash_nonce}"
    st.markdown(
        f"""
<style>
@keyframes {flash_id} {{
  0% {{ box-shadow: inset 0 0 0 0 rgba(255, 64, 64, 0); opacity: 0; }}
  20% {{ box-shadow: inset 0 0 0 18px rgba(255, 64, 64, 0.28); opacity: 1; }}
  100% {{ box-shadow: inset 0 0 0 0 rgba(255, 64, 64, 0); opacity: 0; }}
}}
#damage-flash-overlay-{st.session_state.damage_flash_nonce} {{
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 9999;
  animation: {flash_id} 420ms ease-out 1;
}}
</style>
<div id="damage-flash-overlay-{st.session_state.damage_flash_nonce}"></div>
""",
        unsafe_allow_html=True,
    )


def save_snapshot_with_notice():
    if not is_local_storage_available():
        return
    saved = save_active_run_snapshot()
    if saved:
        st.session_state.local_storage_notice = "Progress saved to this device."


def bootstrap_local_recovery():
    restore_status = try_restore_active_run_once()
    if restore_status == "restored":
        st.toast("Recovered active run from local storage.")


def _render_mobile_mic_lock_bridge():
    """
    Mobile helper: hold mic and swipe up to trigger lock toggle.
    """
    components.html(
        """
<script>
(function () {
  const doc = window.parent && window.parent.document ? window.parent.document : document;

  function findButton(prefixes) {
    const buttons = Array.from(doc.querySelectorAll("button"));
    return buttons.find((btn) => {
      const txt = (btn.innerText || "").trim();
      return prefixes.some((prefix) => txt.startsWith(prefix));
    });
  }

  function bind() {
    const micBtn = findButton(["Mic", "Rec"]);
    const lockBtn = findButton(["Lock", "Unlock"]);
    if (!micBtn || !lockBtn || micBtn.dataset.fgMicBound === "1") {
      return;
    }
    micBtn.dataset.fgMicBound = "1";

    let startY = null;
    let startTs = 0;

    micBtn.addEventListener("touchstart", (ev) => {
      if (!ev.touches || ev.touches.length === 0) return;
      startY = ev.touches[0].clientY;
      startTs = Date.now();
    }, { passive: true });

    micBtn.addEventListener("touchmove", (ev) => {
      if (startY === null || !ev.touches || ev.touches.length === 0) return;
      const deltaY = startY - ev.touches[0].clientY;
      const heldMs = Date.now() - startTs;
      if (deltaY > 44 && heldMs > 220) {
        lockBtn.click();
        startY = null;
        startTs = 0;
      }
    }, { passive: true });

    micBtn.addEventListener("touchend", () => {
      startY = null;
      startTs = 0;
    }, { passive: true });
  }

  let attempts = 0;
  const timer = setInterval(() => {
    bind();
    attempts += 1;
    if (attempts > 20) {
      clearInterval(timer);
    }
  }, 250);

  bind();
})();
</script>
""",
        height=0,
        width=0,
    )


def _handle_voice_audio_capture(audio_file):
    audio_bytes = audio_file.getvalue() if audio_file else b""
    if not audio_bytes:
        return

    digest = hashlib.sha256(audio_bytes).hexdigest()
    if digest == st.session_state.voice_last_audio_hash:
        return

    st.session_state.voice_last_audio_hash = digest
    audio_type = getattr(audio_file, "type", None) or "audio/wav"
    with st.spinner("Transcribing audio..."):
        transcript = transcribe_pitch_audio(audio_bytes, audio_type)

    st.session_state.voice_audio_nonce = int(st.session_state.voice_audio_nonce) + 1

    if transcript:
        st.session_state.last_voice_transcript = transcript
        st.session_state.pending_voice_text = transcript
        st.session_state.voice_lock_prompt = "Voice draft ready. Edit and send."
        if not st.session_state.voice_mic_locked:
            st.session_state.voice_recorder_open = False
    else:
        st.session_state.voice_lock_prompt = "Transcription failed. Record again."

    st.rerun()


def render_compact_voice_controls():
    voice_user_input = None
    now = time.time()
    deadline = float(st.session_state.voice_double_click_deadline or 0.0)
    if deadline and now > deadline:
        st.session_state.voice_double_click_deadline = 0.0
        if st.session_state.voice_lock_prompt == "Click mic again to lock on desktop.":
            st.session_state.voice_lock_prompt = ""

    mic_col, lock_col, status_col = st.columns([0.16, 0.16, 0.68], gap="small")
    with mic_col:
        mic_label = "Rec" if st.session_state.voice_recorder_open else "Mic"
        mic_clicked = st.button(
            mic_label,
            key="fg_chat_mic_button",
            help="Tap mic to record once. Double-click on desktop to lock.",
        )
    with lock_col:
        lock_label = "Unlock" if st.session_state.voice_mic_locked else "Lock"
        lock_clicked = st.button(
            lock_label,
            key="fg_chat_mic_lock_button",
            help="Toggle mic lock.",
        )

    if mic_clicked:
        st.session_state.voice_recorder_open = True
        if st.session_state.voice_mic_locked:
            st.session_state.voice_lock_prompt = "Mic is locked."
        else:
            if deadline and now <= deadline:
                st.session_state.voice_mic_locked = True
                st.session_state.voice_double_click_deadline = 0.0
                st.session_state.voice_lock_prompt = "Mic locked (desktop double-click)."
            else:
                st.session_state.voice_double_click_deadline = now + 1.35
                st.session_state.voice_lock_prompt = "Click mic again to lock on desktop."

    if lock_clicked:
        st.session_state.voice_mic_locked = not st.session_state.voice_mic_locked
        st.session_state.voice_double_click_deadline = 0.0
        if st.session_state.voice_mic_locked:
            st.session_state.voice_recorder_open = True
            st.session_state.voice_lock_prompt = "Mic lock enabled."
        else:
            st.session_state.voice_lock_prompt = "Mic lock disabled."

    with status_col:
        if st.session_state.voice_lock_prompt:
            st.caption(st.session_state.voice_lock_prompt)
        else:
            st.caption("Mobile: hold mic and swipe up to lock. Desktop: double-click mic to lock.")

    _render_mobile_mic_lock_bridge()

    show_recorder = bool(st.session_state.voice_recorder_open or st.session_state.voice_mic_locked)
    if show_recorder:
        audio_file = st.audio_input(
            "Record your pitch",
            label_visibility="collapsed",
            sample_rate=16000,
            key=f"fg_chat_audio_{int(st.session_state.voice_audio_nonce)}",
        )
        if audio_file is not None:
            _handle_voice_audio_capture(audio_file)

    if st.session_state.pending_voice_text:
        st.text_area(
            "Voice draft",
            key="pending_voice_text",
            height=88,
            label_visibility="collapsed",
            placeholder="Voice draft (editable before send)",
        )
        send_col, discard_col = st.columns([0.6, 0.4], gap="small")
        if send_col.button("Send Voice", key="fg_send_voice_draft"):
            draft = st.session_state.pending_voice_text.strip()
            if draft:
                voice_user_input = draft
                st.session_state.last_voice_transcript = draft
                st.session_state.pending_voice_text = ""
                if not st.session_state.voice_mic_locked:
                    st.session_state.voice_recorder_open = False
            else:
                st.warning("Voice draft is empty.")
        if discard_col.button("Discard", key="fg_discard_voice_draft"):
            st.session_state.pending_voice_text = ""
            st.session_state.voice_lock_prompt = "Voice draft discarded."

    return voice_user_input


def apply_perk_choice(perk_key, next_level):
    perk = PERKS[perk_key]
    effects = st.session_state.active_perks

    if perk_key == "charisma":
        effects["next_round_damage_multiplier"] = 0.5
    elif perk_key == "tech_shield":
        effects["shield_charges"] += 1

    st.session_state.perk_history.append(
        {
            "level": next_level,
            "perk_key": perk_key,
            "perk_name": perk["name"],
        }
    )
    st.session_state.full_chat_history.append(
        {
            "role": "system",
            "content": f"Perk selected before Level {next_level}: {perk['name']} ({perk['description']})",
        }
    )


def apply_damage_with_perks(raw_damage):
    """
    Applies active perk effects to this turn's damage and updates HP.
    Returns: (effective_damage, notes)
    """
    notes = []
    try:
        base_damage = int(raw_damage)
    except (TypeError, ValueError):
        base_damage = 0

    if base_damage > 0:
        base_damage = 0

    effective_damage = base_damage
    effects = st.session_state.active_perks

    if effective_damage < 0 and effects["shield_charges"] > 0:
        effects["shield_charges"] -= 1
        effective_damage = 0
        notes.append("Technical Cofounder Shield blocked all damage this turn.")

    if effects["next_round_damage_multiplier"] < 1.0:
        multiplier = effects["next_round_damage_multiplier"]
        effects["next_round_damage_multiplier"] = 1.0

        if effective_damage < 0:
            reduced_damage = int(effective_damage * multiplier)
            if reduced_damage == 0:
                reduced_damage = -1
            notes.append(
                f"Charisma Buff reduced damage from {abs(effective_damage)} to {abs(reduced_damage)}."
            )
            effective_damage = reduced_damage
        else:
            notes.append("Charisma Buff was consumed this round (no incoming damage).")

    starting_hp = int(st.session_state.current_hp)
    st.session_state.previous_hp_for_ui = starting_hp
    st.session_state.current_hp += effective_damage
    if effective_damage < 0:
        st.session_state.damage_flash_nonce += 1
        st.session_state.damage_flash_until = time.time() + 0.55
    return effective_damage, notes


def get_or_generate_post_mortem(outcome):
    if (
        st.session_state.post_mortem_report is None
        or st.session_state.post_mortem_outcome != outcome
    ):
        transcript = st.session_state.full_chat_history or st.session_state.chat_history
        with st.spinner("Generating your post-mortem analytics..."):
            st.session_state.post_mortem_report = get_post_mortem_analysis(
                transcript,
                st.session_state.startup_theme,
                outcome,
                st.session_state.pitch_deck_text,
            )
        st.session_state.post_mortem_outcome = outcome
    return st.session_state.post_mortem_report


def persist_outcome_if_needed(outcome, report):
    """
    Saves one completed run to Postgres (once per run).
    """
    if not st.session_state.db_ready:
        return
    if st.session_state.result_persisted:
        return

    handle = st.session_state.player_handle.strip()
    if not handle:
        st.session_state.persistence_notice = "Add a Player Handle to submit this run to the leaderboard."
        return

    clan_name = st.session_state.clan_name.strip()
    valuation_usd = st.session_state.final_valuation_usd if outcome == "victory" else 0

    run_payload = {
        "outcome": outcome,
        "theme": st.session_state.startup_theme,
        "valuation_usd": valuation_usd,
        "hp_remaining": st.session_state.current_hp,
        "level_reached": st.session_state.current_level if outcome != "victory" else 5,
        "post_mortem": report,
        "transcript": st.session_state.full_chat_history,
    }
    run_id = save_run_result(handle, clan_name, run_payload)
    if run_id:
        st.session_state.result_persisted = True
        st.session_state.persisted_run_id = run_id
        st.session_state.persistence_notice = "Run submitted to global rankings."
        load_leaderboards.clear()
    else:
        st.session_state.persistence_notice = "Could not save run to the database."


def render_sidebar():
    in_live_combat = (
        st.session_state.game_started
        and not st.session_state.game_over
        and not st.session_state.victory
        and not st.session_state.awaiting_perk_selection
    )

    with st.sidebar:
        st.title("Founder Stats")

        st.markdown("### Identity")
        st.session_state.player_handle = st.text_input(
            "Player Handle",
            value=st.session_state.player_handle,
            max_chars=40,
            help="Used for global rankings.",
            disabled=in_live_combat,
        ).strip()
        st.session_state.clan_name = st.text_input(
            "Syndicate",
            value=st.session_state.clan_name,
            max_chars=40,
            help="Players with the same syndicate name share a leaderboard entry.",
            disabled=in_live_combat,
        ).strip()

        theme_options = list(THEMES.keys())
        selected_theme = st.selectbox(
            "Startup Theme",
            options=theme_options,
            index=theme_options.index(st.session_state.startup_theme),
            disabled=st.session_state.game_started,
            help="Theme is locked after your first response. Restart to change it.",
        )
        st.session_state.startup_theme = selected_theme
        st.caption(THEMES[selected_theme]["description"])

        st.markdown("### Pitch Deck Ingestion")
        uploaded_deck = st.file_uploader(
            "Upload a PDF business plan or pitch deck",
            type=["pdf"],
            accept_multiple_files=False,
            disabled=st.session_state.game_started,
        )

        if uploaded_deck is not None:
            uploaded_bytes = uploaded_deck.getvalue()
            uploaded_hash = hashlib.sha256(uploaded_bytes).hexdigest()
            if uploaded_hash != st.session_state.pitch_deck_hash:
                with st.spinner("Extracting deck text..."):
                    try:
                        deck_text, page_count = extract_pitch_deck_text(uploaded_bytes)
                        st.session_state.pitch_deck_text = deck_text
                        st.session_state.pitch_deck_filename = uploaded_deck.name
                        st.session_state.pitch_deck_hash = uploaded_hash
                        st.session_state.pitch_deck_pages = page_count
                        st.session_state.pitch_deck_error = None
                        st.session_state.post_mortem_report = None
                    except Exception as exc:
                        clear_pitch_deck_state(clear_error=False)
                        st.session_state.pitch_deck_hash = uploaded_hash
                        st.session_state.pitch_deck_error = str(exc)

        if st.session_state.pitch_deck_error:
            st.warning(f"Deck parsing issue: {st.session_state.pitch_deck_error}")

        if st.session_state.pitch_deck_text:
            st.success(
                f"Loaded deck: {st.session_state.pitch_deck_filename} "
                f"({st.session_state.pitch_deck_pages} pages)"
            )
            if st.button("Remove Pitch Deck", disabled=st.session_state.game_started):
                clear_pitch_deck_state()
                st.rerun()
        else:
            st.caption("No deck loaded. AI will rely only on chat context.")

        st.markdown(f"**Confidence (HP):** {st.session_state.current_hp}/100")
        render_animated_hp_bar()

        st.markdown("### Active Perks")
        active_perk_lines = []
        if st.session_state.active_perks["shield_charges"] > 0:
            active_perk_lines.append(
                f"- Technical Cofounder Shield: {st.session_state.active_perks['shield_charges']} charge(s)"
            )
        if st.session_state.active_perks["next_round_damage_multiplier"] < 1.0:
            active_perk_lines.append("- Charisma Buff: active for next round")
        if not active_perk_lines:
            st.caption("No active perks.")
        else:
            for line in active_perk_lines:
                st.write(line)

        if st.session_state.perk_history:
            last_pick = st.session_state.perk_history[-1]
            st.caption(f"Last perk: {last_pick['perk_name']} (before Level {last_pick['level']})")

        if st.session_state.db_ready:
            st.caption("Multiplayer database: connected")
        else:
            st.caption(f"Multiplayer database: offline ({st.session_state.db_error or 'not configured'})")
        if st.session_state.local_storage_notice:
            st.caption(f"Recovery: {st.session_state.local_storage_notice}")

        st.divider()

        current_lvl_data = LEVELS[st.session_state.current_level] if st.session_state.current_level <= 5 else None
        if current_lvl_data:
            st.subheader(current_lvl_data["title"])
            st.caption(f"Opponent: {current_lvl_data['role']}")
            st.info(f"Tip: {current_lvl_data['win_condition']}")

        if st.button("Restart Game"):
            clear_active_run_snapshot()
            reset_run()
            st.rerun()


def render_game_view():
    bootstrap_local_recovery()
    st.session_state.max_level_reached = max(
        int(st.session_state.max_level_reached),
        int(st.session_state.current_level),
    )
    render_sidebar()
    render_damage_flash_overlay()

    st.title("The Founder's Gauntlet")
    st.markdown("Pitch your startup. Survive the investors. Don't run out of confidence.")
    st.caption(f"Current Theme: {st.session_state.startup_theme}")
    st.caption("Streaming mode enabled: investor replies render token-by-token.")

    if st.session_state.pitch_deck_text:
        st.caption("Pitch deck context loaded. Investor responses cross-reference your uploaded document.")

    if st.session_state.game_over:
        st.error("GAME OVER: You ran out of confidence.")
        st.write("Refine your pitch and try again.")
        report = get_or_generate_post_mortem("game_over")
        st.session_state.final_valuation_usd = 0
        persist_outcome_if_needed("game_over", report)
        if st.session_state.persistence_notice:
            st.caption(st.session_state.persistence_notice)
        render_post_mortem_report(report)
        if st.button("Try Again"):
            clear_active_run_snapshot()
            reset_run()
            st.rerun()
        clear_active_run_snapshot()
        return

    if st.session_state.victory:
        st.success("FUNDED! You survived the gauntlet and secured the investment.")
        st.balloons()
        report = get_or_generate_post_mortem("victory")
        if st.session_state.final_valuation_usd <= 0:
            st.session_state.final_valuation_usd = compute_vc_valuation(
                report=report,
                current_hp=st.session_state.current_hp,
                has_pitch_deck=bool(st.session_state.pitch_deck_text),
                perk_count=len(st.session_state.perk_history),
            )
        st.metric("Secured VC Valuation", format_currency(st.session_state.final_valuation_usd))
        if not st.session_state.victory_audio_played and st.session_state.final_valuation_usd >= 3_500_000:
            play_hidden_sound("valuation", nonce=int(time.time() * 1000))
            st.session_state.victory_audio_played = True
        persist_outcome_if_needed("victory", report)
        if st.session_state.persistence_notice:
            st.caption(st.session_state.persistence_notice)
        render_post_mortem_report(report)
        if st.button("Play Again"):
            clear_active_run_snapshot()
            reset_run()
            st.rerun()
        clear_active_run_snapshot()
        return

    if st.session_state.awaiting_perk_selection:
        next_level = st.session_state.pending_next_level or (st.session_state.current_level + 1)
        st.success(f"Level {next_level - 1} complete.")
        st.subheader(f"Choose a Perk Before Level {next_level}")
        st.write("Pick one progression perk to carry into the next stage.")

        perk_choice = st.radio(
            "Perk",
            options=list(PERKS.keys()),
            format_func=lambda key: f"{PERKS[key]['name']}: {PERKS[key]['description']}",
        )

        if st.button("Lock Perk and Continue"):
            apply_perk_choice(perk_choice, next_level)
            st.session_state.current_level = next_level
            st.session_state.chat_history = []
            st.session_state.awaiting_perk_selection = False
            st.session_state.pending_next_level = None
            save_snapshot_with_notice()
            st.rerun()
        return

    chat_container = st.container()
    with chat_container:
        if not st.session_state.chat_history:
            deck_status = (
                "Deck mode: enabled (cross-referencing your uploaded plan)."
                if st.session_state.pitch_deck_text
                else "Deck mode: disabled (no uploaded document)."
            )
            intro_msg = (
                f"*(Level {st.session_state.current_level} Start)*\n\n"
                f"**{LEVELS[st.session_state.current_level]['role']}** looks at you.\n\n"
                f"Theme focus: **{st.session_state.startup_theme}**\n\n"
                f"{deck_status}"
            )
            intro_entry = {"role": "ai", "content": intro_msg}
            st.session_state.chat_history.append(intro_entry)
            st.session_state.full_chat_history.append(intro_entry)

        for msg in st.session_state.chat_history:
            if msg["role"] == "user":
                st.chat_message("user").write(msg["content"])
            else:
                st.chat_message("assistant").write(msg["content"])

    voice_user_input = render_compact_voice_controls()
    typed_input = st.chat_input("Type your pitch response here...")
    user_input = typed_input or voice_user_input

    if not user_input:
        return

    st.session_state.game_started = True

    user_msg = {"role": "user", "content": user_input}
    st.session_state.chat_history.append(user_msg)
    st.session_state.full_chat_history.append(user_msg)
    st.chat_message("user").write(user_input)

    with st.chat_message("assistant"):
        streamed_reply = st.write_stream(
            stream_investor_reply(
                user_input=user_input,
                current_level=st.session_state.current_level,
                chat_history=st.session_state.chat_history,
                startup_theme=st.session_state.startup_theme,
                pitch_deck_text=st.session_state.pitch_deck_text,
            )
        )
    streamed_reply = (streamed_reply or "").strip()
    if not streamed_reply:
        streamed_reply = "*(The investor is silent. Please try again.)*"

    ai_msg = {"role": "ai", "content": streamed_reply}
    judgment_history = st.session_state.chat_history + [ai_msg]

    with st.spinner("Finalizing round mechanics..."):
        judgment = get_turn_judgment(
            user_input=user_input,
            current_level=st.session_state.current_level,
            chat_history=judgment_history,
            startup_theme=st.session_state.startup_theme,
            pitch_deck_text=st.session_state.pitch_deck_text,
        )

    damage = judgment.get("damage", 0)
    passed = judgment.get("level_passed", False)

    try:
        raw_damage_value = int(damage)
    except (TypeError, ValueError):
        raw_damage_value = 0

    effective_damage, damage_notes = apply_damage_with_perks(raw_damage_value)
    st.session_state.turn_damage_log.append(
        {
            "turn": len(st.session_state.turn_damage_log) + 1,
            "level": int(st.session_state.current_level),
            "raw_damage": int(raw_damage_value),
            "effective_damage": int(effective_damage),
            "hp_after": int(st.session_state.current_hp),
        }
    )

    if raw_damage_value < 0:
        if effective_damage < 0:
            st.toast(f"Took {abs(effective_damage)} damage this round (base: {abs(raw_damage_value)}).")
            vibration_pattern = [200, 100, 200] if abs(effective_damage) >= 10 else [120, 60, 120]
            trigger_haptic_feedback(vibration_pattern, nonce=st.session_state.damage_flash_nonce)
            play_hidden_sound("damage", nonce=st.session_state.damage_flash_nonce)
        else:
            st.toast("No damage taken this round.")

    for note in damage_notes:
        st.toast(note)

    st.session_state.chat_history.append(ai_msg)
    st.session_state.full_chat_history.append(ai_msg)
    save_snapshot_with_notice()

    if st.session_state.current_hp <= 0:
        st.session_state.current_hp = 0
        st.session_state.game_over = True
        st.rerun()

    if passed:
        if st.session_state.current_level >= 5:
            st.session_state.victory = True
            st.rerun()

        st.session_state.awaiting_perk_selection = True
        st.session_state.pending_next_level = st.session_state.current_level + 1
        st.session_state.full_chat_history.append(
            {
                "role": "system",
                "content": (
                    f"Level {st.session_state.current_level} passed. "
                    f"Perk selection shown before Level {st.session_state.pending_next_level}."
                ),
            }
        )
        st.toast("Level complete. Choose a perk for the next room.")
        time.sleep(0.8)
        st.rerun()
    else:
        st.rerun()
