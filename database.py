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
        security_id TEXT,
        entry_price REAL,
        stop_price REAL,
        position_size REAL,
        confidence REAL,
        status TEXT,
        entry_date TEXT,
        buy_order_id TEXT,
        stop_order_id TEXT,
        exit_price REAL,
        pnl REAL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS portfolio (
        id INTEGER PRIMARY KEY,
        peak_equity REAL
    )
    """)

    cursor.execute("SELECT * FROM portfolio WHERE id=1")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO portfolio (id, peak_equity) VALUES (1, ?)", (10000,))

    conn.commit()
    conn.close()


def add_trade(symbol, security_id, entry_price, stop_price,
              position_size, confidence, buy_id, stop_id):

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO trades
    (symbol, security_id, entry_price, stop_price, position_size,
     confidence, status, entry_date, buy_order_id, stop_order_id)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        symbol, security_id, entry_price, stop_price,
        position_size, confidence,
        "ACTIVE", datetime.now().strftime("%Y-%m-%d"),
        buy_id, stop_id
    ))

    conn.commit()
    conn.close()


def get_active_trades():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM trades WHERE status='ACTIVE'")
    data = cursor.fetchall()
    conn.close()
    return data


def get_all_trades():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM trades")
    data = cursor.fetchall()
    conn.close()
    return data


def update_peak_equity(value):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE portfolio SET peak_equity=? WHERE id=1", (value,))
    conn.commit()
    conn.close()


def get_peak_equity():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT peak_equity FROM portfolio WHERE id=1")
    value = cursor.fetchone()[0]
    conn.close()
    return value