import streamlit as st

from ui_helpers import format_currency, load_leaderboards


def render_leaderboard_view():
    st.title("Global Leaderboards")
    st.caption("Founder and syndicate rankings based on secured valuation.")

    if not st.session_state.db_ready:
        if st.session_state.db_error:
            st.warning(f"Leaderboard unavailable: {st.session_state.db_error}")
        else:
            st.info("Set DATABASE_URL to enable persistent multiplayer leaderboards.")
        return

    players, clans = load_leaderboards(limit_players=25, limit_clans=25)

    left, right = st.columns(2)

    with left:
        st.markdown("### Founder Leaderboard")
        if not players:
            st.caption("No founder runs submitted yet.")
        else:
            founder_rows = []
            for rank, row in enumerate(players, start=1):
                founder_rows.append(
                    {
                        "Rank": rank,
                        "Founder": row["player_handle"],
                        "Syndicate": row["clan_name"],
                        "Total Valuation": format_currency(row["total_valuation_usd"]),
                        "Best Run": format_currency(row["best_run_valuation_usd"]),
                        "Runs": row["run_count"],
                    }
                )
            st.dataframe(founder_rows, use_container_width=True, hide_index=True)

    with right:
        st.markdown("### Syndicate Leaderboard")
        if not clans:
            st.caption("No syndicate data submitted yet.")
        else:
            clan_rows = []
            for rank, row in enumerate(clans, start=1):
                clan_rows.append(
                    {
                        "Rank": rank,
                        "Syndicate": row["clan_name"],
                        "Members": row["member_count"],
                        "Total Valuation": format_currency(row["total_valuation_usd"]),
                        "Best Run": format_currency(row["best_run_valuation_usd"]),
                        "Runs": row["run_count"],
                    }
                )
            st.dataframe(clan_rows, use_container_width=True, hide_index=True)
