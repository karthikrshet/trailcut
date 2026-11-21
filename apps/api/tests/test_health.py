import pytest
from fastapi.testclient import TestClient

from trailcut_api import __version__
from trailcut_api.main import create_app

pytestmark = pytest.mark.api


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": __version__}


def test_health_is_json(client: TestClient) -> None:
    assert client.get("/health").headers["content-type"] == "application/json"


@pytest.mark.parametrize("method", ["post", "put", "delete"])
def test_health_rejects_writes(client: TestClient, method: str) -> None:
    assert getattr(client, method)("/health").status_code == 405


def test_unknown_route_is_404(client: TestClient) -> None:
    assert client.get("/nope").status_code == 404


def test_openapi_documents_health(client: TestClient) -> None:
    spec = client.get("/openapi.json").json()
    assert spec["info"]["title"] == "TrailCut API"
    assert "not investment advice" in spec["info"]["description"]
    assert "/health" in spec["paths"]
