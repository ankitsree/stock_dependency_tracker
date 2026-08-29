import { test, expect } from '@playwright/test'
import { mockApi } from './fixtures.js'

test.beforeEach(async ({ page }) => {
  await mockApi(page)
})

test('pasting holdings renders the concentration breakdown', async ({ page }) => {
  await page.goto('/portfolio')

  await expect(page.getByText('Nothing analysed yet')).toBeVisible()

  await page.getByLabel('Your holdings').fill('AMKR 100 shares')
  await expect(page.getByText('1 holding parsed')).toBeVisible()
  await page.getByRole('button', { name: 'Analyze portfolio' }).click()

  // The donut's hero number, the risk read-out, and the heatmap cell all
  // come from the mocked response — enough to prove the whole view mounted.
  await expect(page.getByRole('img', { name: /NVDA is 65%/ })).toBeVisible()
  await expect(page.getByText(/largest single exposure/)).toBeVisible()
  await expect(page.getByRole('cell', { name: '0.82' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Export as CSV' })).toBeVisible()
})
