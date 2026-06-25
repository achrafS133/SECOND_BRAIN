from fastapi.testclient import TestClient

from second_brain.api.main import create_app


def test_health_endpoint():
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert "services" in body
