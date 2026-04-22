from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd
from pydantic import BaseModel, Field

from . import indicators


# ---------- schema ----------

class Rule(BaseModel):
    name: str
    asset: str
    signal: str
    params: dict[str, Any] = Field(default_factory=dict)
    cooldown_minutes: int = 60


class RulesConfig(BaseModel):
    alert_email: str = ""
    rules: list[Rule] = Field(default_factory=list)


# ---------- evaluation ----------

@dataclass
class AssetData:
    """OHLCV data per-asset at different resampled timeframes."""
    symbol: str
    price_now: float
    change_24h_pct: float
    volume_24h_usd: float
    # timeframe label -> OHLCV DataFrame
    frames: dict[str, pd.DataFrame] = field(default_factory=dict)
    # Recent whale-sized transfers (already filtered/priced)
    whale_transfers: list[dict] = field(default_factory=list)


@dataclass
class Trigger:
    rule_name: str
    asset: str
    message: str
    value: float | None = None


def _frame_for(asset: AssetData, timeframe: str) -> pd.DataFrame | None:
    return asset.frames.get(timeframe)


def _eval_rsi(rule: Rule, a: AssetData) -> Trigger | None:
    p = rule.params
    df = _frame_for(a, p.get("timeframe", "1h"))
    if df is None or df.empty:
        return None
    series = indicators.rsi(df["close"], period=int(p.get("period", 14)))
    last = series.iloc[-1]
    if pd.isna(last):
        return None
    thresh = float(p.get("threshold", 30))
    direction = p.get("direction", "below")
    hit = (direction == "below" and last < thresh) or (
        direction == "above" and last > thresh
    )
    if not hit:
        return None
    return Trigger(
        rule.name,
        a.symbol,
        f"RSI({p.get('period', 14)}) = {last:.1f} {direction} {thresh}",
        float(last),
    )


def _eval_macd_cross(rule: Rule, a: AssetData) -> Trigger | None:
    p = rule.params
    df = _frame_for(a, p.get("timeframe", "1h"))
    if df is None or df.empty:
        return None
    m = indicators.macd(df["close"])
    direction = p.get("direction", "bullish")
    if direction == "bullish":
        hit = indicators.crossed_above(m["macd"], m["signal"])
    else:
        hit = indicators.crossed_below(m["macd"], m["signal"])
    if not hit:
        return None
    return Trigger(
        rule.name,
        a.symbol,
        f"MACD {direction} cross (macd={m['macd'].iloc[-1]:.3f}, "
        f"signal={m['signal'].iloc[-1]:.3f})",
        float(m["hist"].iloc[-1]),
    )


def _eval_sma_cross(rule: Rule, a: AssetData) -> Trigger | None:
    p = rule.params
    df = _frame_for(a, p.get("timeframe", "1h"))
    if df is None or df.empty:
        return None
    fast = indicators.sma(df["close"], int(p.get("fast", 20)))
    slow = indicators.sma(df["close"], int(p.get("slow", 50)))
    direction = p.get("direction", "bullish")
    if direction == "bullish":
        hit = indicators.crossed_above(fast, slow)
    else:
        hit = indicators.crossed_below(fast, slow)
    if not hit:
        return None
    return Trigger(
        rule.name,
        a.symbol,
        f"SMA{p.get('fast', 20)}/{p.get('slow', 50)} {direction} cross",
    )


def _eval_bollinger_break(rule: Rule, a: AssetData) -> Trigger | None:
    p = rule.params
    df = _frame_for(a, p.get("timeframe", "1h"))
    if df is None or df.empty:
        return None
    bb = indicators.bollinger(
        df["close"],
        period=int(p.get("period", 20)),
        stddev=float(p.get("stddev", 2.0)),
    )
    last = df["close"].iloc[-1]
    direction = p.get("direction", "above")
    if direction == "above":
        hit = last > bb["upper"].iloc[-1]
    else:
        hit = last < bb["lower"].iloc[-1]
    if not hit or pd.isna(bb["mid"].iloc[-1]):
        return None
    return Trigger(
        rule.name,
        a.symbol,
        f"Bollinger break {direction} (close={last:.4f})",
        float(last),
    )


_WINDOW_TO_BARS_1H = {"1h": 1, "4h": 4, "24h": 24, "7d": 168}


def _eval_price_change_pct(rule: Rule, a: AssetData) -> Trigger | None:
    p = rule.params
    window = p.get("window", "1h")
    bars = _WINDOW_TO_BARS_1H.get(window)
    df = _frame_for(a, "1h")
    if bars is None or df is None or df.empty:
        return None
    pct = indicators.pct_change_over(df["close"], bars)
    if pct is None:
        return None
    thresh = float(p.get("threshold", -5))
    # If threshold is negative treat it as a drop trigger; positive as rise;
    # magnitude comparison for cleanest semantics:
    hit = (thresh < 0 and pct <= thresh) or (thresh > 0 and pct >= thresh)
    if not hit:
        return None
    return Trigger(
        rule.name,
        a.symbol,
        f"Price moved {pct:+.2f}% over {window}",
        pct,
    )


def _eval_price_level(rule: Rule, a: AssetData) -> Trigger | None:
    p = rule.params
    level = float(p.get("level"))
    direction = p.get("direction", "above")
    df = _frame_for(a, "1h")
    if df is None or len(df) < 2:
        return None
    prev = df["close"].iloc[-2]
    cur = df["close"].iloc[-1]
    if direction == "above":
        hit = prev <= level < cur
    else:
        hit = prev >= level > cur
    if not hit:
        return None
    return Trigger(rule.name, a.symbol, f"Price crossed {direction} {level}", cur)


def _eval_volume_spike(rule: Rule, a: AssetData) -> Trigger | None:
    p = rule.params
    lookback = int(p.get("lookback_hours", 24))
    multiplier = float(p.get("multiplier", 3.0))
    df = _frame_for(a, "1h")
    if df is None or df.empty:
        return None
    ratio = indicators.volume_ratio(df["volume"], lookback)
    if ratio is None or ratio < multiplier:
        return None
    return Trigger(
        rule.name,
        a.symbol,
        f"Volume spike: {ratio:.1f}x baseline ({lookback}h)",
        ratio,
    )


def _eval_whale_transfer(rule: Rule, a: AssetData) -> Trigger | None:
    min_usd = float(rule.params.get("min_usd", 500_000))
    for tx in a.whale_transfers:
        if tx.get("usd_value", 0) >= min_usd:
            return Trigger(
                rule.name,
                a.symbol,
                (
                    f"Whale transfer: {tx['amount']:.2f} {a.symbol} "
                    f"(~${tx['usd_value']:,.0f}) tx {tx['tx_hash'][:10]}…"
                ),
                tx["usd_value"],
            )
    return None


_EVALUATORS = {
    "rsi": _eval_rsi,
    "macd_cross": _eval_macd_cross,
    "sma_cross": _eval_sma_cross,
    "bollinger_break": _eval_bollinger_break,
    "price_change_pct": _eval_price_change_pct,
    "price_level": _eval_price_level,
    "volume_spike": _eval_volume_spike,
    "whale_transfer": _eval_whale_transfer,
}


def evaluate_rule(rule: Rule, asset: AssetData) -> Trigger | None:
    fn = _EVALUATORS.get(rule.signal)
    if fn is None:
        return None
    try:
        return fn(rule, asset)
    except (KeyError, ValueError, TypeError):
        return None


def in_cooldown(
    rule: Rule, cooldowns: dict[str, str], now: datetime | None = None
) -> bool:
    last = cooldowns.get(rule.name)
    if not last:
        return False
    try:
        last_dt = datetime.fromisoformat(last)
    except ValueError:
        return False
    now = now or datetime.now(timezone.utc)
    return now - last_dt < timedelta(minutes=rule.cooldown_minutes)
