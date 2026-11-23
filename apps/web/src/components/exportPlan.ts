import type { LotDecision, SchemePlan } from '../api/types';

const ACTIONS: Record<LotDecision['action'], string> = {
  switch_now: 'Switch now',
  wait: 'Wait',
  keep: 'Keep',
  review: 'Review',
};

function cell(value: string | number | null): string {
  const text = value === null ? '' : String(value);
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

/**
 * The plan as CSV, one row per lot. Values are copied exactly as the API sent
 * them (decimal strings); nothing is calculated here.
 *
 * @example planToCsv(plan.schemes, plan.decisions).split('\n')[0]
 */
export function planToCsv(schemes: SchemePlan[], decisions: LotDecision[]): string {
  const names = new Map(schemes.map((s) => [s.scheme_id, s.name]));
  const header = ['Fund', 'Lot', 'Bought', 'Units', 'Value now (Rs)', 'Action', 'Switch on', 'Tax (Rs)',
    'Exit load (Rs)', 'Net benefit (Rs)', 'Why'];
  const rows = decisions.map((d) => [
    names.get(d.scheme_id) ?? d.scheme_id,
    d.lot_id,
    d.buy_date,
    d.units,
    d.value_now,
    ACTIONS[d.action],
    d.switch_on,
    d.tax,
    d.exit_load,
    d.net_benefit,
    d.explanation,
  ]);
  return [header, ...rows].map((r) => r.map(cell).join(',')).join('\n') + '\n';
}

/** Offer the CSV as a download. */
export function downloadCsv(csv: string, filename: string): void {
  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.append(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
