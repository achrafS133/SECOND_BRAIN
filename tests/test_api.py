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


def test_root_serves_dashboard():
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert "CogOS" in response.text


def test_dashboard_static_page():
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/static/index.html")
        assert response.status_code == 200
        assert "CogOS" in response.text
        assert "Reasoning Engine" in response.text


def test_query_stream_endpoint():
    app = create_app()
    with TestClient(app) as client:
        with client.stream(
            "POST",
            "/query/stream",
            json={"query": "What is M0 working memory?", "session_id": "test-stream"},
        ) as response:
            assert response.status_code == 200
            assert "text/event-stream" in response.headers.get("content-type", "")
            body = "".join(response.iter_text())
            assert "User Query" in body
            assert "complete" in body
