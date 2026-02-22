import pandas as pd
from datetime import datetime


def scan(dhan, symbol_map):

    # Sample large liquid stocks
    stocks = [
        "RELIANCE", "TCS", "HDFCBANK", "INFY",
        "ICICIBANK", "SBIN", "ITC", "LT",
        "HCLTECH", "ONGC", "NTPC", "TATAMOTORS"
    ]

    results = []

    for symbol in stocks:

        if symbol not in symbol_map:
            continue

        security_id = symbol_map[symbol]

        try:
            data = dhan.historical_data(
                security_id=security_id,
                exchange_segment=dhan.NSE_EQ,
                instrument=dhan.EQUITY,
                interval=dhan.DAY,
                from_date="2023-01-01",
                to_date=datetime.now().strftime("%Y-%m-%d")
            )

            if not data or "data" not in data:
                continue

            df = pd.DataFrame(data["data"])

            if df.empty or len(df) < 30:
                continue

            latest = df.iloc[-1]

            price = float(latest["close"])

            # 🔹 TEMP STOP: fixed 5% stop
            stop_price = price * 0.95

            # 🔹 TEMP CONFIDENCE: fixed score so it always qualifies
            confidence = 75

            results.append({
                "symbol": symbol,
                "security_id": security_id,
                "price": price,
                "stop_price": stop_price,
                "confidence": confidence
            })

        except Exception:
            continue

    if not results:
        return pd.DataFrame()

    df_results = pd.DataFrame(results)
    df_results = df_results.sort_values("confidence", ascending=False)

    return df_results