import { describe, expect, it } from 'vitest';

import { fractionToPercent, isPercentInput, percentToFraction } from './decimal';
import { formatMonths, formatPercent } from './format';

describe('formatPercent', () => {
  it.each([
    ['0.1171', 2, '11.71%'],
    ['0.0175', 2, '1.75%'],
    ['0.12', 0, '12%'],
    ['0.12', 2, '12.00%'],
    ['1', 0, '100%'],
    ['0', 2, '0.00%'],
    ['-0.05', 1, '-5.0%'],
    ['0.11710993', 2, '11.71%'],
    ['0.6667', 0, '67%'],
  ])('%s (%i digits) -> %s', (input, digits, expected) => {
    expect(formatPercent(input, digits)).toBe(expected);
  });

  it('rejects non-decimals', () => {
    expect(() => formatPercent('12%')).toThrow(TypeError);
  });
});

describe('formatMonths', () => {
  it.each([
    [0, 'right away'],
    [1, '1 month'],
    [11, '11 months'],
    [12, '1 year'],
    [14, '1 year 2 months'],
    [42, '3 years 6 months'],
    [24, '2 years'],
  ])('%i -> %s', (months, expected) => {
    expect(formatMonths(months)).toBe(expected);
  });

  it.each([-1, 1.5, Number.NaN])('rejects %s', (m) => {
    expect(() => formatMonths(m)).toThrow(RangeError);
  });
});

describe('percent input conversions', () => {
  it.each([
    ['12', '0.12'],
    ['1.65', '0.0165'],
    ['7.5', '0.075'],
    ['0', '0'],
    ['30', '0.3'],
    ['100', '1'],
    ['0.7', '0.007'],
    [' 12 ', '0.12'],
  ])('percentToFraction(%j) -> %s', (input, expected) => {
    expect(percentToFraction(input)).toBe(expected);
  });

  it.each(['', 'abc', '-1', '12%', '1.23456', '1e2', '1000'])('percentToFraction rejects %j', (input) => {
    expect(percentToFraction(input)).toBeNull();
    expect(isPercentInput(input)).toBe(false);
  });

  it.each([
    ['0.12', '12'],
    ['0.0165', '1.65'],
    ['0.075', '7.5'],
    ['0.30', '30'],
    ['1', '100'],
    ['0', '0'],
  ])('fractionToPercent(%s) -> %s', (input, expected) => {
    expect(fractionToPercent(input)).toBe(expected);
  });

  it('round-trips', () => {
    for (const p of ['12', '1.65', '0.7', '30', '0', '45.25']) {
      expect(fractionToPercent(percentToFraction(p) ?? 'x')).toBe(p);
    }
  });

  it('fractionToPercent rejects junk', () => {
    expect(() => fractionToPercent('abc')).toThrow(TypeError);
  });
});
