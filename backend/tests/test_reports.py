from datetime import date
from io import BytesIO

from openpyxl import load_workbook

from app.timeutil import today
from tests.helpers import add_sale


def test_stats_does_not_subtract_return_twice(client, session, cars):
    day = today()
    add_sale(session, cars["к20"], "капот", 70000, day)
    add_sale(session, cars["к20"], "дверь", 30000, day)
    client.post("/api/entries/commit", json={"text": "возврат к20 капот - 70000"})

    stats = client.get("/api/stats", params={"group": "month"}).json()
    assert stats["total"] == {"count": 1, "revenue": 30000, "returns_count": 1, "returns_sum": 70000}
    assert stats["periods"][-1]["revenue"] == 30000
    assert stats["by_car"] == [
        {"car_id": cars["к20"].id, "label": "к20", "count": 1, "revenue": 30000, "returns_count": 1, "returns_sum": 70000}
    ]


def test_stats_weeks_start_monday_and_old_car_label(client, session, cars):
    add_sale(session, cars["к20"], "a", 100, date(2026, 9, 6))  # воскресенье
    add_sale(session, cars["к20"], "b", 200, date(2026, 9, 7))  # понедельник
    add_sale(session, cars["с"], "c", 300, date(2026, 9, 8), code="ТКЕ")
    add_sale(session, cars["с"], "d", 400, date(2026, 9, 9), code="АБВ")

    stats = client.get("/api/stats", params={"group": "week", "from": "2026-08-31", "to": "2026-09-13"}).json()
    assert [(p["start"], p["count"], p["revenue"]) for p in stats["periods"]] == [
        ("2026-08-31", 1, 100),
        ("2026-09-07", 3, 900),
    ]
    labels = {c["label"]: c["revenue"] for c in stats["by_car"]}
    assert labels == {"к20": 300, "Старый завоз": 700}

    one_car = client.get(
        "/api/stats", params={"group": "month", "from": "2026-09-01", "to": "2026-09-30", "car_id": cars["с"].id}
    ).json()
    assert one_car["total"]["revenue"] == 700


def test_excel_sheets_columns_and_sorting(client, session, cars):
    add_sale(session, cars["с"], "щиток", 35000, date(2026, 9, 2), code="ТКЕ")
    add_sale(session, cars["к20"], "капот", 70000, date(2026, 9, 5))
    add_sale(session, cars["с"], "фара", 5000, date(2026, 9, 1), code="АБВ")
    add_sale(session, cars["к20"], "дверь", 1500000, date(2026, 9, 1))
    add_sale(session, cars["мерс210"], "сафа", 25000, date(2026, 9, 3))
    add_sale(session, cars["с"], "крыло", 7000, date(2026, 9, 1), code="ТКЕ")
    add_sale(session, cars["к10"], "вне периода", 1, date(2026, 10, 1))
    client.post("/api/entries/commit", json={"text": "возврат мерс210 сафа - 25000"})

    response = client.get("/api/export.xlsx", params={"from": "2026-09-01", "to": "2026-09-30"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/vnd.openxmlformats")
    wb = load_workbook(BytesIO(response.content))
    assert wb.sheetnames == ["Продажи", "Возвраты", "Итоги"]

    ws = wb["Продажи"]
    rows = list(ws.iter_rows(values_only=True))
    assert rows[0] == ("Дата", "Завоз", "Авто", "Деталь", "Цена")
    assert [(r[0].date(), r[1], r[2], r[3], r[4]) for r in rows[1:]] == [
        (date(2026, 9, 1), "Текущий", "к20", "дверь", 1500000),
        (date(2026, 9, 5), "Текущий", "к20", "капот", 70000),
        (date(2026, 9, 1), "Старый завоз", "АБВ", "фара", 5000),
        (date(2026, 9, 1), "Старый завоз", "ТКЕ", "крыло", 7000),
        (date(2026, 9, 2), "Старый завоз", "ТКЕ", "щиток", 35000),
    ]
    assert ws.freeze_panes == "A2"
    assert ws.auto_filter.ref == "A1:E6"
    assert ws["A1"].font.bold
    assert ws["A2"].number_format == "DD.MM.YYYY"
    assert ws["E2"].number_format == "#,##0"

    rows = list(wb["Возвраты"].iter_rows(values_only=True))
    assert rows[0] == ("Дата продажи", "Дата возврата", "Завоз", "Авто", "Деталь", "Цена")
    # Возврат проведён сегодня, а фильтр возвратов — по дате возврата: в выгрузку за сентябрь он не попадает.
    assert len(rows) == 1

    rows = list(wb["Итоги"].iter_rows(values_only=True))
    assert rows[0] == ("Марка", "Количество", "Выручка")
    assert rows[1:4] == [("к20", 2, 1570000), ("Старый завоз", 3, 47000), ("Итого", 5, 1617000)]
    assert rows[-2] == ("Возвраты", "Количество", "Сумма")


def test_excel_without_period_exports_everything(client, session, cars):
    add_sale(session, cars["к20"], "капот", 100, date(2020, 1, 1))
    add_sale(session, cars["к10"], "фара", 200, today())
    client.post("/api/entries/commit", json={"text": "возврат к10 фара - 200"})
    wb = load_workbook(BytesIO(client.get("/api/export.xlsx").content))
    assert wb["Продажи"].max_row == 2
    rows = list(wb["Возвраты"].iter_rows(values_only=True))
    assert [(r[0].date(), r[1].date(), r[2], r[3], r[4], r[5]) for r in rows[1:]] == [
        (today(), today(), "Текущий", "к10", "фара", 200)
    ]
    rows = list(wb["Итоги"].iter_rows(values_only=True))
    assert rows[-1] == ("Всего", 1, 200)  # возвраты не вычитаются из выручки
    assert ("Итого", 1, 100) in rows
