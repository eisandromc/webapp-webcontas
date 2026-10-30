"""Indicadores do painel: totais por mês, categorias, maiores custos e situação de cada pessoa."""
from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import Category, Entry, Month, MonthPerson, Person
from app.services.months import calculate_all_months, months_with_records, received_by_month, registered_periods
from app.services.pdf_parser import normalize_merchant


def participant_overview(db: Session, summaries: dict[str, dict]) -> list[dict]:
    months = list(db.scalars(select(Month).order_by(Month.period).options(selectinload(Month.shares).selectinload(MonthPerson.person))))
    primary = db.scalar(select(Person).where(Person.is_primary.is_(True)))
    received = received_by_month(db)
    people = {person.id: person for person in db.scalars(select(Person).where(Person.active.is_(True)).order_by(Person.position))}
    rows: dict[int, dict] = {
        person_id: {"person_id": person_id, "name": person.name, "is_primary": bool(primary and primary.id == person_id),
                    "part_cents": 0, "paid_cents": 0, "open_cents": 0, "months": []}
        for person_id, person in people.items()
    }
    with_records = months_with_records(db)
    for month in months:
        if month.period not in with_records or month.period not in summaries:
            continue
        summary = summaries[month.period]["people"]
        for share in month.shares:
            row = rows.get(share.person_id)
            if row is None or share.person_id not in summary:
                continue
            data = summary[share.person_id]
            settled = share.person_id == month.primary_person_id or share.person_id in received.get(month.id, {})
            outstanding = 0 if settled else max(data["balance_cents"], 0)
            row["part_cents"] += data["part_cents"]
            row["paid_cents"] += data["paid_cents"]
            row["open_cents"] += outstanding
            row["months"].append({
                "period": month.period,
                "part_cents": data["part_cents"],
                "paid_cents": data["paid_cents"],
                "outstanding_cents": outstanding,
                "accumulated_open_cents": row["open_cents"],
                "settled": settled,
            })
    if primary and primary.id in rows:
        rows[primary.id]["to_receive_cents"] = sum(row["open_cents"] for pid, row in rows.items() if pid != primary.id)
    return list(rows.values())


def build_dashboard(db: Session, months: int) -> dict:
    periods = sorted(registered_periods(db))[-months:]
    month_rows = list(db.scalars(select(Month).where(Month.period.in_(periods)))) if periods else []
    month_ids = {month.id for month in month_rows}
    summaries = calculate_all_months(db)
    entries = list(db.scalars(select(Entry).where(Entry.month_id.in_(month_ids)))) if month_ids else []
    categories = {item.slug: item for item in db.scalars(select(Category))}
    month_by_id = {month.id: month.period for month in month_rows}

    monthly = [
        {
            "period": period,
            "expenses_cents": summaries[period]["expenses_cents"],
            "net_cents": summaries[period]["net_cents"],
            "discounts_cents": summaries[period]["discounts_cents"],
        }
        for period in periods
    ]
    category_totals: dict[str, int] = defaultdict(int)
    merchant_totals: dict[str, int] = defaultdict(int)
    merchant_labels: dict[str, str] = {}
    merchant_months: dict[str, set[str]] = defaultdict(set)
    for entry in entries:
        category_totals[entry.category_slug] += entry.amount_cents
        merchant = normalize_merchant(entry.description) or entry.description.upper()
        merchant_totals[merchant] += entry.amount_cents
        merchant_labels.setdefault(merchant, entry.description)
        merchant_months[merchant].add(month_by_id[entry.month_id])

    category_data = [
        {
            "slug": slug,
            "name": categories[slug].name if slug in categories else slug.title(),
            "color": categories[slug].color if slug in categories else "#65726f",
            "amount_cents": amount,
        }
        for slug, amount in sorted(category_totals.items(), key=lambda item: item[1], reverse=True)
    ]
    top_costs = [
        {
            "description": merchant_labels[key],
            "amount_cents": amount,
            "months": len(merchant_months[key]),
        }
        for key, amount in sorted(merchant_totals.items(), key=lambda item: item[1], reverse=True)[:8]
    ]
    recurring = [item for item in top_costs if item["months"] >= 3][:5]
    total_expenses = sum(item["expenses_cents"] for item in monthly)
    average = round(total_expenses / len(monthly)) if monthly else 0
    latest = monthly[-1]["expenses_cents"] if monthly else 0
    previous = monthly[-2]["expenses_cents"] if len(monthly) > 1 else 0
    trend_percent = round((latest - previous) / abs(previous) * 100, 1) if previous else None
    discretionary = sum(category_totals.get(slug, 0) for slug in ("alimentacao", "extras"))
    scenario_savings = round(max(discretionary, 0) * 0.10)
    largest = category_data[0] if category_data else None
    insights = []
    if largest and total_expenses:
        insights.append({
            "title": "Maior centro de custo",
            "text": f"{largest['name']} concentra {round(largest['amount_cents'] / total_expenses * 100)}% dos gastos analisados.",
            "tone": "attention",
        })
    if trend_percent is not None:
        direction = "subiram" if trend_percent > 0 else "caíram"
        insights.append({
            "title": "Mudança no último mês",
            "text": f"Os gastos {direction} {abs(trend_percent):.1f}% em relação ao mês anterior.",
            "tone": "attention" if trend_percent > 0 else "positive",
        })
    if scenario_savings:
        insights.append({
            "title": "Cenário de economia",
            "text": "Uma redução simulada de 10% em alimentação e extras produziria a economia indicada abaixo.",
            "tone": "positive",
            "amount_cents": scenario_savings,
        })
    return {
        "participants": participant_overview(db, summaries),
        "months": monthly,
        "total_expenses_cents": total_expenses,
        "average_monthly_cents": average,
        "latest_expenses_cents": latest,
        "trend_percent": trend_percent,
        "categories": category_data,
        "top_costs": top_costs,
        "recurring": recurring,
        "insights": insights,
    }
