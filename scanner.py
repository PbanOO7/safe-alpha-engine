import yfinance as yf
import pandas as pd
import ta

# NIFTY 50 Symbols (Yahoo format)
NIFTY50 = [
    "RELIANCE.NS","TCS.NS","INFY.NS","HDFCBANK.NS","ICICIBANK.NS",
    "HINDUNILVR.NS","ITC.NS","SBIN.NS","BHARTIARTL.NS","LT.NS",
    "KOTAKBANK.NS","AXISBANK.NS","BAJFINANCE.NS","ASIANPAINT.NS",
    "MARUTI.NS","TITAN.NS","SUNPHARMA.NS","ULTRACEMCO.NS",
    "HCLTECH.NS","POWERGRID.NS","NTPC.NS","TECHM.NS","M&M.NS",
    "TATAMOTORS.NS","WIPRO.NS","NESTLEIND.NS","JSWSTEEL.NS",
    "GRASIM.NS","ADANIPORTS.NS","COALINDIA.NS","DRREDDY.NS",
    "BAJAJFINSV.NS","CIPLA.NS","HEROMOTOCO.NS","EICHERMOT.NS",
    "HINDALCO.NS","BRITANNIA.NS","INDUSINDBK.NS","TATASTEEL.NS",
    "UPL.NS","BPCL.NS","ONGC.NS","SHREECEM.NS","DIVISLAB.NS",
    "APOLLOHOSP.NS","SBILIFE.NS","HDFCLIFE.NS","BAJAJ-AUTO.NS",
    "ADANIENT.NS","PIDILITIND.NS"
]

def score_stock(symbol):
    try:
        data = yf.download(symbol, period="6mo", interval="1d", auto_adjust=True)
        if data is None or len(data) < 100:
            return None

        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)

        data["EMA20"] = ta.trend.ema_indicator(data["Close"], window=20)
        data["EMA50"] = ta.trend.ema_indicator(data["Close"], window=50)
        data["EMA200"] = ta.trend.ema_indicator(data["Close"], window=200)
        data["RSI"] = ta.momentum.rsi(data["Close"], window=14)

        latest = data.iloc[-1]
        confidence = 0

        # Weekly trend proxy (200 EMA)
        if latest["Close"] > latest["EMA200"]:
            confidence += 25

        # Daily trend structure
        if latest["Close"] > latest["EMA20"] > latest["EMA50"]:
            confidence += 20

        # Volume expansion
        if latest["Volume"] > data["Volume"].rolling(20).mean().iloc[-1]:
            confidence += 15

        # RSI healthy
        if 50 < latest["RSI"] < 70:
            confidence += 10

        # Bullish candle
        if latest["Close"] > latest["Open"]:
            confidence += 10

        # Simple breakout condition
        if latest["Close"] == data["Close"].rolling(20).max().iloc[-1]:
            confidence += 20

        return {
            "symbol": symbol,
            "price": round(float(latest["Close"]),2),
            "confidence": confidence
        }

    except:
        return None


def scan_nifty50():
    results = []
    for symbol in NIFTY50:
        result = score_stock(symbol)
        if result:
            results.append(result)

    df = pd.DataFrame(results)
    df = df.sort_values(by="confidence", ascending=False)
    return df