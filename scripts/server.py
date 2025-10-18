from __future__ import annotations

import sqlite3
from pathlib import Path
import base64
from flask import Flask, jsonify, request, make_response, send_from_directory
from flask_cors import CORS
from datetime import datetime, timedelta, timezone


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "db" / "local.db"


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


app = Flask(__name__)
# Allow cookie credentials for common local dev origins
CORS(app, supports_credentials=True, resources={r"/api/*": {"origins": [
    "http://127.0.0.1:8000", "http://localhost:8000",
    "http://127.0.0.1:5001", "http://localhost:5001"
]}})

@app.get("/")
def root_index():
    return send_from_directory(PROJECT_ROOT, "index.html")

@app.get("/index.html")
def serve_index():
    return send_from_directory(PROJECT_ROOT, "index.html")

@app.get("/groups.html")
def serve_groups():
    return send_from_directory(PROJECT_ROOT, "groups.html")

@app.get("/group.html")
def serve_group():
    return send_from_directory(PROJECT_ROOT, "group.html")

@app.get("/login.html")
def serve_login():
    return send_from_directory(PROJECT_ROOT, "login.html")

@app.get("/create-group.html")
def serve_create_group():
    return send_from_directory(PROJECT_ROOT, "create-group.html")

@app.get("/create-match.html")
def serve_create_match():
    return send_from_directory(PROJECT_ROOT, "create-match.html")

@app.get("/pricing.html")
def serve_pricing():
    return send_from_directory(PROJECT_ROOT, "pricing.html")

@app.get("/matrix.html")
def serve_matrix():
    return send_from_directory(PROJECT_ROOT, "matrix.html")


def _has_team_id_columns(cur: sqlite3.Cursor) -> bool:
    try:
        cur.execute("PRAGMA table_info(matches)")
        cols = {row[1] for row in cur.fetchall()}
        return ("home_team_id" in cols and "away_team_id" in cols)
    except Exception:
        return False


def _blob_to_data_url(blob: bytes | None) -> str | None:
    if not blob:
        return None
    try:
        b64 = base64.b64encode(blob).decode("ascii")
        return f"data:image/png;base64,{b64}"
    except Exception:
        return None


def _result_letter_sql_expr(prefix: str = "m") -> str:
    """Return a SQL CASE expression that yields 'A' | 'B' | 'D' for a match row alias.

    prefix: table alias that has columns match_over, home_score, away_score.
    """
    return f"""
      CASE
        WHEN {prefix}.match_over IN ('A','B','D') THEN {prefix}.match_over
        ELSE (
          CASE
            WHEN (
                  CAST(substr({prefix}.home_score, 1, instr({prefix}.home_score, '-') - 1) AS INTEGER) * 3 +
                  CAST(substr({prefix}.home_score, instr({prefix}.home_score, '-') + 1) AS INTEGER)
                 )
                 >
                 (
                  CAST(substr({prefix}.away_score, 1, instr({prefix}.away_score, '-') - 1) AS INTEGER) * 3 +
                  CAST(substr({prefix}.away_score, instr({prefix}.away_score, '-') + 1) AS INTEGER)
                 ) THEN 'A'
            WHEN (
                  CAST(substr({prefix}.away_score, 1, instr({prefix}.away_score, '-') - 1) AS INTEGER) * 3 +
                  CAST(substr({prefix}.away_score, instr({prefix}.away_score, '-') + 1) AS INTEGER)
                 )
                 >
                 (
                  CAST(substr({prefix}.home_score, 1, instr({prefix}.home_score, '-') - 1) AS INTEGER) * 3 +
                  CAST(substr({prefix}.home_score, instr({prefix}.home_score, '-') + 1) AS INTEGER)
                 ) THEN 'B'
            ELSE 'D'
          END
        )
      END
    """


def _recalc_member_scores_for_group(cur: sqlite3.Cursor, group_id: int) -> None:
    """Recalculate member_scores for a group from picks vs finished matches."""
    # Start all members at 0
    cur.execute("SELECT id FROM members WHERE group_id=?", (group_id,))
    member_ids = [row[0] for row in cur.fetchall()]
    scores = {mid: 0 for mid in member_ids}

    # Aggregate correct picks per member
    res_expr = _result_letter_sql_expr("m")
    cur.execute(
        f"""
        SELECT p.member_id AS mid,
               SUM(CASE WHEN {res_expr} = p.pick THEN 1 ELSE 0 END) AS correct
        FROM picks p
        JOIN matches m ON m.id = p.match_id
        WHERE p.group_id = ? AND (m.match_over IS NOT NULL AND m.match_over <> '0')
        GROUP BY p.member_id
        """,
        (group_id,),
    )
    for row in cur.fetchall():
        scores[row[0]] = int(row[1] or 0)

    # Replace existing rows for this group
    cur.execute("DELETE FROM member_scores WHERE group_id=?", (group_id,))
    for mid, sc in scores.items():
        cur.execute(
            "INSERT INTO member_scores(group_id, member_id, score) VALUES(?,?,?)",
            (group_id, mid, sc),
        )

@app.get("/api/groups")
def api_groups():
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT g.id, g.name, g.county,
                   (SELECT COUNT(*) FROM members m WHERE m.group_id = g.id) AS members
            FROM groups g ORDER BY g.name COLLATE NOCASE
            """
        )
        rows = [dict(r) for r in cur.fetchall()]
    return jsonify(rows)


@app.get("/api/scores")
def api_scores():
    group = request.args.get("group")
    with get_conn() as conn:
        cur = conn.cursor()
        sql = (
            """
            SELECT g.name AS group_name, m.name AS member_name, ms.score AS score
            FROM member_scores ms
            JOIN groups g ON g.id = ms.group_id
            JOIN members m ON m.id = ms.member_id
            """
        )
        params = []
        if group:
            sql += " WHERE g.name = ?"
            params.append(group)
        sql += " ORDER BY g.name COLLATE NOCASE, ms.score DESC, m.name COLLATE NOCASE"
        cur.execute(sql, params)
        rows = [dict(r) for r in cur.fetchall()]
    return jsonify(rows)


@app.get("/api/matches")
def api_matches():
    with get_conn() as conn:
        cur = conn.cursor()
        if _has_team_id_columns(cur):
            cur.execute(
                """
                SELECT m.id,
                       th.team_name AS home_team,
                       ta.team_name AS away_team,
                       th.crest AS home_crest,
                       ta.crest AS away_crest,
                       m.competition, m.county, m.venue, m.kickoff_at,
                       m.prediction_cutoff, m.home_score, m.away_score, m.match_over
                FROM matches m
                JOIN teams th ON th.id = m.home_team_id
                JOIN teams ta ON ta.id = m.away_team_id
                ORDER BY datetime(m.kickoff_at) ASC
                """
            )
        else:
            cur.execute(
                """
                SELECT id, home_team, away_team, NULL AS home_crest, NULL AS away_crest, competition, county, venue, kickoff_at,
                       prediction_cutoff, home_score, away_score, match_over
                FROM matches ORDER BY datetime(kickoff_at) ASC
                """
            )
        rows = [dict(r) for r in cur.fetchall()]

    out = {"upcoming": [], "past": []}
    now = datetime.now(timezone.utc)
    for r in rows:
        mo = r.get("match_over")
        result_letter = mo if isinstance(mo, str) and mo in ("A", "B", "D") else None
        is_past = result_letter is not None
        if not is_past:
            out["upcoming"].append({
                "home": r["home_team"],
                "away": r["away_team"],
                "homeCrest": _blob_to_data_url(r.get("home_crest")),
                "awayCrest": _blob_to_data_url(r.get("away_crest")),
                "competition": r["competition"],
                "county": r["county"],
                "venue": r["venue"],
                "kickoff": r["kickoff_at"],
                "prediction": r["prediction_cutoff"],
            })
        else:
            out["past"].append({
                "home": r["home_team"],
                "away": r["away_team"],
                "homeCrest": _blob_to_data_url(r.get("home_crest")),
                "awayCrest": _blob_to_data_url(r.get("away_crest")),
                "competition": r["competition"],
                "county": r["county"],
                "venue": r["venue"],
                "kickoff": r["kickoff_at"],
                "scoreA": r["home_score"],
                "scoreB": r["away_score"],
                "result": result_letter,
            })
    return jsonify(out)


@app.post("/api/matches")
def api_matches_create():
    if not request.is_json:
        return jsonify({"error": "json required"}), 400
    data = request.get_json(silent=True) or {}
    # Only admin can add matches
    token = request.cookies.get("plp_session")
    with get_conn() as conn:
        cur = conn.cursor()
        user = _get_member_by_session(cur, token) if token else None
        if not user or user["role"] != "admin":
            return jsonify({"error": "forbidden"}), 403
    required = ["home_team", "away_team", "kickoff_at"]
    for k in required:
        if not data.get(k):
            return jsonify({"error": f"missing {k}"}), 400
    # Normalize optional fields
    competition = data.get("competition")
    county = data.get("county")
    venue = data.get("venue")
    kickoff_at = data.get("kickoff_at")
    prediction_cutoff = data.get("prediction_cutoff") or kickoff_at
    home_score = data.get("home_score")
    away_score = data.get("away_score")
    # If scores provided, compute result letter, else leave NULL
    def _to_total(s: str | None) -> int:
        if not s or "-" not in s:
            return 0
        try:
            g, p = s.split("-", 1)
            return int(g) * 3 + int(p)
        except Exception:
            return 0
    match_over = None
    if home_score is not None and away_score is not None:
        ta, tb = _to_total(home_score), _to_total(away_score)
        match_over = "D" if ta == tb else ("A" if ta > tb else "B")
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO matches(home_team, away_team, competition, county, venue,
                                kickoff_at, prediction_cutoff, home_score, away_score, match_over)
            VALUES(?,?,?,?,?,?,?,?,?,?)
            """,
            (
                data.get("home_team"), data.get("away_team"), competition, county, venue,
                kickoff_at, prediction_cutoff, home_score, away_score, match_over,
            ),
        )
        mid = cur.lastrowid
        # If a finished match is being created, recalc scores for any group that has picks for it
        if match_over in ('A','B','D') and home_score is not None and away_score is not None:
            cur.execute("SELECT DISTINCT group_id FROM picks WHERE match_id=?", (mid,))
            rows = cur.fetchall()
            for r in rows:
                _recalc_member_scores_for_group(cur, r[0])
        conn.commit()
    return jsonify({"id": mid})


@app.post("/api/matches/score")
def api_matches_set_score():
    if not request.is_json:
        return jsonify({"error": "json required"}), 400
    data = request.get_json(silent=True) or {}
    # Only admin
    token = request.cookies.get("plp_session")
    with get_conn() as conn:
        cur = conn.cursor()
        user = _get_member_by_session(cur, token) if token else None
        if not user or user["role"] != "admin":
            return jsonify({"error": "forbidden"}), 403
        # Identify match by home/away/kickoff
        home = data.get("home")
        away = data.get("away")
        kickoff = data.get("kickoff")
        sA = data.get("home_score")
        sB = data.get("away_score")
        if not (home and away and kickoff and sA is not None and sB is not None):
            return jsonify({"error": "missing fields"}), 400
        cur.execute(
            """
            SELECT id FROM matches WHERE home_team=? AND away_team=? AND kickoff_at=?
            """,
            (home, away, kickoff),
        )
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "match not found"}), 404
        mid = row[0]
        # Compute result letter from scores
        def _to_total2(s: str | None) -> int:
            if not s or "-" not in s:
                return 0
            try:
                g, p = s.split("-", 1)
                return int(g) * 3 + int(p)
            except Exception:
                return 0
        ta, tb = _to_total2(sA), _to_total2(sB)
        res_letter = "D" if ta == tb else ("A" if ta > tb else "B")
        cur.execute(
            "UPDATE matches SET home_score=?, away_score=?, match_over=? WHERE id=?",
            (sA, sB, res_letter, mid),
        )
        # Recalculate scores for ALL groups that have picks for this match
        cur.execute(
            "SELECT DISTINCT p.group_id FROM picks p WHERE p.match_id=?",
            (mid,),
        )
        for row in cur.fetchall():
            _recalc_member_scores_for_group(cur, row[0])
        conn.commit()
    return jsonify({"id": mid, "home_score": sA, "away_score": sB, "match_over": res_letter})

def _random_token() -> str:
    import secrets
    return secrets.token_urlsafe(32)


def _get_member_by_name_password(cur: sqlite3.Cursor, name: str, password: str):
    cur.execute("SELECT id, name, email FROM members WHERE name=? AND password=?", (name, password))
    return cur.fetchone()


def _get_member_by_session(cur: sqlite3.Cursor, token: str):
    cur.execute(
        """
        SELECT m.id, m.name, m.email, m.role
        FROM sessions s JOIN members m ON m.id = s.member_id
        WHERE s.token = ? AND (s.expires_at IS NULL OR datetime(s.expires_at) > datetime('now'))
        """,
        (token,),
    )
    return cur.fetchone()


@app.post("/api/login")
def api_login():
    if not request.is_json:
        return jsonify({"error": "json required"}), 400
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    password = (data.get("password") or "").strip()
    if not name or not password:
        return jsonify({"error": "missing fields"}), 400
    with get_conn() as conn:
        cur = conn.cursor()
        row = _get_member_by_name_password(cur, name, password)
        if not row:
            return jsonify({"error": "invalid credentials"}), 401
        token = _random_token()
        cur.execute(
            "INSERT INTO sessions(token, member_id, expires_at) VALUES(?,?,datetime('now','+7 days'))",
            (token, row["id"]),
        )
        conn.commit()
    resp = make_response(jsonify({"name": row["name"], "email": row["email"]}))
    resp.set_cookie("plp_session", token, httponly=True, samesite="Lax")
    return resp


@app.post("/api/logout")
def api_logout():
    token = request.cookies.get("plp_session")
    if token:
        with get_conn() as conn:
            conn.execute("DELETE FROM sessions WHERE token=?", (token,))
            conn.commit()
    resp = make_response(jsonify({"ok": True}))
    resp.delete_cookie("plp_session")
    return resp


@app.get("/api/me")
def api_me():
    token = request.cookies.get("plp_session")
    if not token:
        return jsonify({"loggedIn": False}), 200
    with get_conn() as conn:
        cur = conn.cursor()
        row = _get_member_by_session(cur, token)
        if not row:
            return jsonify({"loggedIn": False}), 200
        return jsonify({"loggedIn": True, "name": row["name"], "email": row["email"], "role": row["role"]})


@app.get("/api/picks/stats")
def api_picks_stats():
    """Return per-match prediction accuracy for a group and the current user's picks.

    Query string: ?group=Group%201
    Response:
      {
        "stats": [
          {"home": "Lavey", "away": "Bellaghy", "kickoff": "...", "correct": 3, "total": 5}
        ],
        "mine": {"home|away|kickoff": "A"}
      }
    """
    group_name = request.args.get("group")
    if not group_name:
        return jsonify({"error": "missing group"}), 400
    with get_conn() as conn:
        cur = conn.cursor()
        # Resolve group id
        cur.execute("SELECT id FROM groups WHERE name=?", (group_name,))
        g = cur.fetchone()
        if not g:
            return jsonify({"stats": [], "mine": {}})
        group_id = g[0]
        print(f"[picks_stats] group={group_name!r} -> group_id={group_id}")

        # Compute correct vs total per finished match for this group
        if _has_team_id_columns(cur):
            cur.execute(
                """
            SELECT th.team_name AS home,
                   ta.team_name AS away,
                   m.kickoff_at AS kickoff,
                   SUM(
                     CASE WHEN p.pick = (
                       CASE
                         WHEN m.match_over IN ('A','B','D') THEN m.match_over
                         ELSE (
                           CASE
                             WHEN (
                                   CAST(substr(m.home_score, 1, instr(m.home_score, '-') - 1) AS INTEGER) * 3 +
                                   CAST(substr(m.home_score, instr(m.home_score, '-') + 1) AS INTEGER)
                                  )
                                  >
                                  (
                                   CAST(substr(m.away_score, 1, instr(m.away_score, '-') - 1) AS INTEGER) * 3 +
                                   CAST(substr(m.away_score, instr(m.away_score, '-') + 1) AS INTEGER)
                                  ) THEN 'A'
                             WHEN (
                                   CAST(substr(m.away_score, 1, instr(m.away_score, '-') - 1) AS INTEGER) * 3 +
                                   CAST(substr(m.away_score, instr(m.away_score, '-') + 1) AS INTEGER)
                                  )
                                  >
                                  (
                                   CAST(substr(m.home_score, 1, instr(m.home_score, '-') - 1) AS INTEGER) * 3 +
                                   CAST(substr(m.home_score, instr(m.home_score, '-') + 1) AS INTEGER)
                                  ) THEN 'B'
                             ELSE 'D'
                           END
                         )
                       END
                     ) THEN 1 ELSE 0 END
                   ) AS correct,
                   COUNT(p.id) AS total
            FROM matches m
            JOIN teams th ON th.id = m.home_team_id
            JOIN teams ta ON ta.id = m.away_team_id
            JOIN picks p ON p.match_id = m.id
            WHERE (m.match_over IS NOT NULL AND m.match_over <> '0')
              AND p.group_id = ?
            GROUP BY p.match_id
            """,
            (group_id,)
            )
        else:
            cur.execute(
                """
            SELECT m.home_team AS home, m.away_team AS away, m.kickoff_at AS kickoff,
                   SUM(
                     CASE WHEN p.pick = (
                       CASE
                         WHEN m.match_over IN ('A','B','D') THEN m.match_over
                         ELSE (
                           CASE
                             WHEN (
                                   CAST(substr(m.home_score, 1, instr(m.home_score, '-') - 1) AS INTEGER) * 3 +
                                   CAST(substr(m.home_score, instr(m.home_score, '-') + 1) AS INTEGER)
                                  )
                                  >
                                  (
                                   CAST(substr(m.away_score, 1, instr(m.away_score, '-') - 1) AS INTEGER) * 3 +
                                   CAST(substr(m.away_score, instr(m.away_score, '-') + 1) AS INTEGER)
                                  ) THEN 'A'
                             WHEN (
                                   CAST(substr(m.away_score, 1, instr(m.away_score, '-') - 1) AS INTEGER) * 3 +
                                   CAST(substr(m.away_score, instr(m.away_score, '-') + 1) AS INTEGER)
                                  )
                                  >
                                  (
                                   CAST(substr(m.home_score, 1, instr(m.home_score, '-') - 1) AS INTEGER) * 3 +
                                   CAST(substr(m.home_score, instr(m.home_score, '-') + 1) AS INTEGER)
                                  ) THEN 'B'
                             ELSE 'D'
                           END
                         )
                       END
                     ) THEN 1 ELSE 0 END
                   ) AS correct,
                   COUNT(p.id) AS total
            FROM matches m
            JOIN picks p ON p.match_id = m.id
            WHERE (m.match_over IS NOT NULL AND m.match_over <> '0')
              AND p.group_id = ?
            GROUP BY p.match_id
            """,
            (group_id,)
            )
        stats_rows = [dict(r) for r in cur.fetchall()]
        for r in stats_rows:
            try:
                print(f"[picks_stats] agg match {r['home']} vs {r['away']} @ {r['kickoff']} correct={r['correct']}/{r['total']}")
            except Exception:
                pass

        # Current user's picks in this group (if logged in)
        mine = {}
        token = request.cookies.get("plp_session")
        user = _get_member_by_session(cur, token) if token else None
        if user:
            uid = user["id"] if isinstance(user, sqlite3.Row) else user[0]
            uname = user["name"] if isinstance(user, sqlite3.Row) else (user[1] if len(user) > 1 else None)
            print(f"[picks_stats] logged-in user id={uid} name={uname!r}")
            if _has_team_id_columns(cur):
                cur.execute(
                    """
                    SELECT th.team_name AS home,
                           ta.team_name AS away,
                           m.kickoff_at AS kickoff,
                           p.pick
                    FROM picks p
                    JOIN matches m ON m.id = p.match_id
                    JOIN teams th ON th.id = m.home_team_id
                    JOIN teams ta ON ta.id = m.away_team_id
                    WHERE p.group_id = ? AND p.member_id = ?
                    """,
                    (group_id, uid),
                )
            else:
                cur.execute(
                    """
                    SELECT m.home_team AS home, m.away_team AS away, m.kickoff_at AS kickoff, p.pick
                    FROM picks p JOIN matches m ON m.id = p.match_id
                    WHERE p.group_id = ? AND p.member_id = ?
                    """,
                    (group_id, uid),
                )
            for row in cur.fetchall():
                key = f"{row['home']}|{row['away']}|{row['kickoff']}"
                mine[key] = row["pick"]
                try:
                    print(f"[picks_stats] mine match {row['home']} vs {row['away']} @ {row['kickoff']} pick={row['pick']}")
                except Exception:
                    pass

    return jsonify({"stats": stats_rows, "mine": mine})

@app.get("/api/picks/matrix")
def api_picks_matrix():
    """Return pick matrix for a group.

    Query: ?group=Group%201
    Response:
      {
        "members": ["Alice", "Bob"],
        "matches": [
          {"home": "Lavey", "away": "Bellaghy", "kickoff": "...", "result": "A|B|D"}
        ],
        "picks": { "Alice|home|away|kickoff": "A" }
      }
    """
    group_name = request.args.get("group")
    if not group_name:
        return jsonify({"members": [], "matches": [], "picks": {}})
    with get_conn() as conn:
        cur = conn.cursor()
        # Group id
        cur.execute("SELECT id FROM groups WHERE name=?", (group_name,))
        g = cur.fetchone()
        if not g:
            return jsonify({"members": [], "matches": [], "picks": {}})
        gid = g[0]
        # Members
        cur.execute("SELECT id, name FROM members WHERE group_id=? ORDER BY name COLLATE NOCASE", (gid,))
        members_rows = cur.fetchall()
        member_id_to_name = {row[0]: row[1] for row in members_rows}
        members = [row[1] for row in members_rows]

        # Matches for which group has any picks (order by kickoff)
        if _has_team_id_columns(cur):
            cur.execute(
                """
                SELECT DISTINCT m.id, th.team_name AS home_team, ta.team_name AS away_team, m.kickoff_at,
                       m.home_score, m.away_score, m.match_over AS result,
                       th.crest AS home_crest, ta.crest AS away_crest
                FROM picks p JOIN matches m ON m.id = p.match_id
                JOIN teams th ON th.id = m.home_team_id
                JOIN teams ta ON ta.id = m.away_team_id
                WHERE p.group_id = ?
                  AND (m.match_over IS NOT NULL AND m.match_over <> '0')
                ORDER BY datetime(m.kickoff_at) ASC
                """,
                (gid,)
            )
        else:
            cur.execute(
                """
                SELECT DISTINCT m.id, m.home_team, m.away_team, m.kickoff_at,
                       m.home_score, m.away_score, m.match_over AS result,
                       NULL AS home_crest, NULL AS away_crest
                FROM picks p JOIN matches m ON m.id = p.match_id
                WHERE p.group_id = ?
                  AND (m.match_over IS NOT NULL AND m.match_over <> '0')
                ORDER BY datetime(m.kickoff_at) ASC
                """,
                (gid,)
            )
        matches_rows = cur.fetchall()
        matches = []
        match_id_to_key = {}
        for r in matches_rows:
            mid, home, away, kickoff, home_score, away_score, result, home_crest, away_crest = r
            key = f"{home}|{away}|{kickoff}"
            match_id_to_key[mid] = key
            matches.append({
                "home": home,
                "away": away,
                "kickoff": kickoff,
                "home_score": home_score,
                "away_score": away_score,
                "result": result,
                "homeCrest": _blob_to_data_url(home_crest),
                "awayCrest": _blob_to_data_url(away_crest),
            })

        # Picks
        cur.execute(
            "SELECT member_id, match_id, pick FROM picks WHERE group_id=?",
            (gid,)
        )
        picks = {}
        for r in cur.fetchall():
            mid = r[1]
            key = f"{member_id_to_name.get(r[0])}|{match_id_to_key.get(mid)}"
            picks[key] = r[2]
    return jsonify({"members": members, "matches": matches, "picks": picks})

@app.post("/api/picks")
def api_picks_upsert():
    """Create or update a user's pick for a match.

    Expected JSON body:
    {
      "group": "Group 1",
      "member": "Alice Murphy",
      "match": { "home": "Lavey Erin's Own", "away": "Bellaghy Wolfe Tones", "kickoff": "2025-09-20T12:00:00" },
      "pick": "A" | "B" | "D"
    }
    """
    if not request.is_json:
      return jsonify({"error": "json required"}), 400
    data = request.get_json(silent=True) or {}
    group_name = data.get("group")
    member_name = data.get("member")
    match_obj = data.get("match") or {}
    pick = data.get("pick")
    if pick not in ("A", "B", "D"):
        return jsonify({"error": "invalid pick"}), 400
    for k in (group_name, member_name, match_obj.get("home"), match_obj.get("away"), match_obj.get("kickoff")):
        if not k:
            return jsonify({"error": "missing fields"}), 400

    with get_conn() as conn:
        cur = conn.cursor()
        # Resolve IDs
        print(f"[picks_upsert] incoming group={group_name!r} member={member_name!r} match={match_obj!r} pick={pick!r}")
        cur.execute("SELECT id FROM groups WHERE name=?", (group_name,))
        g = cur.fetchone()
        if not g:
            return jsonify({"error": "group not found"}), 404
        group_id = g[0]
        print(f"[picks_upsert] resolved group_id={group_id}")

        cur.execute("SELECT id FROM members WHERE group_id=? AND name=?", (group_id, member_name))
        m = cur.fetchone()
        if not m:
            # Auto-create member with no email if not exists
            cur.execute("INSERT INTO members(group_id, name, email) VALUES(?,?,?)", (group_id, member_name, None))
            member_id = cur.lastrowid
        else:
            member_id = m[0]
        print(f"[picks_upsert] resolved member_id={member_id}")

        print(f"[picks_upsert] searching match by home={match_obj.get('home')!r} away={match_obj.get('away')!r} kickoff={match_obj.get('kickoff')!r}")
        cur.execute(
            """
            SELECT id FROM matches
            WHERE home_team=? AND away_team=? AND kickoff_at=?
            """,
            (match_obj.get("home"), match_obj.get("away"), match_obj.get("kickoff")),
        )
        mm = cur.fetchone()
        if not mm:
            print("[picks_upsert] match not found with provided identifiers")
            return jsonify({"error": "match not found"}), 404
        match_id = mm[0]
        print(f"[picks_upsert] resolved match_id={match_id}")

        # Enforce single submission: if a pick already exists for this member+match in this group, forbid changes
        cur.execute(
            "SELECT 1 FROM picks WHERE group_id=? AND member_id=? AND match_id=? LIMIT 1",
            (group_id, member_id, match_id),
        )
        exists = cur.fetchone() is not None
        if exists:
            return jsonify({"error": "already submitted"}), 409
        cur.execute(
            "INSERT INTO picks(group_id, member_id, match_id, pick) VALUES(?,?,?,?)",
            (group_id, member_id, match_id, pick),
        )
        conn.commit()
        print(f"[picks_upsert] upserted pick group_id={group_id} member_id={member_id} match_id={match_id} pick={pick}")
        return jsonify({
            "group_id": group_id,
            "member_id": member_id,
            "match_id": match_id,
            "pick": pick
        })

@app.post("/api/test/start")
def api_test_start():
    """Set the earliest upcoming match to start in 10 seconds (dev helper)."""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id FROM matches
            WHERE home_score IS NULL AND away_score IS NULL
            ORDER BY datetime(kickoff_at) ASC
            LIMIT 1
            """
        )
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "no upcoming match"}), 404
        match_id = row[0]
        now = datetime.now(timezone.utc)
        kickoff = (now + timedelta(seconds=10)).isoformat()
        cutoff = (now + timedelta(seconds=8)).isoformat()
        cur.execute(
            "UPDATE matches SET kickoff_at=?, prediction_cutoff=? WHERE id=?",
            (kickoff, cutoff, match_id),
        )
        conn.commit()
    return jsonify({"match_id": match_id, "seconds": 10, "kickoff": kickoff, "prediction_cutoff": cutoff})


@app.post("/api/test/complete")
def api_test_complete():
    """Increment every member's score in a given group by 1 (dev helper)."""
    group = request.args.get("group") or request.json.get("group") if request.is_json else None
    if not group:
        group = "Group 1"
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM groups WHERE name=?", (group,))
        gid_row = cur.fetchone()
        if not gid_row:
            return jsonify({"error": "group not found"}), 404
        gid = gid_row[0]
        cur.execute("UPDATE member_scores SET score = score + 1 WHERE group_id = ?", (gid,))
        conn.commit()
        # Return updated table
        cur.execute(
            """
            SELECT m.name AS member_name, ms.score
            FROM member_scores ms JOIN members m ON m.id = ms.member_id
            WHERE ms.group_id = ? ORDER BY ms.score DESC, m.name COLLATE NOCASE
            """,
            (gid,),
        )
        rows = [dict(r) for r in cur.fetchall()]
    return jsonify({"group": group, "members": rows})


@app.post("/api/test/refresh_upcoming")
def api_test_refresh_upcoming():
    """Move all upcoming matches into the future (staggered) and set prediction cutoffs.

    Kickoff = now + (index+1) hours, cutoff = kickoff - 10 minutes.
    """
    now = datetime.now(timezone.utc)
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id FROM matches WHERE home_score IS NULL AND away_score IS NULL ORDER BY datetime(kickoff_at) ASC"
        )
        ids = [row[0] for row in cur.fetchall()]
        for i, mid in enumerate(ids):
            kickoff = (now + timedelta(hours=i + 1)).isoformat()
            cutoff = (now + timedelta(hours=i + 1) - timedelta(minutes=10)).isoformat()
            cur.execute(
                "UPDATE matches SET kickoff_at=?, prediction_cutoff=? WHERE id=?",
                (kickoff, cutoff, mid),
            )
        conn.commit()
    return jsonify({"updated": len(ids)})


@app.post("/api/test/set_deadline")
def api_test_set_deadline():
    """Set prediction deadline for the earliest upcoming match of a given home team to now + 30s.

    JSON body or query string: { "home": "Lavey Erin's Own" }
    """
    home = request.args.get("home")
    if request.is_json and not home:
        body = request.get_json(silent=True) or {}
        home = body.get("home")
    if not home:
        home = "Lavey Erin's Own"
    now = datetime.now(timezone.utc)
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id FROM matches
            WHERE home_team=? AND home_score IS NULL AND away_score IS NULL
            ORDER BY datetime(kickoff_at) ASC LIMIT 1
            """,
            (home,),
        )
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "match not found"}), 404
        mid = row[0]
        cutoff = (now + timedelta(seconds=30)).isoformat()
        cur.execute("UPDATE matches SET prediction_cutoff=? WHERE id=?", (cutoff, mid))
        conn.commit()
    return jsonify({"match_id": mid, "prediction_cutoff": cutoff})


@app.post("/api/scores/recalc")
def api_scores_recalc():
    """Admin-only: Recalculate and update member_scores for the given group.

    JSON or query: { "group": "Group 1" }
    Returns updated scoreboard rows for that group.
    """
    group_name = request.args.get("group")
    if request.is_json and not group_name:
        body = request.get_json(silent=True) or {}
        group_name = body.get("group")
    if not group_name:
        return jsonify({"error": "missing group"}), 400

    token = request.cookies.get("plp_session")
    with get_conn() as conn:
        cur = conn.cursor()
        user = _get_member_by_session(cur, token) if token else None
        if not user or user["role"] != "admin":
            return jsonify({"error": "forbidden"}), 403

        cur.execute("SELECT id FROM groups WHERE name=?", (group_name,))
        g = cur.fetchone()
        if not g:
            return jsonify({"error": "group not found"}), 404
        gid = g[0]
        _recalc_member_scores_for_group(cur, gid)
        conn.commit()

        cur.execute(
            """
            SELECT m.name AS member_name, ms.score
            FROM member_scores ms JOIN members m ON m.id = ms.member_id
            WHERE ms.group_id = ?
            ORDER BY ms.score DESC, m.name COLLATE NOCASE
            """,
            (gid,),
        )
        rows = [dict(r) for r in cur.fetchall()]
    return jsonify({"group": group_name, "members": rows})

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=True)


