# AMFI data outage

**Detect:** `/v1/sessions/upload` plans show more funds as *Review* than usual; the cached
`NAVAll.txt` is older than a day; refresh errors (when `TRAILCUT_ONLINE=1`).

**Impact:** Direct-plan names may be missing for uploaded statements. Expense ratios come
from `data/market/ter.csv` and are unaffected. The sample portfolio is unaffected.

**First 5 minutes**

1. Fetch `https://www.amfiindia.com/spages/NAVAll.txt` from the host. Is AMFI up?
2. Check the cache file's timestamp under `TRAILCUT_CACHE_DIR`.

**Fix**

1. AMFI down: nothing to do; the service keeps using the last good cache. A garbage
   download is never cached.
2. Network policy change: allow outbound HTTPS to amfiindia.com, or copy a fresh
   `NAVAll.txt` into the cache directory.

**Verify:** a new upload shows Direct-plan names again.
