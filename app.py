import streamlit as st
import yfinance as yf

from scanner import scan_nifty50, market_is_bullish
from database import (
    init_db,
    get_active_trades,
    get_weekly_trade_count,
    add_trade,
    increment_weekly_trade,
    close_trade,
    update_stop,
    get_peak_equity,
    update_peak_equity
)

BASE_CAPITAL = 10000

st.set_page_config(page_title="Safe Alpha Engine", layout="wide")
init_db()

st.title("Safe Alpha Engine Dashboard")

# -------------------------------
# SYSTEM MODE
# -------------------------------

if "system_mode" not in st.session_state:
    st.session_state.system_mode = "ACTIVE"

col1, col2, col3 = st.columns(3)

with col1:
    if st.button("Pause New Entries"):
        st.session_state.system_mode = "ENTRY_PAUSED"

with col2:
    if st.button("Resume System"):
        st.session_state.system_mode = "ACTIVE"

with col3:
    if st.button("Emergency Exit"):
        st.session_state.system_mode = "EMERGENCY_EXIT"

st.markdown("---")
st.write(f"### System Status: {st.session_state.system_mode}")

# -------------------------------
# PORTFOLIO OVERVIEW
# -------------------------------

st.markdown("### Portfolio Overview")
colA, colB, colC, colD = st.columns(4)

colA.metric("Capital", "₹10,000")
colB.metric("Risk per Trade", "1%")
colC.metric("Max Active Trades", "4")
colD.metric("Min Confidence", "72%")

# -------------------------------
# MARKET REGIME
# -------------------------------

market_bullish = market_is_bullish()

st.markdown("---")
if market_bullish:
    st.success("Market Regime: BULLISH (Above 200 DMA)")
else:
    st.error("Market Regime: DEFENSIVE MODE (Below 200 DMA)")

# -------------------------------
# ACTIVE TRADES
# -------------------------------

st.markdown("---")
st.markdown("### Active Trades")

active_trades = get_active_trades()

if active_trades:
    st.dataframe(active_trades, use_container_width=True)
else:
    st.write("No active trades")

weekly_count = get_weekly_trade_count()
st.write(f"Weekly Trades Taken: {weekly_count} / 3")

# -------------------------------
# PORTFOLIO P&L + DRAWDOWN
# -------------------------------

total_unrealized = 0
total_exposure = 0

if active_trades:
    for trade in active_trades:
        symbol = trade[1]
        entry_price = trade[2]
        position_size = trade[4]

        data = yf.download(symbol, period="5d", interval="1d", auto_adjust=True)

        if not data.empty:
            latest_price = float(data["Close"].iloc[-1])
            quantity = position_size / entry_price
            pnl = (latest_price - entry_price) * quantity

            total_unrealized += pnl
            total_exposure += position_size

current_equity = BASE_CAPITAL + total_unrealized
peak_equity = get_peak_equity()

if current_equity > peak_equity:
    update_peak_equity(current_equity)
    peak_equity = current_equity

drawdown_pct = (current_equity - peak_equity) / peak_equity * 100

st.markdown("---")
st.markdown("### Portfolio Performance")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Exposure", f"₹{round(total_exposure,2)}")
col2.metric("Unrealized P&L", f"₹{round(total_unrealized,2)}")
col3.metric("Current Equity", f"₹{round(current_equity,2)}")
col4.metric("Drawdown %", f"{round(drawdown_pct,2)}%")

if drawdown_pct <= -5:
    st.error("⚠ Defensive Mode Triggered (Drawdown ≥ 5%)")