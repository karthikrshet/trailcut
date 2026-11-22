/**
 * Types mirroring the API's JSON. Money, rates and units are decimal strings
 * (Python Decimal); the UI only formats them, never computes with them.
 */

export type Decimal = string;
export type IsoDate = string;

export type Plan = 'regular' | 'direct' | 'unknown';
export type AssetClass = 'equity' | 'debt' | 'hybrid' | 'unknown';
export type Action = 'switch_now' | 'wait' | 'keep' | 'review';
export type TaxRegime = 'equity_stcg' | 'equity_ltcg' | 'other_ltcg' | 'slab';

export type SchemeSummary = {
  scheme_id: string;
  name: string;
  plan: Plan;
  asset_class: AssetClass;
  is_elss: boolean;
  units: Decimal;
  nav: Decimal;
  nav_date: IsoDate;
  value: Decimal;
  invested: Decimal;
  gain: Decimal;
  xirr: Decimal | null;
  cost_complete: boolean;
};

export type PortfolioSummary = {
  as_of: IsoDate;
  value: Decimal;
  invested: Decimal;
  gain: Decimal;
  xirr: Decimal | null;
  regular_value: Decimal;
  direct_value: Decimal;
  schemes: SchemeSummary[];
};

export type SchemeLeak = {
  scheme_id: string;
  name: string;
  plan: Plan;
  value: Decimal;
  ter_regular: Decimal | null;
  ter_direct: Decimal | null;
  yearly_leak: Decimal | null;
  leak_10y: Decimal | null;
  leak_20y: Decimal | null;
};

export type GrowthPoint = { year: number; regular: Decimal; direct: Decimal };

export type Report = {
  summary: PortfolioSummary;
  leaks: SchemeLeak[];
  yearly_leak: Decimal;
  leak_10y: Decimal;
  leak_20y: Decimal;
  growth: GrowthPoint[];
  regular_share: Decimal;
  missing_ter: string[];
  expected_return: Decimal;
};

export type LotDecision = {
  lot_id: string;
  scheme_id: string;
  buy_date: IsoDate;
  units: Decimal;
  action: Action;
  reason: string;
  explanation: string;
  switch_on: IsoDate | null;
  value_now: Decimal;
  sale_value: Decimal;
  exit_load: Decimal;
  gain: Decimal;
  regime: TaxRegime | null;
  tax: Decimal;
  exemption_used: Decimal;
  net_benefit: Decimal;
  grandfathered: boolean;
};

export type Totals = {
  switch_value: Decimal;
  tax: Decimal;
  exit_load: Decimal;
  net_benefit: Decimal;
  break_even_months: number | null;
  lots_switched: number;
};

export type SchemePlan = {
  scheme_id: string;
  name: string;
  plan: Plan;
  value: Decimal;
  ter_regular: Decimal | null;
  ter_direct: Decimal | null;
  yearly_leak: Decimal | null;
  actions: Partial<Record<Action, number>>;
  net_benefit: Decimal;
};

export type TimelineStep = { on: IsoDate; lots: number; value: Decimal; label: string };

export type FyTax = {
  financial_year: string;
  exemption_used: Decimal;
  tax: Decimal;
  rules_assumed: boolean;
};

export type Assumptions = {
  as_of: IsoDate;
  expected_return: Decimal;
  slab_rate: Decimal;
  horizon_years: number;
  other_equity_ltcg_this_fy: Decimal;
  use_next_fy_exemption: boolean;
};

export type SwitchPlan = {
  as_of: IsoDate;
  assumptions: Assumptions;
  decisions: LotDecision[];
  schemes: SchemePlan[];
  totals: Totals;
  switch_all_now: Totals;
  never_switch: Totals;
  fy_tax: FyTax[];
  timeline: TimelineStep[];
  notes: string[];
};

export type SessionResponse = {
  session_id: string;
  is_sample: boolean;
  expires_in_seconds: number;
  report: Report;
  plan: SwitchPlan;
  assumptions: Assumptions;
  notes: string[];
  disclaimer: string;
};

export type AssumptionsUpdate = Partial<{
  expected_return: Decimal;
  slab_rate: Decimal;
  horizon_years: number;
  other_equity_ltcg_this_fy: Decimal;
  use_next_fy_exemption: boolean;
  ter_overrides: Record<string, { regular_percent: Decimal; direct_percent: Decimal }>;
}>;

export type ChatTurn = { role: 'user' | 'assistant'; content: string };

export type ChatResponse = {
  answer: string;
  agent: string;
  mode: 'llm' | 'offline' | 'fallback' | 'rule';
  refused: boolean;
  notice: string | null;
  tools_used: string[];
  trace: { kind: string; name: string; ms: number; detail: string }[];
  turns_left: number;
  disclaimer: string;
};

export type ApiErrorBody = { error: { code: string; message: string } };
