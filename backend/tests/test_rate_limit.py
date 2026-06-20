from tests.conftest import valid_payload

# В conftest лимит выставлен в 5 запросов за окно.


async def test_rate_limit_blocks_after_limit(client):
    codes = []
    for _ in range(6):
        response = await client.post("/api/contact", json=valid_payload())
        codes.append(response.status_code)

    assert codes[:5] == [201, 201, 201, 201, 201]
    assert codes[5] == 429


async def test_rate_limit_response_shape(client):
    for _ in range(5):
        await client.post("/api/contact", json=valid_payload())

    blocked = await client.post("/api/contact", json=valid_payload())
    assert blocked.status_code == 429
    assert blocked.json()["error"] == "rate_limit_exceeded"

    headers = {k.lower(): v for k, v in blocked.headers.items()}
    assert "retry-after" in headers
