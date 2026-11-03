from datetime import date, timedelta

from sqlalchemy import select

from app.models import Return, Sale
from app.timeutil import at_noon, today
from tests.helpers import add_sale, counts


def preview(client, text, day=None, choices=None):
    body = {"text": text, "choices": choices or {}}
    if day:
        body["date"] = day.isoformat()
    response = client.post("/api/entries/preview", json=body)
    assert response.status_code == 200, response.text
    return response.json()["items"]


def commit(client, text, day=None, choices=None):
    body = {"text": text, "choices": choices or {}}
    if day:
        body["date"] = day.isoformat()
    response = client.post("/api/entries/commit", json=body)
    assert response.status_code == 200, response.text
    return response.json()["items"]


def test_commit_sales_with_chosen_date(client, session, cars):
    day = today() - timedelta(days=3)
    items = commit(client, "мерс210 сафа левый правый - 25000\n\n  к20 капот с обшивкой - 70 000", day)
    assert [i["status"] for i in items] == ["ok", "ok"]
    assert [i["line"] for i in items] == [1, 3]
    sales = session.scalars(select(Sale).order_by(Sale.id)).all()
    assert [(s.car.name, s.part, s.price, s.sold_at) for s in sales] == [
        ("мерс210", "сафа левый правый", 25000, at_noon(day)),
        ("к20", "капот с обшивкой", 70000, at_noon(day)),
    ]


def test_default_date_is_today_and_future_rejected(client, session):
    commit(client, "к20 капот - 100")
    assert session.scalars(select(Sale)).one().sold_at == at_noon(today())
    response = client.post("/api/entries/preview", json={"text": "к20 капот - 100", "date": (today() + timedelta(days=1)).isoformat()})
    assert response.status_code == 400


def test_old_car_sale_with_code(client, session):
    items = commit(client, "С тке щиток прибора - 35000")
    assert items[0]["status"] == "ok"
    sale = session.scalars(select(Sale)).one()
    assert (sale.car.name, sale.old_car_code, sale.part, sale.price) == ("с", "ТКЕ", "щиток прибора", 35000)


def test_error_line_does_not_block_others(client, session):
    items = commit(client, "к20 капот - 100\nбмв капот - 100\nк25 дверь - 0\nк10 фара - 300")
    assert [i["status"] for i in items] == ["ok", "error", "error", "ok"]
    assert "Неизвестная марка" in items[1]["error"]
    assert counts(session) == (2, 0)


def test_return_no_match_shows_similar(client, session, cars):
    add_sale(session, cars["к20"], "капот с обшивкой", 70000, today())
    add_sale(session, cars["к20"], "капот", 50000, today())
    add_sale(session, cars["к10"], "капот с обшивкой", 70000, today())
    items = preview(client, "возврат к20 капот с обшивкой - 65000")
    assert items[0]["status"] == "error"
    assert items[0]["error"] == "Продажа для возврата не найдена"
    similar = items[0]["similar"]
    assert 1 <= len(similar) <= 5
    assert similar[0]["part"] == "капот с обшивкой"
    assert all(s["sale_id"] in (1, 2) for s in similar)  # только та же марка
    assert commit(client, "возврат к20 капот с обшивкой - 65000")[0]["saved"] is False
    assert counts(session) == (3, 0)


def test_return_single_match_moves_sale(client, session, cars):
    sold_day = today() - timedelta(days=10)
    add_sale(session, cars["к20"], "Капот  С обшивкой", 70000, sold_day)
    items = preview(client, "возврат K20 капот с обшивкой - 70 000")
    assert items[0]["status"] == "ok"
    assert items[0]["selected"] == "sale:1"

    items = commit(client, "возврат K20 капот с обшивкой - 70 000")
    assert items[0]["saved"] is True
    assert counts(session) == (0, 1)
    ret = session.scalars(select(Return)).one()
    assert (ret.car.name, ret.part, ret.price) == ("к20", "Капот  С обшивкой", 70000)
    assert ret.sold_at == at_noon(sold_day)
    assert ret.returned_at == at_noon(today())


def test_return_ignores_chosen_form_date(client, session, cars):
    add_sale(session, cars["к20"], "капот", 100, today() - timedelta(days=5))
    commit(client, "возврат к20 капот - 100", today() - timedelta(days=2))
    assert session.scalars(select(Return)).one().returned_at == at_noon(today())


def test_return_old_car_matches_code(client, session, cars):
    add_sale(session, cars["с"], "щиток прибора", 35000, today(), code="АБВ")
    add_sale(session, cars["с"], "щиток прибора", 35000, today(), code="ТКЕ")
    items = commit(client, "возврат С ТКЕ щиток прибора - 35000")
    assert items[0]["saved"] and items[0]["status"] == "ok"
    assert session.scalars(select(Sale)).one().old_car_code == "АБВ"
    assert session.scalars(select(Return)).one().old_car_code == "ТКЕ"


def test_return_multiple_matches(client, session, cars):
    old = add_sale(session, cars["к20"], "капот", 100, today() - timedelta(days=20))
    newest = add_sale(session, cars["к20"], "капот", 100, today() - timedelta(days=1))
    middle = add_sale(session, cars["к20"], "капот", 100, today() - timedelta(days=5))

    items = preview(client, "возврат к20 капот - 100")
    assert items[0]["status"] == "ambiguous"
    assert [o["sale_id"] for o in items[0]["options"]] == [newest.id, middle.id, old.id]
    assert items[0]["selected"] == f"sale:{newest.id}"

    items = commit(client, "возврат к20 капот - 100", choices={1: f"sale:{old.id}"})
    assert items[0]["saved"] is True
    remaining = {s.id for s in session.scalars(select(Sale))}
    assert remaining == {newest.id, middle.id}
    assert session.scalars(select(Return)).one().sold_at == old.sold_at


def test_return_multiple_matches_default_newest(client, session, cars):
    add_sale(session, cars["к20"], "капот", 100, today() - timedelta(days=20))
    newest = add_sale(session, cars["к20"], "капот", 100, today())
    commit(client, "возврат к20 капот - 100")
    assert newest.id not in {s.id for s in session.scalars(select(Sale))}


def test_invalid_choice_is_error(client, session, cars):
    add_sale(session, cars["к20"], "капот", 100, today())
    add_sale(session, cars["к20"], "капот", 100, today())
    items = commit(client, "возврат к20 капот - 100", choices={1: "sale:999"})
    assert items[0]["saved"] is False
    assert counts(session) == (2, 0)


def test_preview_does_not_change_db(client, session, cars):
    add_sale(session, cars["к20"], "капот", 100, today())
    before = counts(session)
    items = preview(client, "к10 фара - 500\nвозврат к20 капот - 100\nвозврат к10 фара - 500\nбмв - 1")
    assert [i["status"] for i in items] == ["ok", "ok", "ok", "error"]
    assert counts(session) == before
    assert session.scalars(select(Sale)).one().part == "капот"


def test_return_of_sale_added_above_in_same_batch(client, session):
    text = "к20 капот - 100\nвозврат к20 капот - 100\nвозврат к20 капот - 100"
    items = preview(client, text)
    assert [i["status"] for i in items] == ["ok", "ok", "error"]
    assert items[1]["selected"] == "line:1"

    items = commit(client, text)
    assert [i["saved"] for i in items] == [True, True, False]
    assert counts(session) == (0, 1)


def test_ambiguous_with_batch_sale_choose_batch_line(client, session, cars):
    db_sale = add_sale(session, cars["к20"], "капот", 100, today() - timedelta(days=3))
    text = "к20 капот - 100\nвозврат к20 капот - 100"
    items = preview(client, text)
    assert items[1]["status"] == "ambiguous"
    assert [o["ref"] for o in items[1]["options"]] == ["line:1", f"sale:{db_sale.id}"]

    items = commit(client, text, choices={2: f"sale:{db_sale.id}"})
    assert [i["saved"] for i in items] == [True, True]
    assert session.scalars(select(Sale)).one().id == items[0]["sale_id"]

    items = commit(client, text, choices={2: "line:1"})
    assert [i["saved"] for i in items] == [True, True]
    assert session.scalars(select(Sale)).one().id == items[0]["sale_id"] - 1


def test_two_returns_of_one_sale_in_batch(client, session, cars):
    add_sale(session, cars["к20"], "капот", 100, today())
    items = commit(client, "возврат к20 капот - 100\nвозврат к20 капот - 100")
    assert [i["saved"] for i in items] == [True, False]
    assert counts(session) == (0, 1)


def test_cancel_return_restores_original_date(client, session, cars):
    sold_day = date(2025, 3, 14)
    add_sale(session, cars["с"], "щиток", 35000, sold_day, code="ТКЕ")
    commit(client, "возврат с ткЕ щиток - 35000")
    ret_id = session.scalars(select(Return)).one().id

    response = client.post(f"/api/returns/{ret_id}/cancel")
    assert response.status_code == 200
    assert counts(session) == (1, 0)
    sale = session.scalars(select(Sale)).one()
    assert (sale.car.name, sale.old_car_code, sale.part, sale.price) == ("с", "ТКЕ", "щиток", 35000)
    assert sale.sold_at == at_noon(sold_day)
    assert client.post(f"/api/returns/{ret_id}/cancel").status_code == 404
