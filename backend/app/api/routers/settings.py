from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.schemas import PasswordPayload, PeriodDefaultsPayload
from app.api.security import require_localhost
from app.db.database import get_db
from app.db.models import AppSetting
from app.services.periods import get_period_defaults, save_period_defaults
from app.services.secrets import SecretStoreError, delete_pdf_password, get_pdf_password, set_pdf_password


router = APIRouter()
PASSWORD_SAVED_KEY = "pdf_password_saved_at"


@router.get("/settings/pdf-password")
def password_status(db: Session = Depends(get_db)) -> dict:
    saved = db.get(AppSetting, PASSWORD_SAVED_KEY)
    try:
        return {"configured": get_pdf_password() is not None, "saved_at": saved.value if saved else None}
    except SecretStoreError as exc:
        return {"configured": False, "saved_at": None, "warning": str(exc)}


@router.put("/settings/pdf-password")
def save_password(payload: PasswordPayload, request: Request, db: Session = Depends(get_db)) -> dict:
    require_localhost(request)
    try:
        set_pdf_password(payload.password)
    except (ValueError, SecretStoreError) as exc:
        raise HTTPException(400, str(exc)) from exc
    now = datetime.now(timezone.utc).isoformat()
    setting = db.get(AppSetting, PASSWORD_SAVED_KEY)
    if setting:
        setting.value = now
    else:
        db.add(AppSetting(key=PASSWORD_SAVED_KEY, value=now))
    db.commit()
    return {"configured": True, "saved_at": now}


@router.delete("/settings/pdf-password")
def remove_password(request: Request, db: Session = Depends(get_db)) -> dict:
    require_localhost(request)
    try:
        delete_pdf_password()
    except SecretStoreError as exc:
        raise HTTPException(400, str(exc)) from exc
    setting = db.get(AppSetting, PASSWORD_SAVED_KEY)
    if setting:
        db.delete(setting)
        db.commit()
    return {"configured": False, "saved_at": None}


@router.get("/settings/period-defaults")
def period_defaults(db: Session = Depends(get_db)) -> dict:
    start_day, end_day = get_period_defaults(db)
    return {"start_day": start_day, "end_day": end_day}


@router.put("/settings/period-defaults")
def update_period_defaults(payload: PeriodDefaultsPayload, db: Session = Depends(get_db)) -> dict:
    save_period_defaults(db, payload.start_day, payload.end_day)
    return payload.model_dump()
