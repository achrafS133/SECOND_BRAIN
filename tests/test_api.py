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


def test_root_redirects_to_dashboard():
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 307
        assert response.headers["location"] == "/static/index.html"


def test_dashboard_static_page():
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/static/index.html")
        assert response.status_code == 200
        assert "CogOS" in response.text
        assert "Reasoning Engine" in response.text
