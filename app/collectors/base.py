"""Polite HTTP fetching: https-only, robots.txt aware, rate limited, bounded."""
from __future__ import annotations

import logging
import time
import urllib.robotparser
from dataclasses import dataclass, field
from urllib.parse import urlparse

import requests

from app.collectors.extraction import allowed_host
from app.config import settings

log = logging.getLogger(__name__)

_RETRY_STATUS = {429, 500, 502, 503, 504}


@dataclass
class FetchResult:
    url: str
    final_url: str
    status_code: int
    text: str = ""
    content_type: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    elapsed_ms: int = 0
    error: str | None = None
    skipped_reason: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.status_code < 400

    @property
    def is_html(self) -> bool:
        return "html" in (self.content_type or "").lower()


class HttpFetcher:
    """Small, synchronous fetcher shared by collectors.

    - https + approved government hosts only
    - robots.txt respected, cached per host
    - minimum delay per host
    - bounded response size and retries with backoff
    """

    def __init__(
        self,
        *,
        user_agent: str | None = None,
        timeout: int | None = None,
        max_bytes: int | None = None,
        host_delay: float | None = None,
        session: requests.Session | None = None,
    ) -> None:
        self.user_agent = user_agent or settings.user_agent
        self.timeout = timeout or settings.collector_http_timeout
        self.max_bytes = max_bytes or settings.collector_max_response_bytes
        self.host_delay = host_delay if host_delay is not None else settings.collector_host_delay_seconds
        self.session = session or requests.Session()
        self.session.headers.update(
            {"User-Agent": self.user_agent, "Accept": "text/html,application/xhtml+xml,application/pdf;q=0.8,*/*;q=0.5"}
        )
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
        self._last_request: dict[str, float] = {}
        self.requests_made = 0

    # -- policy helpers -------------------------------------------------
    def robots_for(self, url: str):
        host = (urlparse(url).hostname or "").lower()
        if host in self._robots:
            return self._robots[host]
        parser = urllib.robotparser.RobotFileParser()
        robots_url = f"https://{host}/robots.txt"
        try:
            response = self.session.get(robots_url, timeout=min(self.timeout, 10))
            if response.status_code < 400:
                parser.parse(response.text.splitlines())
            else:
                parser = None
        except requests.RequestException:
            parser = None
        self._robots[host] = parser
        return parser

    def allowed_by_robots(self, url: str) -> bool:
        parser = self.robots_for(url)
        if parser is None:
            return True
        try:
            return parser.can_fetch(self.user_agent, url)
        except Exception:
            return True

    def _respect_delay(self, host: str) -> None:
        last = self._last_request.get(host)
        if last is not None:
            wait = self.host_delay - (time.monotonic() - last)
            if wait > 0:
                time.sleep(min(wait, 5.0))
        self._last_request[host] = time.monotonic()

    # -- requests -------------------------------------------------------
    def _request(self, method: str, url: str, *, retries: int = 2, check_robots: bool = True) -> FetchResult:
        started = time.monotonic()
        if not allowed_host(url):
            return FetchResult(url, url, 0, error="Host is not an approved public government source", skipped_reason="host_not_allowed")
        if check_robots and not self.allowed_by_robots(url):
            return FetchResult(url, url, 0, error="robots.txt disallows automated access", skipped_reason="robots_disallowed")

        host = (urlparse(url).hostname or "").lower()
        last_error: str | None = None
        status_code = 0

        for attempt in range(retries + 1):
            self._respect_delay(host)
            try:
                self.requests_made += 1
                response = self.session.request(
                    method,
                    url,
                    timeout=(5, self.timeout),
                    allow_redirects=True,
                    stream=True,
                )
                status_code = response.status_code
                headers = {key.lower(): value for key, value in response.headers.items()}
                final_url = response.url
                if check_robots and urlparse(final_url).hostname != urlparse(url).hostname:
                    if not allowed_host(final_url) or not self.allowed_by_robots(final_url):
                        response.close()
                        return FetchResult(
                            url, final_url, status_code, headers=headers,
                            error="Redirected outside the approved public source policy",
                            skipped_reason="redirect_not_allowed",
                        )
                if status_code in _RETRY_STATUS and attempt < retries:
                    retry_after = headers.get("retry-after", "")
                    response.close()
                    time.sleep(min(int(retry_after) if retry_after.isdigit() else 2 ** attempt, 10))
                    continue

                text = ""
                if method == "GET" and "html" in headers.get("content-type", "").lower():
                    chunks: list[bytes] = []
                    size = 0
                    for chunk in response.iter_content(chunk_size=65_536):
                        size += len(chunk)
                        chunks.append(chunk)
                        if size >= self.max_bytes:
                            break
                    raw = b"".join(chunks)
                    encoding = response.encoding or "utf-8"
                    try:
                        text = raw.decode(encoding, errors="replace")
                    except (LookupError, UnicodeDecodeError):
                        text = raw.decode("utf-8", errors="replace")

                result = FetchResult(
                    url=url,
                    final_url=final_url,
                    status_code=status_code,
                    text=text,
                    content_type=headers.get("content-type", ""),
                    headers=headers,
                    elapsed_ms=int((time.monotonic() - started) * 1000),
                )
                if status_code >= 400:
                    result.error = f"HTTP {status_code}"
                response.close()
                return result
            except requests.RequestException as exc:
                last_error = str(exc)[:500]
                if attempt < retries:
                    time.sleep(1.5 * (attempt + 1))
                    continue
            finally:
                pass

        return FetchResult(
            url, url, status_code, error=last_error or "Request failed",
            elapsed_ms=int((time.monotonic() - started) * 1000),
        )

    def get(self, url: str, *, retries: int = 2, check_robots: bool = True) -> FetchResult:
        return self._request("GET", url, retries=retries, check_robots=check_robots)

    def head(self, url: str) -> FetchResult | None:
        result = self._request("HEAD", url, retries=1, check_robots=False)
        if result.status_code in {403, 405, 501}:
            # Some servers reject HEAD; a ranged GET is still tiny.
            result = self._request("GET", url, retries=1, check_robots=False)
        return result
