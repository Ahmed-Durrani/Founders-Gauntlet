import streamlit as st

from database import fetch_clan_leaderboard, fetch_player_leaderboard


def clamp_percent(value):
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        numeric = 0
    return max(0, min(100, numeric))


def format_currency(value):
    try:
        amount = int(value)
    except (TypeError, ValueError):
        amount = 0
    return f"${amount:,.0f}"


def compute_vc_valuation(report, current_hp, has_pitch_deck, perk_count):
    """
    Deterministic valuation model used for rankings.
    """
    scores = report.get("scores", {})
    confidence = clamp_percent(scores.get("confidence", 50))
    technical = clamp_percent(scores.get("technical_clarity", 50))
    business = clamp_percent(scores.get("business_viability", 50))
    resilience = clamp_percent(scores.get("resilience_under_pressure", 50))

    score_component = (
        (confidence * 45_000)
        + (technical * 70_000)
        + (business * 90_000)
        + (resilience * 55_000)
    )
    hp_component = max(0, int(current_hp)) * 65_000
    deck_bonus = 500_000 if has_pitch_deck else 0
    perk_depth_bonus = int(perk_count) * 175_000
    base_valuation = 2_500_000

    valuation = base_valuation + score_component + hp_component + deck_bonus + perk_depth_bonus
    return int(round(valuation / 50_000.0) * 50_000)


def render_post_mortem_report(report):
    st.subheader("Post-Mortem Analytics Dashboard")
    scores = report.get("scores", {})
    metrics = [
        ("Confidence", "confidence"),
        ("Technical Clarity", "technical_clarity"),
        ("Business Viability", "business_viability"),
        ("Resilience Under Pressure", "resilience_under_pressure"),
    ]

    col_a, col_b = st.columns(2)
    for idx, (label, key) in enumerate(metrics):
        score = clamp_percent(scores.get(key, 0))
        target_col = col_a if idx % 2 == 0 else col_b
        target_col.metric(label, f"{score}%")
        target_col.progress(score / 100)

    st.markdown("### Summary")
    st.write(report.get("summary", "No summary available."))

    st.markdown("### Strengths")
    for item in report.get("strengths", []):
        st.write(f"- {item}")

    st.markdown("### Weaknesses")
    for item in report.get("weaknesses", []):
        st.write(f"- {item}")

    st.markdown("### Next Practice Actions")
    for item in report.get("next_actions", []):
        st.write(f"- {item}")


@st.cache_data(ttl=20, show_spinner=False)
def load_leaderboards(limit_players=20, limit_clans=20):
    players = fetch_player_leaderboard(limit=limit_players)
    clans = fetch_clan_leaderboard(limit=limit_clans)
    return players, clans
