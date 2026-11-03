"""Предпросмотр и сохранение пакета строк.

Строки обрабатываются по порядку. В предпросмотре изменения пакета держатся в памяти
(добавленные выше продажи и уже «возвращённые» продажи), в БД ничего не пишется.
При сохранении каждая строка коммитится отдельно, поэтому следующие строки видят
результат предыдущих прямо в БД.

Вариант продажи для возврата задаётся ссылкой: «sale:<id>» — продажа из БД,
«line:<номер>» — продажа, добавленная строкой с этим номером в том же пакете.
"""

from dataclasses import dataclass
from datetime import date, datetime
from difflib import SequenceMatcher
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Car, Return, Sale
from app.parser import ParseError, ParsedLine, clean, parse_line, part_key
from app.timeutil import at_noon, local_date, today

SIMILAR_LIMIT = 5


@dataclass
class Candidate:
    ref: str
    sale_id: int | None
    line: int | None
    car_id: int
    old_car_code: str | None
    part: str
    price: int
    sold_at: datetime

    def sort_key(self) -> tuple:
        # Новее — больше sold_at; при равной дате продажи пакета новее продаж из БД,
        # а среди одних и тех же — больше id / номер строки.
        return (self.sold_at, self.sale_id is None, self.sale_id or self.line or 0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ref": self.ref,
            "sale_id": self.sale_id,
            "line": self.line,
            "old_car_code": self.old_car_code,
            "part": self.part,
            "price": self.price,
            "sold_date": local_date(self.sold_at).isoformat(),
        }


def _from_sale(sale: Sale) -> Candidate:
    return Candidate(
        ref=f"sale:{sale.id}",
        sale_id=sale.id,
        line=None,
        car_id=sale.car_id,
        old_car_code=sale.old_car_code,
        part=sale.part,
        price=sale.price,
        sold_at=sale.sold_at,
    )


class BatchProcessor:
    def __init__(self, session: Session, sale_date: date, choices: dict[int, str], commit: bool):
        self.session = session
        self.sale_date = sale_date
        self.choices = choices
        self.commit = commit
        self.cars = {car.name: car for car in session.scalars(select(Car))}
        # Только для предпросмотра.
        self.pending: dict[int, Candidate] = {}
        self.removed_ids: set[int] = set()
        # Только для сохранения: номер строки -> id созданной продажи.
        self.line_sale_ids: dict[int, int] = {}

    def run(self, text: str) -> list[dict[str, Any]]:
        results = []
        for number, raw in enumerate(text.splitlines(), start=1):
            line = clean(raw)
            if line:
                results.append(self._process(number, line))
        return results

    def _process(self, number: int, line: str) -> dict[str, Any]:
        item: dict[str, Any] = {
            "line": number,
            "text": line,
            "kind": None,
            "status": "error",
            "error": None,
            "saved": False,
            "options": [],
            "selected": None,
            "similar": [],
        }
        try:
            parsed = parse_line(line, self.cars.keys())
        except ParseError as e:
            item["error"] = str(e)
            return item

        car = self.cars[parsed.car]
        item.update(
            kind="return" if parsed.is_return else "sale",
            car=car.name,
            car_label=car.label,
            old_car_code=parsed.old_car_code,
            part=parsed.part,
            price=parsed.price,
        )
        try:
            if parsed.is_return:
                self._process_return(number, parsed, car, item)
            else:
                self._process_sale(number, parsed, car, item)
        except Exception:
            if not self.commit:
                raise
            self.session.rollback()
            item.update(status="error", error="Не удалось сохранить строку", saved=False)
        return item

    def _process_sale(self, number: int, parsed: ParsedLine, car: Car, item: dict[str, Any]) -> None:
        sold_at = at_noon(self.sale_date)
        item.update(status="ok", sold_date=self.sale_date.isoformat())
        if self.commit:
            sale = Sale(car_id=car.id, old_car_code=parsed.old_car_code, part=parsed.part, price=parsed.price, sold_at=sold_at)
            self.session.add(sale)
            self.session.commit()
            self.line_sale_ids[number] = sale.id
            item.update(saved=True, sale_id=sale.id)
        else:
            self.pending[number] = Candidate(
                ref=f"line:{number}",
                sale_id=None,
                line=number,
                car_id=car.id,
                old_car_code=parsed.old_car_code,
                part=parsed.part,
                price=parsed.price,
                sold_at=sold_at,
            )

    def _process_return(self, number: int, parsed: ParsedLine, car: Car, item: dict[str, Any]) -> None:
        item["returned_date"] = today().isoformat()
        candidates = self._find_candidates(car, parsed)
        if not candidates:
            item["error"] = "Продажа для возврата не найдена"
            item["similar"] = [c.to_dict() for c in self._similar(car, parsed)]
            return

        chosen = candidates[0]
        choice = self._resolve_choice(self.choices.get(number))
        if choice is not None:
            matching = [c for c in candidates if c.ref == choice]
            if not matching:
                item["error"] = "Выбранная продажа уже недоступна, проверьте варианты заново"
                item["options"] = [c.to_dict() for c in candidates]
                item["selected"] = chosen.ref
                return
            chosen = matching[0]

        item["status"] = "ok" if len(candidates) == 1 else "ambiguous"
        if len(candidates) > 1:
            item["options"] = [c.to_dict() for c in candidates]
        item["selected"] = chosen.ref
        item["sold_date"] = local_date(chosen.sold_at).isoformat()

        if not self.commit:
            if chosen.sale_id is None:
                del self.pending[chosen.line]
            else:
                self.removed_ids.add(chosen.sale_id)
            return

        sale = self.session.get(Sale, chosen.sale_id, with_for_update={"of": Sale})
        if sale is None:
            self.session.rollback()
            item.update(status="error", error="Продажа уже возвращена или удалена")
            return
        ret = move_sale_to_returns(self.session, sale)
        self.session.commit()
        item.update(status="ok", saved=True, return_id=ret.id)

    def _resolve_choice(self, choice: str | None) -> str | None:
        """В режиме сохранения ссылка на строку пакета превращается в ссылку на созданную продажу."""
        if choice and self.commit and choice.startswith("line:"):
            try:
                sale_id = self.line_sale_ids.get(int(choice[5:]))
            except ValueError:
                return choice
            return f"sale:{sale_id}" if sale_id else choice
        return choice

    def _find_candidates(self, car: Car, parsed: ParsedLine) -> list[Candidate]:
        key = part_key(parsed.part)
        query = select(Sale).where(
            Sale.car_id == car.id,
            Sale.price == parsed.price,
            func.lower(func.btrim(func.regexp_replace(Sale.part, r"\s+", " ", "g"))) == key,
        )
        if parsed.old_car_code is None:
            query = query.where(Sale.old_car_code.is_(None))
        else:
            query = query.where(Sale.old_car_code == parsed.old_car_code)

        candidates = [_from_sale(s) for s in self.session.scalars(query) if s.id not in self.removed_ids]
        candidates += [
            c
            for c in self.pending.values()
            if c.car_id == car.id
            and c.price == parsed.price
            and c.old_car_code == parsed.old_car_code
            and part_key(c.part) == key
        ]
        candidates.sort(key=Candidate.sort_key, reverse=True)
        return candidates

    def _similar(self, car: Car, parsed: ParsedLine) -> list[Candidate]:
        key = part_key(parsed.part)
        sales = self.session.scalars(
            select(Sale).where(Sale.car_id == car.id).order_by(Sale.sold_at.desc(), Sale.id.desc()).limit(2000)
        )
        scored = []
        for sale in sales:
            if sale.id in self.removed_ids:
                continue
            score = SequenceMatcher(None, key, part_key(sale.part)).ratio()
            if sale.price == parsed.price:
                score += 0.3
            if parsed.old_car_code and sale.old_car_code == parsed.old_car_code:
                score += 0.3
            scored.append((score, sale))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [_from_sale(sale) for _, sale in scored[:SIMILAR_LIMIT]]


def move_sale_to_returns(session: Session, sale: Sale) -> Return:
    """Перенести продажу в возвраты. Коммит — на вызывающей стороне."""
    ret = Return(
        car_id=sale.car_id,
        old_car_code=sale.old_car_code,
        part=sale.part,
        price=sale.price,
        sold_at=sale.sold_at,
        returned_at=at_noon(today()),
    )
    session.add(ret)
    session.delete(sale)
    session.flush()
    return ret


def cancel_return(session: Session, ret: Return) -> Sale:
    """Восстановить продажу с исходной датой. Коммит — на вызывающей стороне."""
    sale = Sale(
        car_id=ret.car_id,
        old_car_code=ret.old_car_code,
        part=ret.part,
        price=ret.price,
        sold_at=ret.sold_at,
    )
    session.add(sale)
    session.delete(ret)
    session.flush()
    return sale


def preview(session: Session, text: str, sale_date: date, choices: dict[int, str]) -> list[dict[str, Any]]:
    try:
        return BatchProcessor(session, sale_date, choices, commit=False).run(text)
    finally:
        session.rollback()


def commit(session: Session, text: str, sale_date: date, choices: dict[int, str]) -> list[dict[str, Any]]:
    return BatchProcessor(session, sale_date, choices, commit=True).run(text)
