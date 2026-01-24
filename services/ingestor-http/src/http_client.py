from dataclasses import dataclass
import time
import requests


@dataclass(frozen=True)
class HttpResult:
    status: int
    content: bytes
    content_type: str
    duration_ms: int
    rate_limit_remaining: int | None


def fetch_once(url: str, timeout_seconds: int) -> HttpResult:
    started = time.perf_counter()
    resp = requests.get(url, timeout=timeout_seconds)
    duration_ms = int((time.perf_counter() - started) * 1000)

    content_type = resp.headers.get("Content-Type", "application/json")
    rlr = resp.headers.get("X-RateLimit-Remaining")
    rate_limit_remaining = int(rlr) if (rlr is not None and rlr.isdigit()) else None

    # For Day 4 you want "fail fast" if not 2xx
    resp.raise_for_status()

    return HttpResult(
        status=resp.status_code,
        content=resp.content,
        content_type=content_type,
        duration_ms=duration_ms,
        rate_limit_remaining=rate_limit_remaining,
    )
