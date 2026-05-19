# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Setup (Python 3.12 to match CI)
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Tests
pytest -q                                  # full suite
pytest tests/test_rules.py -q              # one file
pytest tests/test_rules.py::test_rsi_oversold_triggers -q   # one test

# Run the analyzer locally
python -m analyzer.main --dry-run          # prints triggers as JSON, writes nothing, sends no email
python -m analyzer.main                    # full run: writes data/snapshot.json + state/*.json, may send email
```

`--dry-run` is the default mode for any local experimentation — the non-dry path mutates `data/` and `state/`, which are committed back to `main` by the cron workflow. Local writes there will be overwritten by the next Action.

Email sending requires `SMTP_USER` + `SMTP_APP_PASSWORD` in the env; without them, `analyzer.alerts.send_email` no-ops. Etherscan whale scans require `ETHERSCAN_API_KEY`.

## Architecture

This is a **serverless** crypto signal analyzer. There is no server, no database, no queue — everything is GitHub-native:

- `.github/workflows/analyze.yml` runs every 10 minutes (cron), executes `python -m analyzer.main`, then `git commit`s the resulting `data/snapshot.json` and `state/*.json` back to the branch. State is therefore versioned in git, not in any external store.
- `.github/workflows/pages.yml` watches `web/` and `data/` and republishes the PWA to GitHub Pages on each push.
- The PWA in `web/` is a static page that polls `./data/snapshot.json` every 60s — it has no knowledge of Python or the analyzer.

### Single-pass run in `analyzer/main.py`

`run()` is one linear pass each invocation:

1. Load `config/tokens.yml` and `config/rules.yml` (Pydantic-validated into `RulesConfig`).
2. `_fetch_assets`: CoinGecko quotes + 7d OHLC for every token, then `resample()` into 1h / 4h / 1d frames stored on `AssetData.frames`.
3. `_fetch_whales`: only runs if at least one rule has `signal: whale_transfer`. Pulls ERC-20 transfers via Etherscan for tokens with an `erc20:` address, or samples recent blocks for `native_eth: true`. Skips tokens with neither.
4. For each rule: check cooldown in `state/cooldowns.json`; call `evaluate_rule()`; if it returns a `Trigger`, write `now` into cooldowns.
5. `_build_snapshot` assembles `data/snapshot.json` with prices, last RSI/SMA, last 168h of 1h candles, and the last 20 alerts.
6. Persist all four state files; if anything triggered, format an email and call `alerts.send_email`.

### Rule evaluation (`analyzer/rules.py`)

Rules are plain dicts in YAML. Each `signal:` type maps to one private `_eval_<signal>` function via the `_EVALUATORS` dict at the bottom of `rules.py`. To add a new signal:

1. Write `_eval_<name>(rule, asset) -> Trigger | None`. Read params from `rule.params`, pull the right timeframe via `_frame_for(asset, p["timeframe"])`, return `None` if the data is insufficient (don't raise — `evaluate_rule` swallows `KeyError/ValueError/TypeError` to keep one bad rule from killing the run, but everything else propagates).
2. Register it in `_EVALUATORS`.
3. Document it in the header comment at the top of `config/rules.yml` and in the README's "Editing alert rules" section.

Timeframes: rules can request `1h`, `4h`, or `1d`. Only `1h` is fetched directly; `4h` and `1d` are resampled from `1h` (`coingecko.resample`). `price_change_pct`, `price_level`, `volume_spike` are hardcoded to the `1h` frame regardless of any `timeframe` param — see `_WINDOW_TO_BARS_1H` for the window → bar mapping.

Whale transfers can only fire for tokens that have `erc20:` or `native_eth: true` in `tokens.yml`. BTC, HYPE, and ATOM live on non-Ethereum chains and are intentionally skipped.

### State files (`state/`)

- `cooldowns.json` — `rule_name → ISO timestamp of last fire`. `in_cooldown` compares to `rule.cooldown_minutes`.
- `alerts.json` — rolling log, trimmed to last 100 entries in `state.save_alerts_log`.
- `seen_txs.json` — per-asset list of tx hashes already alerted on (trimmed to last 200). Prevents duplicate whale alerts across runs. **Newly-discovered transfers are added even when no rule fires** (see the loop in `main.py` after `_build_snapshot`), so the seen-set always reflects what was observed.

### External API quirks

- CoinGecko's `/coins/{id}/ohlc` endpoint returns no volume — volume is fetched separately from `/market_chart` and joined. Bar size varies by `days=` parameter (4h candles for `days >= 2`); the `resample()` call normalizes everything.
- Both source modules use `tenacity` retry with exponential backoff. CoinGecko 429s raise `CoinGeckoError` to trigger a retry rather than `raise_for_status`'ing.
- Etherscan returns `status: "0"` for "no transactions" — this is **not** an error and is special-cased in `_get`.

## Conventions

- Python 3.12, type hints with `from __future__ import annotations`. Dataclasses for runtime structures (`AssetData`, `Trigger`, `Quote`, `Transfer`), Pydantic only for the YAML config schema.
- Source-fetch failures must not abort the run. Wrap CoinGecko/Etherscan calls in try/except and `log.warning` — the analyzer is a cron job, so silent partial output beats a crashing workflow.
- `data/snapshot.json` and `state/*.json` are **bot-managed**. Don't hand-edit them; the next cron run will overwrite. To reset state, delete the file (the loaders default to empty).

## Unrelated subtree

`weakauras/AbolishPoisonTracker/` is a WoW Burning Crusade Classic WeakAura recipe (Lua snippets + README). It shares the repo for convenience but has nothing to do with the crypto analyzer — leave it alone unless explicitly asked.
