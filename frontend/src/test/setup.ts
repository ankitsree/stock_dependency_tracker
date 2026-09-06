// Ambient here (no explicit re-export needed): including this file in the
// TS program via tsconfig's `include: ["src"]` is enough for the jest-dom
// matcher types (toBeInTheDocument, etc.) to apply across every test file.
import '@testing-library/jest-dom/vitest'

import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

// RTL's automatic post-test cleanup hooks into a global `afterEach` — since
// test files here import from 'vitest' explicitly rather than using
// `globals: true`, that hook never gets registered on its own. Without this,
// every render in a file stacks up in the same jsdom document instead of
// being unmounted between tests.
afterEach(cleanup)

// jsdom implements no CSS Object Model media queries, so `window.matchMedia`
// simply doesn't exist there. ThemeProvider calls it during its very first
// render to pick up the OS colour-scheme preference, which means any test
// that renders a themed component crashes on mount without this. Always
// reporting "not dark" makes the light theme the deterministic test default.
if (typeof window !== 'undefined' && !window.matchMedia) {
  window.matchMedia = (query: string): MediaQueryList =>
    ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: () => {},
      removeEventListener: () => {},
      addListener: () => {},
      removeListener: () => {},
      dispatchEvent: () => false,
    }) as MediaQueryList
}
