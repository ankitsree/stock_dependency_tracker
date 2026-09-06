/**
 * Parse a pasted holdings list into the shape POST /api/portfolio/analyze wants.
 *
 * Deliberately forgiving, because people paste whatever their broker exported.
 * All of these are one holding:
 *
 *     AAPL 100 shares
 *     AAPL, 100
 *     AAPL  100
 *     AAPL: 100 sh
 *     100 AAPL
 *     AAPL
 *
 * The rule is: find the ticker-shaped token, find the number, ignore the rest.
 * Anything with no ticker-shaped token at all becomes an `invalid` entry the UI
 * shows back to the user rather than dropping — a silently skipped line would
 * quietly change every percentage on the results screen.
 *
 * Ticker normalisation (upper-casing, merging repeats) is the server's job, not
 * duplicated here — see PortfolioService._normalise.
 */

import type { PortfolioHoldingInput } from '../types/domain'

export interface ParsedHoldings {
  holdings: PortfolioHoldingInput[]
  invalid: string[]
}

/**
 * 1-6 letters, optionally with a `.`/`-` class suffix (BRK.B, RY-A) or a `^`
 * index prefix (^GSPC). Loose enough for real symbols, tight enough that a
 * broker's "Total" row or a currency amount doesn't parse as one.
 */
const TICKER = /^\^?[A-Za-z]{1,6}(?:[.-][A-Za-z]{1,3})?$/

/** A share count. Thousands separators are stripped before this runs. */
const NUMBER = /^\d+(?:\.\d+)?$/

/**
 * Words brokers pad rows with, dropped before matching. The second group
 * exists because they are all *ticker-shaped* — without this, a "Total" or
 * "Cash" summary row would parse as a holding in a symbol nobody owns.
 */
const NOISE = new Set([
  'shares', 'share', 'sh', 'shs', 'qty', 'quantity', 'x', 'units', 'unit',
  'total', 'totals', 'subtotal', 'cash', 'symbol', 'ticker', 'name', 'position',
  'positions', 'value', 'price', 'cost', 'account', 'holding', 'holdings',
])

export function parseHoldings(input: string): ParsedHoldings {
  const holdings: PortfolioHoldingInput[] = []
  const invalid: string[] = []

  // Newlines (and semicolons) are the primary separator.
  for (const rawLine of input.split(/[\n;]+/)) {
    // Thousands separators go first, before anything splits on commas —
    // otherwise "AAPL 1,250" would break into "AAPL 1" and "250".
    const line = rawLine.replace(/(\d),(?=\d{3}(?:\D|$))/g, '$1').trim()
    if (!line) continue

    // A comma-separated line is only split into several holdings when EVERY
    // part is itself a valid holding — that's what tells "AAPL, MSFT, TSM"
    // (three holdings) apart from "AAPL, 100" (one holding, comma-delimited
    // columns), where the "100" part has no ticker and so fails.
    const parts = line.split(',').map((part) => part.trim()).filter(Boolean)
    if (parts.length > 1) {
      const each = parts.map(parseLine)
      if (each.every((holding): holding is PortfolioHoldingInput => holding !== null)) {
        holdings.push(...each)
        continue
      }
    }

    const single = parseLine(line)
    if (single) holdings.push(single)
    else invalid.push(line)
  }

  return { holdings, invalid }
}

function parseLine(line: string): PortfolioHoldingInput | null {
  const tokens = line
    // Strip currency amounts and percentages outright — a "$12,340.00" market
    // value column would otherwise be read as the share count.
    .replace(/[$\u00a3\u20ac]\s*[\d,.]+/g, ' ')
    .replace(/[\d.]+%/g, ' ')
    .split(/[\s,:|\t]+/)
    .map((token) => token.trim())
    .filter((token) => token && !NOISE.has(token.toLowerCase()))

  const tickerIndex = tokens.findIndex((token) => TICKER.test(token))
  if (tickerIndex === -1) return null

  const shares = tokens.find((token, index) => index !== tickerIndex && NUMBER.test(token))
  if (shares === undefined) return { ticker: tokens[tickerIndex], shares: null }

  const value = Number(shares)
  // A zero or negative count is not a position size the API will accept
  // (`shares` is gt=0), so treat it as "unsized" rather than sending a 422.
  return { ticker: tokens[tickerIndex], shares: Number.isFinite(value) && value > 0 ? value : null }
}
