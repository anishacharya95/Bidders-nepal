"""Safe streaming proxy for public bid documents.

Documents are always served from their original public URL. The proxy exists so
the app can read PDFs in-app without redirecting to an external browser, and so
large files stream instead of being loaded into memory.

Safety rules (all enforced per request):
* HTTPS only; no credentials, no non-standard ports.
* The host must already be an approved public source, or an explicitly
  registered JSON feed host.
* The hostname must resolve only to public IP addresses (no loopback, private,
  link-local or reserved ranges) — this blocks SSRF against the platform.
* Redirects are followed manually and every hop is re-validated.
* Response size and content type are capped; anything else is offered as a
  plain download.
"""
from __future__ import annotations

import ipaddress
import logging
import socket
from dataclasses import dataclass
from urllib.parse import urlparse

import requests
from sqlalchemy.orm import Session

from app.collectors.extraction import allowed_host
from app.config import settings
from app.models import Source

log = logging.getLogger(__name__)

PREVIEWABLE_PREFIXES = (
    "application/pdf",
    "image/",
    "text/plain",
    "text/csv",
)
DOWNLOAD_ONLY_TYPES = {
    "application/msword": ".doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.ms-excel": ".xls",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "application/vnd.ms-powerpoint": ".ppt",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
    "application/zip": ".zip",
}

MAX_REDIRECTS = 3
BAD_PORTS = {22, 23, 25, 445, 1433, 3306, 5432, 6379, 9200, 11211}


class DocumentAccessError(RuntimeError):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


@dataclass
class StreamHandle:
    response: requests.Response
    content_type: str
    final_url: str
    content_length: int | None


def _is_public_address(value: str) -> bool:
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False
    return not (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    )


def host_is_public(host: str) -> tuple[bool, str | None]:
    """Resolve a hostname and confirm every address is public."""
    if not host:
        return False, "missing host"
    try:
        infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        return False, "host could not be resolved"
    addresses = {info[4][0] for info in infos if info[4]}
    if not addresses:
        return False, "host could not be resolved"
    for address in addresses:
        if not _is_public_address(address):
            return False, "host resolves to a non-public address"
    return True, None


def base_url_problem(url: str) -> str | None:
    """Return a human-readable reason when a URL must not be fetched."""
    parsed = urlparse(url or "")
    if parsed.scheme != "https":
        return "only HTTPS document URLs are streamed"
    if parsed.username or parsed.password:
        return "URLs with credentials are rejected"
    try:
        port = parsed.port
    except ValueError:
        return "invalid port"
    if port and port not in {443}:
        return "non-standard ports are rejected"
    if not parsed.hostname:
        return "missing host"
    return None


def permitted_feed_hosts(db: Session) -> set[str]:
    rows = (
        db.query(Source.tender_page_url)
        .filter(Source.collector_key == "json_api")
        .filter(Source.tender_page_url.isnot(None))
        .all()
    )
    hosts: set[str] = set()
    for (url,) in rows:
        host = (urlparse(url).hostname or "").lower()
        if host:
            hosts.add(host)
            hosts.add(host.removeprefix("www."))
    return hosts


def document_allowed(db: Session, url: str) -> tuple[bool, str | None]:
    problem = base_url_problem(url)
    if problem:
        return False, problem
    host = (urlparse(url).hostname or "").lower()
    if not (allowed_host(url) or host in permitted_feed_hosts(db)):
        return False, "document host is not an approved public source"
    public, reason = host_is_public(host)
    if not public:
        return False, reason
    return True, None


def _normalise_content_type(value: str | None) -> str:
    if not value:
        return "application/octet-stream"
    return value.split(";")[0].strip().lower() or "application/octet-stream"


def open_stream(url: str, *, range_header: str | None = None, head_only: bool = False) -> StreamHandle:
    """Open a streaming response, following redirects with re-validation."""
    db_hosts: set[str] = set()  # redirects may only stay on the validated host set
    method = "HEAD" if head_only else "GET"
    headers = {
        "User-Agent": settings.user_agent,
        "Accept": "application/pdf,application/octet-stream,image/*,*/*;q=0.8",
    }
    if range_header:
        headers["Range"] = range_header

    current = url
    original_host = (urlparse(url).hostname or "").lower()
    db_hosts.add(original_host)
    db_hosts.add(original_host.removeprefix("www."))

    for hop in range(MAX_REDIRECTS + 1):
        problem = base_url_problem(current)
        if problem:
            raise DocumentAccessError(problem, 403)
        host = (urlparse(current).hostname or "").lower()
        if not (allowed_host(current) or host in db_hosts):
            raise DocumentAccessError("redirect left the approved source host", 403)
        public, reason = host_is_public(host)
        if not public:
            raise DocumentAccessError(reason or "host is not public", 403)

        try:
            response = requests.request(
                method,
                current,
                headers=headers,
                stream=not head_only,
                allow_redirects=False,
                timeout=(settings.document_connect_timeout, settings.document_read_timeout),
            )
        except requests.RequestException as exc:
            raise DocumentAccessError(f"source did not respond: {exc.__class__.__name__}") from exc

        if response.status_code in {301, 302, 303, 307, 308} and response.headers.get("location"):
            location = response.headers["location"]
            response.close()
            if location.startswith("/"):
                parsed = urlparse(current)
                current = f"{parsed.scheme}://{parsed.netloc}{location}"
            elif location.startswith("https://"):
                current = location
            else:
                raise DocumentAccessError("source redirected to an unsupported URL", 403)
            continue

        content_type = _normalise_content_type(response.headers.get("content-type"))
        length_header = response.headers.get("content-length")
        content_length = int(length_header) if length_header and length_header.isdigit() else None
        if content_length and content_length > settings.document_max_stream_bytes:
            response.close()
            raise DocumentAccessError("document is too large to stream", 413)
        return StreamHandle(
            response=response,
            content_type=content_type,
            final_url=current,
            content_length=content_length,
        )

    raise DocumentAccessError("too many redirects", 508)


def iter_response(handle: StreamHandle, max_bytes: int | None = None):
    """Yield the upstream body in chunks without buffering it in memory."""
    limit = max_bytes or settings.document_max_stream_bytes
    sent = 0
    try:
        for chunk in handle.response.iter_content(chunk_size=64 * 1024):
            if not chunk:
                continue
            sent += len(chunk)
            if sent > limit:
                log.warning("Document stream exceeded %s bytes; truncating", limit)
                break
            yield chunk
    finally:
        handle.response.close()


def is_previewable(content_type: str | None, file_format: str | None = None) -> bool:
    value = (content_type or "").lower()
    if any(value.startswith(prefix) for prefix in PREVIEWABLE_PREFIXES):
        return True
    return (file_format or "").upper() in {"PDF", "JPG", "JPEG", "PNG", "TXT", "CSV"}
