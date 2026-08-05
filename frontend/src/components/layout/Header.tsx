import { Link, NavLink } from 'react-router-dom'
import { ThemeToggle } from './ThemeToggle'
import { TickerSearch } from './TickerSearch'

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  'text-sm transition-colors ' + (isActive ? 'text-brand' : 'text-content-dim hover:text-content')

export function Header() {
  return (
    <header className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-b border-hairline px-6 py-3">
      <div className="flex items-baseline gap-6">
        <Link to="/" className="text-base font-semibold tracking-tight text-content">
          Stock&nbsp;Dependency&nbsp;Tracker
        </Link>
        <nav className="flex gap-4">
          <NavLink to="/" end className={navLinkClass}>
            Dashboard
          </NavLink>
          <NavLink to="/relatedness" className={navLinkClass}>
            Relatedness
          </NavLink>
        </nav>
      </div>
      <div className="flex items-center gap-3">
        <TickerSearch />
        <ThemeToggle />
      </div>
    </header>
  )
}
