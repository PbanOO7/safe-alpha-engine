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
DEFAULT_RISK_PERCENT = 1
DEFENSIVE_RISK_PERCENT = 0.5

DEFAULT_MAX_TRADES = 4
DEFENSIVE_MAX_TRADES = 2

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

# -------------------------------
# DEFENSIVE MODE LOGIC
# -------------------------------

if drawdown_pct <= -5:
    st.error("⚠ Defensive Mode Activated (Drawdown ≥ 5%)")
    current_risk_percent = DEFENSIVE_RISK_PERCENT
    max_active_trades = DEFENSIVE_MAX_TRADES
else:
    current_risk_percent = DEFAULT_RISK_PERCENT
    max_active_trades = DEFAULT_MAX_TRADES

st.markdown("---")
st.markdown("### Risk Control Status")

colA, colB = st.columns(2)
colA.metric("Risk Per Trade %", f"{current_risk_percent}%")
colB.metric("Max Active Trades", f"{max_active_trades}")

# -------------------------------
# NIFTY 50 SCANNER + AUTO ENTRY
# -------------------------------

st.markdown("---")
st.markdown("## NIFTY 50 Scanner")

if st.button("Run NIFTY 50 Scan"):

    with st.spinner("Scanning NIFTY 50... Please wait."):
        df = scan_nifty50()

    if df is not None and not df.empty:

        filtered = df[df["confidence"] >= 72]

        if not filtered.empty:

            st.dataframe(
                filtered[[
                    "symbol",
                    "price",
                    "confidence",
                    "stop_price",
                    "stop_pct",
                    "position_size"
                ]],
                use_container_width=True
            )

            top_trade = filtered.iloc[0]
            active_trades = get_active_trades()

            if st.session_state.system_mode != "ACTIVE":
                st.warning("System is paused.")

            elif not market_bullish:
                st.error("Market below 200 DMA. Trades blocked.")

            elif len(active_trades) >= max_active_trades:
                st.warning("Max active trades limit reached.")

            elif weekly_count >= 3:
                st.warning("Weekly trade limit reached.")

            else:
                add_trade(
                    symbol=top_trade["symbol"],
                    entry_price=top_trade["price"],
                    stop_price=top_trade["stop_price"],
                    position_size=top_trade["position_size"],
                    confidence=top_trade["confidence"]
                )

                increment_weekly_trade()
                st.success(f"Auto Trade Simulated: {top_trade['symbol']}")

        else:
            st.warning("No eligible trades today.")