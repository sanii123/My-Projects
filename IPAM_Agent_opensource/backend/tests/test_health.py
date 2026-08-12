"""Smoke test for GET /health - docs/architecture.md section 5.

Does not require live Postgres/Ollama/NetBox: app/api/health.py is written
to report each dependency's status individually rather than crash if one is
unreachable, so this only asserts the endpoint responds with the expected
shape - a real readiness check belongs in CI against the docker-compose stack.
"""


async def test_health_endpoint_responds(client):
    resp = await client.get("/health")
    assert resp.status_code == 200

    body = resp.json()
    assert body["status"] in {"ok", "degraded"}
    assert {d["name"] for d in body["dependencies"]} == {"postgres", "ollama", "netbox"}
