import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
from dhanhq import dhanhq
from database import *
from scanner import scan

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

# -----------------------
# SYMBOL MAP
# -----------------------
def build_symbol_map():
    url = "https://images.dhan.co/api-data/api-scrip-master.csv"
    df = pd.read_csv(url, low_memory=False)
    df.columns = df.columns.str.strip().str.upper()
    df = df[df["SEM_SEGMENT"] == "NSE_EQ"]
    return dict(zip(df["SEM_TRADING_SYMBOL"], df["SEM_SMST_SECURITY_ID"]))

symbol_map = build_symbol_map()

# -----------------------
# PORTFOLIO STATUS
# -----------------------
peak = get_peak_equity()
equity = BASE_CAPITAL
drawdown = (peak - equity) / peak if peak > 0 else 0

st.write(f"Peak Equity: ₹{peak}")
st.write(f"Drawdown: {round(drawdown*100,2)}%")

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

                    buy = dhan.place_order(
                        security_id=security_id,
                        exchange_segment=dhan.NSE_EQ,
                        transaction_type=dhan.BUY,
                        quantity=quantity,
                        order_type=dhan.MARKET,
                        product_type=dhan.CNC,
                        price=0
                    )

                    stop = dhan.place_order(
                        security_id=security_id,
                        exchange_segment=dhan.NSE_EQ,
                        transaction_type=dhan.SELL,
                        quantity=quantity,
                        order_type=dhan.STOP_LOSS,
                        product_type=dhan.CNC,
                        price=round(stop_price, 2),
                        trigger_price=round(stop_price, 2)
                    )

                    buy_id = buy.get("orderId", "LIVE_BUY_FAIL")
                    stop_id = stop.get("orderId", "LIVE_STOP_FAIL")

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
