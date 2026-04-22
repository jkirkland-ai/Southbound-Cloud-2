from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import requests
from tenacity import retry, stop_after_attempt, wait_exponential_jitter

BASE = "https://api.etherscan.io/api"


class EtherscanError(RuntimeError):
    pass


@dataclass
class Transfer:
    tx_hash: str
    timestamp: int  # unix seconds
    from_addr: str
    to_addr: str
    amount: float  # human units (accounting for decimals)
    symbol: str


@retry(stop=stop_after_attempt(4), wait=wait_exponential_jitter(initial=2, max=30))
def _get(params: dict[str, Any]) -> Any:
    key = os.environ.get("ETHERSCAN_API_KEY", "")
    params = {**params, "apikey": key}
    r = requests.get(BASE, params=params, timeout=30)
    r.raise_for_status()
    body = r.json()
    # status "0" with message "No transactions found" is not an error
    if body.get("status") == "0" and body.get("message") not in (
        "No transactions found",
        "No records found",
    ):
        raise EtherscanError(body.get("result") or body.get("message", "unknown"))
    return body.get("result", [])


def fetch_erc20_transfers(
    contract_address: str,
    *,
    lookback_blocks: int = 6000,  # ~20h at 12s blocks
    limit: int = 100,
) -> list[Transfer]:
    """Recent ERC-20 transfer events for a given token contract."""
    # Get current block, then fetch transfers within lookback window.
    latest_hex = _get({"module": "proxy", "action": "eth_blockNumber"})
    try:
        latest = int(latest_hex, 16) if isinstance(latest_hex, str) else int(latest_hex)
    except (TypeError, ValueError):
        return []
    start_block = max(0, latest - lookback_blocks)

    rows = _get(
        {
            "module": "account",
            "action": "tokentx",
            "contractaddress": contract_address,
            "startblock": start_block,
            "endblock": latest,
            "page": 1,
            "offset": limit,
            "sort": "desc",
        }
    )
    if not isinstance(rows, list):
        return []

    out: list[Transfer] = []
    for r in rows:
        try:
            decimals = int(r.get("tokenDecimal", "18"))
            raw = int(r.get("value", "0"))
            amount = raw / (10**decimals)
        except (TypeError, ValueError):
            continue
        out.append(
            Transfer(
                tx_hash=r.get("hash", ""),
                timestamp=int(r.get("timeStamp", "0")),
                from_addr=r.get("from", ""),
                to_addr=r.get("to", ""),
                amount=amount,
                symbol=r.get("tokenSymbol", "") or "",
            )
        )
    return out


def fetch_native_eth_transfers(
    *,
    min_value_eth: float = 100.0,
    lookback_blocks: int = 300,  # native ETH list is expensive; keep tight
    limit: int = 100,
) -> list[Transfer]:
    """
    Large native-ETH transfers. Etherscan's free API cannot efficiently
    stream all block transactions, so we sample the latest N blocks via
    eth_getBlockByNumber and filter by value. Best-effort.
    """
    latest_hex = _get({"module": "proxy", "action": "eth_blockNumber"})
    try:
        latest = int(latest_hex, 16) if isinstance(latest_hex, str) else int(latest_hex)
    except (TypeError, ValueError):
        return []

    out: list[Transfer] = []
    # Only scan a small number of recent blocks to stay within free-tier limits.
    scan = min(lookback_blocks, 25)
    for i in range(scan):
        tag = hex(latest - i)
        block = _get(
            {
                "module": "proxy",
                "action": "eth_getBlockByNumber",
                "tag": tag,
                "boolean": "true",
            }
        )
        if not isinstance(block, dict):
            continue
        txs = block.get("transactions") or []
        ts = int(block.get("timestamp", "0x0"), 16)
        for tx in txs:
            try:
                value_wei = int(tx.get("value", "0x0"), 16)
            except (TypeError, ValueError):
                continue
            value_eth = value_wei / 1e18
            if value_eth >= min_value_eth:
                out.append(
                    Transfer(
                        tx_hash=tx.get("hash", ""),
                        timestamp=ts,
                        from_addr=tx.get("from", "") or "",
                        to_addr=tx.get("to", "") or "",
                        amount=value_eth,
                        symbol="ETH",
                    )
                )
                if len(out) >= limit:
                    return out
    return out
