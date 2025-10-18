import json
import sqlite3
from pathlib import Path


DB_PATH = Path(__file__).resolve().parents[1] / "db" / "local.db"
OUT_PATH = Path(__file__).resolve().parents[1] / "db" / "matches.json"


def export_matches():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id,
                   home_team,
                   away_team,
                   competition,
                   county,
                   kickoff_at,
                   prediction_cutoff,
                   home_score,
                   away_score
            FROM matches
            ORDER BY datetime(kickoff_at) ASC
            """
        )
        rows = [dict(r) for r in cur.fetchall()]

    upcoming = []
    past = []
    for r in rows:
        if r["home_score"] is None and r["away_score"] is None:
            upcoming.append({
                "home": r["home_team"],
                "away": r["away_team"],
                "competition": r["competition"],
                "county": r["county"],
                "kickoff": r["kickoff_at"],
                "prediction": r["prediction_cutoff"],
            })
        else:
            past.append({
                "home": r["home_team"],
                "away": r["away_team"],
                "competition": r["competition"],
                "county": r["county"],
                "kickoff": r["kickoff_at"],
                "scoreA": r["home_score"],
                "scoreB": r["away_score"],
            })

    OUT_PATH.write_text(json.dumps({"upcoming": upcoming, "past": past}, indent=2))
    return OUT_PATH


if __name__ == "__main__":
    path = export_matches()
    print(f"Wrote {path}")


