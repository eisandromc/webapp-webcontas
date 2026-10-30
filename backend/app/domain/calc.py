from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP


@dataclass(frozen=True)
class ShareInput:
    person_id: int
    percentage_bp: int
    position: int


@dataclass(frozen=True)
class DiscountInput:
    amount_cents: int
    distribution: str = "proportional"
    person_id: int | None = None


def allocate_cents(total_cents: int, shares: list[ShareInput]) -> dict[int, int]:
    if not shares:
        return {}
    if sum(item.percentage_bp for item in shares) != 10_000:
        raise ValueError("Os percentuais precisam somar 100%.")
    ordered = sorted(shares, key=lambda item: item.position)
    allocated: dict[int, int] = {}
    used = 0
    for item in ordered[:-1]:
        raw = Decimal(total_cents) * Decimal(item.percentage_bp) / Decimal(10_000)
        value = int(raw.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        allocated[item.person_id] = value
        used += value
    allocated[ordered[-1].person_id] = total_cents - used
    return allocated


def allocate_equally(total_cents: int, shares: list[ShareInput]) -> dict[int, int]:
    ordered = sorted(shares, key=lambda item: item.position)
    if not ordered:
        return {}
    base, residual = divmod(total_cents, len(ordered))
    result = {item.person_id: base for item in ordered}
    result[ordered[-1].person_id] += residual
    return result


def summarize_month(
    entry_cents: list[int],
    vale_cents: list[int],
    discount_cents: list[int],
    shares: list[ShareInput],
    payments: dict[int, int],
    previous: dict[int, int] | None = None,
    targeted_discounts: list[DiscountInput] | None = None,
    primary_id: int | None = None,
) -> dict:
    entries_total = sum(entry_cents)
    vales = sum(vale_cents)
    targeted_discounts = targeted_discounts or []
    # Descontos para todos (proporcionais ou iguais) reduzem o total de gastos.
    shared_discounts = sum(discount_cents) + sum(item.amount_cents for item in targeted_discounts if item.distribution != "person")
    expenses = entries_total - shared_discounts
    net = expenses + vales
    parts = allocate_cents(net, shares)
    # Descontos de uma pessoa específica abatem somente o saldo dela.
    personal: dict[int, int] = {}
    for discount in targeted_discounts:
        if discount.distribution == "person" and discount.person_id in parts:
            personal[discount.person_id] = personal.get(discount.person_id, 0) + discount.amount_cents
    previous = previous or {}
    has_primary = primary_id is not None and primary_id in parts
    # Descontos da fonte primária viram custo extra, cobrado só dos demais participantes.
    primary_discounts = personal.get(primary_id, 0) if has_primary else 0
    # Quem participa com 0% (ex.: pessoa desativada com registros no mês) não recebe custo extra.
    others = [share for share in shares if share.person_id != primary_id and share.percentage_bp > 0] if has_primary else []
    extra = allocate_equally(primary_discounts, others) if others else {}
    people = {}
    for share in shares:
        person_id = share.person_id
        discount = personal.get(person_id, 0)
        if has_primary and person_id == primary_id:
            paid = parts[person_id]
            extra_cents = 0
            balance = 0
        else:
            paid = payments.get(person_id, 0)
            extra_cents = extra.get(person_id, 0)
            balance = parts[person_id] + extra_cents - discount - paid
        # Sem crédito acumulado: só dívidas pendentes seguem para o mês seguinte.
        carried = max(previous.get(person_id, 0), 0)
        people[person_id] = {
            "part_cents": parts[person_id],
            "discount_cents": discount,
            "extra_cents": extra_cents,
            "paid_cents": paid,
            "balance_cents": balance,
            "accumulated_cents": max(carried + balance, 0) if balance >= 0 else balance,
        }
    return {
        "expenses_cents": expenses,
        "vales_cents": vales,
        "cost_cents": net,
        "discounts_cents": sum(personal.values()),
        "net_cents": net,
        "people": people,
    }


def equal_percentages(person_ids: list[int]) -> list[int]:
    if not person_ids:
        return []
    base, remainder = divmod(10_000, len(person_ids))
    return [base + (1 if index < remainder else 0) for index, _ in enumerate(person_ids)]
