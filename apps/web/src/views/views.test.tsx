import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { AssumptionsPanel } from '../components/AssumptionsPanel';
import { TerEntry } from '../components/TerEntry';
import { UploadCard } from '../components/UploadCard';
import { renderUi, sampleSession } from '../test/render';
import { PlanView } from './PlanView';
import { ReportView } from './ReportView';

describe('ReportView', () => {
  it('shows the four headline numbers from the API', () => {
    const { report } = sampleSession();
    renderUi(<ReportView report={report} />);
    expect(screen.getByText('₹21.3L')).toBeInTheDocument(); // current value
    expect(screen.getByText('11.71%')).toBeInTheDocument(); // XIRR
    expect(screen.getByText('₹15,644')).toBeInTheDocument(); // yearly leak (< 1 lakh shows in full)
    expect(screen.getAllByText('₹22.2L').length).toBeGreaterThan(0); // 20-year cost
  });

  it('states the 20-year cost as a sentence', () => {
    renderUi(<ReportView report={sampleSession().report} />);
    expect(screen.getByRole('heading', { level: 2 })).toHaveTextContent(/in extra costs over 20 years/);
  });

  it('lists every fund with its expense ratios', () => {
    renderUi(<ReportView report={sampleSession().report} />);
    expect(screen.getByText('1.65% → 0.70%')).toBeInTheDocument();
    expect(screen.getByText('Already Direct')).toBeInTheDocument();
  });

  it('says so when no commission is found', () => {
    const { report } = sampleSession();
    renderUi(<ReportView report={{ ...report, yearly_leak: '0.00' }} />);
    expect(screen.getByText(/No Regular-plan commission found/)).toBeInTheDocument();
  });

  it('has an empty state', () => {
    const { report } = sampleSession();
    renderUi(<ReportView report={{ ...report, summary: { ...report.summary, schemes: [] } }} />);
    expect(screen.getByText('No funds found in this statement.')).toBeInTheDocument();
  });

  it('shows a dash when XIRR is unavailable', () => {
    const { report } = sampleSession();
    renderUi(<ReportView report={{ ...report, summary: { ...report.summary, xirr: null } }} />);
    expect(screen.getByText('Needs full purchase history')).toBeInTheDocument();
  });
});

describe('PlanView', () => {
  const noop = () => undefined;

  it('shows plan totals and break-even', () => {
    renderUi(<PlanView plan={sampleSession().plan} busy={false} updateError={null} onUpdate={noop} />);
    expect(screen.getByText('₹44,495')).toBeInTheDocument();
    expect(screen.getByText('₹260')).toBeInTheDocument();
    expect(screen.getByText('₹2.3L')).toBeInTheDocument();
    expect(screen.getByText('3 years 6 months')).toBeInTheDocument();
  });

  it('compares with switching everything now', async () => {
    renderUi(<PlanView plan={sampleSession().plan} busy={false} updateError={null} onUpdate={noop} />);
    await userEvent.click(screen.getByRole('switch', { name: 'Compare with switching everything today' }));
    expect(screen.getByRole('heading', { name: 'If you switched everything today' })).toBeInTheDocument();
    expect(screen.getByText('₹75,316')).toBeInTheDocument();
    expect(screen.getByText(/The plan nets ₹2,26,589/)).toBeInTheDocument();
  });

  it('lists funds as expandable sections with action counts', () => {
    renderUi(<PlanView plan={sampleSession().plan} busy={false} updateError={null} onUpdate={noop} />);
    expect(screen.getByText('Sample Small Cap Fund - Regular Plan - Growth')).toBeInTheDocument();
    // Small cap and balanced advantage each have one lot waiting.
    expect(screen.getAllByText('1 wait')).toHaveLength(2);
  });

  it('shows the timeline and notes', () => {
    renderUi(<PlanView plan={sampleSession().plan} busy={false} updateError={null} onUpdate={noop} />);
    expect(screen.getByRole('list', { name: 'Switch timeline' })).toBeInTheDocument();
    expect(screen.getByText(/excludes surcharge/)).toBeInTheDocument();
  });

  it('shows an update error', () => {
    renderUi(<PlanView plan={sampleSession().plan} busy={false} updateError="Server busy" onUpdate={noop} />);
    expect(screen.getByText('Server busy')).toBeInTheDocument();
  });

  it('asks for expense ratios when a fund has none', () => {
    const { plan } = sampleSession();
    const first = plan.decisions[0];
    if (!first) throw new Error('fixture decisions');
    const decisions = [{ ...first, action: 'review' as const, reason: 'no_ter_data', switch_on: null }];
    const schemes = plan.schemes.map((s) => (s.scheme_id === first.scheme_id ? { ...s, actions: { review: 1 } } : s));
    renderUi(<PlanView plan={{ ...plan, decisions, schemes }} busy={false} updateError={null} onUpdate={noop} />);
    expect(screen.getByText('We need two numbers for some funds')).toBeInTheDocument();
  });

  it('has an empty state', () => {
    const { plan } = sampleSession();
    renderUi(<PlanView plan={{ ...plan, decisions: [] }} busy={false} updateError={null} onUpdate={noop} />);
    expect(screen.getByText('Nothing to plan.')).toBeInTheDocument();
  });
});

describe('AssumptionsPanel', () => {
  it('pre-fills current assumptions as percents', () => {
    renderUi(<AssumptionsPanel assumptions={sampleSession().assumptions} busy={false} onApply={vi.fn()} />);
    expect(screen.getByLabelText('Expected yearly return (%)')).toHaveValue('12');
    expect(screen.getByRole('radio', { name: '30%' })).toBeChecked();
  });

  it('sends exact fraction strings', async () => {
    const onApply = vi.fn();
    renderUi(<AssumptionsPanel assumptions={sampleSession().assumptions} busy={false} onApply={onApply} />);
    const ret = screen.getByLabelText('Expected yearly return (%)');
    await userEvent.clear(ret);
    await userEvent.type(ret, '10.5');
    await userEvent.click(screen.getByRole('radio', { name: '20%' }));
    await userEvent.click(screen.getByRole('button', { name: 'Update plan' }));
    expect(onApply).toHaveBeenCalledWith({
      expected_return: '0.105',
      slab_rate: '0.2',
      horizon_years: 10,
      use_next_fy_exemption: true,
    });
  });

  it('blocks invalid input', async () => {
    const onApply = vi.fn();
    renderUi(<AssumptionsPanel assumptions={sampleSession().assumptions} busy={false} onApply={onApply} />);
    const horizon = screen.getByLabelText('Planning horizon (years)');
    await userEvent.clear(horizon);
    await userEvent.type(horizon, '99');
    expect(screen.getByText('Enter 1 to 40 years.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Update plan' })).toBeDisabled();
  });
});

describe('TerEntry', () => {
  const funds = [{ scheme_id: 'F3-S1', name: 'Sample Corporate Bond Fund' }];

  it('renders nothing when no fund needs data', () => {
    const { container } = renderUi(<TerEntry funds={[]} busy={false} onApply={vi.fn()} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('sends only complete, valid entries as percent strings', async () => {
    const onApply = vi.fn();
    renderUi(<TerEntry funds={funds} busy={false} onApply={onApply} />);
    const button = screen.getByRole('button', { name: 'Use these expense ratios' });
    expect(button).toBeDisabled();
    await userEvent.type(screen.getByLabelText('Regular plan TER (%)'), '0.65');
    await userEvent.type(screen.getByLabelText('Direct plan TER (%)'), '0.35');
    await userEvent.click(button);
    expect(onApply).toHaveBeenCalledWith({ ter_overrides: { 'F3-S1': { regular_percent: '0.65', direct_percent: '0.35' } } });
  });
});

describe('UploadCard', () => {
  it('needs a file and consent before uploading', () => {
    renderUi(<UploadCard onUpload={vi.fn()} onSample={vi.fn()} busy={false} />);
    expect(screen.getByRole('button', { name: 'Check my portfolio' })).toBeDisabled();
  });

  it('offers the sample', async () => {
    const onSample = vi.fn();
    renderUi(<UploadCard onUpload={vi.fn()} onSample={onSample} busy={false} />);
    await userEvent.click(screen.getByRole('button', { name: 'Try a sample' }));
    expect(onSample).toHaveBeenCalledOnce();
  });

  it('explains privacy and the password', () => {
    renderUi(<UploadCard onUpload={vi.fn()} onSample={vi.fn()} busy={false} />);
    const form = screen.getByRole('form', { name: 'Upload your CAS statement' });
    expect(within(form).getAllByText(/never stored|Nothing is stored/).length).toBeGreaterThan(0);
    expect(within(form).getByText(/often your PAN in capitals/)).toBeInTheDocument();
  });
});
