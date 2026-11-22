"""Write the web app's test fixture from the real API's sample session.

Component tests then render true engine output. Lots are trimmed to a few per
fund to keep the file small; totals are untouched. Run:

    uv run python scripts/make_web_fixture.py
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient

from trailcut_api.main import create_app
from trailcut_api.settings import Settings

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "apps" / "web" / "src" / "test" / "fixtures" / "session.json"
LOTS_PER_FUND = 3


def build() -> dict[str, object]:
    client = TestClient(create_app(Settings.from_env({}), today=lambda: date(2026, 11, 20)))
    body: dict[str, object] = client.post("/v1/sessions/sample").json()
    plan = body["plan"]
    if not isinstance(plan, dict):
        msg = "unexpected API response shape"
        raise TypeError(msg)
    kept: list[dict[str, object]] = []
    seen: dict[str, int] = {}
    for d in plan["decisions"]:
        n = seen.get(d["scheme_id"], 0)
        if n < LOTS_PER_FUND:
            kept.append(d)
        seen[d["scheme_id"]] = n + 1
    plan["decisions"] = kept
    body["session_id"] = "test-session-id"
    return body


def main() -> None:
    OUT.write_text(json.dumps(build(), indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
