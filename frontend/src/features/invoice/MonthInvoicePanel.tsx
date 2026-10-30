import { useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api, formatDate, formatMoney, json } from '../../api'
import type { Bootstrap, InvoiceDraft, InvoiceImport, InvoiceItem, PersonMonth } from '../../types'
import { CheckIcon, UploadIcon } from '../../components/Icons'
import { useDialogs } from '../../components/Dialogs'

type PanelProps = { closed: boolean; period: string; startDate: string; endDate: string; imports: InvoiceImport[]; people: PersonMonth[]; primaryId?: number | null }
type Row = InvoiceItem & { draftId: number; filename: string }

export function MonthInvoicePanel({ closed, period, startDate, endDate, imports, people, primaryId }: PanelProps) {
  const client = useQueryClient()
  const dialogs = useDialogs()
  const [files, setFiles] = useState<File[]>([])
  const [drafts, setDrafts] = useState<InvoiceDraft[]>([])
  const [failures, setFailures] = useState<string[]>([])
  const [bulk, setBulk] = useState('')
  const [payerChoice, setPayerChoice] = useState<string | null>(null)
  const payer = payerChoice ?? String(primaryId ?? '')
  const status = useQuery({ queryKey: ['password-status'], queryFn: () => api<{ configured: boolean }>('/api/settings/pdf-password') })
  const bootstrap = useQuery({ queryKey: ['bootstrap'], queryFn: () => api<Bootstrap>('/api/bootstrap') })
  const categories = bootstrap.data?.categories ?? []
  const query = `?period=${period}`

  const analyze = useMutation({
    mutationFn: async () => {
      if (!files.length) throw new Error('Escolha ao menos um PDF.')
      const results: InvoiceDraft[] = []
      const errors: string[] = []
      for (const file of files) {
        try {
          const body = new FormData()
          body.append('file', file)
          results.push(await api<InvoiceDraft>(`/api/invoices/analyze${query}`, { method: 'POST', body }))
        } catch (error) {
          errors.push(`${file.name}: ${error instanceof Error ? error.message : 'falha ao analisar'}`)
        }
      }
      return { results, errors }
    },
    onSuccess: ({ results, errors }) => {
      setDrafts(current => {
        const merged = [...current]
        for (const draft of results) {
          const index = merged.findIndex(item => item.id === draft.id)
          if (index >= 0) merged[index] = draft
          else merged.push(draft)
        }
        return merged
      })
      setFailures(errors)
      if (results.length) setFiles([])
    },
  })

  const replaceDraft = (next: InvoiceDraft) => setDrafts(current => current.map(item => item.id === next.id ? next : item))
  const patch = useMutation({
    mutationFn: ({ draftId, id, body }: { draftId: number; id: number; body: any }) => api<InvoiceDraft>(`/api/invoice-drafts/${draftId}/items/${id}${query}`, { method: 'PATCH', body: json(body) }),
    onSuccess: replaceDraft,
  })

  // Lista única de todas as faturas: só itens do período, ordenados pela data.
  const rows: Row[] = drafts
    .flatMap(draft => draft.items.filter(item => item.in_period).map(item => ({ ...item, draftId: draft.id, filename: draft.filename })))
    .sort((a, b) => (a.date ?? '9999').localeCompare(b.date ?? '9999') || a.draftId - b.draftId || a.id - b.id)
  const regular = rows.filter(row => !row.installment_total)
  const parcels = rows.filter(row => row.installment_total)
  const checked = (row: Row) => row.imported || row.included
  const pending = rows.filter(row => !row.imported && row.included)
  const alreadySaved = rows.filter(row => row.imported).length
  const pendingTotal = pending.reduce((sum, row) => sum + row.amount_cents, 0)

  const refreshDraft = async (draftId: number) => replaceDraft(await api<InvoiceDraft>(`/api/invoice-drafts/${draftId}${query}`))
  const setMany = async (targets: Row[], body: any) => {
    for (const row of targets) await api(`/api/invoice-drafts/${row.draftId}/items/${row.id}${query}`, { method: 'PATCH', body: json(body) })
    for (const draftId of new Set(targets.map(row => row.draftId))) await refreshDraft(draftId)
  }
  const toggleAll = useMutation({ mutationFn: (value: boolean) => setMany(rows.filter(row => !row.imported && row.included !== value), { included: value }) })
  const applyBulk = useMutation({ mutationFn: () => setMany(pending, { category_slug: bulk }) })

  const importAll = useMutation({
    mutationFn: async () => {
      let inserted = 0
      for (const draft of drafts) {
        if (!draft.items.some(item => item.in_period && item.included && !item.imported)) continue
        const result = await api<{ inserted: number }>(`/api/invoice-drafts/${draft.id}/import`, { method: 'POST', body: json({ period, paid_by_person_id: payer ? Number(payer) : null }) })
        inserted += result.inserted
      }
      return { inserted }
    },
    onSuccess: result => {
      for (const key of ['month', 'dashboard', 'ledger', 'accounts', 'history']) client.invalidateQueries({ queryKey: [key] })
      void dialogs.alert({ title: 'Importação concluída', message: `${result.inserted} lançamentos importados. Itens repetidos ou já salvos não foram importados novamente.` })
      setDrafts([])
    },
  })

  const renderRow = (row: Row) => {
    const isChecked = checked(row)
    return <tr key={`${row.draftId}-${row.id}`} className={`${row.imported ? 'saved-row' : 'clickable-row'} ${isChecked ? 'selected-row' : ''}`}
      onClick={e => { if (row.imported || patch.isPending || (e.target as HTMLElement).closest('input, select, button, a')) return; patch.mutate({ draftId: row.draftId, id: row.id, body: { included: !row.included } }) }}>
      <td data-label="Incluir"><input type="checkbox" disabled={row.imported} checked={isChecked} onChange={e => patch.mutate({ draftId: row.draftId, id: row.id, body: { included: e.target.checked } })} aria-label={`Incluir ${row.description}`} /></td>
      <td data-label="Data">{formatDate(row.date)}</td>
      <td data-label="Descrição"><input className="name-cell" aria-label="Nome da conta" disabled={row.imported} defaultValue={row.description} onBlur={e => { const value = e.target.value.trim(); if (value && value !== row.description) patch.mutate({ draftId: row.draftId, id: row.id, body: { description: value } }) }} />
        {row.installment_total ? <small>Parcela {row.installment_current}/{row.installment_total}</small> : null}
        {row.imported ? <small className="saved-tag">Já importado — não será importado novamente</small> : row.suggested_exclude ? <small>Pagamento sugerido para exclusão</small> : null}
        {drafts.length > 1 ? <small className="file-origin">{row.filename}</small> : null}</td>
      <td data-label="Categoria"><select disabled={row.imported} value={row.category_slug} onChange={e => patch.mutate({ draftId: row.draftId, id: row.id, body: { category_slug: e.target.value } })}>{categories.map(c => <option key={c.slug} value={c.slug}>{c.name}</option>)}</select></td>
      <td data-label="Valor" className="number">{formatMoney(row.amount_cents)}</td></tr>
  }

  const busy = patch.isPending || toggleAll.isPending || applyBulk.isPending || importAll.isPending
  const error = analyze.error || patch.error || toggleAll.error || applyBulk.error || importAll.error
  return <section className="panel invoice-month" id="importar-fatura"><div className="section-heading"><div><span className="eyebrow">Faturas do mês</span><h2>Importar cartão</h2></div><span className="status-chip">{imports.length} {imports.length === 1 ? 'importada' : 'importadas'}</span></div>
    <p className="helper">Somente compras entre <strong>{formatDate(startDate)}</strong> e <strong>{formatDate(endDate)}</strong> entram neste mês; contas parceladas sempre entram. Envie várias faturas: os itens são reunidos em uma única lista, ordenados pela data. Itens já importados aparecem marcados e não são importados de novo.</p>
    {imports.length ? <ul className="invoice-slots">{imports.map(item => <li key={item.id}><CheckIcon /><div><strong>{item.filename}</strong><small>{item.item_count} itens</small></div><b>{formatMoney(item.amount_cents)}</b></li>)}</ul> : null}
    {closed ? <div className="notice">Mês fechado. Reabra o mês para importar faturas.</div> : !status.data?.configured ? <div className="notice">Configure a senha do PDF em <Link to="/configuracoes">Configurações</Link> antes de importar.</div> :
      <form className="invoice-upload-inline" onSubmit={(e: FormEvent) => { e.preventDefault(); analyze.mutate() }}>
        <label className="file-drop compact"><input type="file" accept="application/pdf" multiple onChange={e => setFiles(Array.from(e.target.files ?? []))} /><UploadIcon /><span>{files.length ? `${files.length} arquivo(s) selecionado(s)` : 'Escolher uma ou mais faturas (PDF)'}</span></label>
        <button className="primary-button" disabled={!files.length || analyze.isPending}>{analyze.isPending ? 'Analisando…' : 'Analisar faturas'}</button>
      </form>}
    {files.length ? <ul className="file-list">{files.map(file => <li key={file.name + file.size}>{file.name}</li>)}</ul> : null}
    {drafts.length ? <div className="invoice-draft">
      <header><div><span className="eyebrow">Revisão unificada</span><h3>{drafts.length} {drafts.length === 1 ? 'fatura' : 'faturas'} · {rows.length} itens no período</h3></div><button className="ghost-button" onClick={() => setDrafts([])}>Descartar tudo</button></header>
      <ul className="file-list">{drafts.map(draft => <li key={draft.id}>{draft.filename}</li>)}</ul>
      <div className="range-summary"><div><span>Marcados para importar</span><strong>{pending.length}</strong></div><div><span>Soma marcada</span><strong>{formatMoney(pendingTotal)}</strong></div><div><span>Já importados</span><strong>{alreadySaved}</strong></div></div>
      <div className="bulk-row"><label>Categoria em lote<select value={bulk} onChange={e => setBulk(e.target.value)}><option value="">Selecione</option>{categories.map(c => <option key={c.slug} value={c.slug}>{c.name}</option>)}</select></label><button className="secondary-button" disabled={!bulk || !pending.length || busy} onClick={() => applyBulk.mutate()}>Aplicar aos marcados</button></div>
      <div className="responsive-table invoice-review"><table><thead><tr><th><input type="checkbox" aria-label="Marcar todos" checked={rows.length > 0 && rows.every(checked)} onChange={e => toggleAll.mutate(e.target.checked)} /></th><th>Data</th><th>Nome da conta</th><th>Categoria</th><th className="number">Valor</th></tr></thead>
        <tbody>{regular.map(renderRow)}{parcels.length ? <tr className="group-divider"><td colSpan={5}>Contas parceladas</td></tr> : null}{parcels.map(renderRow)}</tbody></table></div>
      <div className="payer-row"><label>Para quem organizar os valores (usuário ativo)<select value={payer} onChange={e => setPayerChoice(e.target.value)}><option value="">Ninguém ainda</option>{people.map(p => <option key={p.person_id} value={p.person_id}>{p.name}</option>)}</select></label></div>
      <div className="review-actions"><p><strong>{pending.length}</strong> novos itens prontos para {period}{alreadySaved ? ` · ${alreadySaved} já salvos serão ignorados` : ''}</p><button className="primary-button" disabled={busy || !pending.length} onClick={() => importAll.mutate()}>{importAll.isPending ? 'Importando…' : 'Confirmar importação'}</button></div>
    </div> : null}
    {failures.length ? <div className="notice error" role="alert">{failures.map(text => <div key={text}>{text}</div>)}</div> : null}
    {error ? <div className="notice error" role="alert">{error.message}</div> : null}
  </section>
}
