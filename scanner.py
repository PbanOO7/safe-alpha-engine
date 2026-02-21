import yfinance as yf
import pandas as pd
import ta

def scan_stock(symbol):
    data = yf.download(symbol, period="3mo", interval="1d", auto_adjust=True)

    if data is None or len(data) < 50:
        return None

    # Flatten multi-index columns if present
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    # Ensure columns are 1D Series
    data["Close"] = data["Close"].astype(float)
    data["Open"] = data["Open"].astype(float)
    data["Volume"] = data["Volume"].astype(float)

    # Indicators
    data["EMA20"] = ta.trend.ema_indicator(data["Close"], window=20)
    data["EMA50"] = ta.trend.ema_indicator(data["Close"], window=50)
    data["RSI"] = ta.momentum.rsi(data["Close"], window=14)

    latest = data.iloc[-1]

    confidence = 0

    # Trend alignment
    if latest["Close"] > latest["EMA20"] > latest["EMA50"]:
        confidence += 30

    # RSI momentum
    if 50 < latest["RSI"] < 70:
        confidence += 15

    # Bullish candle
    if latest["Close"] > latest["Open"]:
        confidence += 15

    # Volume expansion
    if latest["Volume"] > data["Volume"].rolling(20).mean().iloc[-1]:
        confidence += 12

    return {
        "symbol": symbol,
        "price": round(float(latest["Close"]), 2),
        "confidence": confidence
    }