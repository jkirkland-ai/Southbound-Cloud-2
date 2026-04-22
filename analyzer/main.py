from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yaml

from . import alerts, state
from .rules import AssetData, RulesConfig, Trigger, evaluate_rule, in_cooldown
from .sources import coingecko, etherscan

log = logging.getLogger("analyzer")

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
TIMEFRAMES = ("1h", "4h", "1d")


def _load_tokens() -> list[dict]:
    data = yaml.safe_load((CONFIG_DIR / "tokens.yml").read_text())
    return data.get("tokens", [])


def _load_rules() -> RulesConfig:
    data = yaml.safe_load((CONFIG_DIR / "rules.yml").read_text())
    return RulesConfig(**data)


def _fetch_assets(tokens: list[dict]) -> dict[str, AssetData]:
    ids = [t["coingecko_id"] for t in tokens if t.get("coingecko_id")]
    quotes = coingecko.fetch_quotes(ids)

    assets: dict[str, AssetData] = {}
    for tok in tokens:
        cid = tok.get("coingecko_id")
        q = quotes.get(cid) if cid else None
        if not q:
            log.warning("no quote for %s", tok["symbol"])
            continue

        try:
            ohlc = coingecko.fetch_ohlc(cid, days=7)
        except Exception as e:  # noqa: BLE001 -- source errors should not abort run
            log.warning("ohlc fetch failed for %s: %s", tok["symbol"], e)
            ohlc = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

        frames = {}
        if not ohlc.empty:
            for tf in TIMEFRAMES:
                rs = coingecko.resample(ohlc, tf)
                if not rs.empty:
                    frames[tf] = rs

        assets[tok["symbol"]] = AssetData(
            symbol=tok["symbol"],
            price_now=q.price_usd,
            change_24h_pct=q.change_24h_pct,
            volume_24h_usd=q.volume_24h_usd,
            frames=frames,
        )
    return assets


def _fetch_whales(
    tokens: list[dict], assets: dict[str, AssetData], seen: dict[str, list[str]]
) -> None:
    """Populate asset.whale_transfers with unseen ERC-20 / native ETH transfers."""
    for tok in tokens:
        symbol = tok["symbol"]
        a = assets.get(symbol)
        if not a:
            continue

        transfers = []
        try:
            if tok.get("native_eth"):
                # Only trigger large ETH if there's a rule wanting it; we still
                # scan, since the rule evaluator checks min_usd.
                min_eth = 50.0  # ~ $150k+ at typical prices — cheap filter
                transfers = etherscan.fetch_native_eth_transfers(
                    min_value_eth=min_eth
                )
            elif tok.get("erc20"):
                transfers = etherscan.fetch_erc20_transfers(tok["erc20"])
        except Exception as e:  # noqa: BLE001
            log.warning("etherscan fetch failed for %s: %s", symbol, e)
            continue

        seen_list = set(seen.get(symbol, []))
        whales = []
        for t in transfers:
            if t.tx_hash in seen_list:
                continue
            usd = t.amount * a.price_now
            whales.append(
                {
                    "tx_hash": t.tx_hash,
                    "timestamp": t.timestamp,
                    "from": t.from_addr,
                    "to": t.to_addr,
                    "amount": t.amount,
                    "usd_value": usd,
                }
            )
        a.whale_transfers = whales


def _build_snapshot(
    assets: dict[str, AssetData], recent_alerts: list[dict], generated_at: str
) -> dict:
    from .indicators import rsi, sma

    snap = {"generated_at": generated_at, "assets": {}, "recent_alerts": recent_alerts[-20:]}

    for symbol, a in assets.items():
        entry: dict = {
            "price_usd": a.price_now,
            "change_24h_pct": a.change_24h_pct,
            "volume_24h_usd": a.volume_24h_usd,
            "indicators": {},
            "candles_1h": [],
        }
        df = a.frames.get("1h")
        if df is not None and not df.empty:
            try:
                last_rsi = rsi(df["close"], 14).iloc[-1]
                entry["indicators"]["rsi14_1h"] = (
                    None if pd.isna(last_rsi) else float(last_rsi)
                )
                for n in (20, 50):
                    last_sma = sma(df["close"], n).iloc[-1]
                    entry["indicators"][f"sma{n}_1h"] = (
                        None if pd.isna(last_sma) else float(last_sma)
                    )
            except Exception:  # noqa: BLE001
                pass
            tail = df.tail(168)  # ~ last 7 days of 1h candles
            entry["candles_1h"] = [
                {
                    "t": int(ts.timestamp()),
                    "o": float(row.open),
                    "h": float(row.high),
                    "l": float(row.low),
                    "c": float(row.close),
                    "v": float(row.volume),
                }
                for ts, row in tail.iterrows()
            ]
        snap["assets"][symbol] = entry
    return snap


def run(dry_run: bool = False) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    now = datetime.now(timezone.utc)
    generated_at = now.isoformat(timespec="seconds").replace("+00:00", "Z")

    tokens = _load_tokens()
    rules_cfg = _load_rules()

    log.info("fetching quotes / OHLC for %d tokens", len(tokens))
    assets = _fetch_assets(tokens)

    # Only look for whales if at least one rule needs them.
    needs_whales = any(r.signal == "whale_transfer" for r in rules_cfg.rules)
    seen_txs = state.load_seen_tx_hashes()
    if needs_whales:
        log.info("scanning on-chain transfers")
        _fetch_whales(tokens, assets, seen_txs)

    cooldowns = state.load_cooldowns()
    triggers: list[Trigger] = []
    for rule in rules_cfg.rules:
        a = assets.get(rule.asset)
        if not a:
            continue
        if in_cooldown(rule, cooldowns, now):
            continue
        t = evaluate_rule(rule, a)
        if t:
            triggers.append(t)
            cooldowns[rule.name] = generated_at

    alerts_log = state.load_alerts_log()
    new_entries = [
        {"ts": generated_at, "rule": t.rule_name, "asset": t.asset, "message": t.message}
        for t in triggers
    ]
    alerts_log.extend(new_entries)

    # Record whale tx hashes so we don't re-alert on the same transfer.
    for symbol, a in assets.items():
        if a.whale_transfers:
            seen_txs.setdefault(symbol, []).extend(
                tx["tx_hash"] for tx in a.whale_transfers if tx.get("tx_hash")
            )

    snapshot = _build_snapshot(assets, alerts_log, generated_at)

    log.info("%d trigger(s); dry_run=%s", len(triggers), dry_run)
    for t in triggers:
        log.info("  trigger [%s] %s: %s", t.asset, t.rule_name, t.message)

    if dry_run:
        # print a compact summary and bail without writing state
        import json

        print(json.dumps({"generated_at": generated_at, "triggers": new_entries}, indent=2))
        return 0

    state.save_snapshot(snapshot)
    state.save_cooldowns(cooldowns)
    state.save_alerts_log(alerts_log)
    state.save_seen_tx_hashes(seen_txs)

    if triggers and rules_cfg.alert_email:
        subject, body = alerts.format_alert_email(new_entries, generated_at)
        ok = alerts.send_email(rules_cfg.alert_email, subject, body)
        log.info("email to %s: %s", rules_cfg.alert_email, "sent" if ok else "FAILED")

    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="Skip writing state / emails")
    args = ap.parse_args(argv)
    return run(dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
