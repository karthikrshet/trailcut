import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { Action } from '../api/types';
import { renderUi, sampleSession, setReducedMotion } from '../test/render';
import { schemeSummary } from './actionMeta';
import { CountUp } from './CountUp';
import { GrowthChart } from './GrowthChart';
import { ProcessingSteps } from './ProcessingSteps';
import { EmptyBlock, ErrorBlock, LoadingBlock } from './StateViews';
import { StatusBadge } from './StatusBadge';
import { Timeline } from './Timeline';

afterEach(() => {
  setReducedMotion(false);
});

describe('StatusBadge', () => {
  it.each<[Action, string]>([
    ['switch_now', 'Switch now'],
    ['wait', 'Wait'],
    ['keep', 'Keep'],
    ['review', 'Review'],
  ])('%s shows a word, not just a colour', (action, word) => {
    const { container } = renderUi(<StatusBadge action={action} />);
    expect(screen.getByText(word)).toBeInTheDocument();
    expect(container.querySelector('svg[aria-hidden="true"]')).not.toBeNull();
  });

  it('appends a date suffix', () => {
    renderUi(<StatusBadge action="wait" suffix="until 16 Dec 2026" />);
    expect(screen.getByText('Wait until 16 Dec 2026')).toBeInTheDocument();
  });
});

describe('schemeSummary', () => {
  it('lists action counts in a fixed order', () => {
    const s = sampleSession().plan.schemes[0];
    if (!s) throw new Error('fixture has schemes');
    expect(schemeSummary({ ...s, actions: { wait: 2, switch_now: 5, keep: 1 } })).toBe('5 switch now · 2 wait · 1 keep');
    expect(schemeSummary({ ...s, actions: {} })).toBe('No units held');
  });
});

describe('state views', () => {
  it('loading is announced politely', () => {
    renderUi(<LoadingBlock label="Loading your plan" />);
    expect(screen.getByRole('status', { name: 'Loading your plan' })).toBeInTheDocument();
  });

  it('error shows the message and one action', async () => {
    const onAction = vi.fn();
    renderUi(<ErrorBlock title="Oops" message="Try a fresh copy." actionLabel="Start again" onAction={onAction} />);
    expect(screen.getByText('Try a fresh copy.')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Start again' }));
    expect(onAction).toHaveBeenCalledOnce();
  });

  it('error without an action has no button', () => {
    renderUi(<ErrorBlock title="Oops" message="m" />);
    expect(screen.queryByRole('button')).toBeNull();
  });

  it('empty state explains what to do', () => {
    renderUi(<EmptyBlock title="Nothing here">Upload a statement.</EmptyBlock>);
    expect(screen.getByText('Nothing here')).toBeInTheDocument();
    expect(screen.getByText('Upload a statement.')).toBeInTheDocument();
  });
});

describe('ProcessingSteps', () => {
  it('marks earlier steps done and the current one active', () => {
    renderUi(<ProcessingSteps step="pricing" kind="upload" />);
    expect(screen.getByText('Working on your statement')).toBeInTheDocument();
    expect(screen.getByText('(done)')).toBeInTheDocument();
    expect(screen.getAllByRole('listitem')).toHaveLength(3);
    expect(screen.getByText(/never stored/)).toBeInTheDocument();
  });

  it('names the sample when loading it', () => {
    renderUi(<ProcessingSteps step="reading" kind="sample" />);
    expect(screen.getByText('Loading the sample portfolio')).toBeInTheDocument();
  });
});

describe('CountUp', () => {
  it('exposes the exact final value to screen readers immediately', () => {
    renderUi(<CountUp value="2222303.51" options={{ compact: true }} />);
    expect(screen.getByLabelText('₹22.2L')).toBeInTheDocument();
  });

  it('jumps straight to the final value with reduced motion', () => {
    renderUi(<CountUp value="125000" />, { reducedMotion: true });
    expect(screen.getByText('₹1,25,000')).toBeInTheDocument();
  });
});

describe('Timeline', () => {
  it('renders steps in order with compact values', () => {
    renderUi(<Timeline steps={sampleSession().plan.timeline.slice(0, 3)} />);
    const items = screen.getAllByRole('listitem');
    expect(items).toHaveLength(3);
    expect(items[0]).toHaveTextContent('Now');
    expect(items[1]).toHaveTextContent('Dec 2026');
  });

  it('renders nothing for an empty plan', () => {
    const { container } = renderUi(<Timeline steps={[]} />);
    expect(container.querySelector('ol')).toBeNull();
  });
});

describe('GrowthChart', () => {
  it('describes the end values in its accessible name', () => {
    const growth = sampleSession().report.growth;
    renderUi(<GrowthChart points={growth} />);
    const last = growth[growth.length - 1];
    if (!last) throw new Error('fixture growth');
    expect(screen.getByRole('img').getAttribute('aria-label')).toContain('After 20 years');
    expect(screen.getByText(/Shaded: money lost/)).toBeInTheDocument();
  });

  it('renders nothing with too few points', () => {
    const { container } = renderUi(<GrowthChart points={[]} />);
    expect(container.querySelector('svg')).toBeNull();
  });
});

describe('animations on hidden pages', () => {
  it('shows the final value immediately when the page is not visible', () => {
    const spy = vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('hidden');
    renderUi(<CountUp value="2222303.51" options={{ compact: true }} />);
    expect(screen.getByText('₹22.2L')).toBeInTheDocument();
    spy.mockRestore();
  });
});
