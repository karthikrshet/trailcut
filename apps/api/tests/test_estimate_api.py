from typing import Any

import pytest
from fastapi.testclient import TestClient

from trailcut_api.main import create_app
from trailcut_api.settings import Settings

pytestmark = pytest.mark.api

BODY = {
    "lump_sum": "500000",
    "monthly_sip": "10000",
    "years": 15,
    "ter_regular_percent": "1.65",
    "ter_direct_percent": "0.70",
    "expected_return_percent": "12",
}


def client(**env: str) -> TestClient:
    return TestClient(create_app(Settings.from_env({"TRAILCUT_RATE_LIMIT": "100", **env})))


def test_estimate_returns_engine_figures_as_strings() -> None:
    r = client().post("/v1/estimate", json=BODY)
    assert r.status_code == 200
    body = r.json()
    assert body["years"] == 15
    assert body["invested"] == "2300000.00"
    assert isinstance(body["leak"], str)
    assert len(body["series"]) == 16
    assert float(body["direct_value"]) > float(body["regular_value"])


def test_estimate_needs_no_session() -> None:
    assert client().post("/v1/estimate", json={**BODY, "lump_sum": "0"}).status_code == 200


@pytest.mark.parametrize(
    ("changes", "code"),
    [
        ({"lump_sum": "0", "monthly_sip": "0"}, "invalid_request"),
        ({"ter_direct_percent": "2", "ter_regular_percent": "1"}, "invalid_request"),
        ({"years": 0}, "invalid_request"),
        ({"ter_regular_percent": "9"}, "invalid_request"),
        ({"lump_sum": "-5"}, "invalid_request"),
        ({"surprise": 1}, "invalid_request"),
    ],
)
def test_estimate_validation(changes: dict[str, Any], code: str) -> None:
    r = client().post("/v1/estimate", json={**BODY, **changes})
    assert (r.status_code, r.json()["error"]["code"]) == (422, code)


def test_estimate_is_rate_limited() -> None:
    c = client(TRAILCUT_RATE_LIMIT="2")
    codes = [c.post("/v1/estimate", json=BODY).status_code for _ in range(3)]
    assert codes == [200, 200, 429]
