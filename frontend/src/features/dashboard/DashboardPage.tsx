import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api, formatMoney, formatMonthName, formatPeriod } from '../../api'
import type { DashboardData } from '../../types'
import { ErrorState, Loading } from '../../components/Feedback'

export function DashboardPage() {
  const query = useQuery({ queryKey: ['dashboard'], queryFn: () => api<DashboardData>('/api/dashboard?months=12') })
  if (query.isLoading) return <Loading />
  if (query.error || !query.data) return <ErrorState error={query.error} />
  const data = query.data
  const maxMonth = Math.max(1, ...data.months.map(item => Math.abs(item.expenses_cents)))
  const maxCategory = Math.max(1, ...data.categories.map(item => Math.abs(item.amount_cents)))
  const latest = data.months.at(-1)?.period
  return <div className="page dashboard-page">
    <section className="page-title"><div><span className="eyebrow">Saúde financeira da casa</span><h1>Painel de custos</h1><p>Entenda para onde o dinheiro está indo e encontre oportunidades reais de economia.</p></div>{latest?<Link className="primary-button" to={`/mes/${latest}`}>Abrir mês atual</Link>:null}</section>
    <ParticipantsPanel participants={data.participants}/>
    <section className="kpi-grid" aria-label="Resumo dos últimos 12 meses">
      <Kpi label="Gasto acumulado" value={formatMoney(data.total_expenses_cents)} detail={`${data.months.length} meses analisados`}/>
      <Kpi label="Média mensal" value={formatMoney(data.average_monthly_cents)} detail="referência para o orçamento"/>
      <Kpi label="Último mês" value={formatMoney(data.latest_expenses_cents)} detail={data.trend_percent == null?'sem comparação':`${data.trend_percent > 0 ? '+' : ''}${data.trend_percent.toFixed(1).replace('.', ',')}% versus anterior`} tone={(data.trend_percent??0)>0?'debt':'credit'}/>
    </section>
    <div className="dashboard-grid">
      <section className="panel chart-panel"><div className="section-heading"><div><span className="eyebrow">Evolução</span><h2>Gastos por mês</h2></div></div>
        <div className="bar-chart" role="img" aria-label="Gráfico de gastos mensais">{data.months.map(item=><Link to={`/mes/${item.period}`} className="bar-column" key={item.period} title={`${formatPeriod(item.period)}: ${formatMoney(item.expenses_cents)}`}><span className="bar-value">{formatMoney(item.expenses_cents)}</span><span className="bar-track"><i style={{height:`${Math.max(4,Math.abs(item.expenses_cents)/maxMonth*100)}%`}}/></span><small>{item.period.slice(5)}/{item.period.slice(2,4)}</small></Link>)}</div>
        <details className="data-alternative"><summary>Ver dados do gráfico</summary><ul>{data.months.map(item=><li key={item.period}><span>{formatPeriod(item.period)}</span><strong>{formatMoney(item.expenses_cents)}</strong></li>)}</ul></details>
      </section>
      <section className="panel"><div className="section-heading"><div><span className="eyebrow">Composição</span><h2>Maiores categorias</h2></div></div><div className="category-bars">{data.categories.map(item=><div key={item.slug}><div><span>{item.name}</span><strong>{formatMoney(item.amount_cents)}</strong></div><span className="progress"><i style={{width:`${Math.max(2,item.amount_cents/maxCategory*100)}%`,background:item.color}}/></span></div>)}</div></section>
    </div>
    <div className="dashboard-grid">
      <section className="panel"><div className="section-heading"><div><span className="eyebrow">Onde pesa mais</span><h2>Principais custos</h2></div><Link to="/lancamentos">Ver lançamentos</Link></div><ol className="ranking-list">{data.top_costs.map(item=><li key={item.description}><div><strong>{item.description}</strong><small>{item.months} {item.months===1?'mês':'meses'} com ocorrência</small></div><span>{formatMoney(item.amount_cents)}</span></li>)}</ol></section>
      <section className="panel insight-panel"><div className="section-heading"><div><span className="eyebrow">Leitura econômica</span><h2>Oportunidades de economia</h2></div></div>{data.insights.map(item=><article className={`insight ${item.tone}`} key={item.title}><div><strong>{item.title}</strong><p>{item.text}</p></div>{item.amount_cents?<b>{formatMoney(item.amount_cents)}</b>:null}</article>)}<p className="method-note">As sugestões são indicativas e usam apenas os lançamentos registrados. O cenário não altera seus dados.</p></section>
    </div>
  </div>
}

function Kpi({label,value,detail,tone=''}:{label:string;value:string;detail:string;tone?:string}) { return <article className={`kpi ${tone}`}><span>{label}</span><strong>{value}</strong><small>{detail}</small></article> }

function ParticipantsPanel({participants}:{participants:DashboardData['participants']}){
  if(!participants.length)return null
  return <section className="panel participants-panel"><div className="section-heading"><div><span className="eyebrow">Participantes</span><h2>Quanto cada pessoa deve</h2></div></div>
    <div className="participants-grid">{participants.map(person=>{const owes=person.open_cents>0;return <article className={`participant-card ${owes?'owes':'clear'}`} key={person.person_id}>
      <header><h3>{person.name}</h3>{person.is_primary?<span className="primary-tag">fonte primária</span>:null}</header>
      <dl><div><dt>Parte nos meses lançados</dt><dd>{formatMoney(person.part_cents)}</dd></div><div><dt>Já pagou</dt><dd>{formatMoney(person.paid_cents)}</dd></div></dl>
      {person.is_primary?<div className="participant-total receive"><span>A receber dos outros</span><strong>{formatMoney(person.to_receive_cents??0)}</strong></div>:<div className={`participant-total ${owes?'debt':'ok'}`}><span>{owes?'Acumulado em aberto':'Tudo acertado'}</span><strong>{formatMoney(person.open_cents)}</strong></div>}
      {person.months.length?<details><summary>Ver mês a mês</summary><ul className="participant-months">{person.months.slice().reverse().map(item=><li key={item.period}><span>{formatMonthName(item.period)} <small>{item.period.slice(0,4)}</small></span><span className={item.settled?'settled':item.outstanding_cents>0?'pending':''}>{item.settled?'Pago':item.outstanding_cents>0?`Em aberto ${formatMoney(item.outstanding_cents)}`:'Sem pendência'}</span>{!person.is_primary?<b>{formatMoney(item.accumulated_open_cents)}</b>:null}</li>)}</ul></details>:null}
    </article>})}</div></section>
}
