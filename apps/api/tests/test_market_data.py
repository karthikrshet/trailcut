from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from trailcut_api.market.amfi import by_isin, normalize_name, pair_direct, parse_navall
from trailcut_api.market.service import (
    MarketService,
    exit_load_key,
    parse_exit_load_defaults,
    parse_ter_csv,
)
from trailcut_api.settings import REPO_ROOT
from trailcut_engine.portfolio import AssetClass
from trailcut_engine.testing import buy, make_scheme
from trailcut_ingest.sample import load_sample_portfolio

D = Decimal
NAVALL = """Scheme Code;ISIN Div Payout/ ISIN Growth;ISIN Div Reinvestment;Scheme Name;Net Asset Value;Date

Open Ended Schemes(Equity Scheme - Flexi Cap Fund)

Sample Mutual Fund

900001;INF000S01011;-;Sample Flexi Cap Fund - Regular Plan - Growth;150.1234;20-Nov-2026
900101;INF000S01D11;-;Sample Flexi Cap Fund - Direct Plan - Growth;160.5;20-Nov-2026
900002;INF000S01102;INF000S01110;Sample Flexi Cap Fund - Regular Plan - IDCW;20.1;20-Nov-2026
900102;INF000S01D29;-;Sample Flexi Cap Fund - Direct Plan - IDCW;21.0;20-Nov-2026

Other Mutual Fund

800001;INF000O01011;-;Sample Flexi Cap Fund - Regular Plan - Growth;99.0;20-Nov-2026
800002;INF000O01029;-;Other Liquid Fund - Regular Plan - Growth;N.A.;bad-date
not;a;valid;line
"""


def test_parse_navall_records() -> None:
    records = parse_navall(NAVALL)
    assert len(records) == 6
    first = records[0]
    assert (first.amfi_code, first.isins, first.nav, first.nav_date) == (
        "900001",
        ("INF000S01011",),
        D("150.1234"),
        date(2026, 11, 20),
    )
    assert first.amc == "Sample Mutual Fund"
    assert first.category.startswith("Open Ended Schemes(")
    assert records[2].isins == ("INF000S01102", "INF000S01110")
    assert (records[5].nav, records[5].nav_date) == (None, None)


def test_pairs_regular_with_direct_of_same_amc_and_option() -> None:
    twins = pair_direct(parse_navall(NAVALL))
    assert twins["INF000S01011"].isins == ("INF000S01D11",)
    assert twins["INF000S01102"].isins == ("INF000S01D29",)
    assert twins["INF000S01110"].isins == ("INF000S01D29",)
    # Same scheme name at a different AMC must not pair across AMCs.
    assert "INF000O01011" not in twins


def test_by_isin_indexes_every_isin() -> None:
    idx = by_isin(parse_navall(NAVALL))
    assert idx["INF000S01110"].amfi_code == "900002"


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Sample Flexi Cap Fund - Regular Plan - Growth", "sample flexi cap fund"),
        ("SAMPLE FLEXI CAP FUND - DIRECT PLAN - GROWTH OPTION", "sample flexi cap fund"),
        ("Sample Fund - Regular - IDCW Payout", "sample fund"),
        ("Sample Banking & PSU Debt Fund - Direct", "sample banking psu debt fund"),
    ],
)
def test_normalize_name(name: str, expected: str) -> None:
    assert normalize_name(name) == expected


def test_parse_ter_csv() -> None:
    text = "isin,ter_percent,as_of,source\nINF000S01011,1.65,2026-11-20,AMFI\nBAD,x,,\nINF000S01D11,0.70,,\nINF1,150,,\n"
    ter = parse_ter_csv(text)
    assert ter["INF000S01011"] == (D("0.0165"), date(2026, 11, 20), "AMFI")
    assert ter["INF000S01D11"][0] == D("0.007")
    assert ter["INF000S01D11"][1] is None
    assert "BAD" not in ter
    assert "INF1" not in ter


def test_exit_load_defaults_file_is_valid() -> None:
    rules = parse_exit_load_defaults(
        (REPO_ROOT / "data" / "exit_loads" / "defaults.yaml").read_text(encoding="utf-8")
    )
    assert set(rules) == {"equity", "elss", "hybrid", "debt", "unknown"}
    assert rules["equity"].rate_on(date(2026, 1, 1), date(2026, 6, 1)) == D("0.01")
    assert rules["elss"].tiers == ()
    assert rules["debt"].tiers == ()


@pytest.mark.parametrize(
    ("asset", "elss", "key"),
    [
        (AssetClass.EQUITY, False, "equity"),
        (AssetClass.EQUITY, True, "elss"),
        (AssetClass.DEBT, False, "debt"),
        (AssetClass.HYBRID, False, "hybrid"),
        (AssetClass.UNKNOWN, False, "unknown"),
    ],
)
def test_exit_load_key(asset: AssetClass, elss: bool, key: str) -> None:
    assert (
        exit_load_key(make_scheme([buy(date(2024, 1, 1), "1")], asset_class=asset, is_elss=elss))
        == key
    )


def make_service(
    tmp_path: Path, *, ter: str = "", navall: str | None = NAVALL, **kw: object
) -> MarketService:
    data = tmp_path / "data"
    (data / "market").mkdir(parents=True)
    (data / "exit_loads").mkdir()
    (data / "samples").mkdir()
    (data / "market" / "ter.csv").write_text(
        "isin,ter_percent,as_of,source\n" + ter, encoding="utf-8"
    )
    (data / "exit_loads" / "defaults.yaml").write_text(
        (REPO_ROOT / "data" / "exit_loads" / "defaults.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (data / "samples" / "sample_market.json").write_text(
        (REPO_ROOT / "data" / "samples" / "sample_market.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    cache = tmp_path / "cache"
    if navall is not None:
        cache.mkdir()
        (cache / "NAVAll.txt").write_text(navall, encoding="utf-8")
    return MarketService(data, cache, **kw)  # type: ignore[arg-type]


def test_sample_market_covers_every_sample_scheme(tmp_path: Path) -> None:
    p = load_sample_portfolio()
    md = make_service(tmp_path).sample_market(p)
    assert set(md.schemes) == {s.scheme_id for s in p.schemes}
    assert md.as_of == date(2026, 11, 20)


def test_market_for_real_portfolio_uses_ter_and_direct_twin(tmp_path: Path) -> None:
    p = load_sample_portfolio()
    svc = make_service(
        tmp_path, ter="INF000S01011,1.65,2026-11-01,AMFI\nINF000S01D11,0.70,2026-11-01,AMFI\n"
    )
    md = svc.market_for(p)
    flexi = md.for_scheme("F1-S1")
    assert (flexi.ter_regular, flexi.ter_direct) == (D("0.0165"), D("0.007"))
    assert flexi.direct_name == "Sample Flexi Cap Fund - Direct Plan - Growth"
    assert flexi.exit_load is not None
    assert md.as_of == date(2026, 11, 1)
    # No TER data for the others: unknown, not guessed.
    assert md.for_scheme("F3-S1").ter_regular is None


def test_overrides_replace_expense_ratios(tmp_path: Path) -> None:
    p = load_sample_portfolio()
    svc = make_service(tmp_path)
    md = svc.market_for(p, {"F3-S1": (D("0.0065"), D("0.0035"))})
    assert md.for_scheme("F3-S1").ter_gap == D("0.0030")
    assert md.for_scheme("F3-S1").source == "entered by you"
    again = svc.with_overrides(svc.market_for(p), {"F2-S1": (D("0.018"), D("0.0075"))})
    assert again.for_scheme("F2-S1").ter_regular == D("0.018")


def test_offline_service_never_fetches(tmp_path: Path) -> None:
    calls: list[str] = []

    def fetch(url: str) -> str:
        calls.append(url)
        return ""

    svc = make_service(tmp_path, navall=None, online=False, fetcher=fetch)
    assert svc.navall() == []
    assert calls == []


def test_online_service_fetches_and_caches_when_stale(tmp_path: Path) -> None:
    calls: list[str] = []

    def fetch(url: str) -> str:
        calls.append(url)
        return NAVALL

    svc = make_service(tmp_path, navall=None, online=True, fetcher=fetch)
    assert len(svc.navall()) == 6
    assert calls == ["https://www.amfiindia.com/spages/NAVAll.txt"]
    assert (tmp_path / "cache" / "NAVAll.txt").exists()
    svc.navall()
    assert len(calls) == 1  # memoised


def test_online_fetch_failure_falls_back_to_cache(tmp_path: Path) -> None:
    def fail(url: str) -> str:
        raise OSError("network down")

    svc = make_service(tmp_path, online=True, fetcher=fail, clock=lambda: 10**12)
    assert len(svc.navall()) == 6


def test_garbage_download_is_not_cached(tmp_path: Path) -> None:
    svc = make_service(tmp_path, navall=None, online=True, fetcher=lambda url: "<html>error</html>")
    assert svc.navall() == []
    assert not (tmp_path / "cache" / "NAVAll.txt").exists()
