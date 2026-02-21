import streamlit as st
from scanner import scan_nifty50
from database import (
    init_db,
    get_active_trades,
    get_weekly_trade_count,
    add_trade,
    increment_weekly_trade
)

# -------------------------------
# PAGE CONFIG
# -------------------------------

st.set_page_config(page_title="Safe Alpha Engine", layout="wide")

# Initialize Database
init_db()

st.title("Safe Alpha Engine Dashboard")

# -------------------------------
# SYSTEM MODE STATE
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

with colA:
    st.metric("Capital", "₹10,000")

with colB:
    st.metric("Risk per Trade", "1%")

with colC:
    st.metric("Max Active Trades", "4")

with colD:
    st.metric("Min Confidence", "72%")

# -------------------------------
# ACTIVE TRADES SECTION
# -------------------------------

st.markdown("---")
st.markdown("### Active Trades")

active_trades = get_active_trades()

if active_trades:
    st.dataframe(active_trades, use_container_width=True)
else:
    st.write("No active trades")
import yfinance as yf
from database import close_trade

# -------------------------------
# STOP MONITORING
# -------------------------------

if active_trades:
    st.markdown("### Stop Monitoring")

    for trade in active_trades:
        trade_id = trade[0]
        symbol = trade[1]
        entry_price = trade[2]
        stop_price = trade[3]
        position_size = trade[4]

        data = yf.download(symbol, period="5d", interval="1d", auto_adjust=True)

        if not data.empty:
            latest_price = float(data["Close"].iloc[-1])

            if latest_price <= stop_price:
                close_trade(trade_id)
                st.error(f"Stop Hit — Trade Closed: {symbol}")
                
# -------------------------------
# WEEKLY TRADE COUNT
# -------------------------------

weekly_count = get_weekly_trade_count()
st.write(f"Weekly Trades Taken: {weekly_count} / 3")

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

        st.markdown("### Eligible Trades (Confidence ≥ 72%)")

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

            # Pick top 1
            top_trade = filtered.iloc[0]

            # Refresh active & weekly count
            active_trades = get_active_trades()
            weekly_count = get_weekly_trade_count()

            # Safety checks
            if st.session_state.system_mode != "ACTIVE":
                st.warning("System is paused. No trade executed.")

            elif len(active_trades) >= 4:
                st.warning("Max active trades reached.")

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
            st.warning("No stocks meet the 72% confidence threshold today.")

    else:
        st.error("Scanner returned no data.")