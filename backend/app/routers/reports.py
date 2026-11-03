from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Car, Return, Sale
from app.routers.common import check_period
from app.services.export import build_workbook
from app.services.stats import build_stats

router = APIRouter(tags=["reports"])

PART_SUGGESTIONS_LIMIT = 3000


@router.get("/stats")
def stats(
    group: Literal["week", "month"] = "week",
    date_from: date | None = Query(None, alias="from"),
    date_to: date | None = Query(None, alias="to"),
    car_id: int | None = None,
    session: Session = Depends(get_session),
) -> dict:
    check_period(date_from, date_to)
    return build_stats(session, group, date_from, date_to, car_id)


@router.get("/export.xlsx")
def export_xlsx(
    date_from: date | None = Query(None, alias="from"),
    date_to: date | None = Query(None, alias="to"),
    session: Session = Depends(get_session),
) -> Response:
    check_period(date_from, date_to)
    content = build_workbook(session, date_from, date_to)
    if date_from or date_to:
        name = f"prodazhi_{date_from or 'nachalo'}_{date_to or 'segodnya'}.xlsx"
    else:
        name = "prodazhi_vse.xlsx"
    return Response(
        content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@router.get("/suggestions")
def suggestions(session: Session = Depends(get_session)) -> dict:
    """Подсказки для поля ввода: марки, запчасти по маркам (частые сначала), коды старых машин."""
    cars = session.scalars(select(Car).order_by(Car.name)).all()
    names = {car.id: car.name for car in cars}

    key = func.lower(Sale.part)
    rows = session.execute(
        select(Sale.car_id, func.min(Sale.part), func.count().label("n"))
        .group_by(Sale.car_id, key)
        .order_by(func.count().desc())
        .limit(PART_SUGGESTIONS_LIMIT)
    )
    parts: dict[str, list[str]] = {}
    for car_id, part, _ in rows:
        parts.setdefault(names[car_id], []).append(part)

    codes = session.scalars(
        select(Sale.old_car_code).where(Sale.old_car_code.is_not(None))
        .union(select(Return.old_car_code).where(Return.old_car_code.is_not(None)))
    ).all()
    return {
        "cars": [{"name": car.name, "label": car.label} for car in cars],
        "parts": parts,
        "codes": sorted(codes),
    }
