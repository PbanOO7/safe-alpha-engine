import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
from dhanhq import dhanhq
from database import *
from scanner import scan

# -----------------------
# CONFIG
# -----------------------
BASE_CAPITAL = 10000
RISK_PER_TRADE = 0.01
MAX_DRAWDOWN = 0.08

st.set_page_config(layout="wide")
st.title("Safe Alpha Engine — EOD Mode")

# -----------------------
# INIT DATABASE
# -----------------------
init_db()

# -----------------------
# INIT DHAN SDK
# -----------------------
dhan = dhanhq(
    st.secrets["DHAN_CLIENT_ID"],
    st.secrets["DHAN_ACCESS_TOKEN"]
)

# -----------------------
# BUILD SYMBOL MAP (Correct SEM Schema)
# -----------------------
def build_symbol_map():

    url = "https://images.dhan.co/api-data/api-scrip-master.csv"
    df = pd.read_csv(url)

    df.columns = df.columns.str.strip().str.upper()

    # Filter NSE Equity
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
    st.error("⚠ Circuit Breaker Active — Max Drawdown Hit")
    st.stop()

# -----------------------
# RUN EOD SCAN
# -----------------------
if st.button("Run EOD Scan"):

    df = scan(dhan, symbol_map)

    if df is None or df.empty:
        st.warning("No valid setups today.")
    else:

        top = df.iloc[0]

        price = top.get("price")
        stop_price = top.get("stop_price")
        confidence = top.get("confidence", 0)
        security_id = top.get("security_id")
        symbol = top.get("symbol")

        if price is None or stop_price is None or security_id is None:
            st.error("Scanner output format mismatch.")
            st.json(df)
            st.stop()

        # Risk-based sizing
        risk_capital = BASE_CAPITAL * RISK_PER_TRADE
        stop_pct = (price - stop_price) / price

        if stop_pct <= 0:
            st.warning("Invalid stop calculation.")
            st.stop()

        position_value = risk_capital / stop_pct
        quantity = int(position_value / price)

        if quantity <= 0:
            st.warning("Quantity calculated as zero.")
            st.stop()

        # -----------------------
        # PLACE BUY ORDER
        # -----------------------
        buy = dhan.place_order(
            security_id=security_id,
            exchange_segment=dhan.NSE_EQ,
            transaction_type=dhan.BUY,
            quantity=quantity,
            order_type=dhan.MARKET,
            product_type=dhan.CNC,
            price=0
        )

        if "orderId" not in buy:
            st.error("Buy order failed.")
            st.json(buy)
            st.stop()

        # -----------------------
        # PLACE STOP LOSS ORDER
        # -----------------------
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

        if "orderId" not in stop:
            st.error("Stop order failed.")
            st.json(stop)
            st.stop()

        # -----------------------
        # SAVE TRADE
        # -----------------------
        add_trade(
            symbol=symbol,
            security_id=security_id,
            entry_price=price,
            stop_price=stop_price,
            position_size=position_value,
            confidence=confidence,
            buy_id=buy["orderId"],
            stop_id=stop["orderId"]
        )

        st.success(f"Trade Executed: {symbol} | Qty: {quantity}")

# -----------------------
# TRADE JOURNAL (Dynamic Schema Safe)
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