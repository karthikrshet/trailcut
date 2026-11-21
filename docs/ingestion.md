# Ingestion

`packages/ingest` (`trailcut_ingest`) turns an uploaded CAS PDF into a PII-free
`trailcut_engine.portfolio.Portfolio`. It is the only code that sees the PDF, the
password, or the investor's personal details, and it keeps none of them.

```
bytes ──check_upload──▶ casparser.read_cas_pdf ──▶ normalize_cas ──▶ Portfolio
         (size, magic)     (in memory, BytesIO)      (mask + map)     (no PII fields)
```

## Supported statements

| Statement | Result |
| --- | --- |
| CAMS / KFintech **Detailed** CAS | Parsed |
| Summary CAS | `summary_statement`: ask for the Detailed one |
| NSDL / CDSL depository CAS | `depository_statement` |
| MF Central CAS | `mf_central_statement` (detected by first-page text) |
| Wrong password | `wrong_password` |
| Anything else | `unrecognized_statement` / `parse_failed` |

Every error has a stable `code` and a plain-language `user_message` (see
`trailcut_ingest/errors.py`). Parser exception text is never shown, because it can
contain folio numbers or PAN.

## Privacy

- Upload guard: non-empty, starts with `%PDF-`, **under 10 MB**.
- The password is a `SecretStr`; a `bytearray` upload is zeroed after parsing.
- The engine models have **no fields** for name, PAN, email, phone, address,
  nominees or folio numbers. Folios become `F1`, `F2`…; schemes `F1-S1`…
- Every string that survives (scheme and AMC names, parser warnings) is masked:
  first exact values from the statement header, then PII-shaped patterns.
- A repo policy test forbids logging, printing, temp files and file writes in
  `trailcut_ingest`.
- Hypothesis plants random PAN/folio/email/phone/name values in every field and
  checks none reach the output.

## Classification

Scheme names are untrusted text; `classify.py` only matches keywords.

- **Plan:** "Direct"/"Regular" in the name, else the advisor code (`ARN-` →
  Regular, `INA`/`DIRECT` → Direct).
- **Asset class:** equity-oriented hybrids (arbitrage, equity savings, aggressive
  hybrid, balanced advantage) count as equity for tax; FoFs, overseas and gold
  funds are `UNKNOWN` so the user is asked rather than guessed for.

## Sample portfolio

`scripts/make_sample.py` generates `trailcut_ingest/samples/sample_cas.json`, a
fictional statement covering every planning case. A test fails if the committed
file drifts from the generator.
