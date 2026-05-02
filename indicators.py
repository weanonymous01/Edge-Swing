"""
Indicator scoring engine — deterministic scoring based on technical indicators.
Implements the mandatory trading logic and scoring system from the PRD.
"""

from config import STOP_LOSS_PCT, TARGET1_PCT, TARGET2_PCT, CAPITAL, RISK_AMOUNT


def compute_trend_score(price: float, sma_50: float, sma_200: float) -> int:
    """
    Trend Score (0–20):
    - Strong trend: price > SMA50 > SMA200 → 20
    - price > SMA50 but SMA50 < SMA200 → 12
    - price < SMA50 but > SMA200 → 6
    - price < SMA50 and < SMA200 → 0 (heavy penalty)
    """
    if price > sma_50 > sma_200:
        return 20
    elif price > sma_50 and sma_50 <= sma_200:
        return 12
    elif price < sma_50 and price > sma_200:
        return 6
    else:
        return 0


def compute_rsi_score(rsi: float) -> int:
    """
    RSI Score (0–20):
    - Ideal zone 45–65 → 20
    - 35–45 or 65–70 → 12
    - >70 overbought → 4 (penalty)
    - <35 very weak → 2 (penalty)
    - 30–35 → 6
    - 70–80 → 4
    - >80 → 0
    """
    if 45 <= rsi <= 65:
        return 20
    elif 40 <= rsi < 45 or 65 < rsi <= 70:
        return 14
    elif 35 <= rsi < 40:
        return 8
    elif 70 < rsi <= 80:
        return 4
    elif rsi > 80:
        return 0
    elif rsi < 35:
        return 2
    return 10  # fallback


def compute_volume_score(volume: int, avg_volume_20: int) -> int:
    """
    Volume Score (0–15):
    - volume >= 1.5x avg → 15
    - volume >= avg → 12
    - volume >= 0.7x avg → 6
    - volume < 0.7x avg → 0
    """
    if avg_volume_20 <= 0:
        return 0
    ratio = volume / avg_volume_20
    if ratio >= 1.5:
        return 15
    elif ratio >= 1.0:
        return 12
    elif ratio >= 0.7:
        return 6
    else:
        return 0


def compute_risk_reward_score(
    price: float, day_high: float, day_low: float, sma_50: float
) -> int:
    """
    Risk-Reward Score (0–20):
    Evaluates entry quality based on price position relative to range and SMA50.
    """
    score = 0

    # Proximity to SMA50 (pullback opportunity)
    if sma_50 > 0:
        pct_from_sma50 = abs(price - sma_50) / sma_50
        if pct_from_sma50 < 0.01:   # within 1%
            score += 10
        elif pct_from_sma50 < 0.02:
            score += 7
        elif pct_from_sma50 < 0.04:
            score += 4
        else:
            score += 1

    # Day range position — lower in the range is better for entry
    day_range = day_high - day_low
    if day_range > 0:
        position = (price - day_low) / day_range
        if position < 0.3:
            score += 10   # near low — excellent entry
        elif position < 0.5:
            score += 7
        elif position < 0.7:
            score += 4
        else:
            score += 1    # near high — risky entry

    return min(score, 20)


def compute_sector_momentum(etf_name: str) -> int:
    """
    Sector Momentum (0–25):
    Placeholder — static scores. Can be enhanced with sector index data later.
    """
    # Static sector strength estimates (can be overridden by LLM later)
    sector_map = {
        "ITBEES": 18,
        "PHARMABEES": 14,
        "PSUBNKBEES": 12,
        "AUTOBEES": 16,
        "MID150BEES": 15,
        "NIFTYBEES": 17,
        "GOLDBEES": 13,
        "GROWWDEFNC": 11,
    }
    return sector_map.get(etf_name, 12)


def determine_entry_type(
    price: float, day_high: float, sma_50: float
) -> str:
    """Determine entry type: 'breakout' or 'pullback'."""
    if price >= day_high * 0.998:  # within 0.2% of day high
        return "breakout"
    elif abs(price - sma_50) / sma_50 < 0.02:  # within 2% of SMA50
        return "pullback"
    else:
        return "pullback"


def compute_position_sizing(entry_price: float) -> dict:
    """
    Compute stop loss, targets, units, and position size.
    Returns dict with all position sizing fields.
    """
    stop_loss = round(entry_price * (1 - STOP_LOSS_PCT), 2)
    target1 = round(entry_price * (1 + TARGET1_PCT), 2)
    target2 = round(entry_price * (1 + TARGET2_PCT), 2)

    risk_per_unit = entry_price - stop_loss
    if risk_per_unit <= 0:
        return {
            "stop_loss": stop_loss,
            "target1": target1,
            "target2": target2,
            "units": 0,
            "position_size": 0,
            "risk_amount": 0,
        }

    units = int(RISK_AMOUNT / risk_per_unit)
    position_size = round(units * entry_price, 2)
    actual_risk = round(units * risk_per_unit, 2)

    # Cap position size to available capital
    if position_size > CAPITAL:
        units = int(CAPITAL / entry_price)
        position_size = round(units * entry_price, 2)
        actual_risk = round(units * risk_per_unit, 2)

    return {
        "stop_loss": stop_loss,
        "target1": target1,
        "target2": target2,
        "units": units,
        "position_size": position_size,
        "risk_amount": actual_risk,
    }


def score_etf(etf_name: str, data: dict) -> dict:
    """
    Master scoring function. Takes ETF name + data dict, returns full signal dict.
    """
    price = data["price"]
    rsi = data["rsi"]
    sma_50 = data["sma_50"]
    sma_200 = data["sma_200"]
    volume = data["volume"]
    avg_volume_20 = data["avg_volume_20"]
    day_high = data["day_high"]
    day_low = data["day_low"]

    # ── Score components ──
    sector_momentum = compute_sector_momentum(etf_name)
    trend_score = compute_trend_score(price, sma_50, sma_200)
    rsi_score = compute_rsi_score(rsi)
    volume_score = compute_volume_score(volume, avg_volume_20)
    risk_reward_score = compute_risk_reward_score(price, day_high, day_low, sma_50)

    total_score = (
        sector_momentum + trend_score + rsi_score + volume_score + risk_reward_score
    )

    # ── Action ──
    if total_score >= 70:
        action = "BUY"
    elif total_score >= 50:
        action = "WATCH"
    else:
        action = "SKIP"

    # ── Entry & position sizing ──
    entry_type = determine_entry_type(price, day_high, sma_50)
    entry_price = price
    sizing = compute_position_sizing(entry_price)

    return {
        "etf": etf_name,
        "action": action,
        "score": total_score,
        "score_breakdown": {
            "sector_momentum": sector_momentum,
            "trend_score": trend_score,
            "rsi_score": rsi_score,
            "volume_score": volume_score,
            "risk_reward_score": risk_reward_score,
        },
        "entry_type": entry_type,
        "entry_price": entry_price,
        "stop_loss": sizing["stop_loss"],
        "target1": sizing["target1"],
        "target2": sizing["target2"],
        "position_size": sizing["position_size"],
        "units": sizing["units"],
        "risk_amount": sizing["risk_amount"],
        "data": {
            "rsi": rsi,
            "sma_50": sma_50,
            "sma_200": sma_200,
            "volume": volume,
            "avg_volume_20": avg_volume_20,
            "day_high": day_high,
            "day_low": day_low,
            "prev_close": data.get("prev_close", price),
        },
        "reason": "",  # filled by LLM
    }
