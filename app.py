import streamlit as st
from scanner import scan_nifty50

st.set_page_config(page_title="Safe Alpha Engine", layout="wide")

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

st.markdown("---")

# -------------------------------
# NIFTY 50 SCANNER
# -------------------------------

st.markdown("## NIFTY 50 Scanner")

if st.button("Run NIFTY 50 Scan"):

    with st.spinner("Scanning NIFTY 50... Please wait."):
        df = scan_nifty50()

    if df is not None and not df.empty:

        st.markdown("### All Results (Sorted by Confidence)")
        st.dataframe(df, use_container_width=True)

        filtered = df[df["confidence"] >= 72]

        st.markdown("### Eligible Trades (Confidence ≥ 72%)")

        if not filtered.empty:
            st.success(f"{len(filtered)} Stocks Eligible")
            st.dataframe(filtered, use_container_width=True)
        else:
            st.warning("No stocks meet the 72% confidence threshold today.")

    else:
        st.error("Scanner returned no data.")