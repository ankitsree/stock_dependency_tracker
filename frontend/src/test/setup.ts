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
