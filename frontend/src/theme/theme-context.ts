import { createContext, useContext } from 'react'
import type { ThemeName } from './tokens'

export interface ThemeContextValue {
  theme: ThemeName
  setTheme: (theme: ThemeName) => void
  toggleTheme: () => void
}

/**
 * Context + hook live here (separate from the ThemeProvider component) so no
 * single file exports both a component and non-components — which keeps React
 * Fast Refresh working cleanly during dev.
 */
export const ThemeContext = createContext<ThemeContextValue | null>(null)

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error('useTheme must be used within <ThemeProvider>')
  return ctx
}
