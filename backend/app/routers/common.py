from datetime import date

from fastapi import HTTPException
from sqlalchemy import ColumnElement, or_

from app.models import Return, Sale
from app.timeutil import day_end_exclusive, day_start, local_date


def check_period(date_from: date | None, date_to: date | None) -> None:
    if date_from and date_to and date_from > date_to:
        raise HTTPException(400, "Начало периода позже конца")


def period_filter(column, date_from: date | None, date_to: date | None) -> list[ColumnElement[bool]]:
    conditions = []
    if date_from:
        conditions.append(column >= day_start(date_from))
    if date_to:
        conditions.append(column < day_end_exclusive(date_to))
    return conditions


def search_filter(model: type[Sale] | type[Return], q: str | None) -> list[ColumnElement[bool]]:
    q = " ".join((q or "").split())
    if not q:
        return []
    escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    pattern = "%" + escaped + "%"
    return [or_(model.part.ilike(pattern, escape="\\"), model.old_car_code.ilike(pattern, escape="\\"))]


def sale_dict(sale: Sale) -> dict:
    return {
        "id": sale.id,
        "car_id": sale.car_id,
        "car": sale.car.name,
        "car_label": sale.car.label,
        "old_car_code": sale.old_car_code,
        "part": sale.part,
        "price": sale.price,
        "sold_date": local_date(sale.sold_at).isoformat(),
    }


def return_dict(ret: Return) -> dict:
    return {
        "id": ret.id,
        "car_id": ret.car_id,
        "car": ret.car.name,
        "car_label": ret.car.label,
        "old_car_code": ret.old_car_code,
        "part": ret.part,
        "price": ret.price,
        "sold_date": local_date(ret.sold_at).isoformat(),
        "returned_date": local_date(ret.returned_at).isoformat(),
    }
