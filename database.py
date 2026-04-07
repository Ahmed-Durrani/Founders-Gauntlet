import json
import os
from urllib.parse import parse_qsl, quote, unquote, urlencode, urlsplit, urlunsplit

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:
    psycopg = None
    dict_row = None

CONNECT_TIMEOUT_SECONDS = 8


class DatabaseConnectionError(RuntimeError):
    def __init__(self, message, failures=None):
        super().__init__(message)
        self.failures = failures or []


def _get_database_url():
    database_url = (os.getenv("DATABASE_URL") or "").strip()
    if len(database_url) >= 2 and database_url[0] == database_url[-1] and database_url[0] in {"'", '"'}:
        database_url = database_url[1:-1].strip()
    return database_url


def _url_host(parts):
    return (parts.hostname or "").strip().lower()


def _contains_any(text, patterns):
    lowered = text.lower()
    return any(pattern.lower() in lowered for pattern in patterns)


def _with_default_sslmode(query):
    params = parse_qsl(query, keep_blank_values=True)
    if not any(key.lower() == "sslmode" for key, _ in params):
        params.append(("sslmode", "require"))
    return urlencode(params, doseq=True)


def _normalize_database_url(database_url):
    parts = urlsplit(database_url)
    host = _url_host(parts)
    if "supabase" not in host:
        return database_url

    normalized_query = _with_default_sslmode(parts.query)
    return urlunsplit(
        (
            parts.scheme or "postgresql",
            parts.netloc,
            parts.path or "/postgres",
            normalized_query,
            parts.fragment,
        )
    )


def _build_supabase_direct_candidate(parts):
    host = _url_host(parts)
    username = parts.username or ""
    if not host.endswith(".pooler.supabase.com"):
        return None
    if "." not in username or not username.startswith("postgres."):
        return None

    project_ref = username.split(".", 1)[1].strip()
    if not project_ref:
        return None

    password = unquote(parts.password or "")
    query = _with_default_sslmode(parts.query)
    direct_netloc = (
        f"{quote('postgres', safe='')}:{quote(password, safe='')}"
        f"@db.{project_ref}.supabase.co:5432"
    )
    direct_url = urlunsplit(
        (
            parts.scheme or "postgresql",
            direct_netloc,
            parts.path or "/postgres",
            query,
            "",
        )
    )
    return "supabase_direct", direct_url


def _build_connection_candidates(database_url):
    normalized_url = _normalize_database_url(database_url)
    candidates = [("primary", normalized_url)]
    direct_candidate = _build_supabase_direct_candidate(urlsplit(normalized_url))
    if direct_candidate and direct_candidate[1] != normalized_url:
        candidates.append(direct_candidate)
    return candidates


def _summarize_connection_error(database_url, failures):
    parts = urlsplit(database_url)
    host = parts.hostname or "database host"
    combined_text = "\n".join(str(exc) for _, exc in failures)
    first_error = str(failures[-1][1]).splitlines()[0].strip() if failures else "Unknown database error."

    if _contains_any(combined_text, ["tenant or user not found"]):
        direct_dns_failed = any(
            label == "supabase_direct"
            and _contains_any(
                str(exc),
                [
                    "getaddrinfo failed",
                    "could not translate host name",
                    "name or service not known",
                    "temporary failure in name resolution",
                ],
            )
            for label, exc in failures
        )
        if direct_dns_failed:
            return (
                "Supabase rejected DATABASE_URL (tenant or user not found), and the matching direct host "
                "could not be resolved. DATABASE_URL likely points at the wrong Supabase project or a deleted one."
            )
        return (
            "Supabase rejected DATABASE_URL (tenant or user not found). "
            "Replace it with a fresh Postgres connection string from the active Supabase project."
        )

    if _contains_any(combined_text, ["password authentication failed"]):
        return "Database password authentication failed. Check DATABASE_URL."

    if _contains_any(
        combined_text,
        [
            "getaddrinfo failed",
            "could not translate host name",
            "name or service not known",
            "temporary failure in name resolution",
        ],
    ):
        return f"Database host '{host}' could not be resolved."

    if _contains_any(combined_text, ["permission denied (0x0000271d/10013)"]):
        return f"Database host '{host}' is blocked from this environment."

    if _contains_any(combined_text, ["timeout expired", "timed out"]):
        return f"Timed out connecting to database host '{host}'."

    if _contains_any(combined_text, ["connection refused"]):
        return f"Database host '{host}' refused the connection."

    return first_error


def _connect_to_database(row_factory=None):
    database_url = _get_database_url()
    if psycopg is None:
        raise DatabaseConnectionError("psycopg is not installed.")
    if not database_url:
        raise DatabaseConnectionError("DATABASE_URL is not set.")

    connect_kwargs = {"connect_timeout": CONNECT_TIMEOUT_SECONDS}
    if row_factory is not None:
        connect_kwargs["row_factory"] = row_factory

    failures = []
    for label, conninfo in _build_connection_candidates(database_url):
        try:
            return psycopg.connect(conninfo, **connect_kwargs)
        except Exception as exc:
            failures.append((label, exc))

    raise DatabaseConnectionError(_summarize_connection_error(database_url, failures), failures=failures)


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
    try:
        with _connect_to_database() as conn:
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
    except DatabaseConnectionError as exc:
        return False, str(exc)
    except Exception as exc:
        return False, str(exc).splitlines()[0].strip()


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
    if psycopg is None:
        return None
    if not _get_database_url():
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
        with _connect_to_database() as conn:
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
    if psycopg is None:
        return []
    if not _get_database_url():
        return []

    safe_limit = max(1, min(int(limit), 100))

    try:
        with _connect_to_database(row_factory=dict_row) as conn:
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
    if psycopg is None:
        return []
    if not _get_database_url():
        return []

    safe_limit = max(1, min(int(limit), 100))

    try:
        with _connect_to_database(row_factory=dict_row) as conn:
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
