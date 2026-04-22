from __future__ import annotations

import numpy as np
import pandas as pd


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Wilder RSI. Returns NaN for the first `period` bars."""
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    # Wilder smoothing = EMA with alpha = 1/period
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    out = 100 - (100 / (1 + rs))
    # If avg_loss is 0 the series is strictly non-decreasing → RSI 100.
    out = out.where(avg_loss != 0, 100.0)
    return out


def sma(close: pd.Series, period: int) -> pd.Series:
    return close.rolling(period, min_periods=period).mean()


def ema(close: pd.Series, period: int) -> pd.Series:
    return close.ewm(span=period, adjust=False, min_periods=period).mean()


def macd(
    close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> pd.DataFrame:
    macd_line = ema(close, fast) - ema(close, slow)
    signal_line = macd_line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    return pd.DataFrame(
        {
            "macd": macd_line,
            "signal": signal_line,
            "hist": macd_line - signal_line,
        }
    )


def bollinger(
    close: pd.Series, period: int = 20, stddev: float = 2.0
) -> pd.DataFrame:
    mid = close.rolling(period, min_periods=period).mean()
    std = close.rolling(period, min_periods=period).std(ddof=0)
    return pd.DataFrame(
        {"mid": mid, "upper": mid + stddev * std, "lower": mid - stddev * std}
    )


def crossed_above(a: pd.Series, b: pd.Series) -> bool:
    """True iff `a` crossed above `b` on the last bar."""
    if len(a) < 2 or len(b) < 2:
        return False
    prev = a.iloc[-2] - b.iloc[-2]
    cur = a.iloc[-1] - b.iloc[-1]
    if pd.isna(prev) or pd.isna(cur):
        return False
    return bool(prev <= 0 < cur)


def crossed_below(a: pd.Series, b: pd.Series) -> bool:
    if len(a) < 2 or len(b) < 2:
        return False
    prev = a.iloc[-2] - b.iloc[-2]
    cur = a.iloc[-1] - b.iloc[-1]
    if pd.isna(prev) or pd.isna(cur):
        return False
    return bool(prev >= 0 > cur)


def pct_change_over(close: pd.Series, bars: int) -> float | None:
    """Percent change from `bars` ago to now. None if insufficient data."""
    if len(close) <= bars:
        return None
    now = close.iloc[-1]
    then = close.iloc[-1 - bars]
    if pd.isna(now) or pd.isna(then) or then == 0:
        return None
    return (now - then) / then * 100.0


def volume_ratio(volume: pd.Series, lookback: int) -> float | None:
    """Latest bar's volume divided by mean of previous `lookback` bars."""
    if len(volume) <= lookback:
        return None
    recent = float(volume.iloc[-1])
    baseline = float(volume.iloc[-1 - lookback : -1].mean())
    if baseline <= 0:
        return None
    return recent / baseline
