from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = ROOT / "state"
DATA_DIR = ROOT / "data"


def _load(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return default


def _save(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, default=str))


def load_cooldowns() -> dict[str, str]:
    """Maps rule name -> ISO timestamp of last fire."""
    return _load(STATE_DIR / "cooldowns.json", {})


def save_cooldowns(data: dict[str, str]) -> None:
    _save(STATE_DIR / "cooldowns.json", data)


def load_alerts_log() -> list[dict]:
    return _load(STATE_DIR / "alerts.json", [])


def save_alerts_log(entries: list[dict], keep: int = 100) -> None:
    _save(STATE_DIR / "alerts.json", entries[-keep:])


def save_snapshot(snapshot: dict) -> None:
    _save(DATA_DIR / "snapshot.json", snapshot)


def load_seen_tx_hashes() -> dict[str, list[str]]:
    """Per-asset list of tx hashes we've already alerted on."""
    return _load(STATE_DIR / "seen_txs.json", {})


def save_seen_tx_hashes(data: dict[str, list[str]], keep_per_asset: int = 200) -> None:
    trimmed = {k: v[-keep_per_asset:] for k, v in data.items()}
    _save(STATE_DIR / "seen_txs.json", trimmed)
