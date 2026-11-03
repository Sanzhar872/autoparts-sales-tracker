from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.constants import MAX_PRICE, OLD_CAR
from app.db import get_session
from app.models import Car, Sale
from app.parser import clean
from app.routers.common import check_period, period_filter, sale_dict, search_filter
from app.timeutil import at_noon, today

router = APIRouter(prefix="/sales", tags=["sales"])


class SaleIn(BaseModel):
    car_id: int
    old_car_code: str | None = None
    part: str
    price: int
    sold_date: date


@router.get("")
def list_sales(
    date_from: date | None = Query(None, alias="from"),
    date_to: date | None = Query(None, alias="to"),
    car_id: int | None = None,
    q: str | None = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
) -> dict:
    check_period(date_from, date_to)
    conditions = period_filter(Sale.sold_at, date_from, date_to) + search_filter(Sale, q)
    if car_id:
        conditions.append(Sale.car_id == car_id)
    total, amount = session.execute(
        select(func.count(), func.coalesce(func.sum(Sale.price), 0)).where(*conditions)
    ).one()
    sales = session.scalars(
        select(Sale).where(*conditions).order_by(Sale.sold_at.desc(), Sale.id.desc()).limit(limit).offset(offset)
    )
    return {"items": [sale_dict(s) for s in sales], "total": total, "sum": amount}


@router.patch("/{sale_id}")
def update_sale(sale_id: int, body: SaleIn, session: Session = Depends(get_session)) -> dict:
    sale = session.get(Sale, sale_id)
    if sale is None:
        raise HTTPException(404, "Продажа не найдена")
    car = session.get(Car, body.car_id)
    if car is None:
        raise HTTPException(400, "Марка не найдена")
    part = clean(body.part)
    if not part:
        raise HTTPException(400, "Не указана запчасть")
    if not 0 < body.price <= MAX_PRICE:
        raise HTTPException(400, "Цена должна быть целым числом больше нуля")
    if body.sold_date > today():
        raise HTTPException(400, "Дата продажи не может быть в будущем")
    code = clean(body.old_car_code or "").upper() or None
    if car.name == OLD_CAR:
        if not code or " " in code:
            raise HTTPException(400, "Для старого завоза укажите код машины одним словом")
    else:
        code = None

    sale.car_id = car.id
    sale.old_car_code = code
    sale.part = part
    sale.price = body.price
    sale.sold_at = at_noon(body.sold_date)
    session.commit()
    session.refresh(sale)
    return sale_dict(sale)


@router.delete("/{sale_id}", status_code=204)
def delete_sale(sale_id: int, session: Session = Depends(get_session)) -> None:
    sale = session.get(Sale, sale_id)
    if sale is None:
        raise HTTPException(404, "Продажа не найдена")
    session.delete(sale)
    session.commit()
