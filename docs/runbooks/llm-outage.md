# LLM outage

**Detect:** chat answers come back with `mode: "fallback"` for most requests; trace
steps show `error: APIConnectionError` / `RateLimitError` / `InternalServerError`.

**Impact:** chat still answers, but from the calculator's own figures instead of written
explanations. Report and switch plan are unaffected (they never use the model).

**First 5 minutes**

1. Check the Anthropic status page and your account's rate limits.
2. Confirm the key in the platform secret manager is present and not expired.
3. If spend is the problem, nothing to do in the app: fallback answers cost nothing.

**Fix**

1. Provider incident: wait; the app degrades gracefully.
2. Rate limits: lower `TRAILCUT_MAX_CHAT_TURNS` or `TRAILCUT_RATE_LIMIT` and redeploy.
3. To switch chat fully off, unset `ANTHROPIC_API_KEY`; `/v1/meta` then reports
   `chat_mode: "offline"`.

**Verify:** new chat answers return `mode: "llm"`.

**Never:** turn off the numeric-claim validator to "get answers through".
