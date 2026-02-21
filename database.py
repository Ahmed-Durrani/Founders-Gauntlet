import json
import os

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:
    psycopg = None
    dict_row = None


def _get_database_url():
    return (os.getenv("DATABASE_URL") or "").strip()


def _clean_text(value, max_len):
    cleaned = " ".join((value or "").strip().split())
    if not cleaned:
        return ""
    return cleaned[:max_len]


def initialize_database():
    """
    Initializes required tables.
    Returns: (is_ready, error_message)
    """
    database_url = _get_database_url()
    if psycopg is None:
        return False, "psycopg is not installed."
    if not database_url:
        return False, "DATABASE_URL is not set."

    try:
        with psycopg.connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS clans (
                        id BIGSERIAL PRIMARY KEY,
                        name TEXT NOT NULL UNIQUE,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS players (
                        id BIGSERIAL PRIMARY KEY,
                        handle TEXT NOT NULL UNIQUE,
                        clan_id BIGINT REFERENCES clans(id) ON DELETE SET NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS runs (
                        id BIGSERIAL PRIMARY KEY,
                        player_id BIGINT NOT NULL REFERENCES players(id) ON DELETE CASCADE,
                        outcome TEXT NOT NULL,
                        theme TEXT NOT NULL,
                        valuation_usd BIGINT NOT NULL DEFAULT 0,
                        hp_remaining INT NOT NULL DEFAULT 0,
                        level_reached INT NOT NULL DEFAULT 1,
                        post_mortem JSONB NOT NULL DEFAULT '{}'::jsonb,
                        transcript JSONB NOT NULL DEFAULT '[]'::jsonb,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                    """
                )
                cur.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_runs_player_created_at
                    ON runs (player_id, created_at DESC);
                    """
                )
                cur.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_runs_valuation
                    ON runs (valuation_usd DESC);
                    """
                )
            conn.commit()
        return True, None
    except Exception as exc:
        return False, str(exc)


def _upsert_clan(cur, clan_name):
    if not clan_name:
        return None

    cur.execute(
        """
        INSERT INTO clans (name)
        VALUES (%s)
        ON CONFLICT (name)
        DO UPDATE SET name = EXCLUDED.name
        RETURNING id;
        """,
        (clan_name,),
    )
    row = cur.fetchone()
    return row[0] if row else None


def _upsert_player(cur, handle, clan_id):
    cur.execute(
        """
        INSERT INTO players (handle, clan_id)
        VALUES (%s, %s)
        ON CONFLICT (handle)
        DO UPDATE SET clan_id = EXCLUDED.clan_id, updated_at = NOW()
        RETURNING id;
        """,
        (handle, clan_id),
    )
    row = cur.fetchone()
    return row[0] if row else None


def save_run_result(player_handle, clan_name, run_payload):
    """
    Persists one completed run.
    Returns run_id on success, None on failure.
    """
    database_url = _get_database_url()
    if psycopg is None:
        return None
    if not database_url:
        return None

    handle = _clean_text(player_handle, 40)
    if not handle:
        return None
    clan = _clean_text(clan_name, 40)

    outcome = _clean_text(run_payload.get("outcome"), 24) or "unknown"
    theme = _clean_text(run_payload.get("theme"), 64) or "General SaaS"

    try:
        valuation_usd = int(run_payload.get("valuation_usd", 0))
    except (TypeError, ValueError):
        valuation_usd = 0
    valuation_usd = max(0, valuation_usd)

    try:
        hp_remaining = int(run_payload.get("hp_remaining", 0))
    except (TypeError, ValueError):
        hp_remaining = 0

    try:
        level_reached = int(run_payload.get("level_reached", 1))
    except (TypeError, ValueError):
        level_reached = 1

    post_mortem = run_payload.get("post_mortem", {})
    transcript = run_payload.get("transcript", [])

    try:
        with psycopg.connect(database_url) as conn:
            with conn.cursor() as cur:
                clan_id = _upsert_clan(cur, clan) if clan else None
                player_id = _upsert_player(cur, handle, clan_id)
                if not player_id:
                    return None

                cur.execute(
                    """
                    INSERT INTO runs (
                        player_id,
                        outcome,
                        theme,
                        valuation_usd,
                        hp_remaining,
                        level_reached,
                        post_mortem,
                        transcript
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb)
                    RETURNING id;
                    """,
                    (
                        player_id,
                        outcome,
                        theme,
                        valuation_usd,
                        hp_remaining,
                        level_reached,
                        json.dumps(post_mortem),
                        json.dumps(transcript),
                    ),
                )
                row = cur.fetchone()
            conn.commit()
        return row[0] if row else None
    except Exception:
        return None


def fetch_player_leaderboard(limit=10):
    database_url = _get_database_url()
    if psycopg is None:
        return []
    if not database_url:
        return []

    safe_limit = max(1, min(int(limit), 100))

    try:
        with psycopg.connect(database_url, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        p.handle AS player_handle,
                        COALESCE(c.name, 'Solo') AS clan_name,
                        COUNT(r.id)::INT AS run_count,
                        COALESCE(SUM(r.valuation_usd), 0)::BIGINT AS total_valuation_usd,
                        COALESCE(MAX(r.valuation_usd), 0)::BIGINT AS best_run_valuation_usd
                    FROM players p
                    JOIN runs r ON r.player_id = p.id
                    LEFT JOIN clans c ON c.id = p.clan_id
                    GROUP BY p.id, p.handle, c.name
                    ORDER BY total_valuation_usd DESC, best_run_valuation_usd DESC, run_count DESC, p.handle ASC
                    LIMIT %s;
                    """,
                    (safe_limit,),
                )
                return list(cur.fetchall())
    except Exception:
        return []


def fetch_clan_leaderboard(limit=10):
    database_url = _get_database_url()
    if psycopg is None:
        return []
    if not database_url:
        return []

    safe_limit = max(1, min(int(limit), 100))

    try:
        with psycopg.connect(database_url, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        COALESCE(c.name, 'Solo') AS clan_name,
                        COUNT(DISTINCT p.id)::INT AS member_count,
                        COUNT(r.id)::INT AS run_count,
                        COALESCE(SUM(r.valuation_usd), 0)::BIGINT AS total_valuation_usd,
                        COALESCE(MAX(r.valuation_usd), 0)::BIGINT AS best_run_valuation_usd
                    FROM runs r
                    JOIN players p ON p.id = r.player_id
                    LEFT JOIN clans c ON c.id = p.clan_id
                    GROUP BY c.name
                    ORDER BY total_valuation_usd DESC, best_run_valuation_usd DESC, member_count DESC, clan_name ASC
                    LIMIT %s;
                    """,
                    (safe_limit,),
                )
                return list(cur.fetchall())
    except Exception:
        return []
