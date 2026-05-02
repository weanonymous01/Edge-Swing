"""
Edge Swing — ETF Swing Trading CLI Assistant (India)
Main entry point: fetches data, scores ETFs, enriches with LLM, displays results.

Data priority: yfinance (primary) → Alpha Vantage (fallback)
"""

import sys
import json
import time
from config import ETF_MAP, ALPHA_VANTAGE_API_KEY
from data.yfinance_fallback import fetch_etf_data as yf_fetch
from data.alphavantage_fallback import fetch_etf_data as av_fetch
from indicators import score_etf
from ai_engine import enrich_signals_with_llm
from formatter import (
    console,
    display_header,
    display_market_mood,
    display_signals,
    display_avoid_list,
    display_summary,
    display_json_output,
    display_error,
    display_progress,
    display_success,
    display_warning,
)


def fetch_all_etfs() -> dict[str, dict]:
    """Fetch data for all ETFs using yfinance primary, Alpha Vantage fallback."""
    results = {}
    use_alphavantage = bool(ALPHA_VANTAGE_API_KEY)

    for etf_name, symbols in ETF_MAP.items():
        data = None

        # Primary: yfinance
        display_progress(f"Fetching {etf_name} from yfinance...")
        try:
            data = yf_fetch(symbols["yfinance"])
            if data:
                display_success(f"{etf_name} — yfinance OK")
        except Exception as e:
            display_warning(f"{etf_name} yfinance error: {e}")

        # Fallback: Alpha Vantage
        if data is None and use_alphavantage:
            display_warning(f"{etf_name} — falling back to Alpha Vantage...")
            try:
                data = av_fetch(symbols["alphavantage"])
                if data:
                    display_success(f"{etf_name} — Alpha Vantage OK")
            except Exception as e:
                display_error(f"{etf_name} Alpha Vantage failed: {e}")

        if data is None:
            display_error(f"{etf_name} — all sources failed -> SKIP")

        results[etf_name] = data

    return results


def run(json_mode: bool = False):
    """Main execution flow."""
    start = time.time()

    if not json_mode:
        display_header()

    # Step 1: Fetch data
    if not json_mode:
        console.print("[bold]Step 1/3:[/bold] Fetching market data...\n")
    etf_data = fetch_all_etfs()

    if not json_mode:
        console.print()

    # Step 2: Score ETFs
    if not json_mode:
        console.print("[bold]Step 2/3:[/bold] Scoring ETFs...\n")

    signals = []
    for etf_name, data in etf_data.items():
        if data is None:
            signals.append({
                "etf": etf_name,
                "action": "SKIP",
                "score": 0,
                "score_breakdown": {
                    "sector_momentum": 0, "trend_score": 0,
                    "rsi_score": 0, "volume_score": 0,
                    "risk_reward_score": 0,
                },
                "entry_type": "none",
                "entry_price": 0, "stop_loss": 0,
                "target1": 0, "target2": 0,
                "position_size": 0, "units": 0, "risk_amount": 0,
                "reason": "Data unavailable — all sources failed.",
                "data": {},
            })
            continue

        try:
            signal = score_etf(etf_name, data)
            signals.append(signal)
            if not json_mode:
                display_success(f"{etf_name}: Score {signal['score']} -> {signal['action']}")
        except Exception as e:
            display_error(f"{etf_name} scoring failed: {e}")
            signals.append({
                "etf": etf_name, "action": "SKIP", "score": 0,
                "score_breakdown": {
                    "sector_momentum": 0, "trend_score": 0,
                    "rsi_score": 0, "volume_score": 0,
                    "risk_reward_score": 0,
                },
                "entry_type": "none",
                "entry_price": 0, "stop_loss": 0,
                "target1": 0, "target2": 0,
                "position_size": 0, "units": 0, "risk_amount": 0,
                "reason": f"Scoring error: {e}",
                "data": {},
            })

    if not json_mode:
        console.print()

    # Step 3: Enrich with LLM
    if not json_mode:
        console.print("[bold]Step 3/3:[/bold] Analyzing with AI...\n")

    result = enrich_signals_with_llm(signals)

    elapsed = round(time.time() - start, 1)

    if not json_mode:
        console.print()
        # Sort signals: BUY first, then WATCH, then SKIP
        order = {"BUY": 0, "WATCH": 1, "SKIP": 2}
        result["signals"].sort(key=lambda s: (order.get(s["action"], 3), -s["score"]))

        display_market_mood(result.get("market_mood", ""))
        display_signals(result["signals"])
        display_avoid_list(result.get("avoid", []))
        display_summary(result.get("summary", ""))
        console.print(f"[dim]Completed in {elapsed}s[/dim]\n")
    else:
        display_json_output(result)


if __name__ == "__main__":
    json_mode = "--json" in sys.argv
    try:
        run(json_mode=json_mode)
    except KeyboardInterrupt:
        console.print("\n[dim]Interrupted.[/dim]")
        sys.exit(1)
    except Exception as e:
        display_error(f"Fatal: {e}")
        sys.exit(1)
