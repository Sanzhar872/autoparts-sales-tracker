from datetime import timedelta

from fastapi.testclient import TestClient

from app.main import app
from app.timeutil import today
from tests.helpers import add_sale, counts


def test_health_without_auth(session):
    with TestClient(app) as c:
        response = c.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_api_requires_auth(session):
    with TestClient(app) as c:
        for path in ("/api/cars", "/api/sales", "/api/returns", "/api/stats", "/api/export.xlsx", "/api/suggestions", "/api/auth/me"):
            assert c.get(path).status_code == 401, path
        assert c.post("/api/entries/preview", json={"text": "к20 a - 1"}).status_code == 401
        assert c.post("/api/auth/login", json={"password": "wrong"}).status_code == 401
        response = c.post("/api/auth/login", json={"password": "test-password"})
        assert response.status_code == 200
        cookie = response.headers["set-cookie"].lower()
        assert "httponly" in cookie and "samesite=lax" in cookie and "max-age=2592000" in cookie
        assert c.get("/api/cars").status_code == 200
        c.post("/api/auth/logout")
        assert c.get("/api/cars").status_code == 401


def test_cars_crud_and_protection(client, session, cars):
    response = client.post("/api/cars", json={"name": "  НИВA "})
    assert response.status_code == 201
    new = response.json()
    assert new["name"] == "нива"
    assert client.post("/api/cars", json={"name": "НИВА"}).status_code == 409
    assert client.post("/api/cars", json={"name": "две марки"}).status_code == 400

    assert client.patch(f"/api/cars/{new['id']}", json={"name": "нива2"}).json()["name"] == "нива2"
    assert client.delete(f"/api/cars/{new['id']}").status_code == 204

    old = cars["с"].id
    assert client.patch(f"/api/cars/{old}", json={"name": "старый"}).status_code == 400
    assert client.delete(f"/api/cars/{old}").status_code == 400

    add_sale(session, cars["к20"], "капот", 100, today())
    assert client.delete(f"/api/cars/{cars['к20'].id}").status_code == 409
    client.post("/api/entries/commit", json={"text": "возврат к20 капот - 100"})
    assert counts(session) == (0, 1)
    assert client.delete(f"/api/cars/{cars['к20'].id}").status_code == 409
    assert client.delete(f"/api/cars/{cars['к10'].id}").status_code == 204


def test_sales_filters_edit_delete(client, session, cars):
    add_sale(session, cars["к20"], "капот", 100, today() - timedelta(days=10))
    sale = add_sale(session, cars["к10"], "фара левая", 200, today())
    data = client.get("/api/sales", params={"q": "ФАРА"}).json()
    assert data["total"] == 1 and data["sum"] == 200
    data = client.get("/api/sales", params={"from": (today() - timedelta(days=1)).isoformat()}).json()
    assert [s["id"] for s in data["items"]] == [sale.id]
    assert client.get("/api/sales", params={"car_id": cars["к20"].id}).json()["total"] == 1

    body = {"car_id": cars["с"].id, "old_car_code": "тке", "part": " фара  правая ", "price": 300, "sold_date": today().isoformat()}
    updated = client.patch(f"/api/sales/{sale.id}", json=body).json()
    assert (updated["car"], updated["old_car_code"], updated["part"], updated["price"]) == ("с", "ТКЕ", "фара правая", 300)
    assert client.patch(f"/api/sales/{sale.id}", json={**body, "old_car_code": ""}).status_code == 400
    assert client.patch(f"/api/sales/{sale.id}", json={**body, "price": 0}).status_code == 400

    assert client.delete(f"/api/sales/{sale.id}").status_code == 204
    assert counts(session) == (1, 0)


def test_suggestions(client, session, cars):
    add_sale(session, cars["к20"], "капот", 100, today())
    add_sale(session, cars["к20"], "Капот", 100, today())
    add_sale(session, cars["с"], "щиток", 100, today(), code="ТКЕ")
    data = client.get("/api/suggestions").json()
    assert {"name": "с", "label": "Старый завоз"} in data["cars"]
    assert len(data["parts"]["к20"]) == 1
    assert data["codes"] == ["ТКЕ"]
