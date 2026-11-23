import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { ApiError } from '../api/client';
import type { EstimateResponse } from '../api/types';
import { renderUi, sampleSession } from '../test/render';
import { ThemeRoot, ThemeToggle } from '../theme';
import { useColorScheme } from '../themeContext';
import { Estimator } from './Estimator';
import { planToCsv } from './exportPlan';
import { HeroStack } from './HeroStack';

const RESULT: EstimateResponse = {
  years: 15,
  invested: '2300000.00',
  regular_value: '6400000.00',
  direct_value: '6900000.00',
  leak: '500000.00',
  leak_share: '0.0725',
  first_year_fees_gap: '6250.00',
  series: [
    { year: 0, invested: '500000.00', regular: '500000.00', direct: '500000.00' },
    { year: 15, invested: '2300000.00', regular: '6400000.00', direct: '6900000.00' },
  ],
};

describe('Estimator', () => {
  it('sends the typed values as exact strings and shows engine figures', async () => {
    const estimate = vi.fn().mockResolvedValue(RESULT);
    renderUi(<Estimator estimate={estimate} />, { reducedMotion: true });
    await userEvent.click(screen.getByRole('button', { name: 'Estimate my commission' }));
    expect(estimate).toHaveBeenCalledWith({
      lump_sum: '500000',
      monthly_sip: '10000',
      years: 15,
      ter_regular_percent: '1.65',
      ter_direct_percent: '0.70',
      expected_return_percent: '12',
    });
    expect(await screen.findByText('₹5L')).toBeInTheDocument();
    expect(screen.getByText(/7.3% of what the same money could grow to/)).toBeInTheDocument();
    expect(screen.getByText(/₹6,250 in extra fees in the first year/)).toBeInTheDocument();
    expect(screen.getByText('₹69L')).toBeInTheDocument();
  });

  it('blocks invalid input', async () => {
    renderUi(<Estimator estimate={vi.fn()} />);
    const years = screen.getByLabelText('Years');
    await userEvent.clear(years);
    await userEvent.type(years, '99');
    expect(screen.getByText('1 to 40 years.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Estimate my commission' })).toBeDisabled();
  });

  it('needs a lump sum or a SIP', async () => {
    renderUi(<Estimator estimate={vi.fn()} />);
    await userEvent.clear(screen.getByLabelText('Invested today (₹)'));
    await userEvent.clear(screen.getByLabelText('Monthly SIP (₹)'));
    expect(screen.getByRole('button', { name: 'Estimate my commission' })).toBeDisabled();
  });

  it('rejects commas and decimals in rupee fields', async () => {
    renderUi(<Estimator estimate={vi.fn()} />);
    const lump = screen.getByLabelText('Invested today (₹)');
    await userEvent.clear(lump);
    await userEvent.type(lump, '5,00,000');
    expect(screen.getAllByText('Whole rupees, digits only.').length).toBeGreaterThan(0);
  });

  it('shows API errors plainly', async () => {
    const estimate = vi.fn().mockRejectedValue(new ApiError(429, 'rate_limited', 'Too many requests. Please wait a moment.'));
    renderUi(<Estimator estimate={estimate} />);
    await userEvent.click(screen.getByRole('button', { name: 'Estimate my commission' }));
    expect(await screen.findByText('Too many requests. Please wait a moment.')).toBeInTheDocument();
  });
});

describe('planToCsv', () => {
  it('writes one row per lot with API values copied exactly', () => {
    const { plan } = sampleSession();
    const csv = planToCsv(plan.schemes, plan.decisions);
    const lines = csv.trim().split('\n');
    expect(lines[0]).toBe(
      'Fund,Lot,Bought,Units,Value now (Rs),Action,Switch on,Tax (Rs),Exit load (Rs),Net benefit (Rs),Why',
    );
    expect(lines).toHaveLength(plan.decisions.length + 1);
    const first = plan.decisions[0];
    if (!first) throw new Error('fixture');
    expect(lines[1]).toContain(first.lot_id);
    expect(lines[1]).toContain(first.value_now);
  });

  it('quotes cells containing commas and quotes', () => {
    const { plan } = sampleSession();
    const d = plan.decisions[0];
    const s = plan.schemes[0];
    if (!d || !s) throw new Error('fixture');
    const csv = planToCsv([{ ...s, scheme_id: d.scheme_id, name: 'Fund, "A"' }], [d]);
    expect(csv.split('\n')[1]?.startsWith('"Fund, ""A"""')).toBe(true);
  });
});

describe('HeroStack', () => {
  it('shows example cards with words, hidden from screen readers', () => {
    const { container } = renderUi(<HeroStack />, { reducedMotion: true });
    expect(screen.getByText('Small Cap Fund')).toBeInTheDocument();
    expect(screen.getByText('Wait until it turns long term')).toBeInTheDocument();
    expect(container.querySelector('[aria-hidden="true"]')).not.toBeNull();
  });
});

describe('dark mode', () => {
  function Probe() {
    return <span>{useColorScheme().scheme}</span>;
  }

  it('toggles and remembers the choice', async () => {
    window.localStorage.removeItem('trailcut.colorScheme');
    renderUi(
      <ThemeRoot>
        <ThemeToggle />
        <Probe />
      </ThemeRoot>,
    );
    expect(screen.getByText('light')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('switch', { name: 'Dark mode' }));
    expect(screen.getByText('dark')).toBeInTheDocument();
    expect(window.localStorage.getItem('trailcut.colorScheme')).toBe('dark');
  });

  it('starts from a saved choice', () => {
    window.localStorage.setItem('trailcut.colorScheme', 'dark');
    renderUi(
      <ThemeRoot>
        <Probe />
      </ThemeRoot>,
    );
    expect(screen.getByText('dark')).toBeInTheDocument();
    window.localStorage.removeItem('trailcut.colorScheme');
  });
});
