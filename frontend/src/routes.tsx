import { Route, Routes } from 'react-router-dom'
import { AppShell } from './components/layout/AppShell'
import DashboardPage from './pages/DashboardPage'
import AnchorDetailPage from './pages/AnchorDetailPage'
import RelatednessPage from './pages/RelatednessPage'

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<DashboardPage />} />
        <Route path="anchor/:ticker" element={<AnchorDetailPage />} />
        <Route path="relatedness" element={<RelatednessPage />} />
      </Route>
    </Routes>
  )
}
