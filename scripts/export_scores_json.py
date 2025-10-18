import json
import sqlite3
from pathlib import Path


DB_PATH = Path(__file__).resolve().parents[1] / "db" / "local.db"
OUT_PATH = Path(__file__).resolve().parents[1] / "db" / "scores.json"


def export_scores():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            """
            SELECT g.name AS group_name,
                   m.name AS member_name,
                   ms.score AS score
            FROM member_scores ms
            JOIN groups g ON g.id = ms.group_id
            JOIN members m ON m.id = ms.member_id
            ORDER BY g.name COLLATE NOCASE, ms.score DESC, m.name COLLATE NOCASE
            """
        )
        rows = [dict(r) for r in cur.fetchall()]
    OUT_PATH.write_text(json.dumps(rows, indent=2))
    return OUT_PATH


if __name__ == "__main__":
    path = export_scores()
    print(f"Wrote {path}")


