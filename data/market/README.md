# Market data

Public, non-personal data the planner needs for real statements.

| File | What | How it's refreshed |
| --- | --- | --- |
| `ter.csv` | Total expense ratio per ISIN, in percent | Maintainer exports AMFI's "TER of MF schemes" page and converts it to these columns. Ships with headers only. |
| `.cache/market/NAVAll.txt` | AMFI daily NAVs (Regular and Direct ISINs) | Downloaded from AMFI when `TRAILCUT_ONLINE=1`; cached for a day. |

`ter.csv` columns: `isin,ter_percent,as_of,source` — for example
`INF000S01011,1.65,2026-11-20,AMFI TER disclosure`.

When a fund has no TER here, the planner marks it **Review** and the UI asks the
user for the two expense ratios (shown on the fund's factsheet) instead of guessing.
