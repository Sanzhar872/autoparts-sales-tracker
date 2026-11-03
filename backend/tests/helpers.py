from datetime import date

from sqlalchemy import func, select

from app.models import Return, Sale
from app.timeutil import at_noon


def add_sale(session, car, part, price, day: date, code=None) -> Sale:
    sale = Sale(car_id=car.id, old_car_code=code, part=part, price=price, sold_at=at_noon(day))
    session.add(sale)
    session.commit()
    return sale


def counts(session) -> tuple[int, int]:
    session.expire_all()
    return (
        session.scalar(select(func.count()).select_from(Sale)),
        session.scalar(select(func.count()).select_from(Return)),
    )
