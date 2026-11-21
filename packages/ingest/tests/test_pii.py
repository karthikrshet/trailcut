import pytest
from hypothesis import given
from hypothesis import strategies as st

from trailcut_ingest.pii import (
    EMAIL_MASK,
    FOLIO_MASK,
    PAN_MASK,
    PHONE_MASK,
    REDACTED_MASK,
    PiiMasker,
    contains_pii,
    mask_text,
)

# ---------- PAN ----------


@pytest.mark.parametrize(
    "pan",
    ["ABCPE1234F", "AAACR5055K", "AAAHA1234B", "AAAFT9876Z", "abcpe1234f", "ZZZTZ0000Z"],
)
def test_masks_pan(pan: str) -> None:
    assert mask_text(f"PAN: {pan} KYC OK") == f"PAN: {PAN_MASK} KYC OK"


@pytest.mark.parametrize(
    "text",
    [
        "ABCDE1234F",  # 4th char D is not a valid holder type
        "ABCPE12345",  # wrong shape
        "XABCPE1234F",  # embedded in a longer token
        "ABCPE1234FX",
        "INF209K01VA6",  # an ISIN
    ],
)
def test_does_not_mask_non_pan(text: str) -> None:
    assert mask_text(text) == text


# ---------- email ----------


@pytest.mark.parametrize(
    "email",
    ["ravi@example.com", "a.b+cas@mail.co.in", "first_last@sub.domain.org", "X@Y.IN"],
)
def test_masks_email(email: str) -> None:
    assert mask_text(f"Email Id: {email}.") == f"Email Id: {EMAIL_MASK}."


@pytest.mark.parametrize("text", ["user@", "@domain.com", "no at sign", "a@b"])
def test_does_not_mask_non_email(text: str) -> None:
    assert mask_text(text) == text


# ---------- phone ----------


@pytest.mark.parametrize(
    "phone",
    [
        "9876543210",
        "+919876543210",
        "+91 9876543210",
        "+91-98765-43210",
        "919876543210",
        "09876543210",
        "98765 43210",
        "6000000000",
        "00919876543210",
    ],
)
def test_masks_indian_mobile(phone: str) -> None:
    assert mask_text(f"Mobile: {phone}") == f"Mobile: {PHONE_MASK}"


@pytest.mark.parametrize(
    "text",
    [
        "5876543210",  # starts with 5
        "98765432",  # too short
        "1,25,000.00",
        "98,76,54,321",  # an amount with commas
        "Units 9876543210.123",  # decimal number
        "NAV 123.4567",
        "Balance 12345.678",
    ],
)
def test_does_not_mask_numbers_that_are_not_phones(text: str) -> None:
    assert mask_text(text) == text


# ---------- folio ----------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Folio No: 1234567/89", f"Folio No: {FOLIO_MASK}"),
        ("Folio No: 1234567 / 89", f"Folio No: {FOLIO_MASK}"),
        ("FOLIO NO. 91012345678", f"FOLIO NO. {FOLIO_MASK}"),
        ("folio: ABC1234", f"folio: {FOLIO_MASK}"),
        ("Folio Number - 77889900", f"Folio Number - {FOLIO_MASK}"),
        ("Folio #12345", f"Folio #{FOLIO_MASK}"),
        ("in folio 5566778 units", f"in folio {FOLIO_MASK} units"),
    ],
)
def test_masks_folio_references(text: str, expected: str) -> None:
    assert mask_text(text) == expected


def test_does_not_mask_the_word_portfolio() -> None:
    assert mask_text("portfolio 123456 value") == "portfolio 123456 value"


# ---------- combined / idempotent ----------


def test_masks_everything_in_one_line() -> None:
    text = "Folio No: 1234567/89 PAN ABCPE1234F mail a.b@x.in ph +91 9876543210"
    assert (
        mask_text(text)
        == f"Folio No: {FOLIO_MASK} PAN {PAN_MASK} mail {EMAIL_MASK} ph {PHONE_MASK}"
    )


@pytest.mark.parametrize(
    "text",
    [
        "Sample Flexi Cap Fund - Regular Plan - Growth",
        "Purchase - Systematic Investment",
        "ISIN: INF000S01011 (Advisor: ARN-123456)",
        "Closing Unit Balance: 1,234.567 NAV on 20-Nov-2026: INR 123.4567",
    ],
)
def test_leaves_ordinary_statement_text_alone(text: str) -> None:
    assert mask_text(text) == text
    assert not contains_pii(text)


@pytest.mark.parametrize("text", ["ABCPE1234F", "x@y.com", "9876543210", "Folio No: 123456"])
def test_contains_pii(text: str) -> None:
    assert contains_pii(text)
    assert not contains_pii(mask_text(text))


# ---------- known values ----------


def test_known_values_are_masked_anywhere() -> None:
    masker = PiiMasker(["Ravi Kumar", "1234567/89", "12 MG Road, Bengaluru"])
    out = masker.mask("RAVI KUMAR lives at 12 MG Road, Bengaluru, ref 1234567 / 89 and 1234567")
    assert (
        out == f"{REDACTED_MASK} lives at {REDACTED_MASK}, ref {REDACTED_MASK} and {REDACTED_MASK}"
    )


def test_known_values_collapse_whitespace() -> None:
    assert PiiMasker(["Ravi   Kumar"]).mask("Ravi Kumar") == REDACTED_MASK


@pytest.mark.parametrize("value", ["", None, "AB", "abc"])
def test_short_or_empty_known_values_are_ignored(value: str | None) -> None:
    masker = PiiMasker([value])
    assert masker.mask("abc AB fund") == "abc AB fund"


def test_known_phone_matches_last_ten_digits() -> None:
    assert PiiMasker(["+91 98765 43210"]).mask("call 9876543210") == f"call {REDACTED_MASK}"


def test_masker_without_known_values_still_masks_patterns() -> None:
    assert PiiMasker().mask("PAN ABCPE1234F") == f"PAN {PAN_MASK}"


def test_known_value_with_regex_characters_is_escaped() -> None:
    assert PiiMasker(["a+b (c)"]).mask("x a+b (c) y") == f"x {REDACTED_MASK} y"


# ---------- properties ----------

pans = st.from_regex(r"[A-Z]{3}[ABCFGHLJPT][A-Z][0-9]{4}[A-Z]", fullmatch=True)
emails = st.from_regex(r"[a-z][a-z0-9._]{0,10}@[a-z]{2,8}\.(com|in|org|co\.in)", fullmatch=True)
phones = st.from_regex(r"[6-9][0-9]{9}", fullmatch=True)
filler = st.text(alphabet=st.characters(categories=["L", "Zs"]), max_size=40)


@pytest.mark.property
@given(pan=pans, email=emails, phone=phones, before=filler, after=filler)
def test_no_pii_survives_masking(pan: str, email: str, phone: str, before: str, after: str) -> None:
    text = f"{before} {pan} {email} {phone} {after}"
    out = mask_text(text)
    assert pan not in out
    assert email not in out
    assert phone not in out
    assert not contains_pii(out)


@pytest.mark.property
@given(text=st.text(max_size=200))
def test_masking_is_idempotent(text: str) -> None:
    once = mask_text(text)
    assert mask_text(once) == once


@pytest.mark.property
@given(folio=st.from_regex(r"[0-9]{5,12}(/[0-9]{1,3})?", fullmatch=True), noise=filler)
def test_known_folio_never_survives(folio: str, noise: str) -> None:
    out = PiiMasker([folio]).mask(f"{noise} folio {folio} {noise} {folio}")
    assert folio not in out
