import sqlite3
from datetime import datetime

DB_NAME = "trades.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT,
        entry_price REAL,
        stop_price REAL,
        position_size REAL,
        confidence REAL,
        status TEXT,
        entry_date TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS trade_stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        week_number INTEGER,
        trade_count INTEGER
    )
    """)

    conn.commit()
    conn.close()


def add_trade(symbol, entry_price, stop_price, position_size, confidence):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO trades (symbol, entry_price, stop_price, position_size, confidence, status, entry_date)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        symbol,
        entry_price,
        stop_price,
        position_size,
        confidence,
        "ACTIVE",
        datetime.now().strftime("%Y-%m-%d")
    ))

    conn.commit()
    conn.close()


def get_active_trades():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM trades WHERE status='ACTIVE'")
    trades = cursor.fetchall()

    conn.close()
    return trades


def get_week_number():
    return datetime.now().isocalendar()[1]


def increment_weekly_trade():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    week = get_week_number()

    cursor.execute("SELECT * FROM trade_stats WHERE week_number=?", (week,))
    result = cursor.fetchone()

    if result:
        cursor.execute("""
        UPDATE trade_stats
        SET trade_count = trade_count + 1
        WHERE week_number=?
        """, (week,))
    else:
        cursor.execute("""
        INSERT INTO trade_stats (week_number, trade_count)
        VALUES (?, ?)
        """, (week, 1))

    conn.commit()
    conn.close()


def get_weekly_trade_count():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    week = get_week_number()

    cursor.execute("SELECT trade_count FROM trade_stats WHERE week_number=?", (week,))
    result = cursor.fetchone()

    conn.close()

    return result[0] if result else 0