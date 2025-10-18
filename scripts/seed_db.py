import random
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path


DB_PATH = Path(__file__).resolve().parents[1] / "db" / "local.db"

FIRST_NAMES = ["Liam","Noah","Oliver","James","Benjamin","Emma","Olivia","Ava","Isla","Amelia","Jack","Harry","Emily","Grace","Sophie","Chloe"]
LAST_NAMES = ["Murphy","Kelly","OConnor","OBrien","Doyle","Walsh","Byrne","Ryan","ONeill","Daly","Gallagher","Kennedy"]

DERBY_CLUBS = [
    "Watty Graham's Glen",
    "Slaughtneil Emmet's",
    "Ballinderry Shamrocks",
    "Bellaghy Wolfe Tones",
    "Lavey Erin's Own",
    "Magherafelt O'Donovan Rossa",
    "Coleraine Eoghan Rua",
    "Glenullin John Mitchel's",
    "Loup St Patrick's",
    "Dungiven St Canice's",
    "Banagher St Mary's",
]


def rand_name():
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"


def rand_email(name: str) -> str:
    handle = name.lower().replace(" ", ".").replace("'", "")
    domains = ["example.com", "mail.com", "test.io"]
    return f"{handle}@{random.choice(domains)}"


def rand_password(name: str) -> str:
    # simple dev password generator (not for production)
    base = name.lower().split(" ")[0]
    return base + str(random.randint(1000, 9999))


def rand_score() -> str:
    return f"{random.randint(0,4)}-{random.randint(0,20)}"


def gaelic_total(score: str) -> int:
    g, p = score.split("-")
    return int(g) * 3 + int(p)


def seed(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    # groups
    groups = [("Lavey group", "Derry"), ("Work Group", "Dublin"), ("Family Group", "Cork")]
    for name, county in groups:
        cur.execute("INSERT OR IGNORE INTO groups(name, county) VALUES(?,?)", (name, county))

    # members per group (8-16)
    cur.execute("SELECT id, name FROM groups")
    group_rows = cur.fetchall()
    for gid, gname in group_rows:
        n = random.randint(8, 16)
        admin_assigned = False
        for i in range(n):
            person = rand_name()
            role = 'admin' if not admin_assigned else 'normal'
            if not admin_assigned:
                admin_assigned = True
            cur.execute(
                "INSERT OR IGNORE INTO members(group_id, name, email, password, role) VALUES(?,?,?,?,?)",
                (gid, person, rand_email(person), rand_password(person), role),
            )

    # matches: 5 upcoming, 6 past
    now = datetime.utcnow()
    match_ids = []
    for i in range(5):
        a, b = random.sample(DERBY_CLUBS, 2)
        kickoff = now + timedelta(hours=random.randint(2, 72))
        cutoff = kickoff - timedelta(hours=random.randint(1, 3))
        cur.execute(
            """
            INSERT INTO matches(home_team, away_team, competition, county, kickoff_at, prediction_cutoff)
            VALUES(?,?,?,?,?,?)
            """,
            (a, b, "Derry SFC", "Derry", kickoff.isoformat(), cutoff.isoformat()),
        )
        match_ids.append(cur.lastrowid)
    for i in range(6):
        a, b = random.sample(DERBY_CLUBS, 2)
        kickoff = now - timedelta(hours=random.randint(2, 7 * 24))
        sA, sB = rand_score(), rand_score()
        cur.execute(
            """
            INSERT INTO matches(home_team, away_team, competition, county, kickoff_at, home_score, away_score)
            VALUES(?,?,?,?,?,?,?)
            """,
            (a, b, "Derry SFC", "Derry", kickoff.isoformat(), sA, sB),
        )
        match_ids.append(cur.lastrowid)

    # picks for each group/member for a subset of matches
    cur.execute("SELECT id FROM members")
    member_ids = [row[0] for row in cur.fetchall()]
    cur.execute("SELECT id FROM groups")
    group_ids = [row[0] for row in cur.fetchall()]
    for mid in member_ids:
        gid = random.choice(group_ids)
        for match_id in random.sample(match_ids, k=min(5, len(match_ids))):
            pick = random.choice(["A", "B", "D"])
            cur.execute(
                "INSERT OR IGNORE INTO picks(group_id, member_id, match_id, pick) VALUES(?,?,?,?)",
                (gid, mid, match_id, pick),
            )

    conn.commit()


def counts(conn: sqlite3.Connection) -> dict:
    cur = conn.cursor()
    res = {}
    for table in ("groups", "members", "matches", "picks"):
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        res[table] = cur.fetchone()[0]
    return res


if __name__ == "__main__":
    with sqlite3.connect(DB_PATH) as conn:
        seed(conn)
        print(counts(conn))


