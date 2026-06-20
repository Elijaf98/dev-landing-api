from tests.conftest import valid_payload


async def test_metrics_empty(client):
    response = await client.get("/api/metrics")
    assert response.status_code == 200
    assert response.json()["total_requests"] == 0


async def test_metrics_counts_requests(client):
    await client.post("/api/contact", json=valid_payload())
    await client.post("/api/contact", json=valid_payload(message="Спасибо, всё отлично получилось!"))

    data = (await client.get("/api/metrics")).json()
    assert data["total_requests"] == 2
    assert data["last_24h"] == 2
    # Сумма по любой из разбивок должна совпадать с общим числом обращений.
    assert sum(data["by_category"].values()) == 2
    assert data["last_request_at"] is not None


async def test_metrics_open_without_key(client):
    # По умолчанию ключ не задан — метрики открыты.
    assert (await client.get("/api/metrics")).status_code == 200


async def test_metrics_requires_key_when_configured(client, monkeypatch):
    from app.core import security

    monkeypatch.setattr(security.settings, "metrics_api_key", "secret-key")

    # Без ключа — 401.
    unauthorized = await client.get("/api/metrics")
    assert unauthorized.status_code == 401
    assert unauthorized.json()["error"] == "unauthorized"

    # С верным ключом — 200.
    authorized = await client.get("/api/metrics", headers={"X-API-Key": "secret-key"})
    assert authorized.status_code == 200
