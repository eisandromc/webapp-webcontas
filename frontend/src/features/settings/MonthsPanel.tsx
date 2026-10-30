import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api, formatDate, formatPeriod, json } from '../../api'
import type { AccountMonth } from '../../types'
import { EditIcon, PlusIcon, TrashIcon } from '../../components/Icons'
import { EmptyState, ErrorState, Loading } from '../../components/Feedback'
import { MonthFormModal, deleteBlockReason, useDeleteMonth } from '../accounts/MonthForms'

/** Cadastro de meses: listar, cadastrar, editar, fechar/reabrir e excluir. */
export function MonthsPanel(){
  const client=useQueryClient()
  const query=useQuery({queryKey:['accounts'],queryFn:()=>api<{months:AccountMonth[]}>('/api/accounts')})
  const [creating,setCreating]=useState(false);const [editing,setEditing]=useState<AccountMonth|null>(null)
  const deleteMonth=useDeleteMonth()
  const toggleClosed=useMutation({mutationFn:(month:AccountMonth)=>api(`/api/months/${month.period}/closed`,{method:'PUT',body:json({closed:!month.closed})}),onSuccess:()=>{for(const key of ['accounts','month','history'])client.invalidateQueries({queryKey:[key]})}})
  return <section className="panel months-panel">
    <div className="section-heading"><div><span className="eyebrow">Cadastro</span><h2>Meses</h2></div><button className="primary-button" onClick={()=>setCreating(true)}><PlusIcon/>Cadastrar mês</button></div>
    <p className="helper">Meses fechados não podem ser editados. Só é possível excluir meses abertos e sem registros (lançamentos, vales, descontos ou pagamentos).</p>
    {query.isLoading?<Loading/>:query.error||!query.data?<ErrorState error={query.error}/>:query.data.months.length===0?<EmptyState title="Nenhum mês cadastrado" text="Use Cadastrar mês para abrir o mês vigente das contas."/>:
    <div className="responsive-table"><table className="months-table">
      <thead><tr><th>Mês de cobrança</th><th>Contas de</th><th>Período financeiro</th><th className="number">Registros</th><th>Situação</th><th><span className="sr-only">Ações</span></th></tr></thead>
      <tbody>{query.data.months.map(month=>{const {entries,adjustments,payments}=month.counts;const blocked=deleteBlockReason(month);return <tr key={month.period}>
        <td data-label="Mês de cobrança"><Link to={`/mes/${month.period}`}><strong>{formatPeriod(month.period)}</strong></Link></td>
        <td data-label="Contas de">{formatPeriod(month.reference_period)}</td>
        <td data-label="Período financeiro">{formatDate(month.start_date)} a {formatDate(month.end_date)}</td>
        <td data-label="Registros" className="number" title={`${entries} lançamentos · ${adjustments} vales e descontos · ${payments} pagamentos`}>{entries+adjustments+payments}</td>
        <td data-label="Situação"><span className={`month-state ${month.closed?'closed':'open'}`}>{month.closed?'Fechado':'Aberto'}</span></td>
        <td className="actions">
          <button className="ghost-button small" disabled={toggleClosed.isPending} onClick={()=>toggleClosed.mutate(month)}>{month.closed?'Reabrir':'Fechar'}</button>
          <button className="icon-button" disabled={month.closed} title={month.closed?'Mês fechado não pode ser editado':'Editar mês'} aria-label={`Editar ${formatPeriod(month.period)}`} onClick={()=>setEditing(month)}><EditIcon/></button>
          <button className="icon-button danger" disabled={!!blocked} title={blocked??'Excluir mês'} aria-label={`Excluir ${formatPeriod(month.period)}`} onClick={()=>deleteMonth(month)}><TrashIcon/></button>
        </td>
      </tr>})}</tbody>
    </table></div>}
    {creating?<MonthFormModal onClose={()=>setCreating(false)}/>:null}
    {editing?<MonthFormModal month={editing} onClose={()=>setEditing(null)}/>:null}
    {toggleClosed.error?<div className="toast error" role="alert">{toggleClosed.error.message}</div>:null}
  </section>
}
