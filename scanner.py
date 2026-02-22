import pandas as pd
from datetime import datetime


def scan(dhan, symbol_map):

    symbol = "RELIANCE"

    if symbol not in symbol_map:
        print("❌ RELIANCE not found in symbol_map")
        return pd.DataFrame()

    security_id = symbol_map[symbol]
    print("✅ Security ID:", security_id)

    try:
        data = dhan.historical_data(
            security_id=security_id,
            exchange_segment=dhan.NSE_EQ,
            instrument=dhan.EQUITY,
            interval=dhan.DAY,
            from_date="2023-01-01",
            to_date=datetime.now().strftime("%Y-%m-%d")
        )

        print("📦 RAW API RESPONSE:")
        print(data)

    except Exception as e:
        print("❌ API ERROR:", str(e))

    return pd.DataFrame()