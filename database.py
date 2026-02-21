import sqlite3
from datetime import datetime

DB_NAME = "trades.db"


def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # -------------------------------
    # TRADES TABLE (Schema-safe)
    # -------------------------------

    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='trades'
    """)
    table_exists = cursor.fetchone()

    if table_exists:
        cursor.execute("PRAGMA table_info(trades)")
        columns = [col[1] for col in cursor.fetchall()]

        if "buy_order_id" not in columns:
            cursor.execute("DROP TABLE trades")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT,
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

    # -------------------------------
    # WEEKLY TRADE STATS
    # -------------------------------

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS trade_stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        week_number INTEGER,
        trade_count INTEGER
    )
    """)

    # -------------------------------
    # PORTFOLIO TABLE
    # -------------------------------

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS portfolio (
        id INTEGER PRIMARY KEY,
        peak_equity REAL
    )
    """)

    # -------------------------------
    # EQUITY HISTORY
    # -------------------------------

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS equity_history (
        date TEXT PRIMARY KEY,
        equity REAL
    )
    """)

    # Initialize peak equity if not exists
    cursor.execute("SELECT * FROM portfolio WHERE id=1")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO portfolio (id, peak_equity) VALUES (1, ?)", (10000,))

    conn.commit()
    conn.close()


# -------------------------------
# TRADE FUNCTIONS
# -------------------------------

def add_trade(symbol, entry_price, stop_price, position_size, confidence,
              buy_id=None, stop_id=None):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO trades
    (symbol, entry_price, stop_price, position_size, confidence,
     status, entry_date, buy_order_id, stop_order_id)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        symbol,
        entry_price,
        stop_price,
        position_size,
        confidence,
        "ACTIVE",
        datetime.now().strftime("%Y-%m-%d"),
        buy_id,
        stop_id
    ))

    conn.commit()
    conn.close()


def close_trade(trade_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE trades SET status='CLOSED' WHERE id=?", (trade_id,))
    conn.commit()
    conn.close()


def update_stop(trade_id, new_stop):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE trades SET stop_price=? WHERE id=?", (new_stop, trade_id))
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


# -------------------------------
# WEEKLY TRACKING
# -------------------------------

def get_week_number():
    return datetime.now().isocalendar()[1]


def increment_weekly_trade():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    week = get_week_number()

    cursor.execute("SELECT * FROM trade_stats WHERE week_number=?", (week,))
    result = cursor.fetchone()

    if result:
        cursor.execute(
            "UPDATE trade_stats SET trade_count=trade_count+1 WHERE week_number=?",
            (week,)
        )
    else:
        cursor.execute(
            "INSERT INTO trade_stats (week_number, trade_count) VALUES (?, ?)",
            (week, 1)
        )

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


# -------------------------------
# PORTFOLIO FUNCTIONS
# -------------------------------

def get_peak_equity():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT peak_equity FROM portfolio WHERE id=1")
    result = cursor.fetchone()
    conn.close()
    return result[0]


def update_peak_equity(new_peak):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE portfolio SET peak_equity=? WHERE id=1", (new_peak,))
    conn.commit()
    conn.close()


def record_equity(date, equity):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO equity_history (date, equity)
        VALUES (?, ?)
    """, (date, equity))
    conn.commit()
    conn.close()


def get_equity_history():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT date, equity FROM equity_history ORDER BY date")
    data = cursor.fetchall()
    conn.close()
    return data