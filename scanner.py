import yfinance as yf
import pandas as pd
import ta

CAPITAL = 10000
RISK_PER_TRADE = 0.01  # 1%
MAX_STOP_CAP = 0.10    # 10%

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
        data["ATR"] = ta.volatility.average_true_range(
            data["High"], data["Low"], data["Close"], window=14
        )

        latest = data.iloc[-1]
        confidence = 0

        # Trend alignment
        if latest["Close"] > latest["EMA200"]:
            confidence += 25

        if latest["Close"] > latest["EMA20"] > latest["EMA50"]:
            confidence += 20

        # Volume
        if latest["Volume"] > data["Volume"].rolling(20).mean().iloc[-1]:
            confidence += 15

        # RSI
        if 50 < latest["RSI"] < 70:
            confidence += 10

        # Bullish candle
        if latest["Close"] > latest["Open"]:
            confidence += 10

        # Breakout condition
        if latest["Close"] >= data["Close"].rolling(20).max().iloc[-1]:
            confidence += 20

        # -------------------
        # STOP CALCULATION
        # -------------------

        entry_price = float(latest["Close"])

        # ATR stop
        atr_stop = entry_price - (2 * latest["ATR"])
        atr_stop_pct = (entry_price - atr_stop) / entry_price

        # Structure stop (recent swing low)
        recent_low = data["Low"].rolling(20).min().iloc[-1]
        structure_stop_pct = (entry_price - recent_low) / entry_price

        # Choose tighter of the two
        stop_pct = min(atr_stop_pct, structure_stop_pct)

        # Cap at 10%
        stop_pct = min(stop_pct, MAX_STOP_CAP)

        stop_price = entry_price * (1 - stop_pct)

        # Position sizing
        risk_amount = CAPITAL * RISK_PER_TRADE
        position_size = risk_amount / stop_pct

        return {
            "symbol": symbol,
            "price": round(entry_price, 2),
            "confidence": round(confidence, 1),
            "stop_price": round(stop_price, 2),
            "stop_pct": round(stop_pct * 100, 2),
            "position_size": round(position_size, 0)
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

def market_is_bullish():
    import yfinance as yf
    import pandas as pd
    import ta

    data = yf.download("^NSEI", period="1y", interval="1d", auto_adjust=True)

    if data is None or len(data) < 200:
        return False

    # Flatten multi-index if present
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    data["Close"] = data["Close"].astype(float)

    data["EMA200"] = ta.trend.ema_indicator(data["Close"], window=200)

    latest = data.iloc[-1]

    return float(latest["Close"]) > float(latest["EMA200"])