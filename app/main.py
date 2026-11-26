import csv, io
from datetime import datetime, timezone
from fastapi import FastAPI, Depends, HTTPException, Query, UploadFile, File
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import or_, func
from sqlalchemy.orm import Session
from app.config import settings
from app.database import Base, engine, get_db, SessionLocal
from app.models import User, Tender, AuditLog
from app.schemas import LoginInput, TenderCreate, TenderUpdate, TenderOut
from app.security import hash_password, verify_password, create_access_token, get_current_admin
from app.collector import collect_public_notices
from app.collector_scheduler import start_scheduler, stop_scheduler

app = FastAPI(title="Bidders Nepal API", version="1.0.0",
              description="Tender discovery, verification and management API.")
origins = ["*"] if settings.cors_origins.strip() == "*" else [x.strip() for x in settings.cors_origins.split(",")]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=False,
                   allow_methods=["GET", "POST", "PATCH", "OPTIONS"], allow_headers=["*"])

@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    start_scheduler()
    if settings.admin_email and settings.admin_password:
        with SessionLocal() as db:
            user = db.query(User).filter(func.lower(User.email) == settings.admin_email.lower()).first()
            if not user:
                db.add(User(email=settings.admin_email.lower(),
                            password_hash=hash_password(settings.admin_password), role="admin"))
                db.commit()

@app.on_event("shutdown")
def shutdown():
    stop_scheduler()

@app.get("/")
def root():
    return {"name": settings.app_name, "version": "1.0.0", "docs": "/docs", "health": "/health"}

@app.get("/health")
def health():
    return {"status": "ok", "service": "bidders-nepal-api",
            "time": datetime.now(timezone.utc).isoformat()}

def authenticate_user(email: str, password: str, db: Session):
    user = db.query(User).filter(func.lower(User.email) == email.lower()).first()
    if not user or not user.is_active or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    return user

@app.post("/api/v1/auth/login")
def login(payload: LoginInput, db: Session = Depends(get_db)):
    """JSON login for apps and API clients."""
    user = authenticate_user(payload.email, payload.password, db)
    return {"access_token": create_access_token(user), "token_type": "bearer"}

@app.post("/api/v1/auth/token")
def oauth_token(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """OAuth2 form login used by Swagger's Authorize button. Enter the admin email as username."""
    user = authenticate_user(form.username, form.password, db)
    return {"access_token": create_access_token(user), "token_type": "bearer"}

def audit(db, admin, action, tender_id, details=None):
    db.add(AuditLog(actor_user_id=admin.id, action=action, entity_id=tender_id, details=details))

@app.get("/api/v1/tenders")
def list_tenders(q: str | None = None, category: str | None = None,
                 province: str | None = None, district: str | None = None,
                 status: str | None = "open", page: int = Query(1, ge=1),
                 page_size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    query = db.query(Tender).filter(Tender.verification_status == "verified")
    if q:
        term = f"%{q.strip()}%"
        query = query.filter(or_(Tender.title.ilike(term), Tender.organization_name.ilike(term),
                                 Tender.notice_number.ilike(term), Tender.description.ilike(term)))
    if category: query = query.filter(Tender.category == category)
    if province: query = query.filter(Tender.province.ilike(province))
    if district: query = query.filter(Tender.district.ilike(district))
    if status: query = query.filter(Tender.status == status)
    total = query.count()
    rows = query.order_by(Tender.deadline.asc().nullslast(), Tender.created_at.desc()) \
                 .offset((page-1)*page_size).limit(page_size).all()
    return {"items": [TenderOut.model_validate(x).model_dump(mode="json") for x in rows],
            "total": total, "page": page, "page_size": page_size}

@app.get("/api/v1/tenders/all")
def list_all_tenders(q: str | None = None, category: str | None = None,
                     province: str | None = None, district: str | None = None,
                     status: str | None = None, verification_status: str | None = Query(
                         default=None, pattern="^(pending|verified|rejected)$"),
                     include_rejected: bool = False,
                     page: int = Query(1, ge=1),
                     page_size: int = Query(100, ge=1, le=500),
                     db: Session = Depends(get_db)):
    """Public full-record feed. Includes pending and verified tenders; rejected are excluded by default."""
    query = db.query(Tender)
    if verification_status:
        query = query.filter(Tender.verification_status == verification_status)
    elif not include_rejected:
        query = query.filter(Tender.verification_status != "rejected")
    if q:
        term = f"%{q.strip()}%"
        query = query.filter(or_(Tender.title.ilike(term), Tender.organization_name.ilike(term),
                                 Tender.notice_number.ilike(term), Tender.description.ilike(term)))
    if category:
        query = query.filter(Tender.category == category)
    if province:
        query = query.filter(Tender.province.ilike(province))
    if district:
        query = query.filter(Tender.district.ilike(district))
    if status:
        query = query.filter(Tender.status == status)
    total = query.count()
    rows = query.order_by(Tender.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"items": [TenderOut.model_validate(x).model_dump(mode="json") for x in rows],
            "total": total, "page": page, "page_size": page_size}


@app.get("/api/v1/tenders/{tender_id}", response_model=TenderOut)
def tender_detail(tender_id: int, db: Session = Depends(get_db)):
    tender = db.get(Tender, tender_id)
    if not tender or tender.verification_status != "verified":
        raise HTTPException(status_code=404, detail="Tender not found")
    return tender

@app.post("/api/v1/admin/tenders", response_model=TenderOut, status_code=201)
def create_tender(payload: TenderCreate, db: Session = Depends(get_db),
                  admin: User = Depends(get_current_admin)):
    if payload.notice_number and db.query(Tender).filter(Tender.notice_number == payload.notice_number).first():
        raise HTTPException(status_code=409, detail="Duplicate notice number")
    tender = Tender(**payload.model_dump(), created_by=admin.id,
                    verification_status="pending", status="open")
    db.add(tender); db.flush(); audit(db, admin, "create", tender.id)
    db.commit(); db.refresh(tender)
    return tender

@app.patch("/api/v1/admin/tenders/{tender_id}", response_model=TenderOut)
def update_tender(tender_id: int, payload: TenderUpdate, db: Session = Depends(get_db),
                  admin: User = Depends(get_current_admin)):
    tender = db.get(Tender, tender_id)
    if not tender: raise HTTPException(status_code=404, detail="Tender not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(tender, key, value)
    audit(db, admin, "update", tender.id); db.commit(); db.refresh(tender)
    return tender

@app.get("/api/v1/admin/tenders")
def review_queue(verification_status: str = "pending", page: int = 1,
                 db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    query = db.query(Tender).filter(Tender.verification_status == verification_status)
    return {"items": query.order_by(Tender.created_at.desc()).offset((page-1)*20).limit(20).all(),
            "total": query.count()}

@app.post("/api/v1/admin/tenders/{tender_id}/verify", response_model=TenderOut)
def verify_tender(tender_id: int, decision: str = Query(pattern="^(verified|rejected)$"),
                  db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    tender = db.get(Tender, tender_id)
    if not tender: raise HTTPException(status_code=404, detail="Tender not found")
    tender.verification_status = decision
    audit(db, admin, decision, tender.id); db.commit(); db.refresh(tender)
    return tender

@app.post("/api/v1/admin/tenders/import-csv")
async def import_csv(file: UploadFile = File(...), db: Session = Depends(get_db),
                     admin: User = Depends(get_current_admin)):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Upload a CSV file")
    raw = await file.read()
    if len(raw) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="CSV must be 5 MB or smaller")
    try:
        reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
        if not reader.fieldnames or not {"title", "organization_name"}.issubset(reader.fieldnames):
            raise ValueError("CSV needs title and organization_name columns")
        added = skipped = 0
        for row in reader:
            title = (row.get("title") or "").strip()
            organization = (row.get("organization_name") or "").strip()
            if not title or not organization:
                skipped += 1; continue
            notice = (row.get("notice_number") or "").strip() or None
            if notice and db.query(Tender).filter(Tender.notice_number == notice).first():
                skipped += 1; continue
            def date_value(key):
                value = (row.get(key) or "").strip()
                return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None
            db.add(Tender(title=title[:500], organization_name=organization[:300], notice_number=notice,
                category=(row.get("category") or "Other").strip(),
                province=(row.get("province") or "").strip() or None,
                district=(row.get("district") or "").strip() or None,
                description=(row.get("description") or "").strip() or None,
                published_date=date_value("published_date"), deadline=date_value("deadline"),
                source_name=(row.get("source_name") or "CSV import").strip(),
                source_url=(row.get("source_url") or "").strip() or None,
                document_url=(row.get("document_url") or "").strip() or None,
                created_by=admin.id, verification_status="pending", status="open"))
            added += 1
        audit(db, admin, "csv_import", None, f"added={added}; skipped={skipped}")
        db.commit()
        return {"success": True, "added": added, "skipped": skipped,
                "message": "Imported notices require admin verification."}
    except (UnicodeDecodeError, csv.Error, ValueError) as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Invalid CSV: {exc}")

@app.post("/api/v1/admin/collector/run")
def run_collector(db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    result = collect_public_notices(db)
    audit(db, admin, "collector_run", None, str(result))
    db.commit()
    return result

@app.get("/api/v1/admin/audit")
def audit_history(limit: int = Query(50, ge=1, le=200),
                  db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    rows = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).all()
    return [{"id": r.id, "actor_user_id": r.actor_user_id, "action": r.action,
             "entity_id": r.entity_id, "details": r.details, "created_at": r.created_at}
            for r in rows]
