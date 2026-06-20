from tests.conftest import valid_payload


async def test_contact_success(client):
    response = await client.post("/api/contact", json=valid_payload())
    assert response.status_code == 201

    data = response.json()
    assert data["success"] is True
    assert data["request_id"]
    # Без ключа анализ выполняет fallback, но результат всё равно должен прийти.
    assert data["analysis"]["provider"] == "fallback"
    # В тексте есть «заказать», «под ключ», «бюджет» — это заказ.
    assert data["analysis"]["category"] == "order"


async def test_contact_returns_request_id_header(client):
    response = await client.post("/api/contact", json=valid_payload())
    headers = {k.lower(): v for k, v in response.headers.items()}
    assert "x-request-id" in headers


async def test_contact_invalid_email(client):
    response = await client.post("/api/contact", json=valid_payload(email="not-an-email"))
    assert response.status_code == 422

    body = response.json()
    assert body["error"] == "validation_error"
    assert "email" in body["details"]


async def test_contact_short_name(client):
    response = await client.post("/api/contact", json=valid_payload(name="Я"))
    assert response.status_code == 422
    assert "name" in response.json()["details"]


async def test_contact_name_without_letters(client):
    response = await client.post("/api/contact", json=valid_payload(name="12345"))
    assert response.status_code == 422
    assert "name" in response.json()["details"]


async def test_contact_phone_without_digits(client):
    response = await client.post("/api/contact", json=valid_payload(phone="телефон"))
    assert response.status_code == 422
    assert "phone" in response.json()["details"]


async def test_contact_message_too_short(client):
    response = await client.post("/api/contact", json=valid_payload(message="привет"))
    assert response.status_code == 422
    assert "message" in response.json()["details"]


async def test_contact_missing_fields(client):
    response = await client.post("/api/contact", json={"name": "Илья"})
    assert response.status_code == 422
