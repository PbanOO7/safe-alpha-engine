import os
import sqlite3
from datetime import datetime

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
SQLITE_DB_NAME = os.getenv("SQLITE_DB_NAME", "trades.db")
TRADE_COLUMNS = [
    "id",
    "symbol",
    "security_id",
    "entry_price",
    "stop_price",
    "position_size",
    "confidence",
    "status",
    "entry_date",
    "buy_order_id",
    "stop_order_id",
]


def _is_postgres():
    value = DATABASE_URL.lower()
    return value.startswith("postgresql://") or value.startswith("postgres://")


def _connect():
    if _is_postgres():
        try:
            import psycopg2
        except ImportError as exc:
            raise RuntimeError("Install psycopg2-binary to use DATABASE_URL/Postgres.") from exc
        return psycopg2.connect(DATABASE_URL)
    return sqlite3.connect(SQLITE_DB_NAME)


def _ph():
    return "%s" if _is_postgres() else "?"


def init_db():
    conn = _connect()
    cursor = conn.cursor()

    if _is_postgres():
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id BIGSERIAL PRIMARY KEY,
            symbol TEXT,
            security_id TEXT,
            entry_price DOUBLE PRECISION,
            stop_price DOUBLE PRECISION,
            position_size DOUBLE PRECISION,
            confidence DOUBLE PRECISION,
            status TEXT,
            entry_date TEXT,
            buy_order_id TEXT,
            stop_order_id TEXT
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS portfolio (
            id INTEGER PRIMARY KEY,
            peak_equity DOUBLE PRECISION
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS app_state (
            id INTEGER PRIMARY KEY,
            kill_switch BOOLEAN
        )
        """)
    else:
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
            stop_order_id TEXT
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS portfolio (
            id INTEGER PRIMARY KEY,
            peak_equity REAL
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS app_state (
            id INTEGER PRIMARY KEY,
            kill_switch INTEGER
        )
        """)

    cursor.execute(f"SELECT * FROM portfolio WHERE id={_ph()}", (1,))
    if not cursor.fetchone():
        cursor.execute(
            f"INSERT INTO portfolio (id, peak_equity) VALUES ({_ph()}, {_ph()})",
            (1, 10000),
        )

    cursor.execute(f"SELECT * FROM app_state WHERE id={_ph()}", (1,))
    if not cursor.fetchone():
        cursor.execute(
            f"INSERT INTO app_state (id, kill_switch) VALUES ({_ph()}, {_ph()})",
            (1, False if _is_postgres() else 0),
        )

    conn.commit()
    conn.close()


def add_trade(symbol, security_id, entry_price, stop_price,
              position_size, confidence, buy_id, stop_id):

    conn = _connect()
    cursor = conn.cursor()
    ph = _ph()

    cursor.execute(f"""
    INSERT INTO trades
    (symbol, security_id, entry_price, stop_price, position_size,
     confidence, status, entry_date, buy_order_id, stop_order_id)
    VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})
    """, (
        symbol, security_id, entry_price, stop_price,
        position_size, confidence,
        "ACTIVE", datetime.now().strftime("%Y-%m-%d"),
        buy_id, stop_id
    ))

    conn.commit()
    conn.close()


def get_active_trades():
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM trades WHERE status={_ph()}", ("ACTIVE",))
    data = cursor.fetchall()
    conn.close()
    return data


def get_all_trades():
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM trades ORDER BY id DESC")
    data = cursor.fetchall()
    conn.close()
    return data


def update_peak_equity(value):
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute(f"UPDATE portfolio SET peak_equity={_ph()} WHERE id={_ph()}", (value, 1))
    conn.commit()
    conn.close()


def get_peak_equity():
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute(f"SELECT peak_equity FROM portfolio WHERE id={_ph()}", (1,))
    value = cursor.fetchone()[0]
    conn.close()
    return value


def set_kill_switch(enabled):
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute(
        f"UPDATE app_state SET kill_switch={_ph()} WHERE id={_ph()}",
        ((bool(enabled) if _is_postgres() else (1 if enabled else 0)), 1),
    )
    conn.commit()
    conn.close()


def get_kill_switch():
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute(f"SELECT kill_switch FROM app_state WHERE id={_ph()}", (1,))
    row = cursor.fetchone()
    conn.close()
    return bool(row[0]) if row else False


def get_trade_columns():
    return TRADE_COLUMNS
