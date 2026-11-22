"""The switch optimizer: when to move each Regular lot to Direct, if ever.

For every remaining lot of every Regular scheme it evaluates switching on a few
candidate dates (today; when the lot turns long term; when its exit load ends;
when an ELSS lock-in ends; 1 April for a fresh LTCG exemption) and picks the date
with the highest value at the horizon. If no date beats staying put, it keeps the
lot.

Value at the horizon (``H`` years from today) for a switch on date ``D``:

    value at D   = value today grown at (return - Regular TER) until D
    reinvested   = value at D - exit load - tax
    switched     = reinvested grown at (return - Direct TER) until H
    stayed       = value today grown at (return - Regular TER) until H
    net benefit  = switched - stayed

The yearly LTCG exemption is shared across lots: lots with the biggest benefit are
planned first and use the exemption first. Plans are deterministic, never sell
locked ELSS units, and are never worse than switching everything today.

Example:
    >>> plan = plan_switch(portfolio, market, [rules], Assumptions(as_of=date(2026, 11, 20)))
    >>> plan.totals.net_benefit > 0
    True
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from trailcut_engine.dates import fy_start_year, next_fy_start
from trailcut_engine.display import format_date, format_inr
from trailcut_engine.lots import Lot, build_lots
from trailcut_engine.market import NO_EXIT_LOAD, MarketData, SchemeMarket
from trailcut_engine.portfolio import Plan, Portfolio, Scheme
from trailcut_engine.projection import break_even_months, grow
from trailcut_engine.tax import (
    GainBuckets,
    LotGain,
    TaxRegime,
    lock_in_until,
    long_term_from,
    lot_gain,
    tax_on_gains,
)
from trailcut_engine.tax_rules import TaxRules, fy_label
from trailcut_engine.types import DecimalField

ZERO = Decimal(0)
PAISE = Decimal("0.01")
DAYS_PER_YEAR = Decimal(365)


def _paise(x: Decimal) -> Decimal:
    return x.quantize(PAISE, ROUND_HALF_UP)


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


Fraction = Annotated[DecimalField, Field(ge=0, le=1)]


class Assumptions(_Model):
    """User-editable planning inputs. Shown in the UI; never hidden."""

    as_of: date
    expected_return: Annotated[DecimalField, Field(ge=Decimal("-0.5"), le=Decimal("0.5"))] = (
        Decimal("0.12")
    )
    """Yearly return before expense ratios."""
    slab_rate: Fraction = Decimal("0.30")
    """Income-tax slab rate for gains taxed at slab (debt bought after 1 Apr 2023)."""
    horizon_years: Annotated[int, Field(ge=1, le=40)] = 10
    other_equity_ltcg_this_fy: Annotated[DecimalField, Field(ge=0)] = ZERO
    """Equity LTCG already booked this FY elsewhere (uses up the exemption)."""
    use_next_fy_exemption: bool = True
    """Allow waiting until 1 April to use next year's LTCG exemption."""


class Action(StrEnum):
    SWITCH_NOW = "switch_now"
    WAIT = "wait"
    KEEP = "keep"
    REVIEW = "review"


class Reason(StrEnum):
    ALREADY_DIRECT = "already_direct"
    NO_TER_DATA = "no_ter_data"
    NO_TER_GAP = "no_ter_gap"
    UNKNOWN_COST = "unknown_cost"
    SWITCH_FREE = "switch_free"
    SWITCH_WORTH_IT = "switch_worth_it"
    WAIT_LOCK_IN = "wait_lock_in"
    WAIT_LONG_TERM = "wait_long_term"
    WAIT_EXIT_LOAD = "wait_exit_load"
    WAIT_NEXT_FY = "wait_next_fy"
    KEEP_COST_EXCEEDS_BENEFIT = "keep_cost_exceeds_benefit"
    KEEP_LOCKED_PAST_HORIZON = "keep_locked_past_horizon"
    LOCKED_TODAY = "locked_today"


class LotDecision(_Model):
    """What to do with one lot, and why."""

    lot_id: str
    scheme_id: str
    buy_date: date
    units: DecimalField
    action: Action
    reason: Reason
    explanation: str
    switch_on: date | None
    value_now: DecimalField
    sale_value: DecimalField
    """Value on the switch date, before exit load and tax."""
    exit_load: DecimalField
    gain: DecimalField
    regime: TaxRegime | None
    tax: DecimalField
    exemption_used: DecimalField
    net_benefit: DecimalField
    """Extra value at the horizon versus never switching this lot."""
    grandfathered: bool = False


class SchemePlan(_Model):
    """Per-scheme rollup."""

    scheme_id: str
    name: str
    plan: Plan
    value: DecimalField
    ter_regular: DecimalField | None
    ter_direct: DecimalField | None
    yearly_leak: DecimalField | None
    actions: dict[Action, int]
    net_benefit: DecimalField


class Totals(_Model):
    """Totals for a plan or baseline."""

    switch_value: DecimalField
    tax: DecimalField
    exit_load: DecimalField
    net_benefit: DecimalField
    break_even_months: int | None
    lots_switched: int


class FyTax(_Model):
    """Exact tax for one financial year of the plan, after set-off and exemption."""

    financial_year: str
    gains: GainBuckets
    exemption_used: DecimalField
    tax: DecimalField
    rules_assumed: bool
    """True if this FY has no published rules and the latest rules were assumed."""


class TimelineStep(_Model):
    on: date
    lots: int
    value: DecimalField
    label: str


class SwitchPlan(_Model):
    """The full plan with baselines for comparison."""

    as_of: date
    assumptions: Assumptions
    decisions: tuple[LotDecision, ...]
    schemes: tuple[SchemePlan, ...]
    totals: Totals
    switch_all_now: Totals
    never_switch: Totals
    fy_tax: tuple[FyTax, ...]
    timeline: tuple[TimelineStep, ...]
    notes: tuple[str, ...]


# ---------- internals ----------


@dataclass(frozen=True)
class _Option:
    on: date
    years: Decimal
    value: Decimal
    exit_load: Decimal
    gain: LotGain
    events: frozenset[Reason]


@dataclass(frozen=True)
class _Evaluated:
    option: _Option
    tax: Decimal
    exemption: Decimal
    net: Decimal


def rules_for(on: date, rules: Sequence[TaxRules]) -> tuple[TaxRules, bool]:
    """Rules covering ``on``; else the latest rules, flagged as assumed."""
    ordered = sorted(rules, key=lambda r: r.effective_from)
    if not ordered:
        msg = "at least one TaxRules set is required"
        raise ValueError(msg)
    for r in ordered:
        if r.covers(on):
            return r, False
    before = [r for r in ordered if r.effective_from <= on]
    return (before[-1] if before else ordered[0]), True


def _standalone_tax(
    gain: LotGain, rules: TaxRules, slab: Decimal, exemption: Decimal
) -> tuple[Decimal, Decimal]:
    """Tax on one lot's gain on its own, using up to ``exemption`` for equity LTCG."""
    if gain.gain <= 0:
        return ZERO, ZERO
    buckets = GainBuckets.from_gains([gain])
    t = tax_on_gains(buckets, rules, slab_rate=slab, exemption_available=exemption)
    return t.total, t.exemption_used


class _Planner:
    def __init__(
        self,
        portfolio: Portfolio,
        market: MarketData,
        rules: Sequence[TaxRules],
        a: Assumptions,
    ) -> None:
        self.portfolio = portfolio
        self.market = market
        self.rules = rules
        self.a = a
        self.horizon_end_years = Decimal(a.horizon_years)
        self.exemption_left: dict[int, Decimal] = {}
        self._first_fy = fy_start_year(a.as_of)
        self._current_rules, _ = rules_for(a.as_of, rules)

    def exemption_for(self, fy: int, on: date) -> Decimal:
        if fy not in self.exemption_left:
            r, _ = rules_for(on, self.rules)
            limit = r.equity.ltcg_exemption_per_fy.value
            if fy == self._first_fy:
                limit = max(limit - self.a.other_equity_ltcg_this_fy, ZERO)
            self.exemption_left[fy] = limit
        return self.exemption_left[fy]

    def options(self, scheme: Scheme, lot: Lot, m: SchemeMarket) -> list[_Option]:
        a = self.a
        ter_r = m.ter_regular or ZERO
        load_rule = m.exit_load or NO_EXIT_LOAD
        events: dict[date, set[Reason]] = {a.as_of: set()}
        locked = lock_in_until(lot.buy_date, scheme.is_elss, self._current_rules)
        lt = long_term_from(lot.buy_date, scheme.asset_class, self._current_rules)
        free = load_rule.free_from(lot.buy_date)
        for d, reason in (
            (locked, Reason.WAIT_LOCK_IN),
            (lt, Reason.WAIT_LONG_TERM),
            (free, Reason.WAIT_EXIT_LOAD),
        ):
            if d is not None and d > a.as_of:
                events.setdefault(d, set()).add(reason)
        if a.use_next_fy_exemption:
            events.setdefault(next_fy_start(a.as_of), set()).add(Reason.WAIT_NEXT_FY)
        value_now = lot.units * scheme.valuation.nav
        out: list[_Option] = []
        for on in sorted(events):
            if locked is not None and on < locked:
                continue
            years = Decimal((on - a.as_of).days) / DAYS_PER_YEAR
            if years > self.horizon_end_years:
                continue
            value = (
                grow(value_now, a.expected_return - ter_r, years) if years else _paise(value_now)
            )
            load = _paise(value * load_rule.rate_on(lot.buy_date, on))
            r, _ = rules_for(on, self.rules)
            gain = lot_gain(
                lot, on, value - load, scheme.asset_class, r, fmv_2018_per_unit=m.fmv_2018_per_unit
            )
            out.append(_Option(on, years, value, load, gain, frozenset(events[on])))
        return out

    def evaluate(self, opt: _Option, value_now: Decimal, m: SchemeMarket) -> _Evaluated:
        a = self.a
        r, _ = rules_for(opt.on, self.rules)
        fy = fy_start_year(opt.on)
        tax, used = _standalone_tax(opt.gain, r, a.slab_rate, self.exemption_for(fy, opt.on))
        tax = _paise(tax)
        reinvested = opt.value - opt.exit_load - tax
        ter_r = m.ter_regular or ZERO
        ter_d = m.ter_direct or ZERO
        switched = grow(reinvested, a.expected_return - ter_d, self.horizon_end_years - opt.years)
        stayed = grow(value_now, a.expected_return - ter_r, self.horizon_end_years)
        return _Evaluated(opt, tax, used, switched - stayed)


def _explain(reason: Reason, ev: _Evaluated | None, scheme: Scheme) -> str:  # noqa: PLR0911, PLR0912
    if reason is Reason.ALREADY_DIRECT:
        return "Already in a Direct plan, so there is no commission to cut."
    if reason is Reason.NO_TER_DATA:
        return "We don't have expense-ratio data for this fund, so we can't size the saving."
    if reason is Reason.NO_TER_GAP:
        return "The Direct plan costs the same, so switching saves nothing."
    if reason is Reason.UNKNOWN_COST:
        return "These units were bought before your statement starts, so we can't work out the tax."
    if reason is Reason.LOCKED_TODAY:
        return "ELSS lock-in hasn't ended, so these units can't be switched today."
    if reason is Reason.KEEP_LOCKED_PAST_HORIZON:
        return "Keep: the lock-in ends after your planning horizon."
    if ev is None:
        msg = f"reason {reason} needs an evaluated option"
        raise ValueError(msg)
    o = ev.option
    when = format_date(o.on)
    if reason is Reason.SWITCH_FREE:
        return "Switch now: no tax and no exit load."
    if reason is Reason.SWITCH_WORTH_IT:
        return (
            f"Switch now: the {format_inr(ev.tax + o.exit_load)} cost is outweighed by "
            f"{format_inr(ev.net)} of extra value over your horizon."
        )
    if reason is Reason.WAIT_LOCK_IN:
        return f"Wait until {when}: ELSS units can't be redeemed before their 3-year lock-in ends."
    if reason is Reason.WAIT_LONG_TERM:
        return f"Wait until {when}: the gain becomes long term and is taxed at a lower rate."
    if reason is Reason.WAIT_EXIT_LOAD:
        return f"Wait until {when}: the exit load ends then."
    if reason is Reason.WAIT_NEXT_FY:
        return (
            f"Wait until {when}: this year's tax-free LTCG limit is used up; "
            "next year's starts then."
        )
    return (
        f"Keep: switching would cost {format_inr(ev.tax + o.exit_load)} in tax and exit load, "
        "more than the lower fees would earn back over your horizon."
    )


def _wait_reason(events: frozenset[Reason]) -> Reason:
    for r in (
        Reason.WAIT_LOCK_IN,
        Reason.WAIT_LONG_TERM,
        Reason.WAIT_EXIT_LOAD,
        Reason.WAIT_NEXT_FY,
    ):
        if r in events:
            return r
    return Reason.WAIT_LONG_TERM


def _decision(
    lot: Lot,
    scheme: Scheme,
    action: Action,
    reason: Reason,
    ev: _Evaluated | None,
) -> LotDecision:
    value_now = _paise(lot.units * scheme.valuation.nav)
    o = ev.option if ev else None
    switching = action in {Action.SWITCH_NOW, Action.WAIT}
    return LotDecision(
        lot_id=lot.lot_id,
        scheme_id=scheme.scheme_id,
        buy_date=lot.buy_date,
        units=lot.units,
        action=action,
        reason=reason,
        explanation=_explain(reason, ev, scheme),
        switch_on=o.on if (o and switching) else None,
        value_now=value_now,
        sale_value=_paise(o.value) if (o and switching) else ZERO,
        exit_load=o.exit_load if (o and switching) else ZERO,
        gain=_paise(o.gain.gain) if (o and switching) else ZERO,
        regime=o.gain.regime if (o and switching) else None,
        tax=ev.tax if (ev and switching) else ZERO,
        exemption_used=_paise(ev.exemption) if (ev and switching) else ZERO,
        net_benefit=_paise(ev.net) if (ev and switching) else ZERO,
        grandfathered=o.gain.grandfathered if (o and switching) else False,
    )


def _plan_lots(  # noqa: PLR0912 - one decision table, kept in one place
    portfolio: Portfolio,
    market: MarketData,
    rules: Sequence[TaxRules],
    a: Assumptions,
    *,
    now_only: bool,
) -> list[LotDecision]:
    planner = _Planner(portfolio, market, rules, a)
    fixed: list[LotDecision] = []
    work: list[tuple[Decimal, str, Scheme, Lot, SchemeMarket]] = []
    for scheme in portfolio.schemes:
        m = market.for_scheme(scheme.scheme_id)
        for lot in build_lots(scheme).open_lots:
            if scheme.plan is Plan.DIRECT:
                fixed.append(_decision(lot, scheme, Action.KEEP, Reason.ALREADY_DIRECT, None))
            elif m.ter_regular is None or m.ter_direct is None:
                fixed.append(_decision(lot, scheme, Action.REVIEW, Reason.NO_TER_DATA, None))
            elif not lot.cost_known:
                fixed.append(_decision(lot, scheme, Action.REVIEW, Reason.UNKNOWN_COST, None))
            elif (m.ter_gap or ZERO) <= 0:
                fixed.append(_decision(lot, scheme, Action.KEEP, Reason.NO_TER_GAP, None))
            else:
                priority = lot.units * scheme.valuation.nav * (m.ter_gap or ZERO)
                work.append((priority, lot.lot_id, scheme, lot, m))
    # Biggest yearly saving first; lot id breaks ties, so plans are deterministic.
    work.sort(key=lambda w: (-w[0], w[1]))
    decided: list[LotDecision] = []
    for _, _, scheme, lot, m in work:
        value_now = lot.units * scheme.valuation.nav
        opts = planner.options(scheme, lot, m)
        if now_only:
            opts = [o for o in opts if o.on == a.as_of]
        if not opts:
            reason = Reason.LOCKED_TODAY if now_only else Reason.KEEP_LOCKED_PAST_HORIZON
            decided.append(_decision(lot, scheme, Action.KEEP, reason, None))
            continue
        evals = [planner.evaluate(o, value_now, m) for o in opts]
        best = max(evals, key=lambda e: (e.net, -e.option.years))
        if best.net <= 0 and not now_only:
            decided.append(
                _decision(lot, scheme, Action.KEEP, Reason.KEEP_COST_EXCEEDS_BENEFIT, best)
            )
            continue
        fy = fy_start_year(best.option.on)
        planner.exemption_left[fy] = planner.exemption_for(fy, best.option.on) - best.exemption
        if best.option.on == a.as_of:
            free = best.tax == 0 and best.option.exit_load == 0
            reason = Reason.SWITCH_FREE if free else Reason.SWITCH_WORTH_IT
            decided.append(_decision(lot, scheme, Action.SWITCH_NOW, reason, best))
        else:
            decided.append(
                _decision(lot, scheme, Action.WAIT, _wait_reason(best.option.events), best)
            )
    by_id = {d.lot_id: d for d in [*fixed, *decided]}
    return [by_id[k] for k in sorted(by_id, key=_lot_sort_key)]


def _lot_sort_key(lot_id: str) -> tuple[int, int, int]:
    f, s, lot = lot_id.split("-")
    return int(f[1:]), int(s[1:]), int(lot[1:])


def _totals(
    decisions: Sequence[LotDecision], portfolio: Portfolio, market: MarketData, a: Assumptions
) -> Totals:
    switching = [d for d in decisions if d.action in {Action.SWITCH_NOW, Action.WAIT}]
    value = sum((d.value_now for d in switching), ZERO)
    tax = sum((d.tax for d in switching), ZERO)
    load = sum((d.exit_load for d in switching), ZERO)
    net = sum((d.net_benefit for d in switching), ZERO)
    gap_weighted = ZERO
    ter_r_weighted = ZERO
    for d in switching:
        m = market.for_scheme(d.scheme_id)
        gap_weighted += d.value_now * (m.ter_gap or ZERO)
        ter_r_weighted += d.value_now * (m.ter_regular or ZERO)
    months: int | None = None
    if value > 0:
        ter_r = ter_r_weighted / value
        ter_d = ter_r - gap_weighted / value
        months = break_even_months(value, tax + load, ter_r, ter_d, a.expected_return)
    return Totals(
        switch_value=_paise(value),
        tax=_paise(tax),
        exit_load=_paise(load),
        net_benefit=_paise(net),
        break_even_months=months,
        lots_switched=len(switching),
    )


def _fy_tax(
    decisions: Sequence[LotDecision], rules: Sequence[TaxRules], a: Assumptions
) -> tuple[FyTax, ...]:
    by_fy: dict[int, list[LotDecision]] = {}
    for d in decisions:
        if d.switch_on is not None and d.regime is not None:
            by_fy.setdefault(fy_start_year(d.switch_on), []).append(d)
    out = []
    for fy in sorted(by_fy):
        on = date(fy, 4, 1)
        r, assumed = rules_for(on, rules)
        totals = dict.fromkeys(TaxRegime, ZERO)
        for d in by_fy[fy]:
            if d.regime is not None:
                totals[d.regime] += d.gain
        buckets = GainBuckets(
            equity_stcg=totals[TaxRegime.EQUITY_STCG],
            equity_ltcg=totals[TaxRegime.EQUITY_LTCG],
            other_ltcg=totals[TaxRegime.OTHER_LTCG],
            slab=totals[TaxRegime.SLAB],
        )
        exemption = r.equity.ltcg_exemption_per_fy.value
        if fy == fy_start_year(a.as_of):
            exemption = max(exemption - a.other_equity_ltcg_this_fy, ZERO)
        t = tax_on_gains(buckets, r, slab_rate=a.slab_rate, exemption_available=exemption)
        out.append(
            FyTax(
                financial_year=fy_label(fy),
                gains=buckets,
                exemption_used=_paise(t.exemption_used),
                tax=_paise(t.total),
                rules_assumed=assumed,
            )
        )
    return tuple(out)


def _timeline(decisions: Sequence[LotDecision], as_of: date) -> tuple[TimelineStep, ...]:
    """Switch steps grouped as "Now", then one step per calendar month."""
    groups: dict[tuple[int, int], list[LotDecision]] = {}
    for d in decisions:
        if d.switch_on is None:
            continue
        key = (0, 0) if d.switch_on == as_of else (d.switch_on.year, d.switch_on.month)
        groups.setdefault(key, []).append(d)
    steps = []
    for key in sorted(groups):
        ds = groups[key]
        first = min(d.switch_on for d in ds if d.switch_on is not None)
        label = "Now" if key == (0, 0) else f"{format_date(first).split(' ', 1)[1]}"
        steps.append(
            TimelineStep(
                on=first,
                lots=len(ds),
                value=_paise(sum((d.value_now for d in ds), ZERO)),
                label=label,
            )
        )
    return tuple(steps)


def _schemes(
    portfolio: Portfolio, market: MarketData, decisions: Sequence[LotDecision]
) -> tuple[SchemePlan, ...]:
    out = []
    for s in portfolio.schemes:
        m = market.for_scheme(s.scheme_id)
        ds = [d for d in decisions if d.scheme_id == s.scheme_id]
        counts: dict[Action, int] = {}
        for d in ds:
            counts[d.action] = counts.get(d.action, 0) + 1
        gap = m.ter_gap
        out.append(
            SchemePlan(
                scheme_id=s.scheme_id,
                name=s.name,
                plan=s.plan,
                value=s.valuation.value,
                ter_regular=m.ter_regular,
                ter_direct=m.ter_direct,
                yearly_leak=_paise(s.valuation.value * gap)
                if (gap is not None and s.plan is Plan.REGULAR)
                else None,
                actions=counts,
                net_benefit=_paise(sum((d.net_benefit for d in ds), ZERO)),
            )
        )
    return tuple(out)


def plan_switch(
    portfolio: Portfolio,
    market: MarketData,
    rules: Sequence[TaxRules],
    assumptions: Assumptions,
) -> SwitchPlan:
    """Build the dated, lot-by-lot switch plan with baselines.

    Deterministic for the same inputs. Never sells ELSS units before their lock-in
    ends. If the optimized plan were ever worse than switching every eligible lot
    today, the switch-all-now plan is returned instead.
    """
    a = assumptions
    planned = _plan_lots(portfolio, market, rules, a, now_only=False)
    all_now = _plan_lots(portfolio, market, rules, a, now_only=True)
    plan_totals = _totals(planned, portfolio, market, a)
    now_totals = _totals(all_now, portfolio, market, a)
    notes: list[str] = []
    if now_totals.net_benefit > plan_totals.net_benefit:
        planned, plan_totals = all_now, now_totals
        notes.append("Switching everything eligible today beats waiting, so the plan does that.")
    fy_tax = _fy_tax(planned, rules, a)
    for f in fy_tax:
        if f.rules_assumed:
            notes.append(
                f"FY {f.financial_year} tax rules aren't published yet; current rules assumed."
            )
    if any(d.reason is Reason.NO_TER_DATA for d in planned):
        notes.append("Some funds have no expense-ratio data and are marked for review.")
    if any(d.reason is Reason.UNKNOWN_COST for d in planned):
        notes.append(
            "Some units pre-date your statement; download a CAS from an earlier start date."
        )
    notes.append("Tax excludes surcharge; it assumes total income under Rs 50 lakh.")
    never = Totals(
        switch_value=ZERO,
        tax=ZERO,
        exit_load=ZERO,
        net_benefit=ZERO,
        break_even_months=None,
        lots_switched=0,
    )
    return SwitchPlan(
        as_of=a.as_of,
        assumptions=a,
        decisions=tuple(planned),
        schemes=_schemes(portfolio, market, planned),
        totals=plan_totals,
        switch_all_now=now_totals,
        never_switch=never,
        fy_tax=fy_tax,
        timeline=_timeline(planned, a.as_of),
        notes=tuple(notes),
    )
