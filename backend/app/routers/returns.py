from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Return
from app.routers.common import check_period, period_filter, return_dict, search_filter
from app.services.entries import cancel_return

router = APIRouter(prefix="/returns", tags=["returns"])


@router.get("")
def list_returns(
    date_from: date | None = Query(None, alias="from"),
    date_to: date | None = Query(None, alias="to"),
    car_id: int | None = None,
    q: str | None = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
) -> dict:
    check_period(date_from, date_to)
    conditions = period_filter(Return.returned_at, date_from, date_to) + search_filter(Return, q)
    if car_id:
        conditions.append(Return.car_id == car_id)
    total, amount = session.execute(
        select(func.count(), func.coalesce(func.sum(Return.price), 0)).where(*conditions)
    ).one()
    returns = session.scalars(
        select(Return).where(*conditions).order_by(Return.returned_at.desc(), Return.id.desc()).limit(limit).offset(offset)
    )
    return {"items": [return_dict(r) for r in returns], "total": total, "sum": amount}


@router.post("/{return_id}/cancel")
def cancel(return_id: int, session: Session = Depends(get_session)) -> dict:
    ret = session.get(Return, return_id, with_for_update={"of": Return})
    if ret is None:
        raise HTTPException(404, "Возврат не найден")
    sale = cancel_return(session, ret)
    session.commit()
    return {"sale_id": sale.id}
