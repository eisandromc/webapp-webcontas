from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Category, Person


CATEGORIES = [
    ("contas", "Contas", "#3E6F8E", 0),
    ("alimentacao", "Alimentação", "#B7791F", 1),
    ("extras", "Extras", "#815A8F", 2),
    ("transporte", "Transporte", "#4A7A62", 3),
]


def seed_database(db: Session) -> None:
    if not db.scalar(select(Person.id).limit(1)):
        db.add_all([Person(name="Ana", position=0), Person(name="Bruno", position=1)])
    for slug, name, color, position in CATEGORIES:
        if db.get(Category, slug) is None:
            db.add(Category(slug=slug, name=name, color=color, position=position))
    db.commit()


def current_period() -> str:
    return datetime.now().strftime("%Y-%m")

