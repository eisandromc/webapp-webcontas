import { createPortal } from 'react-dom'
import { formatDate, formatMoney, formatPeriod } from '../../api'
import { statusLabels, type Adjustment, type Category, type Entry, type MonthData, type PersonMonth } from '../../types'

const byDate=(x:{date?:string|null;id:number},y:{date?:string|null;id:number})=>(x.date??'9999').localeCompare(y.date??'9999')||x.id-y.id
const sum=(items:{amount_cents:number}[])=>items.reduce((total,item)=>total+item.amount_cents,0)
const minus=(cents:number)=>formatMoney(cents?-cents:0)
const today=()=>new Intl.DateTimeFormat('pt-BR',{dateStyle:'short',timeStyle:'short'}).format(new Date())

function adjustmentRule(item:Adjustment){
  if(item.kind==='vale')return 'Soma ao total a dividir'
  if(item.distribution==='person')return `Somente de ${item.person_name??'uma pessoa'}`
  return item.distribution==='equal'?'Igual para todos':'Proporcional'
}

/** Extrato do mês no formato de fatura de cartão. Fica oculto na tela e aparece só na impressão. */
export function MonthStatement({data,categories}:{data:MonthData;categories:Category[]}){
  const entriesTotal=sum(data.entries)
  const vales=data.adjustments.filter(item=>item.kind==='vale')
  const discounts=data.adjustments.filter(item=>item.kind==='desconto')
  const sharedDiscounts=entriesTotal-data.summary.expenses_cents
  const paymentsTotal=sum(data.payments)
  const toPay=data.people.reduce((total,person)=>total+Math.max(person.balance_cents,0),0)
  const known=new Set(categories.map(c=>c.slug))
  const groups=[...categories,{slug:'__outros',name:'Outros',color:'#888'}].map(category=>({category,items:data.entries.filter(item=>category.slug==='__outros'?!known.has(item.category_slug):item.category_slug===category.slug).sort(byDate)})).filter(group=>group.items.length)
  return createPortal(<div className="print-statement">
    <header className="st-header">
      <div className="st-brand"><img src="/logo.svg" alt="" width="40" height="40"/><div><strong>Divisão de Contas</strong><small>Extrato mensal · contas da casa</small></div></div>
      <div className="st-doc"><span>Fatura de</span><strong>{formatPeriod(data.period)}</strong><small>Emitida em {today()}</small></div>
    </header>

    <section className="st-summary">
      <div className="st-total"><span>Total a dividir</span><strong>{formatMoney(data.summary.net_cents)}</strong><small>{statusLabels[data.status]}</small></div>
      <dl className="st-facts">
        <div><dt>Contas de</dt><dd>{formatPeriod(data.reference_period)}</dd></div>
        <div><dt>Período financeiro</dt><dd>{formatDate(data.start_date)} a {formatDate(data.end_date)}</dd></div>
        <div><dt>Pessoas na divisão</dt><dd>{data.people.length}</dd></div>
        <div><dt>Saldo a receber no mês</dt><dd>{formatMoney(toPay)}</dd></div>
      </dl>
      <dl className="st-calc">
        <div><dt>Lançamentos ({data.entries.length})</dt><dd>{formatMoney(entriesTotal)}</dd></div>
        {sharedDiscounts?<div><dt>(−) Descontos gerais</dt><dd>{minus(sharedDiscounts)}</dd></div>:null}
        <div><dt>(+) Vales</dt><dd>{formatMoney(data.summary.vales_cents)}</dd></div>
        <div className="st-calc-total"><dt>(=) Total a dividir</dt><dd>{formatMoney(data.summary.net_cents)}</dd></div>
      </dl>
    </section>

    <section className="st-section">
      <h2><span>1</span>Lançamentos do mês</h2>
      {groups.length===0?<p className="st-empty">Nenhum lançamento neste mês.</p>:<table className="st-table">
        <thead><tr><th className="st-date">Data</th><th>Descrição</th><th className="st-mid">Parcela</th><th className="st-num">Valor</th></tr></thead>
        {groups.map(({category,items})=><tbody key={category.slug}>
          <tr className="st-group"><td colSpan={3}><i style={{background:category.color}}/>{category.name}</td><td className="st-num">{formatMoney(sum(items))}</td></tr>
          {items.map((item:Entry)=><tr key={item.id}><td className="st-date">{formatDate(item.date)}</td><td>{item.description}{item.paid_by_name&&item.paid_by_person_id!==data.primary_person_id?<small>Pago por {item.paid_by_name}</small>:null}</td><td className="st-mid">{item.installment_total?`${String(item.installment_current).padStart(2,'0')}/${String(item.installment_total).padStart(2,'0')}`:''}</td><td className="st-num">{formatMoney(item.amount_cents)}</td></tr>)}
        </tbody>)}
        <tfoot><tr><td colSpan={3}>Total dos lançamentos</td><td className="st-num">{formatMoney(entriesTotal)}</td></tr></tfoot>
      </table>}
    </section>

    <section className="st-section">
      <h2><span>2</span>Vales e descontos</h2>
      {data.adjustments.length===0?<p className="st-empty">Nenhum vale ou desconto neste mês.</p>:<table className="st-table">
        <thead><tr><th className="st-mid">Tipo</th><th>Descrição</th><th>Aplicação</th><th className="st-num">Valor</th></tr></thead>
        <tbody>{[...vales,...discounts].map(item=><tr key={item.id}><td className="st-mid"><span className={`st-kind ${item.kind}`}>{item.kind==='vale'?'Vale':'Desconto'}</span></td><td>{item.description}</td><td>{adjustmentRule(item)}</td><td className="st-num">{item.kind==='vale'?formatMoney(item.amount_cents):minus(item.amount_cents)}</td></tr>)}</tbody>
        <tfoot>
          <tr><td colSpan={3}>Total de vales</td><td className="st-num">{formatMoney(sum(vales))}</td></tr>
          <tr><td colSpan={3}>Total de descontos</td><td className="st-num">{minus(sum(discounts))}</td></tr>
        </tfoot>
      </table>}
    </section>

    <section className="st-section">
      <h2><span>3</span>Pagamentos</h2>
      {data.payments.length===0?<p className="st-empty">Nenhum pagamento registrado neste mês.</p>:<table className="st-table">
        <thead><tr><th className="st-date">Data</th><th>Pessoa</th><th>Observação</th><th className="st-num">Valor</th></tr></thead>
        <tbody>{[...data.payments].sort(byDate).map(item=><tr key={item.id}><td className="st-date">{formatDate(item.date)}</td><td>{item.person_name}</td><td>{item.note||'—'}</td><td className="st-num">{minus(item.amount_cents)}</td></tr>)}</tbody>
        <tfoot><tr><td colSpan={3}>Total pago</td><td className="st-num">{minus(paymentsTotal)}</td></tr></tfoot>
      </table>}
    </section>

    <section className="st-section st-closing">
      <h2><span>4</span>Fechamento</h2>
      <div className="st-people">{data.people.map(person=><PersonSlip key={person.person_id} person={person} primaryName={data.people.find(p=>p.is_primary)?.name}/>)}</div>
    </section>

    <footer className="st-footer">Divisão de Contas · Fatura de {formatPeriod(data.period)} · Valores em reais (R$). Valores negativos abatem o saldo.</footer>
  </div>,document.body)
}

function PersonSlip({person,primaryName}:{person:PersonMonth;primaryName?:string}){
  const monthTotal=person.part_cents+person.extra_cents-person.discount_cents
  const due=Math.max(person.balance_cents,0)
  const previous=Math.max(person.accumulated_cents,0)-due
  return <article className={`st-slip ${person.is_primary?'primary':''}`}>
    <header><strong>{person.name}</strong><span>{person.is_primary?'Fonte primária':`${(person.percentage_bp/100).toFixed(2).replace('.',',')}%`}</span></header>
    <dl>
      <div><dt>Parte do total</dt><dd>{formatMoney(person.part_cents)}</dd></div>
      {person.extra_cents?<div><dt>(+) Custo extra</dt><dd>{formatMoney(person.extra_cents)}</dd></div>:null}
      {person.discount_cents?<div><dt>(−) Descontos</dt><dd>{minus(person.discount_cents)}</dd></div>:null}
      <div className="st-sub"><dt>(=) Total do mês</dt><dd>{formatMoney(monthTotal)}</dd></div>
      <div><dt>(−) {person.is_primary?'Pago como fonte primária':'Pagamentos'}</dt><dd>{minus(person.paid_cents)}</dd></div>
      {previous>0?<div><dt>(+) Saldo de meses anteriores</dt><dd>{formatMoney(previous)}</dd></div>:null}
    </dl>
    <footer><span>Valor a pagar</span><strong>{formatMoney(due+Math.max(previous,0))}</strong><small>{person.is_primary?'Recebe os acertos dos demais':due+Math.max(previous,0)>0?`Pagar a ${primaryName??'fonte primária'}`:'Quitado'}</small></footer>
  </article>
}
