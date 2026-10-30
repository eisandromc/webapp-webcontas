import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api, formatDate, formatDateTime, formatMoney, formatPeriod, json } from '../../api'
import { statusLabels, type AccountMonth } from '../../types'
import { EmptyState, ErrorState, Loading } from '../../components/Feedback'
import { EditIcon, PlusIcon, PrintIcon, TrashIcon } from '../../components/Icons'
import { MonthFormModal, deleteBlockReason, useDeleteMonth } from './MonthForms'

export function StatusBadge({status,children}:{status:'processing'|'awaiting'|'paid'|'pending';children?:React.ReactNode}){
  const tone=status==='paid'?'paid':status==='processing'?'processing':'awaiting'
  const label=status==='pending'?'Aguardando pagamento':statusLabels[status as keyof typeof statusLabels]
  return <span className={`pay-badge ${tone}`}>{children??label}</span>
}

export function AccountsPage(){
  const client=useQueryClient()
  const [creating,setCreating]=useState(false);const [editing,setEditing]=useState<AccountMonth|null>(null);const deleteMonth=useDeleteMonth()
  const query=useQuery({queryKey:['accounts'],queryFn:()=>api<{months:AccountMonth[]}>('/api/accounts')})
  const settle=useMutation({
    mutationFn:({period,personId,received}:{period:string;personId:number;received:boolean})=>api(`/api/months/${period}/settlements/${personId}`,{method:'PUT',body:json({received})}),
    onSuccess:()=>{for(const key of ['accounts','month','history'])client.invalidateQueries({queryKey:[key]})},
  })
  const reopen=useMutation({mutationFn:(period:string)=>api(`/api/months/${period}/closed`,{method:'PUT',body:json({closed:false})}),onSuccess:()=>{for(const key of ['accounts','month','history'])client.invalidateQueries({queryKey:[key]})}})
  if(query.isLoading)return <Loading/>
  if(query.error||!query.data)return <ErrorState error={query.error}/>
  const months=query.data.months
  return <div className="page"><section className="page-title"><div><span className="eyebrow">Acompanhamento</span><h1>Contas</h1><p>Cada mês mostra o custo e quem já acertou. A fonte primária já consta como paga; os demais aguardam a confirmação de recebimento.</p></div><div className="page-actions"><button className="primary-button" onClick={()=>setCreating(true)}><PlusIcon/>Cadastrar mês</button></div></section>
    {months.length===0?<section className="panel"><EmptyState title="Nenhum mês cadastrado" text="Use Cadastrar mês para abrir o mês vigente das contas."/></section>:<div className="account-list">{months.map(month=>{const primary=month.people.find(p=>p.is_primary);return <article className="account-card" key={month.period}>
      <header className="account-head"><div><Link to={`/mes/${month.period}`}><h2>{formatPeriod(month.period)}</h2></Link><small>Contas de {formatPeriod(month.reference_period)}</small></div><div className="account-total"><span>Total dos custos</span><strong>{formatMoney(month.cost_cents)}</strong></div><StatusBadge status={month.status}/></header>
      <ul className="account-people">{month.people.map(person=><li key={person.person_id}>
        <div className="who"><strong>{person.name}</strong>{person.is_primary?<span className="primary-tag">fonte primária</span>:null}</div>
        <span className="part">{formatMoney(person.part_cents)}</span>
        <StatusBadge status={person.status}/>
        <div className="act">{!person.is_primary&&primary?(person.status==='pending'?<button className="secondary-button small" disabled={settle.isPending} onClick={()=>settle.mutate({period:month.period,personId:person.person_id,received:true})}>{primary.name} recebeu</button>:<button className="ghost-button small" disabled={settle.isPending} title={person.received_at?`Recebido em ${formatDateTime(person.received_at)}`:undefined} onClick={()=>settle.mutate({period:month.period,personId:person.person_id,received:false})}>Desfazer</button>):null}</div>
      </li>)}</ul>
      {!primary?<p className="warning-text account-warning">Defina a fonte primária em Configurações.</p>:null}
      <footer className="account-foot"><small>Período financeiro: {formatDate(month.start_date)} a {formatDate(month.end_date)}{month.closed?' · Mês fechado':''}</small><div className="account-foot-actions">{month.closed?<button className="secondary-button small" disabled={reopen.isPending} onClick={()=>reopen.mutate(month.period)}>Reabrir mês</button>:null}<Link className="ghost-button small" to={`/mes/${month.period}?imprimir=1`}><PrintIcon/>Imprimir extrato</Link><button className="ghost-button small" disabled={month.closed} title={month.closed?'Reabra o mês para editar':undefined} onClick={()=>setEditing(month)}><EditIcon/>Editar</button><button className="ghost-button small danger-text" disabled={!!deleteBlockReason(month)} title={deleteBlockReason(month)??undefined} onClick={()=>deleteMonth(month)}><TrashIcon/>Excluir</button></div></footer>
    </article>})}</div>}
    {creating?<MonthFormModal onClose={()=>setCreating(false)}/>:null}
    {editing?<MonthFormModal month={editing} onClose={()=>setEditing(null)}/>:null}
    {(settle.error||reopen.error)?<div className="toast error" role="alert">{(settle.error||reopen.error)?.message}</div>:null}
  </div>
}
