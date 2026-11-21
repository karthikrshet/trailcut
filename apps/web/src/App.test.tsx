import { BladeProvider } from '@razorpay/blade/components';
import { bladeTheme } from '@razorpay/blade/tokens';
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { App } from './App';

function renderApp() {
  return render(
    <BladeProvider themeTokens={bladeTheme} colorScheme="light">
      <App />
    </BladeProvider>,
  );
}

describe('App shell', () => {
  it('renders the product name as the page heading', () => {
    renderApp();
    expect(screen.getByRole('heading', { level: 1, name: 'TrailCut' })).toBeInTheDocument();
  });

  it('renders inside a main landmark', () => {
    renderApp();
    expect(screen.getByRole('main')).toBeInTheDocument();
  });

  it('always shows the not-investment-advice notice', () => {
    renderApp();
    expect(screen.getByText('Not investment advice')).toBeInTheDocument();
    expect(screen.getByText(/never places orders or names funds to buy/)).toBeInTheDocument();
  });

  it('states the privacy promise', () => {
    renderApp();
    expect(screen.getByText(/processed in memory and never stored/)).toBeInTheDocument();
  });
});
