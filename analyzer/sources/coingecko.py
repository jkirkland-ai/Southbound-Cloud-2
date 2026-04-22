from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd
import requests
from tenacity import retry, stop_after_attempt, wait_exponential_jitter

BASE = "https://api.coingecko.com/api/v3"
USER_AGENT = "southbound-cloud-analyzer/1.0"


class CoinGeckoError(RuntimeError):
    pass


@dataclass
class Quote:
    price_usd: float
    change_24h_pct: float
    volume_24h_usd: float
    market_cap_usd: float


@retry(stop=stop_after_attempt(4), wait=wait_exponential_jitter(initial=2, max=30))
def _get(path: str, params: dict[str, Any] | None = None) -> Any:
    r = requests.get(
        f"{BASE}{path}",
        params=params or {},
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        timeout=30,
    )
    if r.status_code == 429:
        raise CoinGeckoError("rate limited")
    r.raise_for_status()
    return r.json()


def fetch_quotes(coingecko_ids: list[str]) -> dict[str, Quote]:
    """Batch price+volume+24h change for a list of coingecko ids."""
    if not coingecko_ids:
        return {}
    data = _get(
        "/simple/price",
        {
            "ids": ",".join(coingecko_ids),
            "vs_currencies": "usd",
            "include_24hr_change": "true",
            "include_24hr_vol": "true",
            "include_market_cap": "true",
        },
    )
    out: dict[str, Quote] = {}
    for cid in coingecko_ids:
        row = data.get(cid)
        if not row:
            continue
        out[cid] = Quote(
            price_usd=float(row.get("usd", 0.0)),
            change_24h_pct=float(row.get("usd_24h_change", 0.0) or 0.0),
            volume_24h_usd=float(row.get("usd_24h_vol", 0.0) or 0.0),
            market_cap_usd=float(row.get("usd_market_cap", 0.0) or 0.0),
        )
    return out


def fetch_ohlc(coingecko_id: str, days: int = 7) -> pd.DataFrame:
    """
    Hourly-ish OHLC. CoinGecko's /coins/{id}/ohlc returns 4h candles for
    days>=2 and 30-min candles for 1d. We combine this with /market_chart
    for volume (OHLC endpoint does not include volume).
    """
    ohlc = _get(f"/coins/{coingecko_id}/ohlc", {"vs_currency": "usd", "days": days})
    if not ohlc:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

    df = pd.DataFrame(ohlc, columns=["ts_ms", "open", "high", "low", "close"])
    df["ts"] = pd.to_datetime(df["ts_ms"], unit="ms", utc=True)
    df = df.set_index("ts").drop(columns=["ts_ms"]).astype(float)

    mkt = _get(
        f"/coins/{coingecko_id}/market_chart",
        {"vs_currency": "usd", "days": days},
    )
    vol = pd.DataFrame(mkt.get("total_volumes", []), columns=["ts_ms", "volume"])
    if not vol.empty:
        vol["ts"] = pd.to_datetime(vol["ts_ms"], unit="ms", utc=True)
        vol = vol.set_index("ts").drop(columns=["ts_ms"]).astype(float)
        df = df.join(vol, how="left")
        df["volume"] = df["volume"].ffill().fillna(0.0)
    else:
        df["volume"] = 0.0

    return df.sort_index()


def resample(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    """Resample an OHLCV frame to a new bar size (e.g. '1h', '4h', '1d')."""
    if df.empty:
        return df
    agg = {
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }
    return df.resample(rule).agg(agg).dropna(subset=["close"])
