# Crypto Chart Analyzer

A serverless analyzer that watches a basket of crypto tokens, computes
technical + on-chain signals, emails opportunity alerts, and publishes a
mobile-friendly PWA dashboard from GitHub Pages.

**Watched:** BTC · ETH · BIO · HYPE · ONDO · ATOM
**Alerts to:** email (configurable in `config/rules.yml`)

No always-on server. Everything runs from GitHub:

- A cron-driven Actions workflow runs the analyzer every ~10 minutes.
- Snapshots are committed back to the repo.
- A second workflow publishes `web/` + `data/snapshot.json` to GitHub Pages.

## Setup (mobile-friendly)

All steps work from github.com on a phone.

### 1. Create the required secrets

Settings → *Secrets and variables* → *Actions* → *New repository secret*:

| Name                 | Value                                                                 |
|----------------------|------------------------------------------------------------------------|
| `ETHERSCAN_API_KEY`  | Free key from https://etherscan.io/myapikey                           |
| `SMTP_USER`          | Gmail address that will send the alerts                                |
| `SMTP_APP_PASSWORD`  | [Gmail app password](https://myaccount.google.com/apppasswords)       |
| `SMTP_HOST` *(opt.)* | Defaults to `smtp.gmail.com`                                           |
| `SMTP_PORT` *(opt.)* | Defaults to `587`                                                      |
| `SMTP_FROM` *(opt.)* | Defaults to `SMTP_USER`                                                |

Tip: If you don't use Gmail, any SMTP provider works — set `SMTP_HOST`/`SMTP_PORT`
accordingly.

### 2. Enable GitHub Pages

Settings → *Pages* → Source: **GitHub Actions**.

### 3. Kick off the first run

Actions tab → *analyze* workflow → **Run workflow** (on the branch you want).
After it completes, a `data/snapshot.json` is committed and the *pages*
workflow publishes the dashboard.

### 4. Add the dashboard to your home screen

Open the Pages URL on your phone → browser menu → *Add to Home Screen*.
The PWA updates every 60 seconds when visible.

## Editing alert rules

`config/rules.yml` is the one file you'll change most often. Edit it on
github.com (pencil icon → commit), and the next scheduled run picks it up.

Supported `signal` types:

- `rsi` – `period`, `threshold`, `direction` (`above`/`below`), `timeframe` (`1h`/`4h`/`1d`)
- `macd_cross` – `direction` (`bullish`/`bearish`), `timeframe`
- `sma_cross` – `fast`, `slow`, `direction`, `timeframe`
- `bollinger_break` – `period`, `stddev`, `direction`, `timeframe`
- `price_change_pct` – `window` (`1h`/`4h`/`24h`/`7d`), `threshold` (percent; negative = drop)
- `price_level` – `level`, `direction`
- `volume_spike` – `lookback_hours`, `multiplier`
- `whale_transfer` – `min_usd` *(ETH, BIO, ONDO only in v1)*

Every rule may set `cooldown_minutes` to avoid repeated firings.

## Local development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest
python -m analyzer.main --dry-run
```

`--dry-run` prints triggered rules as JSON without writing state or sending email.

## Architecture

```
GitHub Actions (cron every 10m)
  └─ analyzer/main.py
       ├─ CoinGecko  : quotes + OHLCV for all tokens
       ├─ Etherscan  : ERC-20 token transfers + sampled large ETH txs
       ├─ indicators : RSI, MACD, SMA, Bollinger, volume ratio
       ├─ rules      : evaluates rules.yml against the data
       ├─ alerts     : SMTP email sender (honours cooldowns)
       └─ state      : commits data/snapshot.json + state/*.json

GitHub Pages (pages.yml)
  └─ web/ + data/snapshot.json  →  PWA dashboard with live charts
```

### Layout

```
analyzer/            Python package (sources, indicators, rules, alerts, state, main)
config/              tokens.yml + rules.yml (user-editable)
data/snapshot.json   latest state; consumed by the PWA
state/*.json         cooldowns, alert log, seen whale tx hashes
web/                 static PWA (published to Pages)
tests/               pytest suite (indicators, rules)
.github/workflows/   analyze.yml (cron) + pages.yml (deploy)
```

## Notes and limits

- **Coverage:** BTC, HYPE, and ATOM live on non-Ethereum chains, so
  whale-transfer rules only evaluate for ETH / BIO / ONDO.
- **Free-tier APIs:** CoinGecko public endpoints (no key) and Etherscan free
  tier. The analyzer backs off gracefully on 429s.
- **Email:** SMTP from inside the Action. Gmail requires an app password.
  No SendGrid/Twilio account needed.
- **Data freshness:** 10-minute cron is the minimum GitHub Actions guarantees;
  actual runs can lag 2–5 minutes at times.
