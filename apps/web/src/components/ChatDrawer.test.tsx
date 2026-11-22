import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { ApiError } from '../api/client';
import type { ChatResponse } from '../api/types';
import { renderUi } from '../test/render';
import { ChatDrawer } from './ChatDrawer';
import { SUGGESTIONS } from './chatSuggestions';

const first = SUGGESTIONS[0] ?? '';
const second = SUGGESTIONS[1] ?? '';

function reply(over: Partial<ChatResponse> = {}): ChatResponse {
  return {
    answer: 'Total tax is ₹44,495.',
    agent: 'switch_planner',
    mode: 'llm',
    refused: false,
    notice: null,
    tools_used: ['get_switch_plan'],
    trace: [
      { kind: 'route', name: 'switch_planner', ms: 0, detail: '' },
      { kind: 'tool', name: 'get_switch_plan', ms: 3, detail: 'ok' },
    ],
    turns_left: 29,
    disclaimer: 'Not investment advice.',
    ...over,
  };
}

describe('ChatDrawer', () => {
  it('offers suggested questions when empty', () => {
    renderUi(<ChatDrawer isOpen onClose={vi.fn()} ask={vi.fn()} />);
    for (const s of SUGGESTIONS) expect(screen.getByRole('button', { name: s })).toBeInTheDocument();
  });

  it('asks a suggested question and shows the answer', async () => {
    const ask = vi.fn().mockResolvedValue(reply());
    renderUi(<ChatDrawer isOpen onClose={vi.fn()} ask={ask} />);
    await userEvent.click(screen.getByRole('button', { name: second }));
    expect(await screen.findByText('Total tax is ₹44,495.')).toBeInTheDocument();
    expect(ask).toHaveBeenCalledWith(second, []);
  });

  it('sends typed questions with recent history', async () => {
    const ask = vi.fn().mockResolvedValue(reply());
    renderUi(<ChatDrawer isOpen onClose={vi.fn()} ask={ask} />);
    const box = screen.getByLabelText('Your question');
    await userEvent.type(box, 'How much tax?');
    await userEvent.click(screen.getByRole('button', { name: 'Ask' }));
    await screen.findByText('Total tax is ₹44,495.');
    await userEvent.type(box, 'And the exit load?');
    await userEvent.click(screen.getByRole('button', { name: 'Ask' }));
    await waitFor(() => {
      expect(ask).toHaveBeenCalledTimes(2);
    });
    expect(ask.mock.calls[1]).toEqual([
      'And the exit load?',
      [
        { role: 'user', content: 'How much tax?' },
        { role: 'assistant', content: 'Total tax is ₹44,495.' },
      ],
    ]);
  });

  it('shows the not-advice notice when the reply has one', async () => {
    const ask = vi.fn().mockResolvedValue(reply({ notice: 'This is a calculation, not investment advice.' }));
    renderUi(<ChatDrawer isOpen onClose={vi.fn()} ask={ask} />);
    await userEvent.click(screen.getByRole('button', { name: first }));
    expect(await screen.findByText('This is a calculation, not investment advice.')).toBeInTheDocument();
  });

  it('reveals how the answer was produced', async () => {
    renderUi(<ChatDrawer isOpen onClose={vi.fn()} ask={vi.fn().mockResolvedValue(reply())} />);
    await userEvent.click(screen.getByRole('button', { name: first }));
    await userEvent.click(await screen.findByRole('button', { name: 'How I got this' }));
    expect(screen.getByText('tool: get_switch_plan (ok)')).toBeInTheDocument();
  });

  it('shows a plain error when asking fails', async () => {
    const ask = vi.fn().mockRejectedValue(new ApiError(429, 'chat_limit', 'This session has reached its chat limit.'));
    renderUi(<ChatDrawer isOpen onClose={vi.fn()} ask={ask} />);
    await userEvent.click(screen.getByRole('button', { name: first }));
    expect(await screen.findByText('This session has reached its chat limit.')).toBeInTheDocument();
  });

  it('does not send an empty question', () => {
    renderUi(<ChatDrawer isOpen onClose={vi.fn()} ask={vi.fn()} />);
    expect(screen.getByRole('button', { name: 'Ask' })).toBeDisabled();
  });

  it('says no funds are recommended', () => {
    renderUi(<ChatDrawer isOpen onClose={vi.fn()} ask={vi.fn()} />);
    expect(screen.getByText(/No funds are recommended/)).toBeInTheDocument();
  });

  it('closes on Escape', async () => {
    const onClose = vi.fn();
    renderUi(<ChatDrawer isOpen onClose={onClose} ask={vi.fn()} />);
    await userEvent.keyboard('{Escape}');
    expect(onClose).toHaveBeenCalled();
  });
});
