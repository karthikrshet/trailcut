/**
 * Exact conversions between what users type and the API's decimal strings.
 * No floating point: strings are validated and shifted digit by digit.
 */

const NUMBER = /^\d{1,3}(\.\d{1,4})?$/;

/** True if `text` is a plain non-negative number like "12" or "1.65". */
export function isPercentInput(text: string): boolean {
  return NUMBER.test(text.trim());
}

/**
 * "12" -> "0.12", "1.65" -> "0.0165". Returns null for invalid input.
 *
 * @example percentToFraction('7.5') // "0.075"
 */
export function percentToFraction(text: string): string | null {
  const t = text.trim();
  if (!NUMBER.test(t)) return null;
  const [whole = '0', frac = ''] = t.split('.');
  const digits = whole.padStart(3, '0') + frac;
  const cut = digits.length - frac.length - 2;
  const result = `${digits.slice(0, cut)}.${digits.slice(cut)}`.replace(/^0+(?=\d)/, '');
  return result.replace(/(\.\d*?)0+$/, '$1').replace(/\.$/, '');
}

/**
 * "0.12" -> "12", "0.0165" -> "1.65".
 *
 * @example fractionToPercent('0.075') // "7.5"
 */
export function fractionToPercent(fraction: string): string {
  if (!/^-?\d+(\.\d+)?$/.test(fraction)) throw new TypeError(`not a decimal: ${fraction}`);
  const negative = fraction.startsWith('-');
  const [whole = '0', frac = ''] = (negative ? fraction.slice(1) : fraction).split('.');
  const padded = frac.padEnd(2, '0');
  let out = `${whole}${padded.slice(0, 2)}.${padded.slice(2)}`.replace(/^0+(?=\d)/, '');
  out = out.replace(/(\.\d*?)0+$/, '$1').replace(/\.$/, '');
  return `${negative ? '-' : ''}${out}`;
}
