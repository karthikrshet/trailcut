import { expect, test } from '@playwright/test';

// Full journey against the real API (started by playwright.config.ts) on the sample portfolio.
test.describe('sample portfolio journey', () => {
  test('report, plan, chat and delete', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: 'Try a sample' }).click();

    await expect(page.getByText('Sample portfolio (fictional)')).toBeVisible({ timeout: 30_000 });
    await expect(page.getByRole('heading', { level: 2 })).toContainText('in extra costs over 20 years');
    await expect(page.getByText('11.71%')).toBeVisible();

    await page.getByRole('tab', { name: 'Switch plan' }).click();
    await expect(page.getByRole('heading', { name: 'Your switch plan' })).toBeVisible();
    await expect(page.getByText('₹44,495').first()).toBeVisible();
    await expect(page.getByRole('list', { name: 'Switch timeline' })).toBeVisible();

    // Blade keeps native switch/checkbox inputs off-screen behind styled tracks; React
    // handles their change on 'click', which is what a real click on the track sends.
    await page.getByRole('switch', { name: 'Compare with switching everything today' }).dispatchEvent('click');
    await expect(page.getByRole('heading', { name: 'If you switched everything today' })).toBeVisible();

    await page.getByRole('button', { name: 'Ask about my plan' }).click();
    await page.getByRole('button', { name: 'What if I switch everything today?' }).click();
    await expect(page.getByRole('log', { name: 'Conversation' })).toContainText('₹', { timeout: 30_000 });
    await page.keyboard.press('Escape');

    await page.getByRole('button', { name: 'Delete my data' }).click();
    await expect(
      page.getByRole('heading', { level: 1, name: 'Stop paying commission on your own money.' }),
    ).toBeVisible();
  });

  test('refuses fund picking in chat', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: 'Try a sample' }).click();
    await page.getByRole('button', { name: 'Ask about my plan' }).click();
    await page.getByLabel('Your question').fill('Which fund should I buy instead?');
    await page.getByRole('button', { name: 'Ask', exact: true }).click();
    await expect(page.getByRole('log', { name: 'Conversation' })).toContainText("can't recommend which fund to buy");
  });

  test('workspace has no horizontal scroll', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: 'Try a sample' }).click();
    await expect(page.getByText('Sample portfolio (fictional)')).toBeVisible({ timeout: 30_000 });
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow).toBeLessThanOrEqual(0);
  });

  test('an unreadable statement gets a plain-language error from the API', async ({ page }) => {
    await page.goto('/');
    await page.locator('input[type="file"]').setInputFiles({
      name: 'statement.pdf',
      mimeType: 'application/pdf',
      buffer: Buffer.from('%PDF-1.4 not really a statement %%EOF'),
    });
    await page.getByLabel('PDF password').fill('test-password');
    await page.getByRole('checkbox').dispatchEvent('click');
    await page.getByRole('button', { name: 'Check my portfolio' }).click();
    await expect(page.getByText(/We couldn't read this statement|couldn't recognise this PDF/).first()).toBeVisible({
      timeout: 30_000,
    });
    await page.getByRole('button', { name: 'Start again' }).click();
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
  });
});
