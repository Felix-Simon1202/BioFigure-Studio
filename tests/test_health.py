from fastapi.testclient import TestClient

from backend.api.app import app


def test_health_check_is_local_and_minimal() -> None:
    response = TestClient(app).get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "version": "0.1.0",
        "mode": "local",
    }
