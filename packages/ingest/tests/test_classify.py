import pytest
from hypothesis import given
from hypothesis import strategies as st

from trailcut_engine.portfolio import AssetClass, Plan, SchemeOption, TxnKind
from trailcut_ingest.classify import (
    detect_asset_class,
    detect_option,
    detect_plan,
    is_elss,
    map_transaction_type,
)

# ---------- plan ----------


@pytest.mark.parametrize(
    ("name", "advisor", "expected"),
    [
        ("Sample Flexi Cap Fund - Direct Plan - Growth", None, Plan.DIRECT),
        ("Sample Flexi Cap Fund - Regular Plan - Growth", None, Plan.REGULAR),
        ("SAMPLE FLEXI CAP FUND - DIRECT - IDCW", None, Plan.DIRECT),
        ("Sample Liquid Fund - Retail Plan - Growth", None, Plan.REGULAR),
        ("Sample Fund Growth", "ARN-123456", Plan.REGULAR),
        ("Sample Fund Growth", "INA000012345", Plan.DIRECT),
        ("Sample Fund Growth", "DIRECT", Plan.DIRECT),
        ("Sample Fund Growth", " arn-99 ", Plan.REGULAR),
        ("Sample Fund Growth", None, Plan.UNKNOWN),
        ("Sample Fund Growth", "", Plan.UNKNOWN),
        ("Sample Directional Fund - Growth", None, Plan.UNKNOWN),  # 'Directional' is not 'Direct'
        # The name wins over a conflicting advisor code.
        ("Sample Fund - Direct Plan", "ARN-1", Plan.DIRECT),
        ("Sample Fund - Regular Plan", "INA1", Plan.REGULAR),
    ],
)
def test_detect_plan(name: str, advisor: str | None, expected: Plan) -> None:
    assert detect_plan(name, advisor) is expected


# ---------- option ----------


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("X Fund - Regular Plan - Growth", SchemeOption.GROWTH),
        ("X Fund - Regular Plan - Growth Option", SchemeOption.GROWTH),
        ("X Fund - Regular - Cumulative", SchemeOption.GROWTH),
        ("X Fund - Regular Plan - IDCW", SchemeOption.IDCW),
        ("X Fund - Regular Plan - IDCW Payout", SchemeOption.IDCW),
        ("X Fund - Dividend Reinvestment", SchemeOption.IDCW),
        ("X Fund - Regular - Monthly Dividend", SchemeOption.IDCW),
        ("X Fund - Regular - Income Distribution cum Capital Withdrawal", SchemeOption.IDCW),
        ("X Fund - Regular Plan", SchemeOption.UNKNOWN),
    ],
)
def test_detect_option(name: str, expected: SchemeOption) -> None:
    assert detect_option(name) is expected


# ---------- ELSS ----------


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("X ELSS Tax Saver Fund - Regular - Growth", True),
        ("X Tax Saver Fund - Growth", True),
        ("X Taxsaver (ELSS) - Growth", True),
        ("X Tax Saving Fund - Growth", True),
        ("X Long Term Equity Fund (ELSS) - Growth", True),
        ("X Tax Plan - Growth", True),
        ("X Flexi Cap Fund - Growth", False),
        ("X Taxable Bond Fund", False),
    ],
)
def test_is_elss(name: str, expected: bool) -> None:
    assert is_elss(name) is expected


# ---------- asset class ----------


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("X Flexi Cap Fund - Regular - Growth", AssetClass.EQUITY),
        ("X Large Cap Fund", AssetClass.EQUITY),
        ("X Small Cap Fund", AssetClass.EQUITY),
        ("X Mid Cap Opportunities Fund", AssetClass.EQUITY),
        ("X Nifty 50 Index Fund - Direct - Growth", AssetClass.EQUITY),
        ("X ELSS Tax Saver Fund", AssetClass.EQUITY),
        ("X Focused Fund", AssetClass.EQUITY),
        ("X Value Fund", AssetClass.EQUITY),
        ("X Pharma and Healthcare Fund", AssetClass.EQUITY),
        ("X Arbitrage Fund", AssetClass.EQUITY),
        ("X Equity Savings Fund", AssetClass.EQUITY),
        ("X Aggressive Hybrid Fund", AssetClass.EQUITY),
        ("X Balanced Advantage Fund", AssetClass.EQUITY),
        ("X Dynamic Asset Allocation Fund", AssetClass.EQUITY),
        ("X Conservative Hybrid Fund", AssetClass.HYBRID),
        ("X Multi Asset Allocation Fund", AssetClass.HYBRID),
        ("X Multi-Asset Fund", AssetClass.HYBRID),
        ("X Liquid Fund", AssetClass.DEBT),
        ("X Overnight Fund", AssetClass.DEBT),
        ("X Corporate Bond Fund", AssetClass.DEBT),
        ("X Gilt Fund", AssetClass.DEBT),
        ("X Banking and PSU Debt Fund", AssetClass.DEBT),
        ("X Banking & PSU Fund", AssetClass.DEBT),
        ("X Short Duration Fund", AssetClass.DEBT),
        ("X Money Market Fund", AssetClass.DEBT),
        ("X Credit Risk Fund", AssetClass.DEBT),
        ("X Floater Fund", AssetClass.DEBT),
        ("X CRISIL IBX Gilt Index - Target Maturity", AssetClass.DEBT),
        ("X US Equity Fund of Funds", AssetClass.UNKNOWN),
        ("X Nasdaq 100 FoF", AssetClass.UNKNOWN),
        ("X Gold Fund", AssetClass.UNKNOWN),
        ("X Something Fund", AssetClass.UNKNOWN),
    ],
)
def test_detect_asset_class_from_name(name: str, expected: AssetClass) -> None:
    assert detect_asset_class(name) is expected


@pytest.mark.parametrize(
    ("statement_type", "expected"),
    [
        ("EQUITY", AssetClass.EQUITY),
        ("DEBT", AssetClass.DEBT),
        ("equity", AssetClass.EQUITY),
        ("UNKNOWN", AssetClass.UNKNOWN),
        (None, AssetClass.UNKNOWN),
        ("", AssetClass.UNKNOWN),
    ],
)
def test_detect_asset_class_falls_back_to_statement_type(
    statement_type: str | None, expected: AssetClass
) -> None:
    assert detect_asset_class("X Something Fund", statement_type) is expected


def test_name_rule_beats_statement_type() -> None:
    assert detect_asset_class("X Liquid Fund", "EQUITY") is AssetClass.DEBT


# ---------- transaction mapping ----------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("PURCHASE", TxnKind.PURCHASE),
        ("PURCHASE_SIP", TxnKind.SIP),
        ("REDEMPTION", TxnKind.REDEMPTION),
        ("DIVIDEND_PAYOUT", TxnKind.DIVIDEND_PAYOUT),
        ("DIVIDEND_REINVEST", TxnKind.DIVIDEND_REINVEST),
        ("SWITCH_IN", TxnKind.SWITCH_IN),
        ("SWITCH_IN_MERGER", TxnKind.MERGER_IN),
        ("SWITCH_OUT", TxnKind.SWITCH_OUT),
        ("SWITCH_OUT_MERGER", TxnKind.MERGER_OUT),
        ("STT_TAX", TxnKind.TAX),
        ("STAMP_DUTY_TAX", TxnKind.TAX),
        ("TDS_TAX", TxnKind.TAX),
        ("SEGREGATION", TxnKind.SEGREGATION),
        ("GIFT_IN", TxnKind.GIFT_IN),
        ("GIFT_OUT", TxnKind.GIFT_OUT),
        ("REVERSAL", TxnKind.REVERSAL),
        ("MISC", TxnKind.OTHER),
        ("UNKNOWN", TxnKind.OTHER),
        ("TransactionType.PURCHASE_SIP", TxnKind.SIP),
        (" purchase ", TxnKind.PURCHASE),
        ("SOMETHING_NEW", TxnKind.OTHER),
    ],
)
def test_map_transaction_type(raw: str, expected: TxnKind) -> None:
    assert map_transaction_type(raw) is expected


@pytest.mark.property
@given(name=st.text(max_size=120), advisor=st.none() | st.text(max_size=20))
def test_classifiers_are_total(name: str, advisor: str | None) -> None:
    assert detect_plan(name, advisor) in Plan
    assert detect_option(name) in SchemeOption
    assert detect_asset_class(name, advisor) in AssetClass
    assert isinstance(is_elss(name), bool)
    assert map_transaction_type(name) in TxnKind
