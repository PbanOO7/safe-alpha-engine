from datetime import datetime, timedelta
import pandas as pd

MIN_CANDLES = 30
BREAKOUT_LOOKBACK = 20
STOP_LOOKBACK = 5

# A compact, liquid NSE universe to keep API calls practical for EOD scans.
UNIVERSE = [
    "RELIANCE",
    "TCS",
    "INFY",
    "HDFCBANK",
    "ICICIBANK",
    "SBIN",
    "ITC",
    "LT",
    "BHARTIARTL",
    "KOTAKBANK",
]


def fetch_daily_history(dhan_client, security_id, from_date, to_date):
    """Compatibility wrapper across dhanhq versions."""
    if hasattr(dhan_client, "historical_data"):
        return dhan_client.historical_data(
            security_id=str(security_id),
            exchange_segment=dhan_client.NSE_EQ,
            instrument=dhan_client.EQUITY,
            interval=dhan_client.DAY,
            from_date=from_date,
            to_date=to_date,
        )

    if hasattr(dhan_client, "historical_daily_data"):
        return dhan_client.historical_daily_data(
            security_id=str(security_id),
            exchange_segment=dhan_client.NSE_EQ,
            instrument_type=dhan_client.EQUITY,
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


def _confidence_score(price, prev_high, volume, avg_volume):
    breakout_strength = max(0.0, (price - prev_high) / prev_high) if prev_high > 0 else 0.0
    volume_boost = max(0.0, (volume / avg_volume) - 1.0) if avg_volume > 0 else 0.0
    score = (breakout_strength * 1000) + (volume_boost * 30)
    return round(min(99.0, max(1.0, score)), 2)


def scan(dhan, symbol_map):
    candidates = []
    diagnostics = []

    def log(symbol, status, reason, **extra):
        row = {"symbol": symbol, "status": status, "reason": reason}
        row.update(extra)
        diagnostics.append(row)

    to_date = datetime.now().strftime("%Y-%m-%d")
    from_date = (datetime.now() - timedelta(days=120)).strftime("%Y-%m-%d")

    for symbol in UNIVERSE:
        security_id = symbol_map.get(symbol)
        if not security_id:
            log(symbol, "skipped", "missing_security_id")
            continue

        try:
            raw = fetch_daily_history(
                dhan_client=dhan,
                security_id=security_id,
                from_date=from_date,
                to_date=to_date,
            )
        except Exception as exc:
            log(symbol, "error", "historical_data_failed", message=str(exc))
            continue

        df = _to_candle_df(raw)
        if len(df) < MIN_CANDLES:
            log(symbol, "skipped", "insufficient_candles", candles=int(len(df)))
            continue

        latest = df.iloc[-1]
        previous = df.iloc[:-1]
        prev_high = previous["high"].tail(BREAKOUT_LOOKBACK).max()
        avg_volume = previous["volume"].tail(BREAKOUT_LOOKBACK).mean()

        is_breakout = latest["close"] > prev_high
        has_volume = latest["volume"] > (avg_volume * 1.2 if avg_volume > 0 else 0)
        if not (is_breakout and has_volume):
            log(
                symbol,
                "skipped",
                "setup_conditions_not_met",
                breakout=bool(is_breakout),
                volume_confirmed=bool(has_volume),
            )
            continue

        stop_price = previous["low"].tail(STOP_LOOKBACK).min()
        if stop_price <= 0 or stop_price >= latest["close"]:
            log(symbol, "skipped", "invalid_stop", stop_price=float(stop_price), close=float(latest["close"]))
            continue

        candidate = {
            "symbol": symbol,
            "security_id": str(security_id),
            "price": round(float(latest["close"]), 2),
            "stop_price": round(float(stop_price), 2),
            "confidence": _confidence_score(
                float(latest["close"]),
                float(prev_high),
                float(latest["volume"]),
                float(avg_volume) if pd.notna(avg_volume) else 0.0,
            ),
        }
        candidates.append(candidate)
        log(symbol, "selected", "candidate_found", confidence=float(candidate["confidence"]))

    if not candidates:
        df_candidates = pd.DataFrame(columns=["symbol", "security_id", "price", "stop_price", "confidence"])
    else:
        df_candidates = pd.DataFrame(candidates).sort_values("confidence", ascending=False).reset_index(drop=True)

    df_diagnostics = pd.DataFrame(diagnostics)
    return df_candidates, df_diagnostics
