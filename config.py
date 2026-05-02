"""
Configuration module for ETF Swing Trading CLI Assistant.
Loads environment variables and defines constants.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ─── API Keys ───────────────────────────────────────────────
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY", "")

# ─── ETF Universe ───────────────────────────────────────────
# Maps display name → yfinance symbol and Alpha Vantage symbol
ETF_MAP = {
    "ITBEES":      {"yfinance": "ITBEES.NS",     "alphavantage": "ITBEES.BSE"},
    "PHARMABEES":  {"yfinance": "PHARMABEES.NS",  "alphavantage": "PHARMABEES.BSE"},
    "PSUBNKBEES":  {"yfinance": "PSUBNKBEES.NS",  "alphavantage": "PSUBNKBEES.BSE"},
    "AUTOBEES":    {"yfinance": "AUTOBEES.NS",    "alphavantage": "AUTOBEES.BSE"},
    "MID150BEES":  {"yfinance": "MID150BEES.NS",  "alphavantage": "MID150BEES.BSE"},
    "NIFTYBEES":   {"yfinance": "NIFTYBEES.NS",   "alphavantage": "NIFTYBEES.BSE"},
    "GOLDBEES":    {"yfinance": "GOLDBEES.NS",    "alphavantage": "GOLDBEES.BSE"},
    "GROWWDEFNC":  {"yfinance": "GROWWDEFNC.NS",  "alphavantage": "GROWWDEFNC.BSE"},
    "BANKBEES":    {"yfinance": "BANKBEES.NS",    "alphavantage": "BANKBEES.BSE"},
    "MON100":      {"yfinance": "MON100.NS",      "alphavantage": "MON100.BSE"},
    "INFRABEES":   {"yfinance": "INFRABEES.NS",   "alphavantage": "INFRABEES.BSE"},
    "CPSEETF":     {"yfinance": "CPSEETF.NS",     "alphavantage": "CPSEETF.BSE"},
    "HDFCBANK":    {"yfinance": "HDFCBANK.NS",    "alphavantage": "HDFCBANK.BSE"},
    "RELIANCE":    {"yfinance": "RELIANCE.NS",    "alphavantage": "RELIANCE.BSE"},
    "INFY":        {"yfinance": "INFY.NS",        "alphavantage": "INFY.BSE"},
    "TCS":         {"yfinance": "TCS.NS",         "alphavantage": "TCS.BSE"},
    "ICICIBANK":   {"yfinance": "ICICIBANK.NS",   "alphavantage": "ICICIBANK.BSE"},
    "SBIN":        {"yfinance": "SBIN.NS",        "alphavantage": "SBIN.BSE"},
    "LT":          {"yfinance": "LT.NS",          "alphavantage": "LT.BSE"},
    "ITC":         {"yfinance": "ITC.NS",         "alphavantage": "ITC.BSE"},
    "AXISBANK":    {"yfinance": "AXISBANK.NS",    "alphavantage": "AXISBANK.BSE"},
    "KOTAKBANK":   {"yfinance": "KOTAKBANK.NS",   "alphavantage": "KOTAKBANK.BSE"},
    "M&M":         {"yfinance": "M&M.NS",         "alphavantage": "M&M.BSE"},
    "BHARTIARTL":  {"yfinance": "BHARTIARTL.NS",  "alphavantage": "BHARTIARTL.BSE"},
}

# ─── Trading Parameters (v3.2 Spec) ────────────────────────
CAPITAL = 115_000          # ₹1,15,000 total capital
MAX_RISK_PCT = 0.02        # 2% initial stop loss risk
RISK_AMOUNT = CAPITAL * MAX_RISK_PCT  # ₹2,300

STOP_LOSS_PCT = 0.02       # -2.0%
TARGET1_PCT = 0.03          # +3% (Breakeven trigger)
TARGET2_PCT = 0.05          # +5% (Pyramid & Trail trigger)

# ─── Scoring Thresholds ────────────────────────────────────
SCORE_BUY = 72
SCORE_WATCH = 60

# ─── LLM Config ────────────────────────────────────────────
LLM_MODEL = "deepseek/deepseek-chat"  # Changed to V3 (fast) instead of R1 (slow)
LLM_TEMPERATURE = 0.3
LLM_MAX_TOKENS = 4096
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"

# ─── Indicator Defaults ────────────────────────────────────
RSI_PERIOD = 14
SMA_SHORT = 50
SMA_LONG = 200
AVG_VOLUME_PERIOD = 20
