import yfinance as yf
import pandas as pd
import ta


# -------------------------------------------------
# MARKET REGIME CHECK (NIFTY 200 EMA)
# -------------------------------------------------

def market_is_bullish():
    try:
        data = yf.download("^NSEI", period="1y", interval="1d",
                           auto_adjust=True, progress=False)

        if data is None or len(data) < 200:
            return False

        data["EMA200"] = ta.trend.ema_indicator(data["Close"], window=200)

        latest = data.iloc[-1]

        return float(latest["Close"]) > float(latest["EMA200"])

    except Exception:
        return False


# -------------------------------------------------
# NIFTY 50 SCANNER (Batch + Safe)
# -------------------------------------------------

def scan_nifty50():

    nifty50 = [
        "RELIANCE.NS","TCS.NS","HDFCBANK.NS","INFY.NS",
        "ICICIBANK.NS","SBIN.NS","ITC.NS","LT.NS",
        "HINDUNILVR.NS","BHARTIARTL.NS","KOTAKBANK.NS",
        "BAJFINANCE.NS","ASIANPAINT.NS","MARUTI.NS",
        "AXISBANK.NS","HCLTECH.NS","SUNPHARMA.NS",
        "ULTRACEMCO.NS","TITAN.NS","ONGC.NS",
        "NTPC.NS","TATAMOTORS.NS","POWERGRID.NS",
        "ADANIENT.NS","COALINDIA.NS"
    ]

    try:
        data = yf.download(
            nifty50,
            period="6mo",
            group_by="ticker",
            auto_adjust=True,
            progress=False
        )
    except Exception:
        return pd.DataFrame()

    results = []

    # Handle case where only 1 ticker returned
    if isinstance(data.columns, pd.MultiIndex) is False:
        return pd.DataFrame()

    available_symbols = data.columns.get_level_values(0).unique()

    for symbol in nifty50:

        if symbol not in available_symbols:
            continue

        df = data[symbol].copy()

        if df.empty or len(df) < 50:
            continue

        try:
            df["EMA20"] = ta.trend.ema_indicator(df["Close"], window=20)
            df["EMA50"] = ta.trend.ema_indicator(df["Close"], window=50)
        except Exception:
            continue

        latest = df.iloc[-1]

        price = float(latest["Close"])
        ema20 = float(latest["EMA20"])
        ema50 = float(latest["EMA50"])

        confidence = 50

        if price > ema20:
            confidence += 10
        if ema20 > ema50:
            confidence += 10
        if price > ema50:
            confidence += 5

        # Basic structural stop (4%)
        stop_pct = 4
        stop_price = price * (1 - stop_pct / 100)

        # Position sizing (1% risk model)
        risk_capital = 10000 * 0.01
        position_size = risk_capital / (stop_pct / 100)

        results.append({
            "symbol": symbol,
            "price": round(price, 2),
            "confidence": confidence,
            "stop_price": round(stop_price, 2),
            "stop_pct": stop_pct,
            "position_size": round(position_size, 2)
        })

    if len(results) == 0:
        return pd.DataFrame()

    return pd.DataFrame(results).sort_values("confidence", ascending=False)