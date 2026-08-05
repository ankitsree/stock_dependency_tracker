import { useCallback, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import type { ThemeName } from './tokens'
import { ThemeContext } from './theme-context'

const STORAGE_KEY = 'sdt-theme'

/**
 * The inline script in index.html has already resolved and applied the theme
 * to <html data-theme> before React mounts (this is what prevents a flash of
 * the wrong theme). Read it back here so the React state matches the DOM
 * instead of re-deriving and risking a mismatch.
 */
function resolveInitialTheme(): ThemeName {
  const applied = document.documentElement.dataset.theme
  if (applied === 'light' || applied === 'dark') return applied
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<ThemeName>(resolveInitialTheme)

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    try {
      localStorage.setItem(STORAGE_KEY, theme)
    } catch {
      // localStorage can throw in private mode / when disabled — non-fatal.
    }
  }, [theme])

  const setTheme = useCallback((next: ThemeName) => setThemeState(next), [])
  const toggleTheme = useCallback(
    () => setThemeState((prev) => (prev === 'dark' ? 'light' : 'dark')),
    [],
  )

  return (
    <ThemeContext.Provider value={{ theme, setTheme, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  )
}
