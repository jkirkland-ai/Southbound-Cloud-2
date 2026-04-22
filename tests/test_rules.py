from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from analyzer.rules import AssetData, Rule, evaluate_rule, in_cooldown


def _asset_with_close(closes: list[float], vols: list[float] | None = None) -> AssetData:
    idx = pd.date_range(end="2026-04-22", periods=len(closes), freq="1h", tz="UTC")
    vols = vols or [1.0] * len(closes)
    df = pd.DataFrame(
        {
            "open": closes,
            "high": closes,
            "low": closes,
            "close": closes,
            "volume": vols,
        },
        index=idx,
    )
    return AssetData(
        symbol="TEST",
        price_now=closes[-1],
        change_24h_pct=0.0,
        volume_24h_usd=0.0,
        frames={"1h": df},
    )


def test_price_change_pct_drop_triggers():
    closes = [100.0] * 10 + [94.0]
    asset = _asset_with_close(closes)
    rule = Rule(
        name="drop",
        asset="TEST",
        signal="price_change_pct",
        params={"window": "1h", "threshold": -5},
    )
    t = evaluate_rule(rule, asset)
    assert t is not None
    assert "-6" in t.message or "-6.00" in t.message


def test_price_change_pct_no_trigger():
    closes = [100.0] * 10 + [99.0]
    asset = _asset_with_close(closes)
    rule = Rule(
        name="drop",
        asset="TEST",
        signal="price_change_pct",
        params={"window": "1h", "threshold": -5},
    )
    assert evaluate_rule(rule, asset) is None


def test_volume_spike_triggers():
    vols = [1.0] * 30 + [10.0]
    closes = [100.0] * 31
    asset = _asset_with_close(closes, vols)
    rule = Rule(
        name="vol",
        asset="TEST",
        signal="volume_spike",
        params={"lookback_hours": 24, "multiplier": 3},
    )
    t = evaluate_rule(rule, asset)
    assert t is not None and "10.0x" in t.message


def test_rsi_oversold_triggers():
    closes = list(np.linspace(200, 100, 60))  # strictly falling → RSI low
    asset = _asset_with_close(closes)
    rule = Rule(
        name="rsi",
        asset="TEST",
        signal="rsi",
        params={"period": 14, "threshold": 30, "direction": "below", "timeframe": "1h"},
    )
    t = evaluate_rule(rule, asset)
    assert t is not None


def test_whale_transfer_respects_min_usd():
    asset = AssetData(symbol="TEST", price_now=10.0, change_24h_pct=0, volume_24h_usd=0)
    asset.whale_transfers = [
        {"tx_hash": "0xaa", "amount": 1.0, "usd_value": 100_000},
        {"tx_hash": "0xbb", "amount": 5.0, "usd_value": 600_000},
    ]
    rule = Rule(
        name="whale",
        asset="TEST",
        signal="whale_transfer",
        params={"min_usd": 500_000},
    )
    t = evaluate_rule(rule, asset)
    assert t is not None and "0xbb" in t.message


def test_cooldown_blocks_refire():
    rule = Rule(name="r", asset="X", signal="rsi", cooldown_minutes=60)
    now = datetime.now(timezone.utc)
    cds = {"r": (now - timedelta(minutes=5)).isoformat()}
    assert in_cooldown(rule, cds, now) is True

    cds = {"r": (now - timedelta(minutes=120)).isoformat()}
    assert in_cooldown(rule, cds, now) is False
