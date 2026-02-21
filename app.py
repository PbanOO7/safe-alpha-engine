import streamlit as st

st.set_page_config(page_title="Safe Alpha Engine", layout="wide")

st.title("Safe Alpha Engine Dashboard")

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

st.markdown("### Portfolio Overview")
st.write("Capital: ₹10,000")
st.write("Risk per trade: 1%")
st.write("Max trades: 4")
st.write("Min AI Confidence: 72%")
from scanner import scan_stock

st.markdown("---")
st.markdown("### Scanner Test")

symbol = st.text_input("Enter NSE Stock (e.g., TCS.NS)", "TCS.NS")

if st.button("Run Scan"):
    result = scan_stock(symbol)
    if result:
        st.write("Stock:", result["symbol"])
        st.write("Price:", result["price"])
        st.write("AI Confidence:", result["confidence"], "%")
        
        if result["confidence"] >= 72:
            st.success("Trade Eligible")
        else:
            st.warning("Below Confidence Threshold")
    else:
        st.error("Not enough data")