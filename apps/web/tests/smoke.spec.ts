import { test, expect } from '@playwright/test';

test('login and load projects', async ({ page }) => {
  await page.goto('/login');
  await page.getByPlaceholder('Email').fill('consultant@demo.com');
  await page.getByPlaceholder('Password').fill('Consultant123!');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await page.waitForURL('**/projects');
  await expect(page.getByText('Projects')).toBeVisible();
});
