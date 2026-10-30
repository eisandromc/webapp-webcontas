from __future__ import annotations

import calendar
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AppSetting


START_DAY_KEY = "default_period_start_day"
END_DAY_KEY = "default_period_end_day"


def get_period_defaults(db: Session) -> tuple[int, int]:
    settings = {
        item.key: item.value
        for item in db.scalars(select(AppSetting).where(AppSetting.key.in_([START_DAY_KEY, END_DAY_KEY])))
    }
    return int(settings.get(START_DAY_KEY, "1")), int(settings.get(END_DAY_KEY, "31"))


def save_period_defaults(db: Session, start_day: int, end_day: int) -> None:
    for key, value in ((START_DAY_KEY, start_day), (END_DAY_KEY, end_day)):
        setting = db.get(AppSetting, key)
        if setting:
            setting.value = str(value)
        else:
            db.add(AppSetting(key=key, value=str(value)))
    db.commit()


def _clamped_date(year: int, month: int, day: int) -> date:
    return date(year, month, min(day, calendar.monthrange(year, month)[1]))


REFERENCE_OFFSET_MONTHS = 1


def reference_period(period: str, offset: int = REFERENCE_OFFSET_MONTHS) -> str:
    """O mês de cobrança (ex.: outubro) corresponde às contas do mês anterior (setembro)."""
    year, month = (int(part) for part in period.split("-"))
    index = year * 12 + (month - 1) - offset
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


def default_period_range(period: str, start_day: int, end_day: int, offset: int = 0) -> tuple[str, str]:
    year, month = (int(part) for part in reference_period(period, offset).split("-")) if offset else (int(part) for part in period.split("-"))
    if start_day <= end_day:
        start = _clamped_date(year, month, start_day)
        end = _clamped_date(year, month, end_day)
    else:
        previous_month = 12 if month == 1 else month - 1
        previous_year = year - 1 if month == 1 else year
        start = _clamped_date(previous_year, previous_month, start_day)
        end = _clamped_date(year, month, end_day)
    return start.isoformat(), end.isoformat()


def month_range(db: Session, month) -> tuple[str, str]:
    """Faixa do mês; sem faixa gravada, usa a padrão das Configurações (sem gravar nada)."""
    if month.start_date and month.end_date:
        return month.start_date, month.end_date
    start_day, end_day = get_period_defaults(db)
    return default_period_range(month.period, start_day, end_day, REFERENCE_OFFSET_MONTHS)
