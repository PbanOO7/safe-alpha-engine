import streamlit as st
import yfinance as yf
import pandas as pd
import requests
from datetime import datetime

from scanner import scan_nifty50, market_is_bullish
from database import *

BASE_CAPITAL = 10000

st.set_page_config(page_title="Safe Alpha Engine", layout="wide")
init_db()

st.title("Safe Alpha Engine Dashboard")

# ---------------- LIVE MODE ----------------
if "live_mode" not in st.session_state:
    st.session_state.live_mode = False

live_toggle = st.checkbox("Enable LIVE Trading (Real Orders)", value=False)

if live_toggle:
    st.session_state.live_mode = True
    st.error("LIVE MODE ENABLED")
else:
    st.session_state.live_mode = False
    st.success("Simulation Mode")

# ---------------- ORDER FUNCTIONS ----------------
def place_dhan_order(symbol, quantity):
    url = "https://api.dhan.co/v2/orders"
    headers = {
        "Content-Type": "application/json",
        "access-token": st.secrets["DHAN_ACCESS_TOKEN"]
    }

    payload = {
        "dhanClientId": st.secrets["DHAN_CLIENT_ID"],
        "transactionType": "BUY",
        "exchangeSegment": "NSE_EQ",
        "productType": "CNC",
        "orderType": "MARKET",
        "securityId": symbol.replace(".NS",""),
        "quantity": quantity
    }

    response = requests.post(url, json=payload, headers=headers)
    return response.status_code, response.json()


def place_stop_order(symbol, quantity, stop_price):
    url = "https://api.dhan.co/v2/orders"
    headers = {
        "Content-Type": "application/json",
        "access-token": st.secrets["DHAN_ACCESS_TOKEN"]
    }

    payload = {
        "dhanClientId": st.secrets["DHAN_CLIENT_ID"],
        "transactionType": "SELL",
        "exchangeSegment": "NSE_EQ",
        "productType": "CNC",
        "orderType": "STOP_LOSS",
        "securityId": symbol.replace(".NS",""),
        "quantity": quantity,
        "price": round(stop_price,2),
        "triggerPrice": round(stop_price,2)
    }

    response = requests.post(url, json=payload, headers=headers)
    return response.status_code, response.json()


def modify_dhan_order(order_id, new_stop):
    url = f"https://api.dhan.co/v2/orders/{order_id}"
    headers = {
        "Content-Type": "application/json",
        "access-token": st.secrets["DHAN_ACCESS_TOKEN"]
    }
    payload = {
        "price": round(new_stop,2),
        "triggerPrice": round(new_stop,2)
    }

    response = requests.put(url, json=payload, headers=headers)
    return response.status_code, response.json()


# ---------------- SCANNER + EXECUTION ----------------
if st.button("Run NIFTY 50 Scan"):

    df = scan_nifty50()
    filtered = df[df["confidence"] >= 72]

    if not filtered.empty:
        top = filtered.iloc[0]
        quantity = int(top["position_size"] / top["price"])

        if st.session_state.live_mode:
            status, resp = place_dhan_order(top["symbol"], quantity)

            if status == 200:
                buy_id = resp.get("orderId")

                stop_status, stop_resp = place_stop_order(
                    top["symbol"],
                    quantity,
                    top["stop_price"]
                )

                if stop_status == 200:
                    stop_id = stop_resp.get("orderId")

                    add_trade(
                        symbol=top["symbol"],
                        entry_price=top["price"],
                        stop_price=top["stop_price"],
                        position_size=top["position_size"],
                        confidence=top["confidence"],
                        buy_id=buy_id,
                        stop_id=stop_id
                    )

                    st.success("LIVE Trade + Stop Placed")

                else:
                    st.error("Stop order failed")
            else:
                st.error("Buy failed")
        else:
            add_trade(
                symbol=top["symbol"],
                entry_price=top["price"],
                stop_price=top["stop_price"],
                position_size=top["position_size"],
                confidence=top["confidence"]
            )
            st.success("Simulated trade executed")