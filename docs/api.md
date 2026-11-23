# API

FastAPI service in `apps/api`. Interactive docs at `/docs` when running locally.
Money, units and rates are **decimal strings**; dates are ISO `YYYY-MM-DD`.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | Liveness, no user data |
| GET | `/v1/meta` | Disclaimer, tax years loaded, upload limit, session TTL, chat mode |
| POST | `/v1/estimate` | Lump sum + SIP + years + expense ratios → projected leak (no session) |
| POST | `/v1/sessions/sample` | Session for the fictional sample portfolio |
| POST | `/v1/sessions/upload` | Multipart `file` (CAS PDF, < 10 MB) + `password` → session |
| GET | `/v1/sessions/{id}` | Report + plan + assumptions |
| GET | `/v1/sessions/{id}/report` | Commission-leak report |
| GET | `/v1/sessions/{id}/plan` | Switch plan |
| PATCH | `/v1/sessions/{id}/assumptions` | Change return, slab, horizon, exemption use, expense ratios |
| POST | `/v1/sessions/{id}/chat` | `{message, history}` → answer, agent, mode, notice, trace |
| DELETE | `/v1/sessions/{id}` | Delete my data now |

## Errors

Always `{"error": {"code": "...", "message": "..."}}` with a plain-language message.

| Status | Codes |
| --- | --- |
| 404 | `session_expired` |
| 413 | `file_too_large` |
| 422 | `empty_file`, `not_a_pdf`, `wrong_password`, `mf_central_statement`, `summary_statement`, `depository_statement`, `unrecognized_statement`, `parse_failed`, `invalid_request`, `unknown_scheme` |
| 429 | `rate_limited` (with `Retry-After`), `chat_limit` |

Validation errors list field names only; submitted values (which may include a
password) are never echoed.

## Privacy

Sessions live in memory for 30 minutes after last use and hold only the PII-free
normalized portfolio. Run uvicorn with `--no-access-log` in production: access logs
would record session ids in URLs.
