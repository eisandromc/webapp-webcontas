import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { api, formatPeriod } from '../api'
import type { Bootstrap } from '../types'
import { AccountsIcon, ChartIcon, ChevronIcon, HistoryIcon, HomeIcon, ListIcon, PinIcon, SettingsIcon } from './Icons'

const nav = [
  { to: '/', label: 'Painel', icon: <ChartIcon /> },
  { to: '/mes', label: 'Mês', icon: <HomeIcon /> },
  { to: '/contas', label: 'Contas', icon: <AccountsIcon /> },
  { to: '/lancamentos', label: 'Lançamentos', icon: <ListIcon /> },
  { to: '/historico', label: 'Histórico', icon: <HistoryIcon /> },
  { to: '/configuracoes', label: 'Configurações', icon: <SettingsIcon /> },
]

function readFlag(key: string) {
  try { return localStorage.getItem(key) === '1' } catch { return false }
}
function writeFlag(key: string, value: boolean) {
  try { localStorage.setItem(key, value ? '1' : '0') } catch { /* sem armazenamento */ }
}

export function Layout() {
  const [collapsed, setCollapsed] = useState(() => readFlag('sidebar-collapsed'))
  const [pinned, setPinned] = useState(() => readFlag('sidebar-pinned'))
  const [hover, setHover] = useState(false)
  useEffect(() => writeFlag('sidebar-collapsed', collapsed), [collapsed])
  useEffect(() => writeFlag('sidebar-pinned', pinned), [pinned])
  const server = useQuery({ queryKey: ['server-info'], queryFn: () => api<{ urls: string[] }>('/api/server-info'), staleTime: 300_000 })
  const peek = collapsed && !pinned && hover
  const open = !collapsed || peek
  const { data } = useQuery({ queryKey: ['bootstrap'], queryFn: () => api<Bootstrap>('/api/bootstrap') })
  const navigate = useNavigate()
  const location = useLocation()
  const routedPeriod = location.pathname.match(/^\/mes\/(\d{4}-\d{2})$/)?.[1]
  const focusedPeriod = routedPeriod ?? data?.current_period ?? data?.periods[0] ?? ''
  const resolvedNav = nav.map(item => item.to === '/mes' ? {...item, to: focusedPeriod ? `/mes/${focusedPeriod}` : '/'} : item)
  return (
    <div className={`app-shell ${collapsed ? 'sb-collapsed' : 'sb-expanded'} ${pinned ? 'sb-pinned' : ''}`}>
      <a className="skip-link" href="#conteudo">Pular para o conteúdo</a>
      <aside className={`sidebar ${open ? 'is-open' : 'is-closed'} ${peek ? 'is-peek' : ''}`} onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}>
        <div className="brand"><img className="brand-logo" src="/logo.svg" alt="" width="42" height="42" /><div><strong>Divisão de Contas</strong><small>contas da casa</small></div></div>
        <div className="sidebar-tools">
          <button type="button" className="sidebar-tool" onClick={() => setCollapsed(!collapsed)} aria-label={collapsed ? 'Ampliar menu lateral' : 'Recolher menu lateral'} title={collapsed ? 'Ampliar' : 'Recolher'}><ChevronIcon flipped={collapsed} /><span>{collapsed ? 'Ampliar' : 'Recolher'}</span></button>
          <button type="button" className={`sidebar-tool ${pinned ? 'active' : ''}`} onClick={() => setPinned(!pinned)} aria-pressed={pinned} aria-label={pinned ? 'Desafixar menu lateral' : 'Fixar menu lateral'} title={pinned ? 'Desafixar' : 'Fixar'}><PinIcon /><span>{pinned ? 'Fixado' : 'Fixar'}</span></button>
        </div>
        <nav aria-label="Navegação principal">
          {resolvedNav.map(item => <NavLink key={item.label} to={item.to} end={item.label === 'Painel'}>{item.icon}<span>{item.label}</span></NavLink>)}
        </nav>
        <div className="local-note">Uso local<br/><span>rede de confiança</span>{server.data?.urls.length ? <div className="server-address"><small>Acesse por outro aparelho:</small>{server.data.urls.slice(0, 1).map(url => <a key={url} href={url}>{url}</a>)}</div> : null}</div>
      </aside>
      <div className="content-column">
        <header className="topbar">
          <div><span className="eyebrow">Mês em foco</span><strong>{data ? formatPeriod(focusedPeriod) : 'Carregando…'}</strong></div>
          <label className="month-picker">Trocar mês<select value={focusedPeriod} onChange={e => navigate(`/mes/${e.target.value}`)}>{[...new Set([...(data?.periods ?? []), data?.current_period ?? '', routedPeriod ?? ''])].filter(Boolean).sort().reverse().map(period => <option key={period} value={period}>{formatPeriod(period)}</option>)}</select></label>
        </header>
        <main id="conteudo"><Outlet /></main>
      </div>
      <nav className="mobile-nav" aria-label="Navegação principal">
        {resolvedNav.map(item => <NavLink key={item.label} to={item.to} end={item.label === 'Painel'}>{item.icon}<span>{item.label}</span></NavLink>)}
      </nav>
    </div>
  )
}
