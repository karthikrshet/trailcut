/**
 * Display formatting for money and dates. The UI never computes money: amounts
 * arrive from the API as decimal strings (Python Decimal) and are only formatted
 * here, without going through binary floating point.
 */

const DECIMAL = /^-?\d+(\.\d+)?$/;
const ISO_DATE = /^(\d{4})-(\d{2})-(\d{2})$/;
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

const LAKH_DIGITS = 5;
const CRORE_DIGITS = 7;

export type FormatINROptions = {
  /** Short lakh/crore form for cards, e.g. ₹3.8L, ₹1.2Cr. Full form otherwise. */
  compact?: boolean;
  /** Show paise (two decimals). Ignored in compact form. Default false. */
  paise?: boolean;
};

function assertDecimal(value: string): void {
  if (!DECIMAL.test(value)) {
    throw new TypeError(`formatINR expects a decimal string, got ${JSON.stringify(value)}`);
  }
}

/** Move the decimal point `places` digits left, exactly, on a decimal string. */
export function shiftDecimalLeft(value: string, places: number): string {
  assertDecimal(value);
  const negative = value.startsWith('-');
  const unsigned = negative ? value.slice(1) : value;
  const [whole = '0', fraction = ''] = unsigned.split('.');
  const padded = whole.padStart(places + 1, '0');
  const cut = padded.length - places;
  const shifted = `${padded.slice(0, cut)}.${padded.slice(cut)}${fraction}`;
  return negative ? `-${shifted}` : shifted;
}

// Intl formats decimal strings exactly (ES2023 Intl.NumberFormat v3), so no float rounding.
type Formattable = Parameters<Intl.NumberFormat['format']>[0];
const asIntl = (value: string): Formattable => value as unknown as Formattable;

const fullRupees = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  minimumFractionDigits: 0,
  maximumFractionDigits: 0,
});
const fullPaise = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});
const oneDecimal = new Intl.NumberFormat('en-IN', {
  minimumFractionDigits: 0,
  maximumFractionDigits: 1,
});

function compactINR(value: string): string {
  const negative = value.startsWith('-');
  const unsigned = negative ? value.slice(1) : value;
  const wholeDigits = (unsigned.split('.')[0] ?? '').replace(/^0+/, '').length;
  let body: string;
  if (wholeDigits > CRORE_DIGITS) {
    body = `${oneDecimal.format(asIntl(shiftDecimalLeft(unsigned, CRORE_DIGITS)))}Cr`;
  } else if (wholeDigits > LAKH_DIGITS) {
    const lakhs = oneDecimal.format(asIntl(shiftDecimalLeft(unsigned, LAKH_DIGITS)));
    // 99.96 lakh rounds to "100" lakh; show it as 1 crore instead.
    body = lakhs === '100' ? '1Cr' : `${lakhs}L`;
  } else {
    return fullRupees.format(asIntl(value));
  }
  const zero = /^0(\.0)?(L|Cr)$/.test(body);
  return `${negative && !zero ? '-' : ''}₹${body}`;
}

/**
 * Format a rupee amount the Indian way.
 *
 * @example formatINR('125000') // "₹1,25,000"
 * @example formatINR('380000', { compact: true }) // "₹3.8L"
 * @example formatINR('1250.5', { paise: true }) // "₹1,250.50"
 */
export function formatINR(value: string, options: FormatINROptions = {}): string {
  assertDecimal(value);
  if (options.compact) return compactINR(value);
  return (options.paise ? fullPaise : fullRupees).format(asIntl(value));
}

/**
 * Format an ISO calendar date (YYYY-MM-DD) as "14 Feb 2027". Timezone-free.
 *
 * @example formatDate('2027-02-14') // "14 Feb 2027"
 */
export function formatDate(iso: string): string {
  const match = ISO_DATE.exec(iso);
  if (!match) throw new TypeError(`formatDate expects YYYY-MM-DD, got ${JSON.stringify(iso)}`);
  const [, y, m, d] = match;
  const year = Number(y);
  const month = Number(m);
  const day = Number(d);
  const probe = new Date(Date.UTC(year, month - 1, day));
  if (probe.getUTCFullYear() !== year || probe.getUTCMonth() !== month - 1 || probe.getUTCDate() !== day) {
    throw new RangeError(`formatDate got an impossible date: ${iso}`);
  }
  return `${String(day)} ${MONTHS[month - 1] ?? ""} ${String(year)}`;
}
