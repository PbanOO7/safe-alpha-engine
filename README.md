# Safe Alpha Engine

`Safe Alpha Engine` is a Streamlit-based end-of-day (EOD) equity scanner and execution assistant for Dhan.

It scans a curated NSE universe, scores setups using trend/momentum/volume/pattern signals, applies risk controls, and supports paper or live order placement.

## Features

- EOD scan with scoring model (trend, breakout, ATR compression, volume, bullish engulfing)
- Market regime filter using NIFTY vs EMA200
- Trade sizing based on fixed risk per trade
- Live or paper mode
- Manual kill switch (persistent) + automatic drawdown circuit breaker
- Trade journal persisted in SQLite
- Built-in scan diagnostics (`selected`, `skipped`, `error` + reason codes)
- Dhan SDK compatibility handling across method/constant variants

## Strategy Summary

Each symbol is evaluated with:

- Trend alignment: `price > EMA20 > EMA50 > EMA200` (+25)
- Breakout: close above prior 20-day high (+20)
- ATR compression: `ATR / price < 0.03` (+15)
- Volume spike: volume > `1.5 * 20-day average volume` (+10)
- Bullish engulfing pattern (+10)
- Market regime bonus: NIFTY above EMA200 (+20)

Candidate threshold: `score >= 70`.

## Risk Controls

- `BASE_CAPITAL = 10000`
- `RISK_PER_TRADE = 0.01` (1%)
- `MAX_DRAWDOWN = 0.08` (8%)
- Auto circuit breaker blocks new scans when drawdown breaches threshold
- Manual kill switch blocks new scans regardless of drawdown
- Optional 1-share fallback when normal risk sizing computes `quantity = 0`

## Project Structure

- `app.py`: Streamlit UI, scan trigger, sizing, order placement, kill switch, journal
- `scanner.py`: market data fetch + signal engine + diagnostics
- `database.py`: SQLite schema and persistence helpers
- `requirements.txt`: Python dependencies

## Setup

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Add Streamlit secrets in `.streamlit/secrets.toml`:

```toml
DHAN_CLIENT_ID = "your_client_id"
DHAN_ACCESS_TOKEN = "your_access_token"
```

4. Run the app:

```bash
streamlit run app.py
```

## Streamlit Cloud

For Streamlit Community Cloud deployment, ensure:

- Repository points to `app.py` as the main module
- Secrets are configured in app settings:
  - `DHAN_CLIENT_ID`
  - `DHAN_ACCESS_TOKEN`

## Diagnostics

After each scan, the app shows a diagnostics table with per-symbol outcomes:

- `status`: `selected` / `skipped` / `error`
- `reason`: examples include:
  - `candidate_found`
  - `setup_conditions_not_met`
  - `missing_security_id`
  - `insufficient_candles`
  - `historical_data_failed`
  - `invalid_stop`

This is useful for identifying whether issues come from data/API, mapping, or strategy filters.

## Notes

- The app currently stores data in local SQLite (`trades.db`).
- This is a tooling/automation project and not investment advice.
