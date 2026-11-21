# Parser failures spike

**Detect:** the share of `/v1/parse` responses with codes `parse_failed` or
`unrecognized_statement` rises above its 7-day baseline.

**Impact:** affected users can't get a plan from their statement; the sample still works.

**First 5 minutes**

1. Break the errors down by `code`. A rise in `wrong_password` or
   `mf_central_statement` is user behaviour, not an outage.
2. Check whether CAMS or KFintech changed their statement layout (casparser issues
   tracker, recent CAS samples from the team's *own* statements).
3. Check whether casparser was upgraded in the last deploy (`uv.lock` diff).

**Fix**

1. If a dependency upgrade caused it, roll back to the previous release.
2. If the issuer changed the layout, pin the last good casparser and open an
   upstream issue with a *redacted* description (never attach a real statement).

**Verify:** the error-code mix returns to baseline.

**Never:** ask users to email their statement, or store a failing PDF "to debug".
TrailCut does not keep PDFs.
