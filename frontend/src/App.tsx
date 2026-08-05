import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import { ThemeProvider } from './theme/ThemeProvider'
import { DetailPanelProvider } from './components/ticker-detail/DetailPanelProvider'
import { AppRoutes } from './routes'

/**
 * Query defaults (docs/frontend-build-plan.md, Step 2):
 * - retry: 1        one silent retry; the visible retry action is on ErrorState.
 * - staleTime 2min  don't refetch while a human looks at the same screen
 *                   (independent of the backend's 6h price TTL).
 * - no refetch on window focus — jarring mid research session.
 */
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 2 * 60 * 1000,
      refetchOnWindowFocus: false,
    },
  },
})

export default function App() {
  return (
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <DetailPanelProvider>
            <AppRoutes />
          </DetailPanelProvider>
        </BrowserRouter>
      </QueryClientProvider>
    </ThemeProvider>
  )
}
