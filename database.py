import sqlite3
from datetime import datetime, timedelta

DB_PATH = "dating.db"

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id     INTEGER PRIMARY KEY,
            username    TEXT,
            name        TEXT NOT NULL,
            age         INTEGER NOT NULL,
            gender      TEXT NOT NULL,
            city        TEXT NOT NULL,
            about       TEXT DEFAULT '',
            photo_id    TEXT,
            active      INTEGER DEFAULT 1,
            search_filter TEXT DEFAULT 'all',
            created_at  TEXT DEFAULT (datetime('now')),
            views       INTEGER DEFAULT 0
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS reactions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            from_id     INTEGER NOT NULL,
            to_id       INTEGER NOT NULL,
            type        TEXT NOT NULL,  -- 'like' or 'dislike'
            created_at  TEXT DEFAULT (datetime('now')),
            UNIQUE(from_id, to_id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            from_id     INTEGER NOT NULL,
            to_id       INTEGER NOT NULL,
            created_at  TEXT DEFAULT (datetime('now'))
        )
    """)

    conn.commit()
    conn.close()

# ── USERS ──
def create_user(user_id, username, name, age, gender, city, about, photo_id):
    conn = get_conn()
    conn.execute("""
        INSERT OR REPLACE INTO users (user_id, username, name, age, gender, city, about, photo_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (user_id, username, name, age, gender, city, about, photo_id))
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def update_user(user_id, **kwargs):
    if not kwargs:
        return
    fields = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [user_id]
    conn = get_conn()
    conn.execute(f"UPDATE users SET {fields} WHERE user_id = ?", values)
    conn.commit()
    conn.close()

def delete_user(user_id):
    conn = get_conn()
    conn.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM reactions WHERE from_id = ? OR to_id = ?", (user_id, user_id))
    conn.commit()
    conn.close()

# ── FEED ──
def get_feed(user_id, limit=20):
    user = get_user(user_id)
    if not user:
        return []

    # Определяем фильтр пола
    gender_filter = user.get('search_filter', 'all')
    gender_clause = ""
    if gender_filter == "male":
        gender_clause = "AND u.gender = 'male'"
    elif gender_filter == "female":
        gender_clause = "AND u.gender = 'female'"

    conn = get_conn()
    rows = conn.execute(f"""
        SELECT u.* FROM users u
        WHERE u.user_id != ?
          AND u.active = 1
          {gender_clause}
          AND u.user_id NOT IN (
              SELECT to_id FROM reactions WHERE from_id = ?
          )
        ORDER BY RANDOM()
        LIMIT ?
    """, (user_id, user_id, limit)).fetchall()

    # Увеличиваем просмотры
    for row in rows:
        conn.execute("UPDATE users SET views = views + 1 WHERE user_id = ?", (row['user_id'],))
    conn.commit()
    conn.close()

    return [dict(r) for r in rows]

# ── REACTIONS ──
def add_like(from_id, to_id):
    """Returns True if mutual match"""
    conn = get_conn()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO reactions (from_id, to_id, type) VALUES (?, ?, 'like')",
            (from_id, to_id)
        )
        conn.commit()
    except Exception:
        pass

    # Проверяем взаимность
    mutual = conn.execute("""
        SELECT 1 FROM reactions
        WHERE from_id = ? AND to_id = ? AND type = 'like'
    """, (to_id, from_id)).fetchone()
    conn.close()
    return bool(mutual)

def add_dislike(from_id, to_id):
    conn = get_conn()
    conn.execute(
        "INSERT OR IGNORE INTO reactions (from_id, to_id, type) VALUES (?, ?, 'dislike')",
        (from_id, to_id)
    )
    conn.commit()
    conn.close()

def get_likers(user_id):
    """Люди которые лайкнули user_id но не получили лайк в ответ"""
    conn = get_conn()
    rows = conn.execute("""
        SELECT u.* FROM users u
        INNER JOIN reactions r ON r.from_id = u.user_id
        WHERE r.to_id = ? AND r.type = 'like'
          AND u.user_id NOT IN (
              SELECT to_id FROM reactions WHERE from_id = ? AND type = 'like'
          )
        ORDER BY r.created_at DESC
    """, (user_id, user_id)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_matches(user_id):
    """Взаимные лайки"""
    conn = get_conn()
    rows = conn.execute("""
        SELECT u.* FROM users u
        INNER JOIN reactions r1 ON r1.to_id = u.user_id AND r1.from_id = ?
        INNER JOIN reactions r2 ON r2.from_id = u.user_id AND r2.to_id = ?
        WHERE r1.type = 'like' AND r2.type = 'like'
        ORDER BY r1.created_at DESC
    """, (user_id, user_id)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def add_report(from_id, to_id):
    conn = get_conn()
    conn.execute(
        "INSERT INTO reports (from_id, to_id) VALUES (?, ?)",
        (from_id, to_id)
    )
    conn.commit()
    conn.close()

# ── STATS ──
def get_user_stats(user_id):
    conn = get_conn()

    likes_received = conn.execute(
        "SELECT COUNT(*) FROM reactions WHERE to_id = ? AND type = 'like'",
        (user_id,)
    ).fetchone()[0]

    matches = conn.execute("""
        SELECT COUNT(*) FROM reactions r1
        INNER JOIN reactions r2 ON r1.from_id = r2.to_id AND r1.to_id = r2.from_id
        WHERE r1.from_id = ? AND r1.type = 'like' AND r2.type = 'like'
    """, (user_id,)).fetchone()[0]

    views = conn.execute(
        "SELECT views FROM users WHERE user_id = ?",
        (user_id,)
    ).fetchone()
    views = views[0] if views else 0

    conn.close()
    return {"likes_received": likes_received, "matches": matches, "views": views}

def get_top_users(limit=10):
    conn = get_conn()
    rows = conn.execute("""
        SELECT u.*, COUNT(r.id) as likes_received
        FROM users u
        LEFT JOIN reactions r ON r.to_id = u.user_id AND r.type = 'like'
        WHERE u.active = 1
        GROUP BY u.user_id
        ORDER BY likes_received DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]
def get_all_users():
    conn = sqlite3.connect('dating.db') # ПРОВЕРЬТЕ: имя файла .db должно быть таким же, как в других ваших функциях
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users")
    users = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return users
import os


if os.path.exists('/app/shared'):
    DB_PATH = "/app/shared/dating.db"
else:
    DB_PATH = "dating.db"


