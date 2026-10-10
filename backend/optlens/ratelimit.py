"""Per-client sliding-window rate limiter and client-IP resolution."""

from __future__ import annotations

import ipaddress
import time
from collections import deque
from collections.abc import Callable, Iterable


class RateLimiter:
    def __init__(
        self, limit: int, window_s: float, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self.limit = limit
        self.window_s = window_s
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}

    def check(self, key: str) -> float | None:
        """Record a hit. Return None if allowed, else seconds until the next slot frees."""
        now = self._clock()
        hits = self._hits.setdefault(key, deque())
        while hits and now - hits[0] >= self.window_s:
            hits.popleft()
        if len(hits) >= self.limit:
            return max(0.0, self.window_s - (now - hits[0]))
        hits.append(now)
        if len(self._hits) > 10_000:  # bound memory: forget idle clients
            for k in [k for k, v in self._hits.items() if not v or now - v[-1] >= self.window_s]:
                del self._hits[k]
        return None


def _is_trusted(host: str, trusted: Iterable[str]) -> bool:
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        return False
    for entry in trusted:
        try:
            if addr in ipaddress.ip_network(entry, strict=False):
                return True
        except ValueError:
            continue
    return False


def client_ip(peer: str | None, forwarded_for: str | None, trusted: Iterable[str]) -> str:
    """Honour X-Forwarded-For only when the direct peer is a trusted proxy, and then
    take the right-most address that is not itself a trusted proxy."""
    peer = peer or "unknown"
    trusted = tuple(trusted)
    if not forwarded_for or not _is_trusted(peer, trusted):
        return peer
    for hop in reversed([h.strip() for h in forwarded_for.split(",") if h.strip()]):
        if not _is_trusted(hop, trusted):
            return hop
    return peer
