"""Статистика. Считается запросами к БД, без хранимых итогов.

Выручка и количество — только по sales (по sold_at): возвращённая продажа уже удалена
из sales, поэтому возвраты отдельно не вычитаются. Возвраты считаются отдельно по returned_at.
"""

from datetime import date, timedelta
from typing import Literal

from sqlalchemy import func, literal_column, select
from sqlalchemy.orm import Session

from app.models import Car, Return, Sale
from app.routers.common import period_filter
from app.timeutil import TZ_NAME, today

Group = Literal["week", "month"]
DEFAULT_PERIODS = 12


def bucket_start(d: date, group: Group) -> date:
    if group == "week":
        return d - timedelta(days=d.weekday())
    return d.replace(day=1)


def next_bucket(d: date, group: Group) -> date:
    if group == "week":
        return d + timedelta(days=7)
    return (d.replace(day=28) + timedelta(days=4)).replace(day=1)


def default_from(group: Group, to: date) -> date:
    start = bucket_start(to, group)
    for _ in range(DEFAULT_PERIODS - 1):
        start = bucket_start(start - timedelta(days=1), group)
    return start


def _bucket(column, group: Group):
    # Поле date_trunc вставляется литералом: с параметром Postgres не сопоставит SELECT и GROUP BY.
    # Неделя в Postgres начинается с понедельника.
    local = func.timezone(TZ_NAME, column)
    return func.date_trunc(literal_column(f"'{group}'"), local)


def _per_period(session: Session, model, column, group: Group, conditions) -> dict[date, tuple[int, int]]:
    bucket = _bucket(column, group).label("bucket")
    rows = session.execute(
        select(bucket, func.count(), func.coalesce(func.sum(model.price), 0)).where(*conditions).group_by(bucket)
    )
    return {row[0].date(): (row[1], row[2]) for row in rows}


def _per_car(session: Session, model, conditions) -> dict[int, tuple[int, int]]:
    rows = session.execute(
        select(model.car_id, func.count(), func.coalesce(func.sum(model.price), 0)).where(*conditions).group_by(model.car_id)
    )
    return {row[0]: (row[1], row[2]) for row in rows}


def build_stats(session: Session, group: Group, date_from: date | None, date_to: date | None, car_id: int | None) -> dict:
    date_to = date_to or today()
    date_from = date_from or default_from(group, date_to)

    sale_cond = period_filter(Sale.sold_at, date_from, date_to)
    ret_cond = period_filter(Return.returned_at, date_from, date_to)
    if car_id:
        sale_cond.append(Sale.car_id == car_id)
        ret_cond.append(Return.car_id == car_id)

    sales_by_period = _per_period(session, Sale, Sale.sold_at, group, sale_cond)
    returns_by_period = _per_period(session, Return, Return.returned_at, group, ret_cond)

    periods = []
    start = bucket_start(date_from, group)
    while start <= date_to:
        count, revenue = sales_by_period.get(start, (0, 0))
        returns_count, returns_sum = returns_by_period.get(start, (0, 0))
        periods.append({
            "start": start.isoformat(),
            "end": min(next_bucket(start, group) - timedelta(days=1), date_to).isoformat(),
            "count": count,
            "revenue": revenue,
            "returns_count": returns_count,
            "returns_sum": returns_sum,
        })
        start = next_bucket(start, group)

    sales_by_car = _per_car(session, Sale, sale_cond)
    returns_by_car = _per_car(session, Return, ret_cond)
    by_car = []
    for car in session.scalars(select(Car).order_by(Car.name)):
        if car_id and car.id != car_id:
            continue
        count, revenue = sales_by_car.get(car.id, (0, 0))
        returns_count, returns_sum = returns_by_car.get(car.id, (0, 0))
        if count or returns_count or car_id:
            by_car.append({
                "car_id": car.id,
                "label": car.label,
                "count": count,
                "revenue": revenue,
                "returns_count": returns_count,
                "returns_sum": returns_sum,
            })

    total = {
        key: sum(p[key] for p in periods) for key in ("count", "revenue", "returns_count", "returns_sum")
    }
    return {
        "group": group,
        "from": date_from.isoformat(),
        "to": date_to.isoformat(),
        "car_id": car_id,
        "periods": periods,
        "by_car": by_car,
        "total": total,
    }
