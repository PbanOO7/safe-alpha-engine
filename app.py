import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
from dhanhq import dhanhq
from database import (
    init_db,
    get_peak_equity,
    update_peak_equity,
    add_trade,
    get_all_trades,
    get_active_trades,
)
from scanner import scan, fetch_daily_history

BASE_CAPITAL = 10000
RISK_PER_TRADE = 0.01
MAX_DRAWDOWN = 0.08

st.set_page_config(layout="wide")
st.title("Safe Alpha Engine — EOD Mode")

# -----------------------
# LIVE / PAPER TOGGLE
# -----------------------
live_mode = st.toggle("Live Trading Mode", value=False)

if live_mode:
    st.success("LIVE MODE ENABLED — Real orders will be placed.")
else:
    st.warning("Paper Mode — No real orders will be placed.")

init_db()

dhan = dhanhq(
    st.secrets["DHAN_CLIENT_ID"],
    st.secrets["DHAN_ACCESS_TOKEN"]
)

EXCHANGE_EQ = getattr(dhan, "NSE_EQ", getattr(dhan, "NSE", "NSE_EQ"))
ORDER_TYPE_STOP = getattr(dhan, "STOP_LOSS", getattr(dhan, "SL", "STOP_LOSS"))

# -----------------------
# SYMBOL MAP
# -----------------------
@st.cache_data(ttl=60 * 60)
def build_symbol_map():
    def normalize_symbol(symbol):
        s = str(symbol).strip().upper()
        if s.endswith("-EQ"):
            s = s[:-3]
        return s

    url = "https://images.dhan.co/api-data/api-scrip-master.csv"
    try:
        df = pd.read_csv(url, low_memory=False)
        df.columns = df.columns.str.strip().str.upper()

        if "SEM_SEGMENT" in df.columns:
            segment = df["SEM_SEGMENT"].astype(str).str.strip().str.upper()
            filtered = df[segment == "NSE_EQ"].copy()
            if not filtered.empty:
                df = filtered

        symbol_col = None
        for candidate in ["SEM_TRADING_SYMBOL", "SEM_CUSTOM_SYMBOL", "SEM_SYMBOL"]:
            if candidate in df.columns:
                symbol_col = candidate
                break

        if symbol_col is None or "SEM_SMST_SECURITY_ID" not in df.columns:
            raise ValueError("Required symbol/security-id columns not found in scrip master CSV.")

        mapping = {}
        for _, row in df[[symbol_col, "SEM_SMST_SECURITY_ID"]].dropna().iterrows():
            raw_symbol = str(row[symbol_col]).strip().upper()
            security_id = str(row["SEM_SMST_SECURITY_ID"]).strip()
            if not raw_symbol or not security_id:
                continue

            # Keep both the exact exchange symbol (e.g. RELIANCE-EQ) and normalized key (RELIANCE).
            mapping[raw_symbol] = security_id
            mapping[normalize_symbol(raw_symbol)] = security_id

        return mapping
    except Exception as exc:
        st.warning(f"Could not load symbol map from Dhan master CSV: {exc}")
        return {}


def get_ltp(dhan_client, security_id):
    to_date = datetime.now().strftime("%Y-%m-%d")
    try:
        raw = fetch_daily_history(
            dhan_client=dhan_client,
            security_id=str(security_id),
            from_date=to_date,
            to_date=to_date,
        )
    except Exception:
        return None

    try:
        payload = raw.get("data", raw) if isinstance(raw, dict) else {}
        if isinstance(payload, dict):
            candles = payload.get("candles")
            if candles:
                return float(candles[-1][4])
            closes = payload.get("close", [])
            if closes:
                return float(closes[-1])
        return None
    except Exception:
        return None


def estimate_equity(dhan_client):
    equity = BASE_CAPITAL
    pricing_errors = 0

    for trade in get_active_trades():
        # Table order from database.py:
        # id, symbol, security_id, entry_price, stop_price, position_size, confidence, status, entry_date, buy_order_id, stop_order_id
        security_id = trade[2]
        entry_price = float(trade[3])
        position_size = float(trade[5])
        quantity = int(position_size / entry_price) if entry_price > 0 else 0
        if quantity <= 0:
            continue

        ltp = get_ltp(dhan_client, security_id)
        if ltp is None:
            pricing_errors += 1
            continue

        equity += (ltp - entry_price) * quantity

    return equity, pricing_errors

symbol_map = build_symbol_map()

# -----------------------
# PORTFOLIO STATUS
# -----------------------
peak = get_peak_equity()
equity, mtm_errors = estimate_equity(dhan)
if equity > peak:
    update_peak_equity(equity)
    peak = equity
drawdown = (peak - equity) / peak if peak > 0 else 0

st.write(f"Peak Equity: ₹{peak}")
st.write(f"Estimated Equity: ₹{round(equity, 2)}")
st.write(f"Drawdown: {round(drawdown*100,2)}%")
if mtm_errors > 0:
    st.warning(f"MTM pricing unavailable for {mtm_errors} active trade(s). Equity is partially estimated.")

if drawdown >= MAX_DRAWDOWN:
    st.error("Circuit breaker active")
    st.stop()

# -----------------------
# EOD SCAN
# -----------------------
if st.button("Run EOD Scan"):

    df, diagnostics_df = scan(dhan, symbol_map)
    if not diagnostics_df.empty:
        with st.expander("Scan Diagnostics", expanded=True):
            total = len(diagnostics_df)
            selected = int((diagnostics_df["status"] == "selected").sum())
            skipped = int((diagnostics_df["status"] == "skipped").sum())
            errors = int((diagnostics_df["status"] == "error").sum())
            st.write(f"Total symbols checked: {total} | Selected: {selected} | Skipped: {skipped} | Errors: {errors}")
            st.dataframe(diagnostics_df, use_container_width=True)

    if df.empty:
        st.warning("No valid setups today.")
    else:
        top = df.iloc[0]

        price = top["price"]
        stop_price = top["stop_price"]
        confidence = top["confidence"]
        security_id = top["security_id"]
        symbol = top["symbol"]

        risk_capital = BASE_CAPITAL * RISK_PER_TRADE
        stop_pct = (price - stop_price) / price
        if stop_pct <= 0:
            st.error(f"Invalid stop for {symbol}: stop must be below entry price.")
        else:
            position_value = risk_capital / stop_pct
            quantity = int(position_value / price)
            if quantity <= 0:
                st.error(f"Computed quantity is zero for {symbol}. Skipping trade.")
            else:
                if live_mode:
                    try:
                        buy = dhan.place_order(
                            security_id=security_id,
                            exchange_segment=EXCHANGE_EQ,
                            transaction_type=dhan.BUY,
                            quantity=quantity,
                            order_type=dhan.MARKET,
                            product_type=dhan.CNC,
                            price=0
                        )
                        buy_id = buy.get("orderId", "LIVE_BUY_FAIL") if isinstance(buy, dict) else "LIVE_BUY_FAIL"
                    except Exception as exc:
                        st.error(f"Live BUY order failed for {symbol}: {exc}")
                        buy_id = "LIVE_BUY_FAIL"

                    try:
                        stop = dhan.place_order(
                            security_id=security_id,
                            exchange_segment=EXCHANGE_EQ,
                            transaction_type=dhan.SELL,
                            quantity=quantity,
                            order_type=ORDER_TYPE_STOP,
                            product_type=dhan.CNC,
                            price=round(stop_price, 2),
                            trigger_price=round(stop_price, 2)
                        )
                        stop_id = stop.get("orderId", "LIVE_STOP_FAIL") if isinstance(stop, dict) else "LIVE_STOP_FAIL"
                    except Exception as exc:
                        st.error(f"Live STOP order failed for {symbol}: {exc}")
                        stop_id = "LIVE_STOP_FAIL"

                else:
                    buy_id = "PAPER_BUY"
                    stop_id = "PAPER_STOP"
                    st.info(f"Paper trade simulated: {symbol} | Qty: {quantity}")

                add_trade(
                    symbol,
                    security_id,
                    price,
                    stop_price,
                    position_value,
                    confidence,
                    buy_id,
                    stop_id
                )

# -----------------------
# JOURNAL
# -----------------------
st.markdown("## Trade Journal")

conn = sqlite3.connect("trades.db")
cursor = conn.cursor()

cursor.execute("PRAGMA table_info(trades)")
columns_info = cursor.fetchall()
column_names = [col[1] for col in columns_info]

trades = get_all_trades()

if trades:
    df_trades = pd.DataFrame(trades, columns=column_names)
    st.dataframe(df_trades)
else:
    st.write("No trades yet.")

conn.close()
