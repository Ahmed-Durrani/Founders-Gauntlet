import os

import streamlit as st

from feedback_fx import render_copy_button
from ui_helpers import format_currency, render_post_mortem_report


def _damage_to_emoji(turn_data):
    try:
        effective = abs(int(turn_data.get("effective_damage", 0)))
    except (TypeError, ValueError):
        effective = 0

    if effective <= 0:
        return "🟩"
    if effective <= 10:
        return "🟨"
    return "🟥"


def _build_share_text(outcome, valuation):
    turns = st.session_state.turn_damage_log or []
    emoji_track = "".join(_damage_to_emoji(item) for item in turns) or "⬜"
    run_tag = "🚀" if outcome == "victory" else "💥"
    theme = st.session_state.startup_theme
    level_reached = int(st.session_state.max_level_reached)
    hp_text = f"{int(st.session_state.current_hp)}/100"
    founder = st.session_state.player_handle or "Anonymous Founder"
    app_url = (os.getenv("APP_PUBLIC_URL") or "").strip()
    app_url = app_url or "https://your-streamlit-app-url"

    return (
        f"Founder's Gauntlet {emoji_track} {run_tag}\n"
        f"{founder} | {theme} | Reached L{level_reached} | HP {hp_text} | Valuation {format_currency(valuation)}\n"
        f"Play: {app_url}"
    )


def render_dashboard_view():
    st.title("Performance Dashboard")
    st.caption("Review the latest run analysis and transcript.")

    report = st.session_state.post_mortem_report
    if report is None:
        st.info("No completed run yet. Finish a game to unlock analytics.")
        return

    outcome = st.session_state.post_mortem_outcome or "unknown"
    valuation = st.session_state.final_valuation_usd

    summary_cols = st.columns(4)
    summary_cols[0].metric("Outcome", outcome.replace("_", " ").title())
    summary_cols[1].metric("Theme", st.session_state.startup_theme)
    summary_cols[2].metric("Valuation", format_currency(valuation))
    summary_cols[3].metric("Confidence Remaining", f"{st.session_state.current_hp}/100")

    st.caption(
        f"Founder: {st.session_state.player_handle or 'Unspecified'} | "
        f"Syndicate: {st.session_state.clan_name or 'Solo'}"
    )

    st.markdown("### Share My Run")
    share_text = _build_share_text(outcome=outcome, valuation=valuation)
    render_copy_button(share_text, label="Share My Run")
    st.text_area(
        "Share Text",
        value=share_text,
        height=120,
        help="Use the button above to copy, or manually copy this text.",
    )

    render_post_mortem_report(report)

    with st.expander("Transcript", expanded=False):
        transcript = st.session_state.full_chat_history or []
        if not transcript:
            st.caption("No transcript available.")
        else:
            for msg in transcript:
                role = str(msg.get("role", "unknown")).upper()
                content = msg.get("content", "")
                st.write(f"**{role}:** {content}")
