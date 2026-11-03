import datetime as dt

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_session
from app.services import entries
from app.timeutil import today

router = APIRouter(prefix="/entries", tags=["entries"])


class EntriesIn(BaseModel):
    text: str = Field(max_length=200_000)
    date: dt.date | None = None
    # Номер строки -> выбранный вариант для неоднозначного возврата («sale:<id>» или «line:<номер>»).
    choices: dict[int, str] = {}


def _sale_date(body: EntriesIn) -> dt.date:
    sale_date = body.date or today()
    if sale_date > today():
        raise HTTPException(400, "Дата продажи не может быть в будущем")
    return sale_date


@router.post("/preview")
def preview(body: EntriesIn, session: Session = Depends(get_session)) -> dict:
    return {"items": entries.preview(session, body.text, _sale_date(body), body.choices)}


@router.post("/commit")
def commit(body: EntriesIn, session: Session = Depends(get_session)) -> dict:
    items = entries.commit(session, body.text, _sale_date(body), body.choices)
    return {
        "items": items,
        "saved": sum(1 for item in items if item["saved"]),
        "errors": sum(1 for item in items if not item["saved"]),
    }
