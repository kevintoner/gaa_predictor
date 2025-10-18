import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "db" / "local.db"


def column_exists(cur: sqlite3.Cursor, table: str, column: str) -> bool:
    cur.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cur.fetchall())


def main() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("PRAGMA foreign_keys=OFF")

        # 1) Ensure new columns exist
        cur.execute("PRAGMA table_info(matches)")
        cols = {row[1] for row in cur.fetchall()}
        added = []
        if "home_team_id" not in cols:
            cur.execute("ALTER TABLE matches ADD COLUMN home_team_id INTEGER")
            added.append("home_team_id")
        if "away_team_id" not in cols:
            cur.execute("ALTER TABLE matches ADD COLUMN away_team_id INTEGER")
            added.append("away_team_id")

        # 2) Populate team IDs if name columns exist
        has_name_cols = column_exists(cur, "matches", "home_team") and column_exists(cur, "matches", "away_team")
        if has_name_cols:
            # These updates are idempotent
            cur.execute(
                """
                UPDATE matches
                SET home_team_id = (
                  SELECT id FROM teams WHERE team_name = matches.home_team
                )
                WHERE home_team_id IS NULL
                """
            )
            cur.execute(
                """
                UPDATE matches
                SET away_team_id = (
                  SELECT id FROM teams WHERE team_name = matches.away_team
                )
                WHERE away_team_id IS NULL
                """
            )

        # 3) Check for any unmapped names
        cur.execute("SELECT COUNT(*) FROM matches WHERE home_team_id IS NULL OR away_team_id IS NULL")
        missing = cur.fetchone()[0]

        # 4) Rebuild table to enforce FKs and drop old text columns when we can
        if missing == 0:
            # 4) Rebuild table to enforce FKs and drop old text columns
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS matches_new (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  home_team_id INTEGER NOT NULL,
                  away_team_id INTEGER NOT NULL,
                  competition TEXT,
                  county TEXT,
                  venue TEXT,
                  kickoff_at TIMESTAMP NOT NULL,
                  prediction_cutoff TIMESTAMP,
                  home_score TEXT,
                  away_score TEXT,
                  match_over INTEGER,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (home_team_id) REFERENCES teams(id) ON DELETE RESTRICT,
                  FOREIGN KEY (away_team_id) REFERENCES teams(id) ON DELETE RESTRICT
                )
                """
            )

            if column_exists(cur, "matches", "home_team_id") and column_exists(cur, "matches", "away_team_id"):
                # Copy using existing id columns
                cur.execute(
                    """
                    INSERT INTO matches_new (
                      id, home_team_id, away_team_id, competition, county, venue,
                      kickoff_at, prediction_cutoff, home_score, away_score, match_over, created_at
                    )
                    SELECT id, home_team_id, away_team_id, competition, county, venue,
                           kickoff_at, prediction_cutoff, home_score, away_score, match_over, created_at
                    FROM matches
                    """
                )
            else:
                # Should not happen, but guard
                raise RuntimeError("Expected home_team_id/away_team_id columns to exist before rebuild")

            cur.execute("DROP TABLE matches")
            cur.execute("ALTER TABLE matches_new RENAME TO matches")

            # Indexes
            cur.execute("CREATE INDEX IF NOT EXISTS idx_matches_home_team_id ON matches(home_team_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_matches_away_team_id ON matches(away_team_id)")

        conn.commit()

        print("Migration complete.")
        print(f"Columns added: {added}")
        if missing:
            print(f"WARNING: {missing} rows could not be mapped to teams (null *_team_id).")
            if not has_name_cols:
                print("Note: matches table does not have name columns; populate teams or set ids manually, then re-run.")
        else:
            print("All rows mapped. Foreign keys enforced and text columns removed.")


if __name__ == "__main__":
    main()


