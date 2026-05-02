"""
AI Engine — sends structured prompts to DeepSeek-R1 via OpenRouter
and parses the JSON response to enrich signals with LLM reasoning.
"""

import json
import re
import requests
from datetime import datetime, timezone, timedelta
from config import (
    OPENROUTER_API_KEY, LLM_MODEL, LLM_TEMPERATURE,
    LLM_MAX_TOKENS, OPENROUTER_BASE_URL,
)

IST = timezone(timedelta(hours=5, minutes=30))


def build_prompt(signals: list[dict]) -> str:
    now = datetime.now(IST)
    date_str = now.strftime("%Y-%m-%d %H:%M IST")

    etf_blocks = []
    for sig in signals:
        d = sig.get("data", {})
        block = (
            f"ETF: {sig['etf']} | Price: {sig['entry_price']} | "
            f"RSI: {d.get('rsi')} | SMA50: {d.get('sma_50')} | SMA200: {d.get('sma_200')} | "
            f"Vol: {d.get('volume')} | AvgVol20: {d.get('avg_volume_20')} | "
            f"High: {d.get('day_high')} | Low: {d.get('day_low')} | "
            f"Score: {sig['score']} ({sig['action']}) | "
            f"Breakdown: {json.dumps(sig['score_breakdown'])} | "
            f"Entry: {sig['entry_type']} | SL: {sig['stop_loss']} | "
            f"T1: {sig['target1']} | T2: {sig['target2']} | Units: {sig['units']}"
        )
        etf_blocks.append(block)

    etf_section = "\n".join(etf_blocks)

    return f"""You are an Indian ETF swing trading analyst. Date: {date_str}.

DATA (real, from APIs — do NOT modify numbers):
{etf_section}

RULES: Score>=70→BUY, 50-69→WATCH, <50→SKIP. SL=-1.5%, T1=+3%, T2=+6%.

TASK: For each ETF write a 1-2 sentence "reason". Provide market_mood, avoid list, summary.

Respond ONLY with valid JSON:
{{"signals":[{{"etf":"NAME","action":"BUY|WATCH|SKIP","score":N,"score_breakdown":{{...}},"entry_type":"...","entry_price":N,"stop_loss":N,"target1":N,"target2":N,"position_size":N,"units":N,"risk_amount":N,"reason":"..."}}],"market_mood":"...","avoid":["ETF: reason"],"summary":"..."}}"""


def call_llm(prompt: str) -> dict | None:
    if not OPENROUTER_API_KEY:
        return None

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://edge-swing-cli.local",
        "X-Title": "Edge Swing CLI",
    }
    payload = {
        "model": LLM_MODEL,
        "temperature": LLM_TEMPERATURE,
        "max_tokens": LLM_MAX_TOKENS,
        "messages": [
            {"role": "system", "content": "Respond ONLY with valid JSON. No markdown. No code fences."},
            {"role": "user", "content": prompt},
        ],
    }

    for attempt in range(2):
        try:
            resp = requests.post(OPENROUTER_BASE_URL, headers=headers, json=payload, timeout=60)
            resp.raise_for_status()
            content = resp.json().get("choices", [{}])[0].get("message", {}).get("content", "")
            content = content.strip()
            # Strip code fences
            if content.startswith("```"):
                content = re.sub(r"^```(?:json)?\s*", "", content)
                content = re.sub(r"\s*```$", "", content)
            # Strip DeepSeek thinking tags
            if "<think>" in content:
                content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
            # Extract JSON object
            m = re.search(r"\{[\s\S]*\}", content)
            if m:
                parsed = json.loads(m.group(0))
                if "signals" in parsed:
                    return parsed
        except Exception:
            if attempt == 0:
                continue
            return None
    return None


def _generate_basic_reason(sig: dict) -> str:
    d = sig.get("data", {})
    parts = []
    price, sma50, sma200 = sig["entry_price"], d.get("sma_50", 0), d.get("sma_200", 0)
    rsi = d.get("rsi", 0)
    vol, avg_vol = d.get("volume", 0), d.get("avg_volume_20", 1)

    if price > sma50 > sma200:
        parts.append("Strong uptrend")
    elif price < sma50:
        parts.append("Below SMA50 — weak trend")
    if 45 <= rsi <= 65:
        parts.append(f"RSI {rsi:.1f} ideal")
    elif rsi > 70:
        parts.append(f"RSI {rsi:.1f} overbought")
    elif rsi < 40:
        parts.append(f"RSI {rsi:.1f} weak")
    if avg_vol > 0 and vol >= avg_vol:
        parts.append("Volume confirmed")
    elif avg_vol > 0:
        parts.append("Low volume")
    return ". ".join(parts) + "." if parts else "Insufficient data."


def enrich_signals_with_llm(signals: list[dict]) -> dict:
    buy_signals = [s for s in signals if s["action"] == "BUY"]
    
    # Always generate basic reasons for all signals first
    for sig in signals:
        sig["reason"] = _generate_basic_reason(sig)
        
    if not buy_signals:
        return {
            "signals": signals,
            "market_mood": "No high-conviction BUY signals today. Waiting for clearer setups.",
            "avoid": [f"{s['etf']}: Low score ({s['score']})" for s in signals if s["action"] == "SKIP"],
            "summary": "Deterministic scoring complete. No actionable trade setups found.",
        }

    prompt = build_prompt(buy_signals)
    llm_result = call_llm(prompt)

    if llm_result and "signals" in llm_result:
        llm_map = {s["etf"]: s for s in llm_result["signals"]}
        for sig in signals:
            if sig["action"] == "BUY":
                sig["reason"] = llm_map.get(sig["etf"], {}).get("reason", sig["reason"])
                
        return {
            "signals": signals,
            "market_mood": llm_result.get("market_mood", "Analysis pending."),
            "avoid": [f"{s['etf']}: Low score ({s['score']})" for s in signals if s["action"] == "SKIP"],
            "summary": llm_result.get("summary", "LLM review complete for BUY candidates."),
        }
    else:
        return {
            "signals": signals,
            "market_mood": "LLM unavailable — deterministic analysis only.",
            "avoid": [f"{s['etf']}: Low score ({s['score']})" for s in signals if s["action"] == "SKIP"],
            "summary": "Deterministic scoring complete. Review BUY signals above.",
        }
