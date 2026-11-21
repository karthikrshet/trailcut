import { describe, expect, it } from 'vitest';

import { formatDate, formatINR, shiftDecimalLeft } from './format';

describe('formatINR (full)', () => {
  it.each([
    ['0', '₹0'],
    ['1', '₹1'],
    ['999', '₹999'],
    ['1000', '₹1,000'],
    ['99999', '₹99,999'],
    ['125000', '₹1,25,000'],
    ['1234567', '₹12,34,567'],
    ['12345678', '₹1,23,45,678'],
    ['1000000000', '₹1,00,00,00,000'],
    ['-125000', '-₹1,25,000'],
    ['1250.49', '₹1,250'],
    ['1250.5', '₹1,251'],
  ])('%s -> %s', (input, expected) => {
    expect(formatINR(input)).toBe(expected);
  });

  it('keeps precision beyond float range', () => {
    expect(formatINR('90071992547409931')).toBe('₹90,07,19,92,54,74,09,931');
  });

  it.each([
    ['1250.5', '₹1,250.50'],
    ['0.005', '₹0.01'],
    ['125000', '₹1,25,000.00'],
    ['-0.10', '-₹0.10'],
  ])('paise: %s -> %s', (input, expected) => {
    expect(formatINR(input, { paise: true })).toBe(expected);
  });
});

describe('formatINR (compact)', () => {
  it.each([
    ['0', '₹0'],
    ['85000', '₹85,000'],
    ['99999.4', '₹99,999'],
    ['100000', '₹1L'],
    ['125000', '₹1.3L'],
    ['380000', '₹3.8L'],
    ['1050000', '₹10.5L'],
    ['9940000', '₹99.4L'],
    ['9996000', '₹1Cr'],
    ['10000000', '₹1Cr'],
    ['12000000', '₹1.2Cr'],
    ['2345000000', '₹234.5Cr'],
    ['-380000', '-₹3.8L'],
    ['-12000000', '-₹1.2Cr'],
  ])('%s -> %s', (input, expected) => {
    expect(formatINR(input, { compact: true })).toBe(expected);
  });

  it('ignores paise in compact form', () => {
    expect(formatINR('380000', { compact: true, paise: true })).toBe('₹3.8L');
  });
});

describe('formatINR input validation', () => {
  it.each(['', 'abc', '1,000', '1e5', ' 100', '100 ', '₹100', '.5', '5.', 'NaN', 'Infinity'])(
    'rejects %j',
    (input) => {
      expect(() => formatINR(input)).toThrow(TypeError);
    },
  );
});

describe('shiftDecimalLeft', () => {
  it.each([
    ['380000', 5, '3.80000'],
    ['5', 5, '0.00005'],
    ['12.5', 1, '1.25'],
    ['-100', 2, '-1.00'],
    ['0', 3, '0.000'],
  ])('%s by %i -> %s', (input, places, expected) => {
    expect(shiftDecimalLeft(input, places)).toBe(expected);
  });
});

describe('formatDate', () => {
  it.each([
    ['2027-02-14', '14 Feb 2027'],
    ['2026-04-01', '1 Apr 2026'],
    ['2027-03-31', '31 Mar 2027'],
    ['2028-02-29', '29 Feb 2028'],
    ['2026-12-01', '1 Dec 2026'],
    ['2018-01-31', '31 Jan 2018'],
  ])('%s -> %s', (input, expected) => {
    expect(formatDate(input)).toBe(expected);
  });

  it.each(['2027-02-30', '2027-13-01', '2027-00-10', '2027-02-29', '2026-04-31'])(
    'rejects impossible date %s',
    (input) => {
      expect(() => formatDate(input)).toThrow(RangeError);
    },
  );

  it.each(['', '14 Feb 2027', '2027/02/14', '2027-2-14', '2027-02-14T00:00:00Z'])(
    'rejects non-ISO %j',
    (input) => {
      expect(() => formatDate(input)).toThrow(TypeError);
    },
  );
});
