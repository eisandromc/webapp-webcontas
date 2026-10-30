"""Regras dos meses: participantes, cálculo da divisão, acertos e serialização."""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import date, datetime

from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload

from app.db.models import Adjustment, Entry, Invoice, Month, MonthPerson, MonthSettlement, Payment, Person
from app.domain.calc import DiscountInput, ShareInput, equal_percentages, summarize_month
from app.services.periods import REFERENCE_OFFSET_MONTHS, default_period_range, get_period_defaults, month_range, reference_period


PERIOD_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
CLOSED_MESSAGE = "Este mês está fechado. Reabra o mês para editar."


# ---- Períodos ----

def validate_period(period: str) -> str:
    if not PERIOD_RE.match(period):
        raise HTTPException(400, "Mês inválido. Use AAAA-MM.")
    return period


def validate_range(start_date: str, end_date: str) -> tuple[str, str]:
    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
    except ValueError as exc:
        raise HTTPException(400, "Informe datas válidas.") from exc
    if start > end:
        raise HTTPException(400, "A data inicial precisa ser anterior à data final.")
    if (end - start).days > 62:
        raise HTTPException(400, "A faixa mensal não pode ultrapassar 63 dias.")
    return start.isoformat(), end.isoformat()


def next_period(period: str) -> str:
    year, month = (int(part) for part in period.split("-"))
    index = year * 12 + month
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


def label_period(period: str) -> str:
    return f"{period[5:]}/{period[:4]}"


# ---- Participantes ----

def active_people(db: Session) -> list[Person]:
    return list(db.scalars(select(Person).where(Person.active.is_(True)).order_by(Person.position)))


def people_with_records(db: Session, month_id: int) -> set[int]:
    ids: set[int] = set(db.scalars(select(Payment.person_id).where(Payment.month_id == month_id)))
    ids.update(db.scalars(select(Adjustment.person_id).where(Adjustment.month_id == month_id, Adjustment.person_id.is_not(None))))
    ids.update(db.scalars(select(Entry.paid_by_person_id).where(Entry.month_id == month_id, Entry.paid_by_person_id.is_not(None))))
    return ids


def _share_rows(people: list[Person], inactive_ids: list[int]) -> list[tuple[int, int]]:
    """(pessoa, percentual): divisão igual entre ativos; desativados com registros ficam com 0%."""
    percentages = equal_percentages([person.id for person in people])
    return [(person.id, percentages[index]) for index, person in enumerate(people)] + [(person_id, 0) for person_id in inactive_ids]


def new_month(db: Session, period: str) -> Month:
    """Mês ainda não gravado, com a faixa padrão e as pessoas ativas de agora."""
    people = active_people(db)
    if not people:
        raise HTTPException(400, "Cadastre ao menos uma pessoa ativa.")
    start_day, end_day = get_period_defaults(db)
    start_date, end_date = default_period_range(period, start_day, end_day, REFERENCE_OFFSET_MONTHS)
    month = Month(
        period=period,
        start_date=start_date,
        end_date=end_date,
        closed=False,
        registered=False,
        primary_person_id=next((person.id for person in people if person.is_primary), None),
    )
    by_id = {person.id: person for person in people}
    for position, (person_id, percentage) in enumerate(_share_rows(people, [])):
        share = MonthPerson(person_id=person_id, percentage_bp=percentage, position=position)
        share.person = by_id[person_id]
        month.shares.append(share)
    return month


def reset_shares(db: Session, month: Month) -> None:
    """Refaz a divisão de um mês com as pessoas ativas e a fonte primária atuais."""
    people = active_people(db)
    if not people:
        raise HTTPException(400, "Cadastre ao menos uma pessoa ativa.")
    active_ids = {person.id for person in people}
    involved = people_with_records(db, month.id)
    inactive = [share.person_id for share in sorted(month.shares, key=lambda item: item.position) if share.person_id not in active_ids and share.person_id in involved]
    db.execute(delete(MonthPerson).where(MonthPerson.month_id == month.id))
    db.add_all(
        MonthPerson(month_id=month.id, person_id=person_id, percentage_bp=percentage, position=position)
        for position, (person_id, percentage) in enumerate(_share_rows(people, inactive))
    )
    month.primary_person_id = next((person.id for person in people if person.is_primary), None)
    db.flush()
    db.expire(month, ["shares"])


def resync_open_months(db: Session) -> None:
    """Mudanças nas pessoas valem para os meses abertos; meses fechados preservam a divisão da época."""
    for month in db.scalars(select(Month).where(Month.closed.is_(False)).options(selectinload(Month.shares))).all():
        reset_shares(db, month)


# ---- Busca e criação ----

def find_month(db: Session, period: str) -> Month | None:
    return db.scalar(select(Month).where(Month.period == period).options(selectinload(Month.shares).selectinload(MonthPerson.person)))


def month_or_virtual(db: Session, period: str) -> Month:
    """Para leituras: o mês gravado ou uma prévia em memória, sem gravar nada."""
    validate_period(period)
    return find_month(db, period) or new_month(db, period)


def get_or_create_month(db: Session, period: str) -> Month:
    """Para gravações: cria a linha do mês se preciso. Quem chama faz o commit."""
    validate_period(period)
    month = find_month(db, period)
    if month is None:
        month = new_month(db, period)
        db.add(month)
        db.flush()
    return month


def ensure_open(month: Month) -> None:
    if month.closed:
        raise HTTPException(400, CLOSED_MESSAGE)


def participant_ids(month: Month) -> set[int]:
    return {share.person_id for share in month.shares}


# ---- Meses cadastrados ----

def months_with_records(db: Session) -> set[str]:
    month_ids: set[int] = set()
    for model in (Entry, Adjustment, Payment):
        month_ids.update(db.scalars(select(model.month_id).distinct()))
    if not month_ids:
        return set()
    return set(db.scalars(select(Month.period).where(Month.id.in_(month_ids))))


def registered_periods(db: Session) -> set[str]:
    """Meses cadastrados em Contas: marcados explicitamente ou que já possuem registros."""
    return set(db.scalars(select(Month.period).where(Month.registered.is_(True)))) | months_with_records(db)


def all_month_counts(db: Session) -> dict[int, dict[str, int]]:
    counts: dict[int, dict[str, int]] = defaultdict(lambda: {"entries": 0, "adjustments": 0, "payments": 0})
    for key, model in (("entries", Entry), ("adjustments", Adjustment), ("payments", Payment)):
        for month_id, total in db.execute(select(model.month_id, func.count()).group_by(model.month_id)):
            counts[month_id][key] = total
    return counts


def month_counts(db: Session, month_id: int) -> dict[str, int]:
    return {
        key: db.scalar(select(func.count()).select_from(model).where(model.month_id == month_id)) or 0
        for key, model in (("entries", Entry), ("adjustments", Adjustment), ("payments", Payment))
    }


# ---- Cálculo ----

def calculate_all_months(db: Session, include: Month | None = None) -> dict[str, dict]:
    """Resumo de cada mês cadastrado, em ordem, levando o saldo acumulado adiante.

    Cada mês usa os próprios participantes, percentuais e fonte primária gravados nele.
    `include` acrescenta um mês fora da lista (ex.: a prévia de um mês ainda não gravado).
    """
    listed = registered_periods(db)
    months = [
        month
        for month in db.scalars(select(Month).order_by(Month.period).options(selectinload(Month.shares).selectinload(MonthPerson.person)))
        if month.period in listed
    ]
    if include is not None and all(month.period != include.period for month in months):
        months = sorted([*months, include], key=lambda month: month.period)

    entries: dict[int, list[int]] = defaultdict(list)
    for month_id, amount in db.execute(select(Entry.month_id, Entry.amount_cents)):
        entries[month_id].append(amount)
    adjustments: dict[int, list[Adjustment]] = defaultdict(list)
    for item in db.scalars(select(Adjustment)):
        adjustments[item.month_id].append(item)
    paid: dict[int, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    for month_id, person_id, amount in db.execute(select(Payment.month_id, Payment.person_id, Payment.amount_cents)):
        paid[month_id][person_id] += amount
    settled = {(item.month_id, item.person_id) for item in db.scalars(select(MonthSettlement))}

    accumulated: dict[int, int] = {}
    result: dict[str, dict] = {}
    for month in months:
        month_adjustments = adjustments.get(month.id, []) if month.id is not None else []
        discounts = [item for item in month_adjustments if item.kind == "desconto"]
        shares = sorted(month.shares, key=lambda item: item.position)
        ids = [share.person_id for share in shares]
        percentages = [share.percentage_bp for share in shares]
        if sum(percentages) != 10_000:
            percentages = equal_percentages(ids)
        primary_id = month.primary_person_id if month.primary_person_id in ids else None
        summary = summarize_month(
            entries.get(month.id, []) if month.id is not None else [],
            [item.amount_cents for item in month_adjustments if item.kind == "vale"],
            [item.amount_cents for item in discounts if (item.distribution or "proportional") == "proportional"],
            [ShareInput(person_id, percentages[index], index) for index, person_id in enumerate(ids)],
            dict(paid.get(month.id, {})) if month.id is not None else {},
            accumulated,
            [DiscountInput(item.amount_cents, item.distribution, item.person_id) for item in discounts if (item.distribution or "proportional") != "proportional"],
            primary_id,
        )
        for person_id in ids:
            if (month.id, person_id) in settled and person_id != primary_id:
                row = summary["people"][person_id]
                row["paid_cents"] = row["part_cents"] + row["extra_cents"] - row["discount_cents"]
                row["balance_cents"] = 0
                row["accumulated_cents"] = 0
        for person_id, person_summary in summary["people"].items():
            accumulated[person_id] = person_summary["accumulated_cents"]
        result[month.period] = summary
    return result


# ---- Acertos ----

def received_by_month(db: Session) -> dict[int, dict[int, datetime]]:
    received: dict[int, dict[int, datetime]] = defaultdict(dict)
    for item in db.scalars(select(MonthSettlement)):
        received[item.month_id][item.person_id] = item.received_at
    return received


def month_settlement(month: Month, received: dict[int, datetime]) -> dict:
    shares = list(month.shares)
    primary_id = month.primary_person_id if month.primary_person_id in {share.person_id for share in shares} else None
    people: dict[int, dict] = {}
    for share in shares:
        if share.person_id == primary_id or share.percentage_bp == 0:
            people[share.person_id] = {"status": "paid", "received_at": None}
        elif share.person_id in received:
            people[share.person_id] = {"status": "paid", "received_at": received[share.person_id].isoformat()}
        else:
            people[share.person_id] = {"status": "pending", "received_at": None}
    if not month.closed:
        status = "processing"
    elif all(item["status"] == "paid" for item in people.values()):
        status = "paid"
    else:
        status = "awaiting"
    return {"status": status, "primary_person_id": primary_id, "people": people}


# ---- Serialização ----

def serialize_month(db: Session, month: Month) -> dict:
    start_date, end_date = month_range(db, month)
    summary = calculate_all_months(db, include=month)[month.period]
    stored = month.id is not None
    entries = list(db.scalars(select(Entry).where(Entry.month_id == month.id).order_by(Entry.date, Entry.id))) if stored else []
    adjustments = list(db.scalars(select(Adjustment).where(Adjustment.month_id == month.id).options(selectinload(Adjustment.person)).order_by(Adjustment.id))) if stored else []
    payments = list(db.scalars(select(Payment).where(Payment.month_id == month.id).options(selectinload(Payment.person)).order_by(Payment.date, Payment.id))) if stored else []
    shares = sorted(month.shares, key=lambda item: item.position)
    invoice_ids = {entry.invoice_id for entry in entries if entry.invoice_id is not None}
    invoices = list(db.scalars(select(Invoice).where(Invoice.id.in_(invoice_ids)))) if invoice_ids else []
    received = {item.person_id: item.received_at for item in db.scalars(select(MonthSettlement).where(MonthSettlement.month_id == month.id))} if stored else {}
    settlement = month_settlement(month, received)
    names = {share.person_id: share.person.name for share in shares}
    return {
        "period": month.period,
        "reference_period": reference_period(month.period),
        "registered": bool(month.registered) or bool(entries or adjustments or payments),
        "start_date": start_date,
        "end_date": end_date,
        "closed": bool(month.closed),
        "status": settlement["status"],
        "primary_person_id": settlement["primary_person_id"],
        "summary": summary,
        "people": [
            {
                "person_id": share.person_id,
                "name": share.person.name,
                "percentage_bp": share.percentage_bp,
                "position": share.position,
                "is_primary": share.person_id == settlement["primary_person_id"],
                "settlement_status": settlement["people"][share.person_id]["status"],
                "received_at": settlement["people"][share.person_id]["received_at"],
                **summary["people"].get(share.person_id, {}),
            }
            for share in shares
        ],
        "entries": [
            {
                "id": entry.id,
                "date": entry.date,
                "description": entry.description,
                "amount_cents": entry.amount_cents,
                "category_slug": entry.category_slug,
                "origin": entry.origin,
                "paid_by_person_id": entry.paid_by_person_id,
                "paid_by_name": names.get(entry.paid_by_person_id),
                "installment_current": entry.installment_current,
                "installment_total": entry.installment_total,
            }
            for entry in entries
        ],
        "adjustments": [
            {
                "id": item.id,
                "kind": item.kind,
                "description": item.description,
                "amount_cents": item.amount_cents,
                "distribution": item.distribution or "proportional",
                "person_id": item.person_id,
                "person_name": item.person.name if item.person else None,
            }
            for item in adjustments
        ],
        "payments": [
            {"id": item.id, "person_id": item.person_id, "person_name": item.person.name, "date": item.date, "amount_cents": item.amount_cents, "note": item.note}
            for item in payments
        ],
        "invoice_imports": [
            {
                "id": invoice.id,
                "filename": invoice.filename,
                "item_count": sum(1 for entry in entries if entry.invoice_id == invoice.id),
                "amount_cents": sum(entry.amount_cents for entry in entries if entry.invoice_id == invoice.id),
            }
            for invoice in invoices
        ],
    }
