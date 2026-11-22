import io
import json
from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient

import trailcut_api.main as main_module
from trailcut_api.main import create_app
from trailcut_api.settings import Settings
from trailcut_ingest.pii import contains_pii
from trailcut_ingest.sample import load_sample_portfolio

pytestmark = pytest.mark.api


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def make_pdf(text: str) -> bytes:
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objects, start=1):
        offsets.append(out.tell())
        out.write(b"%d 0 obj\n" % i + body + b"\nendobj\n")
    xref = out.tell()
    out.write(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1))
    for off in offsets:
        out.write(b"%010d 00000 n \n" % off)
    out.write(
        b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref)
    )
    return out.getvalue()


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def client(clock: FakeClock) -> TestClient:
    settings = Settings.from_env({"TRAILCUT_SESSION_TTL": "60", "TRAILCUT_RATE_LIMIT": "5"})
    return TestClient(create_app(settings, clock=clock, today=lambda: date(2026, 11, 22)))


@pytest.fixture
def sample(client: TestClient) -> dict[str, Any]:
    response = client.post("/v1/sessions/sample")
    assert response.status_code == 201
    body: dict[str, Any] = response.json()
    return body


# ---------- meta and headers ----------


def test_meta(client: TestClient) -> None:
    body = client.get("/v1/meta").json()
    assert body["tax_years"] == ["2026-27"]
    assert body["max_upload_mb"] == 10
    assert body["chat_enabled"] is False
    assert "not investment advice" in body["disclaimer"]


@pytest.mark.parametrize("path", ["/health", "/v1/meta"])
def test_security_headers(client: TestClient, path: str) -> None:
    h = client.get(path).headers
    assert h["X-Content-Type-Options"] == "nosniff"
    assert h["X-Frame-Options"] == "DENY"
    assert h["Cache-Control"] == "no-store"
    assert "frame-ancestors 'none'" in h["Content-Security-Policy"]
    assert len(h["X-Request-ID"]) >= 8


def test_request_id_is_echoed(client: TestClient) -> None:
    assert (
        client.get("/health", headers={"X-Request-ID": "abc123"}).headers["X-Request-ID"]
        == "abc123"
    )


def test_cors_allows_web_origin_only(client: TestClient) -> None:
    ok = client.options(
        "/v1/meta",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
    )
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"
    bad = client.options(
        "/v1/meta",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )
    assert "access-control-allow-origin" not in bad.headers


# ---------- sample session ----------


def test_sample_session_has_report_and_plan(sample: dict[str, Any]) -> None:
    assert sample["is_sample"] is True
    assert sample["expires_in_seconds"] == 60
    assert sample["report"]["summary"]["value"] == "2134154.79"
    assert len(sample["report"]["growth"]) == 21
    assert sample["plan"]["as_of"] == "2026-11-20"
    assert sample["plan"]["totals"]["net_benefit"] == sample["plan"]["totals"]["net_benefit"]
    assert sample["notes"][0].startswith("Sample portfolio")
    assert "not investment advice" in sample["disclaimer"]


def test_money_is_serialized_as_strings(sample: dict[str, Any]) -> None:
    assert isinstance(sample["report"]["yearly_leak"], str)
    assert isinstance(sample["plan"]["totals"]["tax"], str)


def test_sample_response_has_no_pii(sample: dict[str, Any]) -> None:
    assert not contains_pii(json.dumps(sample))


def test_get_session_report_and_plan(client: TestClient, sample: dict[str, Any]) -> None:
    sid = sample["session_id"]
    assert client.get(f"/v1/sessions/{sid}").json()["plan"] == sample["plan"]
    assert client.get(f"/v1/sessions/{sid}/report").json() == sample["report"]
    assert client.get(f"/v1/sessions/{sid}/plan").json() == sample["plan"]


def test_unknown_session_is_404(client: TestClient) -> None:
    r = client.get("/v1/sessions/nope")
    assert r.status_code == 404
    assert r.json() == {
        "error": {
            "code": "session_expired",
            "message": "This session has expired or was deleted. Upload your statement again.",
        }
    }


def test_session_expires(client: TestClient, sample: dict[str, Any], clock: FakeClock) -> None:
    clock.now += 61
    assert client.get(f"/v1/sessions/{sample['session_id']}").status_code == 404


def test_delete_my_data(client: TestClient, sample: dict[str, Any]) -> None:
    sid = sample["session_id"]
    assert client.delete(f"/v1/sessions/{sid}").status_code == 204
    assert client.get(f"/v1/sessions/{sid}").status_code == 404
    assert client.delete(f"/v1/sessions/{sid}").status_code == 204


# ---------- assumptions ----------


def test_update_assumptions_changes_plan(client: TestClient, sample: dict[str, Any]) -> None:
    sid = sample["session_id"]
    r = client.patch(
        f"/v1/sessions/{sid}/assumptions", json={"slab_rate": "0.05", "horizon_years": 20}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["assumptions"]["slab_rate"] == "0.05"
    assert body["assumptions"]["horizon_years"] == 20
    assert body["plan"]["totals"] != sample["plan"]["totals"]
    # Persisted in the session.
    assert client.get(f"/v1/sessions/{sid}").json()["assumptions"]["horizon_years"] == 20


def test_expected_return_changes_report(client: TestClient, sample: dict[str, Any]) -> None:
    body = client.patch(
        f"/v1/sessions/{sample['session_id']}/assumptions", json={"expected_return": "0.08"}
    ).json()
    assert body["report"]["expected_return"] == "0.08"
    assert body["report"]["leak_20y"] != sample["report"]["leak_20y"]


@pytest.mark.parametrize(
    "payload",
    [
        {"slab_rate": "1.5"},
        {"horizon_years": 0},
        {"expected_return": "0.9"},
        {"surprise": 1},
        {"slab_rate": 0.3},
        {"ter_overrides": {"F1-S1": {"regular_percent": "20", "direct_percent": "1"}}},
    ],
)
def test_invalid_assumptions_are_rejected(
    client: TestClient, sample: dict[str, Any], payload: dict[str, Any]
) -> None:
    r = client.patch(f"/v1/sessions/{sample['session_id']}/assumptions", json=payload)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "invalid_request"


def test_ter_override_for_unknown_scheme_is_rejected(
    client: TestClient, sample: dict[str, Any]
) -> None:
    r = client.patch(
        f"/v1/sessions/{sample['session_id']}/assumptions",
        json={"ter_overrides": {"F9-S9": {"regular_percent": "1", "direct_percent": "0.5"}}},
    )
    assert (r.status_code, r.json()["error"]["code"]) == (422, "unknown_scheme")


def test_ter_override_applies(client: TestClient, sample: dict[str, Any]) -> None:
    r = client.patch(
        f"/v1/sessions/{sample['session_id']}/assumptions",
        json={"ter_overrides": {"F3-S1": {"regular_percent": "2.0", "direct_percent": "0.2"}}},
    )
    leaks = {x["scheme_id"]: x for x in r.json()["report"]["leaks"]}
    assert leaks["F3-S1"]["ter_regular"] == "0.02"


# ---------- upload ----------


def upload(client: TestClient, data: bytes, password: str = "secret", name: str = "cas.pdf"):  # type: ignore[no-untyped-def]
    return client.post(
        "/v1/sessions/upload",
        files={"file": (name, data, "application/pdf")},
        data={"password": password},
    )


@pytest.mark.parametrize(
    ("data", "code"),
    [
        (b"", "empty_file"),
        (b"hello, not a pdf", "not_a_pdf"),
        (make_pdf("Hello, this is not a statement"), "unrecognized_statement"),
        (make_pdf("MFCentral Consolidated Account Statement"), "mf_central_statement"),
    ],
)
def test_upload_errors_are_plain_language(client: TestClient, data: bytes, code: str) -> None:
    r = upload(client, data)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == code
    assert "secret" not in r.text


def test_upload_of_10mb_or_more_is_rejected(client: TestClient) -> None:
    r = upload(client, b"%PDF-" + b"0" * (10 * 1024 * 1024))
    assert r.status_code in {413, 422}
    assert r.json()["error"]["code"] == "file_too_large"


def test_upload_success_creates_session(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: dict[str, Any] = {}

    def fake_parse(data: bytearray, password: Any) -> Any:
        seen["password"] = password.get_secret_value()
        seen["buffer"] = data
        return load_sample_portfolio()

    monkeypatch.setattr(main_module, "parse_cas_pdf", fake_parse)
    r = upload(client, make_pdf("ok"), password="ABCPE1234F")
    assert r.status_code == 201
    body = r.json()
    assert body["is_sample"] is False
    assert body["plan"]["as_of"] == "2026-11-22"
    assert seen["password"] == "ABCPE1234F"
    assert not any(seen["buffer"])  # buffer zeroed after parsing
    assert "ABCPE1234F" not in r.text


def test_upload_is_rate_limited(client: TestClient) -> None:
    codes = [upload(client, b"nope").status_code for _ in range(6)]
    assert codes[:5] == [422] * 5
    assert codes[5] == 429


def test_rate_limit_response_has_retry_after(client: TestClient) -> None:
    for _ in range(5):
        upload(client, b"nope")
    r = upload(client, b"nope")
    assert r.json()["error"]["code"] == "rate_limited"
    assert int(r.headers["Retry-After"]) >= 1


def test_password_too_long_is_rejected_without_echo(client: TestClient) -> None:
    r = upload(client, make_pdf("x"), password="p" * 500)
    assert r.status_code == 422
    assert "ppp" not in r.text


def test_missing_file_is_rejected(client: TestClient) -> None:
    r = client.post("/v1/sessions/upload", data={"password": "x"})
    assert (r.status_code, r.json()["error"]["code"]) == (422, "invalid_request")


def test_openapi_lists_v1_routes(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]
    for p in [
        "/v1/meta",
        "/v1/sessions/sample",
        "/v1/sessions/upload",
        "/v1/sessions/{session_id}",
        "/v1/sessions/{session_id}/assumptions",
    ]:
        assert p in paths
