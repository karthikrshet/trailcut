import { expect, test } from '@playwright/test';

test.describe('app shell', () => {
  test('loads with heading, privacy note and advice notice', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveTitle('TrailCut');
    await expect(page.getByRole('heading', { level: 1, name: 'TrailCut' })).toBeVisible();
    await expect(page.getByText(/never stored/)).toBeVisible();
    await expect(page.getByText('Not investment advice')).toBeVisible();
  });

  test('has no horizontal scroll', async ({ page }) => {
    await page.goto('/');
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow).toBeLessThanOrEqual(0);
  });

  test('renders with reduced motion and logs no console errors', async ({ page }) => {
    const errors: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') errors.push(msg.text());
    });
    page.on('pageerror', (err) => errors.push(err.message));
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.goto('/');
    await expect(page.getByRole('main')).toBeVisible();
    expect(errors).toEqual([]);
  });

  test('sets the document language for screen readers', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('html')).toHaveAttribute('lang', 'en-IN');
  });
});
