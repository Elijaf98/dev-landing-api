async def test_health_ok(client):
    response = await client.get("/api/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "ok"
    assert data["checks"]["db"] == "up"
    # В тестах ключа нет — AI должен быть отключён, но сервис при этом жив.
    assert data["checks"]["ai"] == "disabled"
    assert data["version"]
