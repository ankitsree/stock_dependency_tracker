import { test, expect } from '@playwright/test'
import { mockApi } from './fixtures.js'

test.beforeEach(async ({ page }) => {
  await mockApi(page)
})

test('dashboard loads the graph for the default anchors', async ({ page }) => {
  await page.goto('/')

  // The heavy canvas-rendered graph (react-force-graph-2d) actually mounted,
  // rather than the app being stuck on LoadingState/ErrorState/EmptyState.
  await expect(page.locator('canvas')).toBeVisible()
  // Anchor chips come from the mocked graph response's "kind": "anchor"
  // nodes (DashboardPage.tsx), not anything hardcoded in the frontend.
  await expect(page.getByLabel('Remove NVDA')).toBeVisible()
  await expect(page.getByLabel('Remove AAPL')).toBeVisible()
})

test('searching an anchor ticker opens its detail panel', async ({ page }) => {
  await page.goto('/')
  await expect(page.locator('canvas')).toBeVisible()

  // AAPL is an anchor, deliberately absent from the mocked /api/companies
  // (satellite universe) response — the same real-world gap the search hint
  // (TickerSearch.tsx) exists to explain. Enter still opens the panel.
  const search = page.getByRole('combobox', { name: 'Search for a ticker' })
  await search.fill('AAPL')
  await expect(page.getByText(/not in the satellite list/i)).toBeVisible()
  await search.press('Enter')

  await expect(page.getByRole('heading', { name: 'AAPL', level: 2 })).toBeVisible()
})
