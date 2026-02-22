import pandas as pd
from datetime import datetime

def calculate_atr(df, period=14):
    high_low = df["high"] - df["low"]
    high_close = abs(df["high"] - df["close"].shift())
    low_close = abs(df["low"] - df["close"].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def detect_pattern(df):
    latest = df.iloc[-1]
    prev = df.iloc[-2]

    body = abs(latest["close"] - latest["open"])
    candle_range = latest["high"] - latest["low"]

    if body < candle_range * 0.1:
        return "DOJI"

    if (prev["close"] < prev["open"] and
        latest["close"] > latest["open"] and
        latest["close"] > prev["open"] and
        latest["open"] < prev["close"]):
        return "BULLISH_ENGULFING"

    return "NONE"


def scan(dhan, symbol_map):

    stocks = ["RELIANCE","TCS","HDFCBANK","INFY",
              "ICICIBANK","SBIN","ITC","LT",
              "HCLTECH","ONGC","NTPC","TATAMOTORS"]

    results = []

    for symbol in stocks:

        if symbol not in symbol_map:
            continue

        security_id = symbol_map[symbol]

        data = dhan.historical_data(
            security_id=security_id,
            exchange_segment=dhan.NSE_EQ,
            instrument=dhan.EQUITY,
            interval=dhan.DAY,
            from_date="2023-01-01",
            to_date=datetime.now().strftime("%Y-%m-%d")
        )

        df = pd.DataFrame(data["data"])

        if df.empty or len(df) < 60:
            continue

        df["EMA20"] = df["close"].ewm(span=20).mean()
        df["EMA50"] = df["close"].ewm(span=50).mean()
        df["ATR"] = calculate_atr(df)

        pattern = detect_pattern(df)

        latest = df.iloc[-1]

        price = latest["close"]
        ema20 = latest["EMA20"]
        ema50 = latest["EMA50"]
        atr = latest["ATR"]

        score = 90

        if price > ema20:
            score += 20
        if ema20 > ema50:
            score += 20
      #  if atr / price < 0.03:
       #     score += 20
        # if pattern == "BULLISH_ENGULFING":
          #  score += 40

        stop_price = price - (atr * 1.5)

        results.append({
            "symbol": symbol,
            "security_id": security_id,
            "price": float(price),
            "stop_price": float(stop_price),
            "confidence": int(score)   # <- THIS IS CRITICAL
        })

    if not results:
        return pd.DataFrame()

    df_results = pd.DataFrame(results)

    # Ensure confidence exists before sorting
    if "confidence" in df_results.columns:
        df_results = df_results.sort_values("confidence", ascending=False)

    return df_results