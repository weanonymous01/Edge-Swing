"""
Edge Swing v3.2 — Wide Trailing Trend Follower (Winning Strategy)
Period: Jan 2024 — Jan 2025
"""

import os, json, warnings
import numpy as np
import pandas as pd
import yfinance as yf
import ta
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime

warnings.filterwarnings("ignore")

from config import CAPITAL, RSI_PERIOD, SMA_SHORT, SMA_LONG, AVG_VOLUME_PERIOD
from indicators import (
    compute_trend_score, compute_rsi_score, compute_volume_score,
    compute_risk_reward_score, compute_sector_momentum
)

# Universe: 23 liquid ETFs & Large Cap Stocks
UNIVERSE = [
    "ITBEES.NS", "PHARMABEES.NS", "PSUBNKBEES.NS", "AUTOBEES.NS",
    "MID150BEES.NS", "NIFTYBEES.NS", "GOLDBEES.NS", "BANKBEES.NS",
    "MON100.NS", "INFRABEES.NS", "CPSEETF.NS", 
    "HDFCBANK.NS", "RELIANCE.NS", "INFY.NS", "TCS.NS",
    "ICICIBANK.NS", "SBIN.NS", "LT.NS", "ITC.NS", 
    "AXISBANK.NS", "KOTAKBANK.NS", "M&M.NS", "BHARTIARTL.NS"
]

# Strict Rules for v3.2
INITIAL_SL_PCT = 0.02
MAX_OPEN_TRADES = 2
MIN_SCORE = 72

CHARTS_DIR = os.path.join(os.path.dirname(__file__), "charts")
os.makedirs(CHARTS_DIR, exist_ok=True)

plt.rcParams.update({
    "figure.facecolor": "#0d1117", "axes.facecolor": "#161b22",
    "axes.edgecolor": "#30363d", "axes.labelcolor": "#c9d1d9",
    "text.color": "#c9d1d9", "xtick.color": "#8b949e",
    "ytick.color": "#8b949e", "grid.color": "#21262d",
    "figure.dpi": 150, "font.size": 10, "axes.grid": True, "grid.alpha": 0.5,
})
C = {"green": "#3fb950", "red": "#f85149", "blue": "#58a6ff",
     "purple": "#bc8cff", "orange": "#d29922", "cyan": "#39d2c0",
     "pink": "#f778ba"}

def download_data(symbol: str, period: str = "5y") -> pd.DataFrame:
    tk = yf.Ticker(symbol)
    df = tk.history(period=period).reset_index()
    if df.empty or len(df) < SMA_LONG + 50:
        return pd.DataFrame()
    df = df.sort_values("Date").reset_index(drop=True)
    df["RSI"] = ta.momentum.RSIIndicator(close=df["Close"], window=RSI_PERIOD).rsi()
    df["SMA20"] = ta.trend.SMAIndicator(close=df["Close"], window=20).sma_indicator()
    df["SMA30"] = ta.trend.SMAIndicator(close=df["Close"], window=30).sma_indicator()
    df["SMA50"] = ta.trend.SMAIndicator(close=df["Close"], window=SMA_SHORT).sma_indicator()
    df["SMA200"] = ta.trend.SMAIndicator(close=df["Close"], window=SMA_LONG).sma_indicator()
    df["AvgVol20"] = df["Volume"].rolling(AVG_VOLUME_PERIOD).mean()
    df["ATR"] = ta.volatility.AverageTrueRange(high=df["High"], low=df["Low"], close=df["Close"], window=14).average_true_range()
    
    df.dropna(subset=["RSI", "SMA20", "SMA30", "SMA50", "SMA200", "AvgVol20", "ATR"], inplace=True)
    df["Date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None)
    return df.reset_index(drop=True)

def score_row(etf_name, row, nifty_row):
    price = float(row["Close"])
    rsi = float(row["RSI"])
    sma50 = float(row["SMA50"])
    sma200 = float(row["SMA200"])
    vol = int(row["Volume"])
    avg_vol = int(row["AvgVol20"])
    high = float(row["High"])
    low = float(row["Low"])
    atr = float(row["ATR"])

    sm = compute_sector_momentum(etf_name)
    ts = compute_trend_score(price, sma50, sma200)
    rs = compute_rsi_score(rsi)
    vs = compute_volume_score(vol, avg_vol)
    rr = compute_risk_reward_score(price, high, low, sma50)
    total = sm + ts + rs + vs + rr

    # STRICT FILTERS
    if nifty_row is None or float(nifty_row["Close"]) <= float(nifty_row["SMA50"]):
        return None
    if total < MIN_SCORE:
        return None
    if not (price > sma50 and sma50 > sma200):
        return None
    if vol < avg_vol * 0.9:
        return None
    if not (45 <= rsi <= 80):
        return None
    if atr / price < 0.01: # Skip low volatility (<1% daily ATR)
        return None

    sl = round(price * (1 - INITIAL_SL_PCT), 2)
    
    return {
        "etf": etf_name.replace(".NS", ""), "score": total, "price": price, "date": row["Date"],
        "initial_sl": sl
    }

def run():
    print("=" * 60)
    print("  EDGE SWING v3.2 — WIDE TRAILING TREND FOLLOWER")
    print("  Period: Jan 2024 — Jan 2025")
    print("=" * 60)

    print(f"\nDownloading data for {len(UNIVERSE)} assets...")
    all_data = {}
    for sym in UNIVERSE:
        df = download_data(sym)
        if not df.empty:
            all_data[sym.replace(".NS", "")] = df
    print("Downloading NIFTY 50 data...")
    nifty_df = download_data("^NSEI")
    
    if nifty_df.empty: return

    bt_start = datetime(2024, 1, 1)
    bt_end = datetime(2025, 1, 31)

    all_dates = sorted(list(set(nifty_df[(nifty_df["Date"] >= bt_start) & (nifty_df["Date"] <= bt_end)]["Date"])))
    
    open_positions = []
    all_trades = []
    capital = CAPITAL
    equity_series = []
    
    consecutive_losses = 0
    skip_next_trade = False

    for current_date in all_dates:
        # ── Update open positions ──
        positions_to_remove = []
        for p in open_positions:
            df = all_data[p["etf"]]
            mask = df["Date"] == current_date
            if mask.sum() == 0: continue
            row = df[mask].iloc[0]
            high, low, close = float(row["High"]), float(row["Low"]), float(row["Close"])
            sma20, sma30 = float(row["SMA20"]), float(row["SMA30"])
            
            # Update highest price reached
            p["highest_price"] = max(p.get("highest_price", high), high)
            profit_pct = (p["highest_price"] - p["entry_price"]) / p["entry_price"]
            
            # 1. Check SL
            if low <= p["current_sl"]:
                exit_price = p["current_sl"]
                pnl = (exit_price - p["entry_price"]) * p["initial_units"]
                if p.get("pyramid_active"):
                    pnl += (exit_price - p["pyramid_price"]) * p["pyramid_units"]
                
                capital += p["capital_allocated"] + pnl
                p["total_pnl"] = pnl
                p["exit_date"] = current_date
                p["exit_price"] = exit_price
                p["result"] = "TRAIL_HIT" if p.get("trail_active") else ("BE_HIT" if p.get("be_active") else "SL_HIT")
                
                if p["total_pnl"] < 0:
                    consecutive_losses += 1
                    if consecutive_losses >= 2:
                        skip_next_trade = True
                        consecutive_losses = 0
                else:
                    consecutive_losses = 0

                positions_to_remove.append(p)
                continue
            
            # 2. Profit Protection Logic
            
            # +3% -> Breakeven
            if profit_pct >= 0.03:
                if not p.get("be_active"):
                    p["be_active"] = True
                    p["current_sl"] = max(p["current_sl"], p["entry_price"])
            
            # +5% -> Trailing + Pyramid
            if profit_pct >= 0.05:
                p["trail_active"] = True
                
                # Pyramid 20%
                if not p.get("pyramid_active"):
                    max_slot_capital = CAPITAL / MAX_OPEN_TRADES
                    pyramid_alloc = max_slot_capital * 0.2
                    if capital >= pyramid_alloc:
                        p["pyramid_active"] = True
                        p["pyramid_price"] = close
                        p["pyramid_units"] = int(pyramid_alloc / p["pyramid_price"])
                        capital -= (p["pyramid_units"] * p["pyramid_price"])
                        p["capital_allocated"] += (p["pyramid_units"] * p["pyramid_price"])
            
            # Update Trailing Stop (v3.2 Logic)
            if p.get("trail_active"):
                # Determine which SMA to use for trailing floor
                floor_sma = sma30 if close > 1.05 * sma20 else sma20
                
                if profit_pct >= 0.10:
                    new_trail_sl = floor_sma
                else:
                    trail_sl = p["highest_price"] * (1 - 0.07)
                    new_trail_sl = max(trail_sl, floor_sma)
                
                p["current_sl"] = max(p["current_sl"], new_trail_sl)

        for p in positions_to_remove:
            p["hold_days"] = (p["exit_date"] - p["entry_date"]).days
            all_trades.append(p)
            open_positions.remove(p)

        # ── Calculate current equity ──
        eq = capital
        for p in open_positions:
            df = all_data[p["etf"]]
            mask = df["Date"] <= current_date
            if mask.sum() > 0:
                close = float(df[mask].iloc[-1]["Close"])
                eq += (close - p["entry_price"]) * p["initial_units"]
                if p.get("pyramid_active"):
                    eq += (close - p["pyramid_price"]) * p["pyramid_units"]
                eq += p["capital_allocated"]
        equity_series.append({"date": current_date, "equity": eq})

        # ── Scan for new entries ──
        if len(open_positions) < MAX_OPEN_TRADES:
            nifty_mask = nifty_df["Date"] <= current_date
            if nifty_mask.sum() == 0: continue
            nifty_row = nifty_df[nifty_mask].iloc[-1]
            
            signals = []
            for etf_name, df in all_data.items():
                if any(p["etf"] == etf_name for p in open_positions): continue
                mask = df["Date"] == current_date
                if mask.sum() == 0: continue
                row = df[mask].iloc[0]
                sig = score_row(etf_name, row, nifty_row)
                if sig:
                    signals.append(sig)
            
            signals.sort(key=lambda x: x["score"], reverse=True)
            for sig in signals:
                if len(open_positions) >= MAX_OPEN_TRADES: break
                
                if skip_next_trade:
                    skip_next_trade = False
                    continue # skipped!
                
                entry = sig["price"]
                # Initial allocation: 80% of max slot
                slot_capital = (capital + sum(p["capital_allocated"] for p in open_positions)) / MAX_OPEN_TRADES
                initial_alloc = slot_capital * 0.8
                
                if initial_alloc > capital: # Not enough cash
                    initial_alloc = capital
                    
                if initial_alloc < 1000: continue
                
                units = int(initial_alloc / entry)
                pos_size = units * entry
                capital -= pos_size
                
                open_positions.append({
                    "etf": sig["etf"], "entry_date": current_date,
                    "entry_price": entry, "current_sl": sig["initial_sl"],
                    "initial_units": units, "capital_allocated": pos_size,
                    "highest_price": entry, "score": sig["score"]
                })

    # Close open positions at end
    for p in open_positions:
        df = all_data[p["etf"]]
        last_row = df[(df["Date"] >= bt_start) & (df["Date"] <= bt_end)].iloc[-1]
        exit_price = float(last_row["Close"])
        pnl = (exit_price - p["entry_price"]) * p["initial_units"]
        if p.get("pyramid_active"):
            pnl += (exit_price - p["pyramid_price"]) * p["pyramid_units"]
        capital += p["capital_allocated"] + pnl
        p["total_pnl"] = pnl
        p["exit_date"] = last_row["Date"]
        p["exit_price"] = exit_price
        p["result"] = "OPEN_CLOSE"
        p["hold_days"] = (p["exit_date"] - p["entry_date"]).days
        all_trades.append(p)

    # ═══ STATS ═══════════════════════════════════════════════
    total_pnl = sum(t["total_pnl"] for t in all_trades)
    wins = [t for t in all_trades if t["total_pnl"] > 0]
    losses = [t for t in all_trades if t["total_pnl"] <= 0]
    win_rate = len(wins) / len(all_trades) * 100 if all_trades else 0
    avg_win = np.mean([t["total_pnl"] for t in wins]) if wins else 0
    avg_loss = np.mean([t["total_pnl"] for t in losses]) if losses else 0
    pf = abs(sum(t["total_pnl"] for t in wins)) / abs(sum(t["total_pnl"] for t in losses)) if losses and sum(t["total_pnl"] for t in losses) != 0 else 0
    largest_win = max([t["total_pnl"] for t in wins]) if wins else 0
    sorted_wins = sorted(wins, key=lambda x: x["total_pnl"], reverse=True)
    top_3_pnl = sum([t["total_pnl"] for t in sorted_wins[:3]])
    top_3_pct = (top_3_pnl / total_pnl * 100) if total_pnl > 0 else 0

    stats = {
        "period": "Jan 2024 — Jan 2025",
        "strategy": "v3.2 Pyramiding (Wide Trailing)",
        "starting_capital": CAPITAL,
        "ending_capital": round(CAPITAL + total_pnl, 2),
        "total_return_pct": round(total_pnl / CAPITAL * 100, 2),
        "total_pnl": round(total_pnl, 2),
        "total_trades": len(all_trades),
        "wins": len(wins), "losses": len(losses),
        "win_rate": round(win_rate, 1),
        "avg_win": round(avg_win, 2), "avg_loss": round(avg_loss, 2),
        "profit_factor": round(pf, 2),
        "largest_win": round(largest_win, 2),
        "top_3_pct": round(top_3_pct, 1)
    }

    print("=" * 60)
    print(f"  TOTAL TRADES: {len(all_trades)}")
    print(f"  WIN RATE: {win_rate:.1f}%")
    print(f"  TOTAL P&L: Rs.{total_pnl:,.2f}")
    print(f"  RETURN: {total_pnl / CAPITAL * 100:.2f}%")
    print(f"  PROFIT FACTOR: {pf:.2f}")
    print(f"  LARGEST WIN: Rs.{largest_win:,.2f}")
    print(f"  TOP 3 WINS % OF RETURNS: {top_3_pct:.1f}%")
    print("=" * 60)
    
    if len(all_trades) > 0:
        print("\nTrades:")
        for t in all_trades:
            print(f"  {t['entry_date'].strftime('%y-%m-%d')} | {t['etf']:10s} | {t['result']:10s} | PNL: Rs.{t['total_pnl']:>8.2f} {'(Pyramided)' if t.get('pyramid_active') else ''}")

    # ═══ CHARTS ══════════════════════════════════════════════
    print("\nGenerating charts...")

    # 1. Equity Curve
    fig, ax = plt.subplots(figsize=(14, 6))
    eq_df = pd.DataFrame(equity_series)
    ax.plot(eq_df["date"], eq_df["equity"], color=C["cyan"], linewidth=2.5)
    ax.fill_between(eq_df["date"], CAPITAL, eq_df["equity"], alpha=0.15,
                     color=C["green"] if eq_df.iloc[-1]["equity"] >= CAPITAL else C["red"])
    ax.axhline(y=CAPITAL, color=C["orange"], linestyle="--", alpha=0.5)
    ax.set_title("Portfolio Equity Curve — v3.2", fontsize=14, fontweight="bold", pad=15)
    ax.set_ylabel("Capital (Rs.)")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    fig.autofmt_xdate(); fig.tight_layout()
    fig.savefig(os.path.join(CHARTS_DIR, "equity_curve.png"), bbox_inches="tight"); plt.close()

    # 2. Drawdown
    eq_s = eq_df["equity"]
    peak = eq_s.cummax()
    dd = (eq_s - peak) / peak * 100
    fig, ax = plt.subplots(figsize=(14, 4))
    ax.fill_between(eq_df["date"], dd, 0, color=C["red"], alpha=0.4)
    ax.plot(eq_df["date"], dd, color=C["red"], linewidth=1)
    ax.set_title("Portfolio Drawdown", fontsize=14, fontweight="bold", pad=15)
    ax.set_ylabel("Drawdown (%)"); ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    if dd.min() < 0:
        ax.annotate(f"Max DD: {dd.min():.2f}%", xy=(eq_df.iloc[dd.idxmin()]["date"], dd.min()),
                    fontsize=10, color=C["red"], fontweight="bold", xytext=(10, -20), textcoords="offset points")
        stats["max_drawdown"] = round(dd.min(), 2)
    else:
        stats["max_drawdown"] = 0
    fig.autofmt_xdate(); fig.tight_layout()
    fig.savefig(os.path.join(CHARTS_DIR, "drawdown.png"), bbox_inches="tight"); plt.close()

    if len(all_trades) > 0:
        # 3. P&L Distribution
        fig, ax = plt.subplots(figsize=(10, 5))
        pnls = [t["total_pnl"] for t in all_trades]
        ax.hist(pnls, bins=max(5, len(pnls)//2), color=C["blue"], edgecolor="#30363d", alpha=0.8)
        ax.axvline(x=0, color=C["orange"], linestyle="--", linewidth=1.5)
        ax.axvline(x=np.mean(pnls), color=C["cyan"], linestyle="-", linewidth=1.5,
                   label=f"Avg: Rs.{np.mean(pnls):,.0f}")
        ax.set_title("Trade P&L Distribution", fontsize=14, fontweight="bold", pad=15)
        ax.set_xlabel("P&L (Rs.)"); ax.set_ylabel("Frequency"); ax.legend()
        fig.tight_layout()
        fig.savefig(os.path.join(CHARTS_DIR, "pnl_distribution.png"), bbox_inches="tight"); plt.close()
        
        # 4. Monthly Returns
        fig, ax = plt.subplots(figsize=(12, 5))
        tdf = pd.DataFrame(all_trades)
        tdf["month"] = tdf["exit_date"].dt.to_period("M")
        monthly = tdf.groupby("month")["total_pnl"].sum()
        m_labels = [str(m) for m in monthly.index]
        m_vals = monthly.values
        m_colors = [C["green"] if v >= 0 else C["red"] for v in m_vals]
        bars = ax.bar(m_labels, m_vals, color=m_colors, edgecolor="#30363d")
        for bar, v in zip(bars, m_vals):
            va = "bottom" if v >= 0 else "top"
            ax.text(bar.get_x() + bar.get_width()/2, v, f"Rs.{v:,.0f}",
                    ha="center", va=va, fontsize=8, fontweight="bold",
                    color=C["green"] if v >= 0 else C["red"])
        ax.axhline(y=0, color="#8b949e", linewidth=0.8)
        ax.set_title("Monthly P&L", fontsize=14, fontweight="bold", pad=15)
        ax.set_ylabel("P&L (Rs.)"); plt.xticks(rotation=45)
        fig.tight_layout()
        fig.savefig(os.path.join(CHARTS_DIR, "monthly_returns.png"), bbox_inches="tight"); plt.close()
        
        # 5. Asset Contribution
        fig, ax = plt.subplots(figsize=(12, 5))
        asset_pnl = tdf.groupby("etf")["total_pnl"].sum().sort_values()
        colors = [C["green"] if x > 0 else C["red"] for x in asset_pnl]
        asset_pnl.plot(kind="bar", color=colors, ax=ax, edgecolor="#30363d")
        ax.set_title("P&L Contribution by Asset", fontsize=14, fontweight="bold", pad=15)
        ax.set_ylabel("Total P&L (Rs.)")
        ax.axhline(y=0, color="#8b949e", linewidth=0.8)
        plt.xticks(rotation=45, ha="right")
        fig.tight_layout()
        fig.savefig(os.path.join(CHARTS_DIR, "asset_contribution.png"), bbox_inches="tight"); plt.close()

    with open(os.path.join(CHARTS_DIR, "backtest_stats.json"), "w") as f:
        json.dump(stats, f, indent=2, default=str)

    print(f"\nAll charts saved to: {CHARTS_DIR}/")

if __name__ == "__main__":
    run()
