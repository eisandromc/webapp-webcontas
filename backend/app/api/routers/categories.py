from __future__ import annotations

import re
import unicodedata

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.api.schemas import CategoryCreate, CategoryUpdate
from app.db.database import get_db
from app.db.models import Category, Entry, InvoiceDraftItem, MerchantRule


router = APIRouter()


def slugify(name: str) -> str:
    base = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", base).strip("-")[:30] or "categoria"


@router.get("/categories")
def list_categories(db: Session = Depends(get_db)) -> list[dict]:
    counts = dict(db.execute(select(Entry.category_slug, func.count()).group_by(Entry.category_slug)).all())
    return [
        {"slug": item.slug, "name": item.name, "color": item.color, "entry_count": counts.get(item.slug, 0)}
        for item in db.scalars(select(Category).order_by(Category.position))
    ]


@router.post("/categories", status_code=201)
def create_category(payload: CategoryCreate, db: Session = Depends(get_db)) -> dict:
    slug = base = slugify(payload.name)
    counter = 2
    while db.get(Category, slug) is not None:
        slug = f"{base[:26]}-{counter}"
        counter += 1
    position = (db.scalar(select(func.max(Category.position))) or 0) + 1
    db.add(Category(slug=slug, name=payload.name.strip(), color=payload.color, position=position))
    db.commit()
    return {"slug": slug}


@router.patch("/categories/{slug}")
def update_category(slug: str, payload: CategoryUpdate, db: Session = Depends(get_db)) -> dict:
    category = db.get(Category, slug)
    if not category:
        raise HTTPException(404, "Categoria não encontrada.")
    if payload.name is not None:
        category.name = payload.name.strip()
    if payload.color is not None:
        category.color = payload.color
    db.commit()
    return {"slug": slug}


@router.delete("/categories/{slug}", status_code=204)
def delete_category(slug: str, db: Session = Depends(get_db)) -> None:
    category = db.get(Category, slug)
    if not category:
        raise HTTPException(404, "Categoria não encontrada.")
    in_use = (db.scalar(select(func.count()).select_from(Entry).where(Entry.category_slug == slug)) or 0) + (
        db.scalar(select(func.count()).select_from(InvoiceDraftItem).where(InvoiceDraftItem.category_slug == slug)) or 0
    )
    if in_use:
        raise HTTPException(400, "Esta categoria possui lançamentos. Mova-os para outra categoria antes de excluir.")
    if (db.scalar(select(func.count()).select_from(Category)) or 0) <= 1:
        raise HTTPException(400, "Mantenha ao menos uma categoria.")
    db.execute(delete(MerchantRule).where(MerchantRule.category_slug == slug))
    db.delete(category)
    db.commit()
