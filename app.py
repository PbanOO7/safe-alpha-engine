import streamlit as st
import pandas as pd
from datetime import datetime
from dhanhq import dhanhq
from database import (
    init_db,
    get_peak_equity,
    update_peak_equity,
    add_trade,
    get_all_trades,
    get_active_trades,
    get_kill_switch,
    set_kill_switch,
    get_trade_columns,
)
from scanner import scan, fetch_daily_history, scan_portfolio_risk

BASE_CAPITAL = 10000
RISK_PER_TRADE = 0.01
MAX_DRAWDOWN = 0.08

st.set_page_config(layout="wide")
st.title("Safe Alpha Engine — EOD Mode")
init_db()

# -----------------------
# LIVE / PAPER TOGGLE
# -----------------------
live_mode = st.toggle("Live Trading Mode", value=False)
allow_min_qty_fallback = st.toggle("Allow 1-share fallback if risk sizing is 0", value=True)
manual_kill_active = get_kill_switch()
manual_kill_toggle = st.toggle("Manual Kill Switch (block new trades)", value=manual_kill_active)
if manual_kill_toggle != manual_kill_active:
    set_kill_switch(manual_kill_toggle)
    manual_kill_active = manual_kill_toggle

if live_mode:
    st.success("LIVE MODE ENABLED — Real orders will be placed.")
else:
    st.warning("Paper Mode — No real orders will be placed.")

dhan = dhanhq(
    st.secrets["DHAN_CLIENT_ID"],
    st.secrets["DHAN_ACCESS_TOKEN"]
)

EXCHANGE_EQ = getattr(dhan, "NSE_EQ", getattr(dhan, "NSE", "NSE_EQ"))
ORDER_TYPE_STOP = getattr(dhan, "STOP_LOSS", getattr(dhan, "SL", "STOP_LOSS"))
ORDER_TYPE_SL = getattr(dhan, "SL", ORDER_TYPE_STOP)
ORDER_TYPE_SLM = getattr(dhan, "SLM", None)
TICK_SIZE = 0.05

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

    def canonical_symbol(symbol):
        return "".join(ch for ch in normalize_symbol(symbol) if ch.isalnum())

    urls = [
        "https://images.dhan.co/api-data/api-scrip-master-detailed.csv",
        "https://images.dhan.co/api-data/api-scrip-master.csv",
    ]
    errors = []
    for url in urls:
        try:
            df = pd.read_csv(url, low_memory=False)
            df.columns = df.columns.str.strip().str.upper()

            if "SEM_SEGMENT" in df.columns:
                segment = df["SEM_SEGMENT"].astype(str).str.strip().str.upper()
                filtered = df[segment == "NSE_EQ"].copy()
                if not filtered.empty:
                    df = filtered

            # Prefer cash-equity series to avoid derivatives/alternate lines with short history.
            for series_col in ["SEM_SERIES", "SERIES", "SM_SERIES"]:
                if series_col in df.columns:
                    series = df[series_col].astype(str).str.strip().str.upper()
                    filtered = df[series == "EQ"].copy()
                    if not filtered.empty:
                        df = filtered
                    break

            symbol_cols = [c for c in ["SEM_TRADING_SYMBOL", "SEM_CUSTOM_SYMBOL", "SEM_SYMBOL"] if c in df.columns]
            security_id_col = None
            for candidate in ["SEM_SMST_SECURITY_ID", "SECURITY_ID", "SECURITYID", "SMST_SECURITY_ID"]:
                if candidate in df.columns:
                    security_id_col = candidate
                    break

            if not symbol_cols or security_id_col is None:
                raise ValueError(
                    f"Required columns missing in {url}. "
                    f"Found symbols={symbol_cols}, security_id_col={security_id_col}."
                )

            mapping = {}

            def add_mapping(key, security_id):
                existing = mapping.get(key)
                if existing is None:
                    mapping[key] = [security_id]
                    return
                if isinstance(existing, list):
                    if security_id not in existing:
                        existing.append(security_id)
                    return
                if existing != security_id:
                    mapping[key] = [existing, security_id]
            for _, row in df.iterrows():
                security_id = str(row.get(security_id_col, "")).strip()
                if not security_id or security_id == "NAN":
                    continue

                for symbol_col in symbol_cols:
                    raw_symbol = str(row.get(symbol_col, "")).strip().upper()
                    if not raw_symbol or raw_symbol == "NAN":
                        continue

                    # Keep all valid mappings per key; scanner will choose the one with sufficient candles.
                    add_mapping(raw_symbol, security_id)
                    add_mapping(normalize_symbol(raw_symbol), security_id)
                    add_mapping(canonical_symbol(raw_symbol), security_id)

                    # Also ensure both base and -EQ aliases exist.
                    base = normalize_symbol(raw_symbol)
                    add_mapping(f"{base}-EQ", security_id)
                    add_mapping(canonical_symbol(base), security_id)

            if mapping:
                return mapping
            raise ValueError(f"No symbol mappings produced from {url}.")
        except Exception as exc:
            errors.append(f"{url}: {exc}")

    st.warning(f"Could not load symbol map from Dhan master CSV. Tried: {' | '.join(errors)}")
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


def _extract_order_id(order_response):
    if not isinstance(order_response, dict):
        return None
    for key in ("orderId", "order_id", "data"):
        value = order_response.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, dict):
            nested = value.get("orderId") or value.get("order_id")
            if isinstance(nested, str) and nested.strip():
                return nested.strip()
    return None


def _place_stop_order(dhan_client, security_id, quantity, stop_price):
    rounded_stop = round(float(stop_price), 2)
    if rounded_stop <= 0:
        raise ValueError(f"Invalid stop price: {stop_price}")

    attempts = []
    if ORDER_TYPE_SLM is not None:
        attempts.append(
            {
                "order_type": ORDER_TYPE_SLM,
                "price": 0,
                "trigger_price": rounded_stop,
                "label": "SLM",
            }
        )

    sl_limit = max(round(rounded_stop - TICK_SIZE, 2), TICK_SIZE)
    attempts.append(
        {
            "order_type": ORDER_TYPE_SL,
            "price": sl_limit,
            "trigger_price": rounded_stop,
            "label": "SL",
        }
    )

    last_error = None
    for attempt in attempts:
        try:
            response = dhan_client.place_order(
                security_id=security_id,
                exchange_segment=EXCHANGE_EQ,
                transaction_type=dhan_client.SELL,
                quantity=quantity,
                order_type=attempt["order_type"],
                product_type=dhan_client.CNC,
                price=attempt["price"],
                trigger_price=attempt["trigger_price"],
            )
            order_id = _extract_order_id(response)
            if order_id:
                return order_id, attempt["label"], response
            last_error = Exception(f"No order id in stop response: {response}")
        except Exception as exc:
            last_error = exc

    raise RuntimeError(str(last_error) if last_error else "Unknown stop order placement failure")

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

auto_circuit_active = drawdown >= MAX_DRAWDOWN
if auto_circuit_active:
    st.error("Auto circuit breaker active (drawdown limit breached).")
if manual_kill_active:
    st.error("Manual kill switch is ON. New trades are blocked.")
trading_blocked = auto_circuit_active or manual_kill_active

# -----------------------
# PORTFOLIO RISK SCAN
# -----------------------
st.markdown("## Portfolio Risk Scan")
if st.button("Run Portfolio Risk Scan"):
    active_trades = get_active_trades()
    if not active_trades:
        st.info("No active trades to scan.")
    else:
        risk_df = scan_portfolio_risk(dhan, active_trades)
        sell_count = int((risk_df["advice"] == "SELL").sum()) if not risk_df.empty else 0
        hold_count = int((risk_df["advice"] == "HOLD").sum()) if not risk_df.empty else 0
        st.write(f"Positions scanned: {len(risk_df)} | SELL alerts: {sell_count} | HOLD: {hold_count}")
        if sell_count > 0:
            st.error("Risk detected in one or more positions. Review SELL alerts.")
        else:
            st.success("No immediate sell alerts from current risk rules.")
        st.dataframe(risk_df, use_container_width=True)

# -----------------------
# EOD SCAN
# -----------------------
if st.button("Run EOD Scan", disabled=trading_blocked):

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
        risk_capital = BASE_CAPITAL * RISK_PER_TRADE
        selected = None

        for _, row in df.iterrows():
            price = float(row["price"])
            stop_price = float(row["stop_price"])
            stop_pct = (price - stop_price) / price if price > 0 else -1
            if stop_pct <= 0:
                continue

            position_value = risk_capital / stop_pct
            quantity = int(position_value / price) if price > 0 else 0
            if quantity <= 0:
                continue

            selected = {
                "symbol": row["symbol"],
                "security_id": row["security_id"],
                "price": price,
                "stop_price": stop_price,
                "confidence": float(row["confidence"]),
                "position_value": position_value,
                "quantity": quantity,
            }
            break

        if selected is None:
            fallback = None
            for _, row in df.iterrows():
                price = float(row["price"])
                stop_price = float(row["stop_price"])
                if price <= 0 or stop_price <= 0 or stop_price >= price:
                    continue
                if price > BASE_CAPITAL:
                    continue
                fallback = {
                    "symbol": row["symbol"],
                    "security_id": row["security_id"],
                    "price": price,
                    "stop_price": stop_price,
                    "confidence": float(row["confidence"]),
                    "position_value": price,
                    "quantity": 1,
                    "signal_strength": row.get("signal_strength", "unknown"),
                }
                break

            if fallback is None or not allow_min_qty_fallback:
                st.warning("No candidate fits current risk sizing (quantity computed as 0 for all setups).")
            else:
                selected = fallback
                per_share_risk = selected["price"] - selected["stop_price"]
                st.warning(
                    f"Using 1-share fallback for {selected['symbol']} (signal: {selected['signal_strength']}). "
                    f"Per-share risk ₹{round(per_share_risk, 2)} exceeds risk budget ₹{round(risk_capital, 2)}."
                )

        if selected is not None:
            symbol = selected["symbol"]
            security_id = selected["security_id"]
            price = selected["price"]
            stop_price = selected["stop_price"]
            confidence = selected["confidence"]
            position_value = selected["position_value"]
            quantity = selected["quantity"]

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
                    stop_id, stop_type, _ = _place_stop_order(
                        dhan_client=dhan,
                        security_id=security_id,
                        quantity=quantity,
                        stop_price=stop_price,
                    )
                    st.info(f"Stop-loss placed ({stop_type}) for {symbol}. Order ID: {stop_id}")
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

trades = get_all_trades()

if trades:
    df_trades = pd.DataFrame(trades, columns=get_trade_columns())
    st.dataframe(df_trades)
else:
    st.write("No trades yet.")
