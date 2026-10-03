import sqlite3, uuid, time
from config import DB_PATH

def q(sql, a=()):
    c = sqlite3.connect(DB_PATH); c.row_factory = sqlite3.Row
    try:
        cur = c.execute(sql, a); c.commit()
        return [dict(r) for r in cur.fetchall()]
    finally:
        c.close()

def uid(): return uuid.uuid4().hex
def now(): return time.time()

def init():
    c = sqlite3.connect(DB_PATH)
    c.executescript("""
    CREATE TABLE IF NOT EXISTS conversations(id TEXT PRIMARY KEY,title TEXT,favorite INT DEFAULT 0,created REAL);
    CREATE TABLE IF NOT EXISTS messages(id TEXT PRIMARY KEY,conv_id TEXT,role TEXT,content TEXT,ts REAL);
    CREATE TABLE IF NOT EXISTS images(id TEXT PRIMARY KEY,name TEXT,data TEXT,ts REAL);
    CREATE TABLE IF NOT EXISTS files(id TEXT PRIMARY KEY,name TEXT,text TEXT,ts REAL);""")
    c.commit(); c.close()
