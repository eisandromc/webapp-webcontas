from __future__ import annotations

import socket
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Category, Person
from app.services.months import registered_periods
from app.api.routers.people import serialize_person


router = APIRouter()


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/bootstrap")
def bootstrap(db: Session = Depends(get_db)) -> dict:
    periods = sorted(registered_periods(db), reverse=True)
    people = list(db.scalars(select(Person).order_by(Person.position)))
    categories = list(db.scalars(select(Category).order_by(Category.position)))
    current = datetime.now().strftime("%Y-%m")
    return {
        "periods": periods,
        "current_period": current,
        "people": [serialize_person(person) for person in people],
        "categories": [{"slug": item.slug, "name": item.name, "color": item.color} for item in categories],
    }


@router.get("/server-info")
def server_info(request: Request) -> dict:
    addresses: list[str] = []
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        probe.connect(("10.255.255.255", 1))
        addresses.append(probe.getsockname()[0])
        probe.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            address = info[4][0]
            if not address.startswith("127.") and not address.startswith("169.254.") and address not in addresses:
                addresses.append(address)
    except OSError:
        pass
    port = request.url.port or 8000
    return {"addresses": addresses, "port": port, "urls": [f"http://{address}:{port}" for address in addresses]}
