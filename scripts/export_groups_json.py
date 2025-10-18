import json
import sqlite3
from pathlib import Path


DB_PATH = Path(__file__).resolve().parents[1] / "db" / "local.db"
OUT_PATH = Path(__file__).resolve().parents[1] / "db" / "groups.json"


def export_groups():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            """
            SELECT g.id,
                   g.name,
                   g.county,
                   (SELECT COUNT(*) FROM members m WHERE m.group_id = g.id) AS members
            FROM groups g
            ORDER BY g.name COLLATE NOCASE
            """
        )
        rows = [dict(r) for r in cur.fetchall()]
    OUT_PATH.write_text(json.dumps(rows, indent=2))
    return OUT_PATH


if __name__ == "__main__":
    path = export_groups()
    print(f"Wrote {path}")


