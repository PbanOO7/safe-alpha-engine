import streamlit as st
import pandas as pd
from dhanhq import dhanhq
from database import *
from scanner import scan

BASE_CAPITAL = 10000
RISK_PER_TRADE = 0.01
MAX_DRAWDOWN = 0.08

st.set_page_config(layout="wide")
st.title("Safe Alpha Engine — EOD Mode")

init_db()

dhan = dhanhq(
    st.secrets["DHAN_CLIENT_ID"],
    st.secrets["DHAN_ACCESS_TOKEN"]
)

@st.cache_data
def build_symbol_map():
    instruments = dhan.get_instruments()
    df = pd.DataFrame(instruments)
    df = df[df["exchangeSegment"] == "NSE_EQ"]
    return dict(zip(df["tradingSymbol"], df["securityId"]))

symbol_map = build_symbol_map()

# -----------------------
# Drawdown Check
# -----------------------
active_trades = get_active_trades()
peak = get_peak_equity()

equity = BASE_CAPITAL
drawdown = (peak - equity) / peak

if drawdown >= MAX_DRAWDOWN:
    st.error("Circuit breaker active — drawdown exceeded")
    st.stop()

# -----------------------
# Scan Button
# -----------------------
if st.button("Run EOD Scan"):

    df = scan(dhan, symbol_map)

    if df.empty:
        st.warning("No setups today")
    else:
        top = df.iloc[0]

        risk_capital = BASE_CAPITAL * RISK_PER_TRADE
        stop_pct = (top["price"] - top["stop_price"]) / top["price"]
        position_size = risk_capital / stop_pct

        quantity = int(position_size / top["price"])

        buy = dhan.place_order(
            security_id=top["security_id"],
            exchange_segment=dhan.NSE_EQ,
            transaction_type=dhan.BUY,
            quantity=quantity,
            order_type=dhan.MARKET,
            product_type=dhan.CNC,
            price=0
        )

        stop = dhan.place_order(
            security_id=top["security_id"],
            exchange_segment=dhan.NSE_EQ,
            transaction_type=dhan.SELL,
            quantity=quantity,
            order_type=dhan.STOP_LOSS,
            product_type=dhan.CNC,
            price=top["stop_price"],
            trigger_price=top["stop_price"]
        )

        add_trade(
            top["symbol"],
            top["security_id"],
            top["price"],
            top["stop_price"],
            position_size,
            top["confidence"],
            buy["orderId"],
            stop["orderId"]
        )

        st.success(f"Trade Executed: {top['symbol']}")

# -----------------------
# Journal
# -----------------------
st.markdown("## Trade Journal")
trades = get_all_trades()

if trades:
    df = pd.DataFrame(trades, columns=[
        "id","symbol","security_id","entry_price","stop_price",
        "position_size","confidence","status","entry_date",
        "buy_order_id","stop_order_id","exit_price","pnl"
    ])
    st.dataframe(df)