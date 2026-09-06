import { describe, expect, it } from 'vitest'
import { parseHoldings } from './parseHoldings'

describe('parseHoldings', () => {
  it('parses the documented "TICKER n shares" shape', () => {
    const { holdings, invalid } = parseHoldings('AAPL 100 shares\nMSFT 50 shares')

    expect(invalid).toEqual([])
    expect(holdings).toEqual([
      { ticker: 'AAPL', shares: 100 },
      { ticker: 'MSFT', shares: 50 },
    ])
  })

  it.each([
    ['AAPL, 100', { ticker: 'AAPL', shares: 100 }],
    ['AAPL  100', { ticker: 'AAPL', shares: 100 }],
    ['AAPL: 100 sh', { ticker: 'AAPL', shares: 100 }],
    ['AAPL\t100\tqty', { ticker: 'AAPL', shares: 100 }],
    ['100 AAPL', { ticker: 'AAPL', shares: 100 }],
    ['AAPL 1,250', { ticker: 'AAPL', shares: 1250 }],
    ['AAPL 10.5', { ticker: 'AAPL', shares: 10.5 }],
  ])('parses %s', (line, expected) => {
    expect(parseHoldings(line).holdings).toEqual([expected])
  })

  it('accepts a bare ticker with no share count', () => {
    expect(parseHoldings('AAPL').holdings).toEqual([{ ticker: 'AAPL', shares: null }])
  })

  it('splits a single comma-separated ticker list', () => {
    expect(parseHoldings('AAPL, MSFT, TSM').holdings).toEqual([
      { ticker: 'AAPL', shares: null },
      { ticker: 'MSFT', shares: null },
      { ticker: 'TSM', shares: null },
    ])
  })

  it('keeps class-suffixed and index tickers', () => {
    expect(parseHoldings('BRK.B 10\n^GSPC').holdings).toEqual([
      { ticker: 'BRK.B', shares: 10 },
      { ticker: '^GSPC', shares: null },
    ])
  })

  it('ignores a currency market-value column instead of reading it as shares', () => {
    expect(parseHoldings('AAPL 100 $23,010.00').holdings).toEqual([{ ticker: 'AAPL', shares: 100 }])
  })

  it('ignores a percentage column', () => {
    expect(parseHoldings('AAPL 100 42.5%').holdings).toEqual([{ ticker: 'AAPL', shares: 100 }])
  })

  it('skips blank lines', () => {
    expect(parseHoldings('\n\nAAPL 5\n   \n').holdings).toEqual([{ ticker: 'AAPL', shares: 5 }])
  })

  it('does not read a broker "Total" summary row as a holding', () => {
    expect(parseHoldings('AAPL 100\nTotal 100').holdings).toEqual([{ ticker: 'AAPL', shares: 100 }])
  })

  it('reports unparseable lines rather than dropping them', () => {
    const { holdings, invalid } = parseHoldings('AAPL 100\n---- total ----\n1234567')

    expect(holdings).toEqual([{ ticker: 'AAPL', shares: 100 }])
    expect(invalid).toEqual(['---- total ----', '1234567'])
  })

  it('treats a zero or negative share count as unsized rather than as a quantity', () => {
    expect(parseHoldings('AAPL 0').holdings).toEqual([{ ticker: 'AAPL', shares: null }])
  })

  it('returns nothing for empty input', () => {
    expect(parseHoldings('   ')).toEqual({ holdings: [], invalid: [] })
  })
})
