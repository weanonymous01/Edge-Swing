"""
Alpha Vantage fallback — used when yfinance (primary) is unavailable or fails.
Fetches daily OHLCV and computes RSI, SMA 50, SMA 200 locally.
Free tier: 25 requests/day, 5/min.
"""

import requests
import time
import ta
import pandas as pd
from config import ALPHA_VANTAGE_API_KEY, RSI_PERIOD, SMA_SHORT, SMA_LONG, AVG_VOLUME_PERIOD

BASE_URL = "https://www.alphavantage.co/query"
TIMEOUT = 20  # seconds
_RATE_DELAY = 12.0  # seconds between calls (5 calls/min limit)
_last_call_time = 0.0
_api_exhausted = False  # set True if daily limit hit


def _rate_limit():
    """Enforce rate limiting for free tier (5 calls/min)."""
    global _last_call_time
    now = time.time()
    elapsed = now - _last_call_time
    if elapsed < _RATE_DELAY and _last_call_time > 0:
        time.sleep(_RATE_DELAY - elapsed)
    _last_call_time = time.time()


def fetch_etf_data(symbol: str) -> dict | None:
    """
    Fetch daily time series from Alpha Vantage (1 API call) and compute
    RSI, SMA50, SMA200 locally using the `ta` library.
    Returns the same dict shape as yfinance module, or None on failure.
    """
    global _api_exhausted

    if not ALPHA_VANTAGE_API_KEY or _api_exhausted:
        return None

    _rate_limit()

    try:
        resp = requests.get(BASE_URL, params={
            "function": "TIME_SERIES_DAILY",
            "symbol": symbol,
            "outputsize": "full",
            "apikey": ALPHA_VANTAGE_API_KEY,
        }, timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        # Check for API limit / error messages
        if "Note" in data or "Information" in data:
            msg = data.get("Note", data.get("Information", ""))
            if "call frequency" in msg.lower() or "limit" in msg.lower():
                _api_exhausted = True
            return None

        if "Error Message" in data:
            return None

        ts = data.get("Time Series (Daily)")
        if not ts or len(ts) < SMA_LONG:
            return None

        # Convert to DataFrame (dates descending by default from API)
        dates = sorted(ts.keys())  # ascending
        rows = []
        for d in dates:
            bar = ts[d]
            rows.append({
                "date": d,
                "open": float(bar["1. open"]),
                "high": float(bar["2. high"]),
                "low": float(bar["3. low"]),
                "close": float(bar["4. close"]),
                "volume": int(bar["5. volume"]),
            })

        df = pd.DataFrame(rows)

        if len(df) < SMA_LONG:
            return None

        # ─── Indicators (computed locally) ──────────────────
        rsi_series = ta.momentum.RSIIndicator(
            close=df["close"], window=RSI_PERIOD
        ).rsi()
        rsi = rsi_series.iloc[-1]

        sma_50_series = ta.trend.SMAIndicator(
            close=df["close"], window=SMA_SHORT
        ).sma_indicator()
        sma_50 = sma_50_series.iloc[-1]

        sma_200_series = ta.trend.SMAIndicator(
            close=df["close"], window=SMA_LONG
        ).sma_indicator()
        sma_200 = sma_200_series.iloc[-1]

        if pd.isna(rsi) or pd.isna(sma_50) or pd.isna(sma_200):
            return None

        # ─── Latest bar ────────────────────────────────────
        latest = df.iloc[-1]
        price = float(latest["close"])
        day_high = float(latest["high"])
        day_low = float(latest["low"])
        volume = int(latest["volume"])
        prev_close = float(df.iloc[-2]["close"]) if len(df) > 1 else price

        # 20-day average volume
        vol_window = df["volume"].iloc[-AVG_VOLUME_PERIOD:]
        avg_volume_20 = int(vol_window.mean())

        return {
            "price": round(price, 2),
            "rsi": round(float(rsi), 2),
            "sma_50": round(float(sma_50), 2),
            "sma_200": round(float(sma_200), 2),
            "volume": volume,
            "avg_volume_20": avg_volume_20,
            "day_high": round(day_high, 2),
            "day_low": round(day_low, 2),
            "prev_close": round(prev_close, 2),
        }

    except Exception:
        return None
