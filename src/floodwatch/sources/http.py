"""HTTP GET with an on-disk cache and polite retries.

Free APIs such as Open-Meteo rate-limit by address, and a shared address can
already be near its limit, so 429 responses are retried with long waits.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

import requests

USER_AGENT = "floodwatch-research/0.1 (open-data flood early warning prototype)"


def cached_get_json(
    url: str,
    params: dict[str, Any],
    cache_dir: Path,
    *,
    max_attempts: int = 8,
    first_wait: float = 30.0,
    timeout: float = 120.0,
) -> Any:
    """Return the JSON body for ``url`` with ``params``, using a file cache."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(
        json.dumps([url, sorted(params.items())], default=str).encode()
    ).hexdigest()[:24]
    path = cache_dir / f"{key}.json"
    if path.exists():
        return json.loads(path.read_text())

    wait = first_wait
    last_error: str | None = None
    for _attempt in range(max_attempts):
        try:
            resp = requests.get(
                url, params=params, timeout=timeout, headers={"User-Agent": USER_AGENT}
            )
        except requests.RequestException as exc:  # network hiccup: retry
            last_error = str(exc)
        else:
            if resp.status_code == 200:
                body = resp.json()
                path.write_text(json.dumps(body))
                return body
            last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
            if resp.status_code not in (429, 500, 502, 503, 504):
                break
        time.sleep(wait)
        wait = min(wait * 2, 600)
    raise RuntimeError(f"GET {url} failed: {last_error}")
