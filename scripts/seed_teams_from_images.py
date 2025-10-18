import sqlite3
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "db" / "local.db"
IMAGES_DIR = ROOT / "images"

CREATE_TEAMS_SQL = """
CREATE TABLE IF NOT EXISTS teams (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  team_name TEXT NOT NULL UNIQUE,
  county TEXT,
  home_pitch TEXT,
  crest BLOB
);
"""


def to_team_name(stem: str) -> str:
  name = stem.replace("_", " ").replace("-", " ")
  # Normalize spacing and casing lightly
  name = " ".join(part for part in name.split() if part)
  if not name:
    return stem
  # Preserve common Irish punctuation
  return name.title().replace("'S", "'s")


def iter_image_files(directory: Path) -> Iterable[Path]:
  exts = {".png", ".jpg", ".jpeg", ".webp", ".svg"}
  if not directory.exists():
    return []
  for p in sorted(directory.iterdir()):
    if p.is_file() and p.suffix.lower() in exts:
      yield p


def main() -> None:
  if not IMAGES_DIR.exists():
    print(f"Images directory not found: {IMAGES_DIR}")
    return

  with sqlite3.connect(DB_PATH) as conn:
    cur = conn.cursor()
    cur.executescript(CREATE_TEAMS_SQL)

    upsert_sql = (
      """
      INSERT INTO teams(team_name, county, home_pitch, crest)
      VALUES(?, ?, ?, ?)
      ON CONFLICT(team_name) DO UPDATE SET
        crest = excluded.crest,
        county = COALESCE(teams.county, excluded.county),
        home_pitch = COALESCE(teams.home_pitch, excluded.home_pitch)
      """
    )

    inserted, updated = 0, 0
    for img in iter_image_files(IMAGES_DIR):
      team_name = to_team_name(img.stem)
      crest_bytes = b""
      try:
        crest_bytes = img.read_bytes()
      except Exception:
        pass
      # Try to detect if row exists to track inserted/updated counts
      cur.execute("SELECT 1 FROM teams WHERE team_name=?", (team_name,))
      existed = cur.fetchone() is not None
      cur.execute(upsert_sql, (team_name, None, None, crest_bytes))
      if existed:
        updated += 1
      else:
        inserted += 1

    conn.commit()
    print(f"Seeded teams from {IMAGES_DIR}: inserted={inserted} updated={updated}")


if __name__ == "__main__":
  main()


