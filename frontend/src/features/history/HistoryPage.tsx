import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api, formatMoney, formatPeriod } from '../../api'
import type { HistoryItem } from '../../types'
import { ErrorState, Loading } from '../../components/Feedback'

export function HistoryPage() {
  const query = useQuery({ queryKey: ['history'], queryFn: () => api<{months:HistoryItem[]}>('/api/history') })
  if (query.isLoading) return <Loading />
  if (query.error || !query.data) return <ErrorState error={query.error}/>
  const months=[...query.data.months].reverse()
  const max=Math.max(1,...months.map(item=>Math.abs(item.net_cents)))
  const years=[...new Set(months.map(item=>item.period.slice(0,4)))]
  return <div className="page"><section className="page-title"><div><span className="eyebrow">Linha do tempo</span><h1>Histórico da casa</h1><p>Compare os meses e acompanhe como os saldos evoluíram.</p></div><span className="count-badge">{months.length} meses</span></section>
    {years.map(year=><section className="panel history-year" key={year}><div className="section-heading"><h2>{year}</h2><span>{months.filter(m=>m.period.startsWith(year)).length} meses</span></div><div className="history-list">{months.filter(m=>m.period.startsWith(year)).map(item=><Link to={`/mes/${item.period}`} className="history-row" key={item.period}><div><strong>{formatPeriod(item.period)}</strong><small>{item.people.map(person=>`${person.name}: ${formatMoney(person.accumulated_cents)}`).join(' · ')}</small></div><div className="history-bar" aria-hidden="true"><span style={{width:`${Math.max(3,Math.abs(item.net_cents)/max*100)}%`}}></span></div><dl><div><dt>Gastos</dt><dd>{formatMoney(item.expenses_cents)}</dd></div><div><dt>Total dividido</dt><dd>{formatMoney(item.net_cents)}</dd></div></dl></Link>)}</div></section>)}
  </div>
}

