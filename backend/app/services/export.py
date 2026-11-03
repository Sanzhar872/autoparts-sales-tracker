"""Выгрузка в Excel. Файл собирается в памяти."""

from datetime import date
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import CURRENT_LABEL, OLD_CAR, OLD_CAR_LABEL
from app.models import Car, Return, Sale
from app.routers.common import period_filter
from app.timeutil import local_date

DATE_FORMAT = "DD.MM.YYYY"
PRICE_FORMAT = "#,##0"
BOLD = Font(bold=True)


def _source(car: Car, old_car_code: str | None) -> tuple[str, str]:
    """(Завоз, Авто)."""
    if car.name == OLD_CAR:
        return OLD_CAR_LABEL, old_car_code or ""
    return CURRENT_LABEL, car.name


def _write_table(ws: Worksheet, headers: list[str], rows: list[list], date_cols: set[int], price_cols: set[int]) -> None:
    ws.append(headers)
    for cell in ws[1]:
        cell.font = BOLD
    for row in rows:
        ws.append(row)
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            if cell.column in date_cols:
                cell.number_format = DATE_FORMAT
            elif cell.column in price_cols:
                cell.number_format = PRICE_FORMAT
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    _fit_columns(ws, date_cols, price_cols)


def _fit_columns(ws: Worksheet, date_cols: set[int], price_cols: set[int]) -> None:
    for idx, column in enumerate(ws.iter_cols(), start=1):
        width = 0
        for cell in column:
            if cell.value is None:
                continue
            if idx in date_cols and cell.row > 1:
                length = 10
            elif idx in price_cols and isinstance(cell.value, int):
                length = len(f"{cell.value:,}")
            else:
                length = len(str(cell.value))
            width = max(width, length)
        ws.column_dimensions[get_column_letter(idx)].width = min(max(width + 3, 8), 60)


def build_workbook(session: Session, date_from: date | None, date_to: date | None) -> bytes:
    sales = session.execute(
        select(Sale, Car)
        .join(Car, Sale.car_id == Car.id)
        .where(*period_filter(Sale.sold_at, date_from, date_to))
        .order_by(Car.name, Sale.old_car_code.nulls_first(), Sale.sold_at, Sale.id)
    ).all()
    returns = session.execute(
        select(Return, Car)
        .join(Car, Return.car_id == Car.id)
        .where(*period_filter(Return.returned_at, date_from, date_to))
        .order_by(Car.name, Return.old_car_code.nulls_first(), Return.returned_at, Return.id)
    ).all()

    wb = Workbook()
    ws = wb.active
    ws.title = "Продажи"
    _write_table(
        ws,
        ["Дата", "Завоз", "Авто", "Деталь", "Цена"],
        [[local_date(s.sold_at), *_source(car, s.old_car_code), s.part, s.price] for s, car in sales],
        date_cols={1},
        price_cols={5},
    )

    ws = wb.create_sheet("Возвраты")
    _write_table(
        ws,
        ["Дата продажи", "Дата возврата", "Завоз", "Авто", "Деталь", "Цена"],
        [
            [local_date(r.sold_at), local_date(r.returned_at), *_source(car, r.old_car_code), r.part, r.price]
            for r, car in returns
        ],
        date_cols={1, 2},
        price_cols={6},
    )

    totals: dict[str, list[int]] = {}
    for sale, car in sales:
        entry = totals.setdefault(car.label, [0, 0])
        entry[0] += 1
        entry[1] += sale.price
    rows = [[label, count, revenue] for label, (count, revenue) in totals.items()]
    ws = wb.create_sheet("Итоги")
    _write_table(ws, ["Марка", "Количество", "Выручка"], rows, date_cols=set(), price_cols={3})
    ws.append(["Итого", sum(r[1] for r in rows), sum(r[2] for r in rows)])
    ws.append([])
    ws.append(["Возвраты", "Количество", "Сумма"])
    ws.append(["Всего", len(returns), sum(r.price for r, _ in returns)])
    total_row, returns_header = ws.max_row - 3, ws.max_row - 1
    for row in (total_row, returns_header):
        for cell in ws[row]:
            cell.font = BOLD
    for row in (total_row, ws.max_row):
        ws.cell(row, 3).number_format = PRICE_FORMAT
    # Автофильтр — только на таблицу по маркам, без строки «Итого».
    ws.auto_filter.ref = f"A1:C{max(len(rows) + 1, 1)}"

    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
