import { useEffect, useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, formatDate, formatPeriod, json } from '../../api'
import { Modal } from '../../components/Modal'
import { useDialogs } from '../../components/Dialogs'
import type { AccountMonth, MonthSuggestion } from '../../types'

const refreshKeys=['accounts','bootstrap','month','history','dashboard','ledger']
function useRefresh(){const client=useQueryClient();return()=>{for(const key of refreshKeys)client.invalidateQueries({queryKey:[key]})}}

/** Cadastro (sem `month`) ou edição (com `month`) de um mês em Contas. Monte só quando for abrir. */
export function MonthFormModal({month,initialPeriod,onClose,onSaved}:{month?:Pick<AccountMonth,'period'|'start_date'|'end_date'>;initialPeriod?:string;onClose:()=>void;onSaved?:(period:string)=>void}){
  const editing=!!month
  const refresh=useRefresh()
  const [period,setPeriod]=useState(month?.period??initialPeriod??'')
  const [start,setStart]=useState(month?.start_date??'')
  const [end,setEnd]=useState(month?.end_date??'')
  const [error,setError]=useState('')
  // Sem período informado, o servidor sugere o mês vigente (ou o próximo ainda não cadastrado).
  const suggestion=useQuery({queryKey:['month-suggestion',period],queryFn:()=>api<MonthSuggestion>(`/api/months/suggestion${period?`?period=${period}`:''}`),enabled:!period||/^\d{4}-\d{2}$/.test(period)})
  const hint=suggestion.data
  // No cadastro, trocar o mês reaplica a faixa padrão; na edição, as datas atuais são mantidas.
  useEffect(()=>{if(!hint)return;if(!period)setPeriod(hint.period);if(!editing){setStart(hint.start_date);setEnd(hint.end_date)}},[hint])
  const taken=!!hint&&hint.registered&&period!==month?.period
  const save=useMutation({
    mutationFn:()=>editing?api(`/api/months/${month!.period}`,{method:'PATCH',body:json({period,start_date:start,end_date:end})}):api('/api/months',{method:'POST',body:json({period,start_date:start,end_date:end})}),
    onSuccess:()=>{refresh();onSaved?.(period);onClose()},
    onError:err=>setError(err instanceof Error?err.message:'Não foi possível salvar.'),
  })
  const submit=(e:FormEvent)=>{e.preventDefault();setError('');if(!period){setError('Informe o mês de cobrança.');return}save.mutate()}
  return <Modal open title={editing?`Editar ${formatPeriod(month!.period)}`:'Cadastrar mês'} onClose={onClose}><form className="dialog-form" onSubmit={submit}>
    <label>Mês de cobrança<input type="month" required value={period} onChange={e=>setPeriod(e.target.value)}/>{period&&/^\d{4}-\d{2}$/.test(period)?<small>Contas de <strong>{formatPeriod(hint?.reference_period??period)}</strong></small>:null}</label>
    {taken?<div className="notice error" role="alert">{formatPeriod(period)} já está cadastrado. Escolha outro mês.</div>:null}
    <div className="range-pair"><label>Início do período financeiro<input type="date" required value={start} onChange={e=>setStart(e.target.value)}/></label><label>Fim do período financeiro<input type="date" required value={end} onChange={e=>setEnd(e.target.value)}/></label></div>
    {hint&&(hint.start_date!==start||hint.end_date!==end)?<button type="button" className="ghost-button small range-reset" onClick={()=>{setStart(hint.start_date);setEnd(hint.end_date)}}>Usar faixa padrão: {formatDate(hint.start_date)} a {formatDate(hint.end_date)}</button>:null}
    <ul className="rule-list">
      <li>O mês de cobrança se refere às contas do mês anterior.</li>
      <li>A faixa do período financeiro vem de Configurações, pode ser ajustada e tem no máximo 63 dias.</li>
      {editing?<li>Lançamentos, vales, descontos e pagamentos continuam no mês editado.</li>:<li>Divisão igual entre as pessoas ativas{hint?.people.length?`: ${hint.people.join(', ')}`:''}.</li>}
      <li>Cada mês só pode ser cadastrado uma vez. Meses fechados não podem ser editados; só meses abertos e sem registros podem ser excluídos.</li>
    </ul>
    {error?<div className="notice error" role="alert">{error}</div>:null}
    <div className="dialog-actions"><button type="button" className="ghost-button" onClick={onClose}>Cancelar</button><button className="primary-button" disabled={save.isPending||taken||!start||!end}>{save.isPending?'Salvando…':editing?'Salvar alterações':'Cadastrar mês'}</button></div>
  </form></Modal>
}

type DeletableMonth=Pick<AccountMonth,'period'|'closed'|'counts'>

/** Motivo que impede excluir o mês, ou null quando a exclusão é permitida. */
export function deleteBlockReason(month:DeletableMonth){
  if(month.closed)return 'Mês fechado não pode ser excluído'
  const {entries,adjustments,payments}=month.counts
  return entries+adjustments+payments>0?'Mês com registros não pode ser excluído':null
}

export function useDeleteMonth(){
  const dialogs=useDialogs();const refresh=useRefresh()
  return async(month:DeletableMonth)=>{
    if(deleteBlockReason(month)||!await dialogs.confirm({title:`Excluir ${formatPeriod(month.period)}`,message:'O mês não tem registros e será removido de Contas. Você pode cadastrá-lo de novo depois.',confirmLabel:'Excluir mês',danger:true}))return
    try{await api(`/api/months/${month.period}`,{method:'DELETE'});refresh()}
    catch(error){await dialogs.alert({title:'Não foi possível excluir',message:error instanceof Error?error.message:'Tente novamente.'})}
  }
}
