import yfinance as yf
import pandas as pd
import ta

def scan_stock(symbol):
    data = yf.download(symbol, period="3mo", interval="1d")
    
    if len(data) < 50:
        return None
    
    data["EMA20"] = ta.trend.ema_indicator(data["Close"], window=20)
    data["EMA50"] = ta.trend.ema_indicator(data["Close"], window=50)
    data["RSI"] = ta.momentum.rsi(data["Close"], window=14)
    
    latest = data.iloc[-1]
    prev = data.iloc[-2]
    
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
        "price": round(latest["Close"], 2),
        "confidence": confidence
    }