"""Document endpoints: metadata, availability, in-app preview and download.

Every response is derived from a real document row and its original public URL.
Nothing here fabricates a file: when the source is unreachable the API says so
with a status the app can display, instead of returning a blank page.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Tender, TenderDocument
from app.services import document_proxy
from app.services.documents import file_format
from app.schemas import TenderDocumentOut

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _load(db: Session, document_id: int) -> tuple[TenderDocument, Tender]:
    document = db.get(TenderDocument, document_id)
    if not document or not document.is_public:
        raise HTTPException(status_code=404, detail="Document not found")
    tender = db.get(Tender, document.tender_id)
    if not tender or tender.verification_status == "rejected":
        raise HTTPException(status_code=404, detail="Document not found")
    return document, tender


def _safe_filename(label: str, url: str, content_type: str | None) -> str:
    base = (label or urlparse(url).path.rsplit("/", 1)[-1] or "bid-document").strip()
    suffix = ""
    fmt = file_format(url)
    if fmt:
        suffix = f".{fmt.lower()}"
    elif content_type in document_proxy.DOWNLOAD_ONLY_TYPES:
        suffix = document_proxy.DOWNLOAD_ONLY_TYPES[content_type]
    base = re.sub(r"\.(pdf|docx?|xlsx?|zip|rar|7z|dwg|jpe?g|png)$", "", base, flags=re.I)
    base = re.sub(r"[^\w\u0900-\u097F\- ]+", "", base).strip().replace(" ", "-")[:80]
    return f"{base or 'bid-document'}{suffix or '.pdf'}"


_HASH_LABEL = re.compile(r"^[0-9a-f]{24,}$", re.IGNORECASE)


def display_label(label: str | None, url: str) -> str:
    """Some feeds publish a hash as the attachment title; show a real label."""
    value = (label or "").strip()
    if not value or _HASH_LABEL.match(value):
        return "Bid document"
    return value


def _document_payload(document: TenderDocument, tender: Tender) -> dict:
    payload = TenderDocumentOut.model_validate(document).model_dump(mode="json")
    payload["label"] = display_label(document.label, document.url)
    payload.update(
        {
            "tender_id": tender.id,
            "tender_title": tender.title,
            "tender_notice_number": tender.notice_number,
            "source_name": tender.source_name,
            "original_url": document.url,
            "preview_url": f"/api/v1/documents/{document.id}/preview",
            "download_url": f"/api/v1/documents/{document.id}/download",
            "viewer_url": f"/api/v1/documents/{document.id}/viewer",
            "previewable": document_proxy.is_previewable(document.content_type, document.file_format),
            "availability": (
                "available"
                if document.is_available
                else "unavailable"
                if document.is_available is False
                else document.download_status or "unverified"
            ),
        }
    )
    return payload


def _probe(document: TenderDocument, db: Session) -> None:
    """HEAD the original URL and store the real result."""
    allowed, reason = document_proxy.document_allowed(db, document.url)
    if not allowed:
        document.download_status = "restricted"
        document.is_available = False
        document.last_checked_at = _now()
        document.checked_count = (document.checked_count or 0) + 1
        db.commit()
        return
    try:
        handle = document_proxy.open_stream(document.url, head_only=True)
    except document_proxy.DocumentAccessError as exc:
        document.download_status = "failed"
        document.is_available = False
        document.last_checked_at = _now()
        document.checked_count = (document.checked_count or 0) + 1
        document.http_status = None
        db.commit()
        log.info("Document %s unreachable: %s", document.id, exc)
        return

    status_code = handle.response.status_code
    handle.response.close()
    document.http_status = status_code
    document.last_checked_at = _now()
    document.checked_count = (document.checked_count or 0) + 1
    if 200 <= status_code < 400:
        document.download_status = "available"
        document.is_available = True
        if handle.content_type and handle.content_type != "application/octet-stream":
            document.content_type = handle.content_type
        if handle.content_length and not document.file_size_bytes:
            document.file_size_bytes = handle.content_length
    elif status_code in {401, 403}:
        document.download_status = "restricted"
        document.is_available = False
    elif status_code in {404, 410}:
        document.download_status = "missing"
        document.is_available = False
    else:
        document.download_status = "failed"
        document.is_available = False
    db.commit()


@router.get("/{document_id:int}")
def document_detail(document_id: int, db: Session = Depends(get_db)):
    document, tender = _load(db, document_id)
    return _document_payload(document, tender)


@router.get("/{document_id:int}/status")
def document_status(
    document_id: int,
    refresh: bool = Query(default=False, description="Re-probe the source before answering."),
    db: Session = Depends(get_db),
):
    document, tender = _load(db, document_id)
    if refresh:
        _probe(document, db)
        db.refresh(document)
    return {
        "id": document.id,
        "tender_id": tender.id,
        "availability": document.download_status or "unverified",
        "is_available": document.is_available,
        "http_status": document.http_status,
        "last_checked_at": document.last_checked_at,
        "checked_count": document.checked_count,
        "preview_url": f"/api/v1/documents/{document.id}/preview",
        "download_url": f"/api/v1/documents/{document.id}/download",
        "original_url": document.url,
    }


@router.post("/{document_id:int}/check")
def document_check(document_id: int, db: Session = Depends(get_db)):
    document, tender = _load(db, document_id)
    _probe(document, db)
    db.refresh(document)
    return {
        "id": document.id,
        "tender_id": tender.id,
        "availability": document.download_status,
        "is_available": document.is_available,
        "http_status": document.http_status,
        "last_checked_at": document.last_checked_at,
    }


@router.get("/{document_id:int}/preview")
def document_preview(
    document_id: int,
    request: Request,
    download: bool = False,
    db: Session = Depends(get_db),
):
    """Stream the original document through the API (inline by default)."""
    document, tender = _load(db, document_id)
    allowed, reason = document_proxy.document_allowed(db, document.url)
    if not allowed:
        document.download_status = "restricted"
        document.is_available = False
        db.commit()
        raise HTTPException(status_code=409, detail=f"Document cannot be streamed: {reason}")

    range_header = request.headers.get("range")
    try:
        handle = document_proxy.open_stream(document.url, range_header=range_header)
    except document_proxy.DocumentAccessError as exc:
        document.download_status = "failed"
        document.is_available = False
        document.last_checked_at = _now()
        db.commit()
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    if handle.response.status_code in {401, 403}:
        handle.response.close()
        document.download_status = "restricted"
        document.is_available = False
        db.commit()
        raise HTTPException(status_code=409, detail="The source now requires authorised access to this file")
    if handle.response.status_code in {404, 410}:
        handle.response.close()
        document.download_status = "missing"
        document.is_available = False
        document.last_checked_at = _now()
        db.commit()
        raise HTTPException(status_code=410, detail="The source no longer hosts this document")
    if handle.response.status_code >= 400:
        handle.response.close()
        document.download_status = "failed"
        document.is_available = False
        db.commit()
        raise HTTPException(
            status_code=502, detail=f"The source returned HTTP {handle.response.status_code}"
        )

    document.download_status = "available"
    document.is_available = True
    document.last_checked_at = _now()
    if handle.content_type and handle.content_type != "application/octet-stream":
        document.content_type = handle.content_type
    if handle.content_length and not document.file_size_bytes:
        document.file_size_bytes = handle.content_length
    db.commit()

    filename = _safe_filename(document.label, document.url, handle.content_type)
    disposition = "attachment" if download else "inline"
    headers = {
        "Content-Disposition": f'{disposition}; filename="{filename}"',
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "private, max-age=300",
        "Accept-Ranges": handle.response.headers.get("accept-ranges", "bytes"),
    }
    if handle.response.headers.get("content-range"):
        headers["Content-Range"] = handle.response.headers["content-range"]

    return StreamingResponse(
        document_proxy.iter_response(handle),
        status_code=handle.response.status_code,
        media_type=handle.content_type,
        headers=headers,
    )


@router.get("/{document_id:int}/download")
def document_download(document_id: int, request: Request, db: Session = Depends(get_db)):
    return document_preview(document_id, request, download=True, db=db)


@router.get("/{document_id:int}/viewer", response_class=HTMLResponse)
def document_viewer(document_id: int, db: Session = Depends(get_db)):
    """Self-hosted PDF.js viewer used by the in-app document reader.

    The page is same-origin with the streaming endpoint, so no CORS tricks and no
    third-party viewer are involved.
    """
    document, tender = _load(db, document_id)
    fmt = (document.file_format or "").upper()
    if fmt not in {"PDF"}:
        raise HTTPException(
            status_code=415,
            detail="This format opens in the device's document handler instead of the PDF viewer",
        )
    title = (document.label or "Bid document").replace("<", "&lt;").replace(">", "&gt;")
    return HTMLResponse(
        f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=5" />
<title>{title}</title>
<style>
  :root {{ color-scheme: light dark; }}
  html, body {{ margin: 0; height: 100%; background: #0b1f3a; font-family: system-ui, sans-serif; }}
  #toolbar {{ display: flex; gap: 8px; align-items: center; padding: 8px 10px; background: #12294a; color: #fff; position: sticky; top: 0; z-index: 2; flex-wrap: wrap; }}
  #toolbar button {{ background: #1e3f6b; color: #fff; border: 0; border-radius: 8px; padding: 7px 11px; font-size: 13px; }}
  #toolbar input {{ background: #0b1f3a; color: #fff; border: 1px solid #2c4c77; border-radius: 8px; padding: 6px 8px; width: 64px; }}
  #status {{ padding: 10px; color: #cbd5e1; font-size: 13px; }}
  #viewer {{ position: absolute; inset: 44px 0 0 0; }}
</style>
</head>
<body>
<div id="toolbar">
  <button id="prev" aria-label="Previous page">‹ Prev</button>
  <span id="pageLabel">–</span>
  <button id="next" aria-label="Next page">Next ›</button>
  <button id="zoomOut" aria-label="Zoom out">−</button>
  <span id="zoomLabel">100%</span>
  <button id="zoomIn" aria-label="Zoom in">+</button>
  <input id="find" placeholder="Search" aria-label="Search text in document" />
  <button id="findNext" aria-label="Next match">Find</button>
  <button id="fullscreen" aria-label="Full screen">⛶</button>
  <a href="/api/v1/documents/{document.id}/download" style="color:#9ec1ff">Download</a>
</div>
<div id="status">Loading document…</div>
<div id="viewer"></div>
<script type="module">
  import * as pdfjsLib from "/static/pdfjs/pdf.min.mjs";
  pdfjsLib.GlobalWorkerOptions.workerSrc = "/static/pdfjs/pdf.worker.min.mjs";
  const statusEl = document.getElementById("status");
  const viewer = document.getElementById("viewer");
  const pageLabel = document.getElementById("pageLabel");
  const zoomLabel = document.getElementById("zoomLabel");
  const url = "/api/v1/documents/{document.id}/preview";
  let pdf = null, page = 1, scale = 1.2, rendering = false, textCache = {{}};

  function fitScale() {{
    const width = viewer.clientWidth || window.innerWidth;
    return Math.min(2.5, Math.max(0.6, (width - 24) / 612));
  }}

  async function render() {{
    if (!pdf || rendering) return;
    rendering = true;
    try {{
      const current = await pdf.getPage(page);
      const viewport = current.getViewport({{ scale }});
      viewer.innerHTML = "";
      const canvas = document.createElement("canvas");
      const ratio = window.devicePixelRatio || 1;
      canvas.width = viewport.width * ratio;
      canvas.height = viewport.height * ratio;
      canvas.style.width = viewport.width + "px";
      canvas.style.height = viewport.height + "px";
      canvas.style.margin = "12px auto";
      canvas.style.display = "block";
      canvas.style.background = "#fff";
      viewer.appendChild(canvas);
      const context = canvas.getContext("2d");
      context.setTransform(ratio, 0, 0, ratio, 0, 0);
      await current.render({{ canvasContext: context, viewport }}).promise;
      pageLabel.textContent = page + " / " + pdf.numPages;
      zoomLabel.textContent = Math.round(scale * 100) + "%";
      viewer.scrollTop = 0;
    }} catch (error) {{
      statusEl.textContent = "This page could not be rendered: " + error.message;
    }} finally {{
      rendering = false;
    }}
  }}

  async function searchPdf(term) {{
    if (!term) return;
    for (let i = page; i <= pdf.numPages; i += 1) {{
      const content = textCache[i] || await (await pdf.getPage(i)).getTextContent();
      textCache[i] = content;
      const text = content.items.map((item) => item.str).join(" ").toLowerCase();
      if (text.includes(term.toLowerCase())) {{
        page = i;
        await render();
        statusEl.textContent = "Match on page " + i + " of " + pdf.numPages;
        return;
      }}
    }}
    statusEl.textContent = "No match for “" + term + "” in this document.";
  }}

  try {{
    pdf = await pdfjsLib.getDocument({{ url }}).promise;
    scale = fitScale();
    statusEl.textContent = "";
    await render();
  }} catch (error) {{
    statusEl.innerHTML = "This PDF could not be loaded. " +
      "The source may be offline or the file may have moved. " +
      '<a style="color:#9ec1ff" href="javascript:location.reload()">Retry</a> · ' +
      '<a style="color:#9ec1ff" href="/api/v1/documents/{document.id}/download">Download</a>';
  }}

  document.getElementById("prev").onclick = () => {{ if (page > 1) {{ page -= 1; render(); }} }};
  document.getElementById("next").onclick = () => {{ if (pdf && page < pdf.numPages) {{ page += 1; render(); }} }};
  document.getElementById("zoomIn").onclick = () => {{ scale = Math.min(4, scale + 0.25); render(); }};
  document.getElementById("zoomOut").onclick = () => {{ scale = Math.max(0.4, scale - 0.25); render(); }};
  document.getElementById("findNext").onclick = () => searchPdf(document.getElementById("find").value);
  document.getElementById("find").addEventListener("keydown", (event) => {{
    if (event.key === "Enter") searchPdf(event.target.value);
  }});
  document.getElementById("fullscreen").onclick = () => {{
    if (document.fullscreenElement) document.exitFullscreen();
    else document.documentElement.requestFullscreen();
  }};
</script>
</body>
</html>""",
        headers={"Cache-Control": "private, max-age=300"},
    )


@router.get("")
def recent_documents(
    limit: int = Query(50, ge=1, le=200),
    tender_id: int | None = None,
    db: Session = Depends(get_db),
):
    query = (
        db.query(TenderDocument, Tender)
        .join(Tender, Tender.id == TenderDocument.tender_id)
        .filter(Tender.verification_status != "rejected")
        .filter(TenderDocument.is_public.is_(True))
    )
    if tender_id:
        query = query.filter(TenderDocument.tender_id == tender_id)
    rows = query.order_by(TenderDocument.discovered_at.desc().nulls_last(), TenderDocument.id.desc()).limit(limit).all()
    return {
        "items": [_document_payload(document, tender) for document, tender in rows],
        "count": len(rows),
    }
