import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { App } from './App';
import { ApiError, type Client } from './api/client';
import { renderUi, sampleSession } from './test/render';

function fakeClient(overrides: Partial<Client> = {}): Client {
  return {
    sample: vi.fn().mockResolvedValue(sampleSession()),
    upload: vi.fn().mockResolvedValue(sampleSession()),
    get: vi.fn().mockResolvedValue(sampleSession()),
    updateAssumptions: vi.fn().mockResolvedValue(sampleSession()),
    remove: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  };
}

describe('App', () => {
  it('starts on the landing page with the promise and privacy note', () => {
    renderUi(<App client={fakeClient()} />);
    expect(screen.getByRole('heading', { level: 1, name: 'Stop paying commission on your own money.' })).toBeInTheDocument();
    expect(screen.getByRole('main')).toBeInTheDocument();
    expect(screen.getAllByText(/never stored/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/not investment advice/i)).toBeInTheDocument();
  });

  it('loads the sample into the workspace', async () => {
    const client = fakeClient();
    renderUi(<App client={client} />);
    await userEvent.click(screen.getByRole('button', { name: 'Try a sample' }));
    expect(await screen.findByText('Sample portfolio (fictional)')).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Report' })).toBeInTheDocument();
    expect(screen.getByText('Not investment advice')).toBeInTheDocument();
    expect(client.sample).toHaveBeenCalledOnce();
  });

  it('shows a plain-language error with a way back', async () => {
    const client = fakeClient({
      sample: vi.fn().mockRejectedValue(new ApiError(422, 'mf_central_statement', 'Download the CAMS one instead.')),
    });
    renderUi(<App client={client} />);
    await userEvent.click(screen.getByRole('button', { name: 'Try a sample' }));
    expect(await screen.findByText('This looks like an MF Central statement')).toBeInTheDocument();
    expect(screen.getByText('Download the CAMS one instead.')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Start again' }));
    expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument();
  });

  it('deletes data and returns to the start', async () => {
    const client = fakeClient();
    renderUi(<App client={client} />);
    await userEvent.click(screen.getByRole('button', { name: 'Try a sample' }));
    await userEvent.click(await screen.findByRole('button', { name: 'Delete my data' }));
    await waitFor(() => {
      expect(client.remove).toHaveBeenCalledWith('test-session-id');
    });
    expect(await screen.findByRole('heading', { level: 1 })).toBeInTheDocument();
  });

  it('still resets if delete fails', async () => {
    const client = fakeClient({ remove: vi.fn().mockRejectedValue(new Error('offline')) });
    renderUi(<App client={client} />);
    await userEvent.click(screen.getByRole('button', { name: 'Try a sample' }));
    await userEvent.click(await screen.findByRole('button', { name: 'Delete my data' }));
    expect(await screen.findByRole('heading', { level: 1 })).toBeInTheDocument();
  });

  it('switches to the plan tab', async () => {
    renderUi(<App client={fakeClient()} />);
    await userEvent.click(screen.getByRole('button', { name: 'Try a sample' }));
    await userEvent.click(await screen.findByRole('tab', { name: 'Switch plan' }));
    expect(await screen.findByRole('heading', { name: 'Your switch plan' })).toBeInTheDocument();
  });
});
