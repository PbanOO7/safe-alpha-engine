import sqlite3
from datetime import datetime

DB_NAME = "trades.db"


def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Trades table
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

    # Weekly stats
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS trade_stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        week_number INTEGER,
        trade_count INTEGER
    )
    """)

    # Portfolio tracking
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS portfolio (
        id INTEGER PRIMARY KEY,
        peak_equity REAL
    )
    """)

    # Equity history
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


def close_trade(trade_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
    UPDATE trades
    SET status='CLOSED'
    WHERE id=?
    """, (trade_id,))

    conn.commit()
    conn.close()


def update_stop(trade_id, new_stop):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
    UPDATE trades
    SET stop_price=?
    WHERE id=?
    """, (new_stop, trade_id))

    conn.commit()
    conn.close()


def get_active_trades():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM trades WHERE status='ACTIVE'")
    trades = cursor.fetchall()
    conn.close()
    return trades


def get_all_trades():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM trades")
    trades = cursor.fetchall()
    conn.close()
    return trades


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