from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.constants import OLD_CAR
from app.db import get_session
from app.models import Car, Return, Sale
from app.parser import RETURN_WORD, clean, normalize_car

router = APIRouter(prefix="/cars", tags=["cars"])


class CarIn(BaseModel):
    name: str


def _normalized_name(raw: str) -> str:
    name = normalize_car(clean(raw))
    if not name:
        raise HTTPException(400, "Укажите название марки")
    if " " in name:
        raise HTTPException(400, "Название марки — одно слово без пробелов")
    if len(name) > 50:
        raise HTTPException(400, "Слишком длинное название")
    if name == RETURN_WORD:
        raise HTTPException(400, "Это слово зарезервировано")
    return name


def _get_car(session: Session, car_id: int) -> Car:
    car = session.get(Car, car_id)
    if car is None:
        raise HTTPException(404, "Марка не найдена")
    return car


def _car_dict(car: Car, sales_count: int = 0, returns_count: int = 0) -> dict:
    return {
        "id": car.id,
        "name": car.name,
        "label": car.label,
        "is_service": car.name == OLD_CAR,
        "sales_count": sales_count,
        "returns_count": returns_count,
    }


def _save(session: Session, car: Car) -> None:
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, "Такая марка уже есть")


@router.get("")
def list_cars(session: Session = Depends(get_session)) -> list[dict]:
    sales = dict(session.execute(select(Sale.car_id, func.count()).group_by(Sale.car_id)).all())
    returns = dict(session.execute(select(Return.car_id, func.count()).group_by(Return.car_id)).all())
    cars = session.scalars(select(Car).order_by(Car.name))
    return [_car_dict(car, sales.get(car.id, 0), returns.get(car.id, 0)) for car in cars]


@router.post("", status_code=201)
def create_car(body: CarIn, session: Session = Depends(get_session)) -> dict:
    car = Car(name=_normalized_name(body.name))
    session.add(car)
    _save(session, car)
    return _car_dict(car)


@router.patch("/{car_id}")
def rename_car(car_id: int, body: CarIn, session: Session = Depends(get_session)) -> dict:
    car = _get_car(session, car_id)
    if car.name == OLD_CAR:
        raise HTTPException(400, "Служебную марку «с» нельзя переименовать")
    car.name = _normalized_name(body.name)
    _save(session, car)
    return _car_dict(car)


@router.delete("/{car_id}", status_code=204)
def delete_car(car_id: int, session: Session = Depends(get_session)) -> None:
    car = _get_car(session, car_id)
    if car.name == OLD_CAR:
        raise HTTPException(400, "Служебную марку «с» нельзя удалить")
    used = session.scalar(select(func.count()).select_from(Sale).where(Sale.car_id == car_id))
    used += session.scalar(select(func.count()).select_from(Return).where(Return.car_id == car_id))
    if used:
        raise HTTPException(409, "Нельзя удалить марку, по которой есть продажи или возвраты")
    session.delete(car)
    session.commit()
