from datetime import datetime
import pandas as pd

HISTORY_START = "2023-01-01"
MIN_CANDLES = 200
SCORE_THRESHOLD = 70

UNIVERSE = [
    "RELIANCE",
    "TCS",
    "HDFCBANK",
    "INFY",
    "ICICIBANK",
    "SBIN",
    "ITC",
    "LT",
    "HCLTECH",
    "ONGC",
    "NTPC",
    "TATAMOTORS",
]


def fetch_daily_history(dhan_client, security_id, from_date, to_date):
    """Compatibility wrapper across dhanhq versions."""
    exchange_eq = getattr(dhan_client, "NSE_EQ", getattr(dhan_client, "NSE", "NSE_EQ"))
    instrument_equity = getattr(dhan_client, "EQUITY", "EQUITY")

    if hasattr(dhan_client, "historical_data"):
        return dhan_client.historical_data(
            security_id=str(security_id),
            exchange_segment=exchange_eq,
            instrument=instrument_equity,
            interval=dhan_client.DAY,
            from_date=from_date,
            to_date=to_date,
        )

    if hasattr(dhan_client, "historical_daily_data"):
        return dhan_client.historical_daily_data(
            security_id=str(security_id),
            exchange_segment=exchange_eq,
            instrument_type=instrument_equity,
            from_date=from_date,
            to_date=to_date,
        )

    raise AttributeError("No compatible historical daily data method found on dhanhq client.")


def _to_candle_df(raw):
    """Normalize common Dhan historical_data response shapes into one DataFrame."""
    if not isinstance(raw, dict):
        return pd.DataFrame()

    payload = raw.get("data", raw)
    if not isinstance(payload, dict):
        return pd.DataFrame()

    # Shape A: {"candles": [[ts, o, h, l, c, v], ...]}
    candles = payload.get("candles")
    if candles:
        cols = ["timestamp", "open", "high", "low", "close", "volume"]
        df = pd.DataFrame(candles, columns=cols)
    else:
        # Shape B: {"timestamp":[...], "open":[...], "high":[...], ...}
        ts = payload.get("timestamp") or payload.get("start_Time") or payload.get("startTime") or []
        opens = payload.get("open", [])
        highs = payload.get("high", [])
        lows = payload.get("low", [])
        closes = payload.get("close", [])
        volumes = payload.get("volume", [])
        n = min(len(ts), len(opens), len(highs), len(lows), len(closes), len(volumes))
        if n == 0:
            return pd.DataFrame()
        df = pd.DataFrame(
            {
                "timestamp": ts[:n],
                "open": opens[:n],
                "high": highs[:n],
                "low": lows[:n],
                "close": closes[:n],
                "volume": volumes[:n],
            }
        )

    if df.empty:
        return df

    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["high", "low", "close"]).reset_index(drop=True)
    return df


def calculate_atr(df, period=14):
    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift()).abs()
    low_close = (df["low"] - df["close"].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def is_bullish_engulfing(df):
    if len(df) < 2:
        return False
    prev = df.iloc[-2]
    curr = df.iloc[-1]
    return (
        curr["close"] > curr["open"]
        and prev["close"] < prev["open"]
        and curr["close"] > prev["open"]
        and curr["open"] < prev["close"]
    )


def resolve_security_id(symbol_map, symbol):
    def canonical_symbol(value):
        text = str(value).strip().upper()
        if text.endswith("-EQ"):
            text = text[:-3]
        return "".join(ch for ch in text if ch.isalnum())

    candidates = [
        symbol,
        str(symbol).upper(),
        f"{str(symbol).upper()}-EQ",
        canonical_symbol(symbol),
    ]
    for key in candidates:
        sec = symbol_map.get(key)
        if sec:
            return sec
    return None


def resolve_security_ids(symbol_map, symbol):
    def canonical_symbol(value):
        text = str(value).strip().upper()
        if text.endswith("-EQ"):
            text = text[:-3]
        return "".join(ch for ch in text if ch.isalnum())

    keys = [
        symbol,
        str(symbol).upper(),
        f"{str(symbol).upper()}-EQ",
        canonical_symbol(symbol),
    ]
    ids = []
    for key in keys:
        sec = symbol_map.get(key)
        if not sec:
            continue
        if isinstance(sec, list):
            for item in sec:
                value = str(item).strip()
                if value and value not in ids:
                    ids.append(value)
        else:
            value = str(sec).strip()
            if value and value not in ids:
                ids.append(value)
    return ids


def scan(dhan, symbol_map):
    candidates = []
    diagnostics = []

    def log(symbol, status, reason, security_id=None, **extra):
        row = {"symbol": symbol, "status": status, "reason": reason, "security_id": security_id}
        row.update(extra)
        diagnostics.append(row)

    to_date = datetime.now().strftime("%Y-%m-%d")
    from_date = HISTORY_START

    # ---------------------------
    # MARKET REGIME CHECK
    # ---------------------------
    regime_score = 0
    nifty_id = None
    for idx_name in ["NIFTY", "NIFTY50", "NIFTY 50"]:
        nifty_id = resolve_security_id(symbol_map, idx_name)
        if nifty_id:
            break

    if nifty_id:
        try:
            raw_nifty = fetch_daily_history(
                dhan_client=dhan,
                security_id=nifty_id,
                from_date=from_date,
                to_date=to_date,
            )
            nifty_df = _to_candle_df(raw_nifty)
            if len(nifty_df) >= 200:
                nifty_df["EMA200"] = nifty_df["close"].ewm(span=200, adjust=False).mean()
                if nifty_df.iloc[-1]["close"] > nifty_df.iloc[-1]["EMA200"]:
                    regime_score = 20
        except Exception as exc:
            log("NIFTY", "error", "regime_fetch_failed", message=str(exc))
    else:
        log("NIFTY", "skipped", "regime_symbol_missing")

    for symbol in UNIVERSE:
        security_ids = resolve_security_ids(symbol_map, symbol)
        if not security_ids:
            log(symbol, "skipped", "missing_security_id")
            continue

        df = pd.DataFrame()
        security_id = None
        best_short_df = pd.DataFrame()
        best_short_id = None
        last_exc = None

        for candidate_id in security_ids:
            try:
                raw = fetch_daily_history(
                    dhan_client=dhan,
                    security_id=candidate_id,
                    from_date=from_date,
                    to_date=to_date,
                )
                candidate_df = _to_candle_df(raw)
            except Exception as exc:
                last_exc = exc
                continue

            if len(candidate_df) >= MIN_CANDLES:
                security_id = str(candidate_id)
                df = candidate_df
                break

            if len(candidate_df) > len(best_short_df):
                best_short_df = candidate_df
                best_short_id = str(candidate_id)

        if df.empty:
            if not best_short_df.empty:
                log(
                    symbol,
                    "skipped",
                    "insufficient_candles",
                    security_id=str(best_short_id),
                    candles=int(len(best_short_df)),
                    candidate_ids=",".join(security_ids),
                )
            else:
                log(
                    symbol,
                    "error",
                    "historical_data_failed",
                    security_id=",".join(security_ids),
                    message=str(last_exc) if last_exc else "no_data_returned",
                )
            continue

        df["EMA20"] = df["close"].ewm(span=20, adjust=False).mean()
        df["EMA50"] = df["close"].ewm(span=50, adjust=False).mean()
        df["EMA200"] = df["close"].ewm(span=200, adjust=False).mean()
        df["ATR"] = calculate_atr(df)
        df["VOL_AVG"] = df["volume"].rolling(20).mean()
        df["HIGH20_PREV"] = df["high"].shift(1).rolling(20).max()
        df["SWING_LOW10"] = df["low"].rolling(10).min()

        latest = df.iloc[-1]
        price = float(latest["close"])
        ema20 = float(latest["EMA20"]) if pd.notna(latest["EMA20"]) else None
        ema50 = float(latest["EMA50"]) if pd.notna(latest["EMA50"]) else None
        ema200 = float(latest["EMA200"]) if pd.notna(latest["EMA200"]) else None
        atr = float(latest["ATR"]) if pd.notna(latest["ATR"]) else None
        vol_avg = float(latest["VOL_AVG"]) if pd.notna(latest["VOL_AVG"]) else None
        high20_prev = float(latest["HIGH20_PREV"]) if pd.notna(latest["HIGH20_PREV"]) else None
        swing_low = float(latest["SWING_LOW10"]) if pd.notna(latest["SWING_LOW10"]) else None
        volume = float(latest["volume"])

        if None in (ema20, ema50, ema200, atr, vol_avg, high20_prev, swing_low):
            log(symbol, "skipped", "indicator_nan", security_id=str(security_id))
            continue

        score = regime_score

        trend_ok = price > ema20 > ema50 > ema200
        breakout_ok = price > high20_prev
        atr_ok = (atr / price) < 0.03 if price > 0 else False
        volume_ok = volume > (1.5 * vol_avg) if vol_avg > 0 else False
        pattern_ok = is_bullish_engulfing(df)

        if trend_ok:
            score += 25
        if breakout_ok:
            score += 20
        if atr_ok:
            score += 15
        if volume_ok:
            score += 10
        if pattern_ok:
            score += 10

        if score < SCORE_THRESHOLD:
            log(
                symbol,
                "skipped",
                "setup_conditions_not_met",
                security_id=str(security_id),
                score=int(score),
                trend_ok=bool(trend_ok),
                breakout_ok=bool(breakout_ok),
                atr_ok=bool(atr_ok),
                volume_ok=bool(volume_ok),
                pattern_ok=bool(pattern_ok),
            )
            continue

        stop_price = min(swing_low, price - (atr * 1.5))
        if stop_price <= 0 or stop_price >= price:
            log(
                symbol,
                "skipped",
                "invalid_stop",
                security_id=str(security_id),
                stop_price=float(stop_price),
                close=float(price),
            )
            continue

        candidate = {
            "symbol": symbol,
            "security_id": str(security_id),
            "price": round(price, 2),
            "stop_price": round(float(stop_price), 2),
            "confidence": int(score),
            "signal_strength": "strict" if score >= 85 else "relaxed",
        }
        candidates.append(candidate)
        log(
            symbol,
            "selected",
            "candidate_found",
            security_id=str(security_id),
            confidence=int(candidate["confidence"]),
            signal_strength=candidate["signal_strength"],
        )

    if not candidates:
        df_candidates = pd.DataFrame(
            columns=["symbol", "security_id", "price", "stop_price", "confidence", "signal_strength"]
        )
    else:
        df_candidates = pd.DataFrame(candidates).sort_values("confidence", ascending=False).reset_index(drop=True)

    df_diagnostics = pd.DataFrame(diagnostics)
    return df_candidates, df_diagnostics


def scan_portfolio_risk(dhan, active_trades):
    """Scan active positions and return SELL/HOLD advisory with reasons."""
    rows = []
    to_date = datetime.now().strftime("%Y-%m-%d")
    from_date = HISTORY_START

    for trade in active_trades:
        # Table order: id, symbol, security_id, entry_price, stop_price, position_size, ...
        symbol = str(trade[1])
        security_id = str(trade[2])
        entry_price = float(trade[3]) if trade[3] is not None else 0.0
        stop_price = float(trade[4]) if trade[4] is not None else 0.0

        try:
            raw = fetch_daily_history(
                dhan_client=dhan,
                security_id=security_id,
                from_date=from_date,
                to_date=to_date,
            )
            df = _to_candle_df(raw)
        except Exception as exc:
            rows.append(
                {
                    "symbol": symbol,
                    "security_id": security_id,
                    "entry_price": round(entry_price, 2),
                    "current_price": None,
                    "stop_price": round(stop_price, 2),
                    "pnl_pct": None,
                    "advice": "SELL",
                    "reason": f"data_fetch_error: {exc}",
                }
            )
            continue

        if len(df) < 60:
            rows.append(
                {
                    "symbol": symbol,
                    "security_id": security_id,
                    "entry_price": round(entry_price, 2),
                    "current_price": None,
                    "stop_price": round(stop_price, 2),
                    "pnl_pct": None,
                    "advice": "SELL",
                    "reason": "insufficient_candles_for_risk_scan",
                }
            )
            continue

        df["EMA20"] = df["close"].ewm(span=20, adjust=False).mean()
        df["EMA50"] = df["close"].ewm(span=50, adjust=False).mean()
        latest = df.iloc[-1]

        current_price = float(latest["close"])
        ema20 = float(latest["EMA20"]) if pd.notna(latest["EMA20"]) else None
        ema50 = float(latest["EMA50"]) if pd.notna(latest["EMA50"]) else None
        pnl_pct = ((current_price - entry_price) / entry_price * 100) if entry_price > 0 else None

        advice = "HOLD"
        reason = "trend_intact"

        if stop_price > 0 and current_price <= stop_price:
            advice = "SELL"
            reason = "stop_loss_breached"
        elif ema50 is not None and current_price < ema50:
            advice = "SELL"
            reason = "close_below_ema50"
        elif ema20 is not None and current_price < ema20 and pnl_pct is not None and pnl_pct < 0:
            advice = "SELL"
            reason = "close_below_ema20_with_negative_pnl"

        rows.append(
            {
                "symbol": symbol,
                "security_id": security_id,
                "entry_price": round(entry_price, 2),
                "current_price": round(current_price, 2),
                "stop_price": round(stop_price, 2),
                "pnl_pct": round(pnl_pct, 2) if pnl_pct is not None else None,
                "advice": advice,
                "reason": reason,
            }
        )

    if not rows:
        return pd.DataFrame(
            columns=["symbol", "security_id", "entry_price", "current_price", "stop_price", "pnl_pct", "advice", "reason"]
        )

    df_risk = pd.DataFrame(rows)
    advice_rank = {"SELL": 0, "HOLD": 1}
    df_risk["advice_rank"] = df_risk["advice"].map(advice_rank).fillna(9)
    df_risk = df_risk.sort_values(["advice_rank", "pnl_pct"], na_position="last").drop(columns=["advice_rank"])
    return df_risk.reset_index(drop=True)
