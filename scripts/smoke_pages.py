import os
import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
os.chdir(ROOT_DIR)
os.environ["FG_DISABLE_LOCAL_RECOVERY"] = "1"
os.environ["DATABASE_URL"] = ""


def _assert_no_exceptions(app_test, label):
    if len(app_test.exception) > 0:
        first_error = app_test.exception[0]
        raise RuntimeError(f"{label} raised exception: {first_error.message}")


def _smoke_app_entry():
    app_test = AppTest.from_file("app.py", default_timeout=30)
    app_test.run()
    _assert_no_exceptions(app_test, "app.py")


def _smoke_game_page():
    def _render():
        import streamlit as st

        from session_utils import ensure_session_state
        from views.game import render_game_view

        ensure_session_state()
        st.session_state.db_ready = False
        st.session_state.db_error = "smoke-mode"
        render_game_view()

    app_test = AppTest.from_function(_render, default_timeout=30)
    app_test.run()
    _assert_no_exceptions(app_test, "views.game.render_game_view")


def _smoke_leaderboard_page():
    def _render():
        import streamlit as st

        from session_utils import ensure_session_state
        from views.leaderboard import render_leaderboard_view

        ensure_session_state()
        st.session_state.db_ready = False
        st.session_state.db_error = "smoke-mode"
        render_leaderboard_view()

    app_test = AppTest.from_function(_render, default_timeout=30)
    app_test.run()
    _assert_no_exceptions(app_test, "views.leaderboard.render_leaderboard_view")


def _smoke_dashboard_page():
    def _render():
        from session_utils import ensure_session_state
        from views.dashboard import render_dashboard_view

        ensure_session_state()
        import streamlit as st

        st.session_state.post_mortem_report = {
            "scores": {
                "confidence": 80,
                "technical_clarity": 75,
                "business_viability": 82,
                "resilience_under_pressure": 78,
            },
            "strengths": ["A", "B", "C"],
            "weaknesses": ["D", "E", "F"],
            "next_actions": ["G", "H", "I"],
            "summary": "Smoke test report payload.",
        }
        st.session_state.post_mortem_outcome = "victory"
        st.session_state.final_valuation_usd = 4_500_000
        render_dashboard_view()

    app_test = AppTest.from_function(_render, default_timeout=30)
    app_test.run()
    _assert_no_exceptions(app_test, "views.dashboard.render_dashboard_view")


def main():
    checks = [
        ("app-entry", _smoke_app_entry),
        ("game-page", _smoke_game_page),
        ("leaderboard-page", _smoke_leaderboard_page),
        ("dashboard-page", _smoke_dashboard_page),
    ]
    failed = []
    for label, check in checks:
        try:
            check()
            print(f"[PASS] {label}")
        except Exception as exc:
            failed.append((label, str(exc)))
            print(f"[FAIL] {label}: {exc}")

    if failed:
        raise SystemExit(1)
    print("All navigation smoke checks passed.")


if __name__ == "__main__":
    main()
