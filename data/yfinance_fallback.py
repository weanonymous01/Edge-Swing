"""
yfinance fallback — used when Twelve Data is unavailable or fails.
Computes RSI, SMA 50, SMA 200, and 20-day average volume locally.
"""

import yfinance as yf
import ta
import pandas as pd
from config import RSI_PERIOD, SMA_SHORT, SMA_LONG, AVG_VOLUME_PERIOD


def fetch_etf_data(symbol: str) -> dict | None:
    """
    Download historical data from Yahoo Finance and compute all required indicators.
    Returns the same dict shape as twelvedata.fetch_etf_data, or None on failure.
    """
    try:
        ticker = yf.Ticker(symbol)
        # Need at least 200+ days for SMA 200; fetch ~250 trading days
        hist = ticker.history(period="1y")

        if hist.empty or len(hist) < SMA_LONG:
            return None

        # Ensure sorted by date ascending
        hist = hist.sort_index()

        # ─── Indicators ────────────────────────────────────
        # RSI (14)
        rsi_series = ta.momentum.RSIIndicator(
            close=hist["Close"], window=RSI_PERIOD
        ).rsi()
        rsi = rsi_series.iloc[-1]
        if pd.isna(rsi):
            return None

        # SMA 50
        sma_50_series = ta.trend.SMAIndicator(
            close=hist["Close"], window=SMA_SHORT
        ).sma_indicator()
        sma_50 = sma_50_series.iloc[-1]

        # SMA 200
        sma_200_series = ta.trend.SMAIndicator(
            close=hist["Close"], window=SMA_LONG
        ).sma_indicator()
        sma_200 = sma_200_series.iloc[-1]

        if pd.isna(sma_50) or pd.isna(sma_200):
            return None

        # ─── Latest bar ────────────────────────────────────
        latest = hist.iloc[-1]
        price = float(latest["Close"])
        day_high = float(latest["High"])
        day_low = float(latest["Low"])
        volume = int(latest["Volume"])

        # Previous close
        prev_close = float(hist.iloc[-2]["Close"]) if len(hist) > 1 else price

        # 20-day average volume
        vol_window = hist["Volume"].iloc[-AVG_VOLUME_PERIOD:]
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
