import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, formatDateTime } from '../../api'
import { useDialogs } from '../../components/Dialogs'

type AuditRow = { id: number; at: string; action: string; status: string; detail?: string | null; client?: string | null }
type BackupFile = { name: string; size_bytes: number; created_at: string }

const kb = (bytes: number) => `${Math.max(1, Math.round(bytes / 1024))} KB`

export function DatabasePanel() {
  const client = useQueryClient()
  const dialogs = useDialogs()
  const local = ['localhost', '127.0.0.1'].includes(location.hostname)
  const [tab, setTab] = useState<'backup' | 'import' | 'reset'>('backup')
  const [file, setFile] = useState<File | null>(null)
  const [confirmReset, setConfirmReset] = useState('')
  const [message, setMessage] = useState<{ tone: 'success' | 'error'; text: string } | null>(null)
  const audit = useQuery({ queryKey: ['audit-log'], queryFn: () => api<AuditRow[]>('/api/audit-log?limit=30') })
  const backups = useQuery({ queryKey: ['backups'], queryFn: () => api<BackupFile[]>('/api/backups') })
  const refreshAll = () => client.invalidateQueries()

  const backup = useMutation({
    mutationFn: async () => {
      const response = await fetch('/api/backup/download')
      if (!response.ok) throw new Error('Não foi possível criar o backup.')
      const blob = await response.blob()
      const name = /filename="?([^";]+)"?/.exec(response.headers.get('Content-Disposition') ?? '')?.[1] ?? 'contas-backup.db'
      const link = document.createElement('a')
      link.href = URL.createObjectURL(blob)
      link.download = name
      link.click()
      URL.revokeObjectURL(link.href)
      return name
    },
    onSuccess: name => { setMessage({ tone: 'success', text: `Backup ${name} baixado e guardado no servidor.` }); refreshAll() },
    onError: error => setMessage({ tone: 'error', text: error.message }),
  })
  const importDb = useMutation({
    mutationFn: () => {
      if (!file) throw new Error('Escolha o arquivo de backup (.db).')
      const body = new FormData()
      body.append('file', file)
      return api<{ safety_backup: string }>('/api/backup/import', { method: 'POST', body })
    },
    onSuccess: result => { setFile(null); setMessage({ tone: 'success', text: `Banco importado. O banco anterior foi guardado em ${result.safety_backup}.` }); refreshAll() },
    onError: error => setMessage({ tone: 'error', text: error.message }),
  })
  const reset = useMutation({
    mutationFn: () => api<{ safety_backup: string }>('/api/backup/reset', { method: 'POST', body: JSON.stringify({ confirm: confirmReset }) }),
    onSuccess: result => { setConfirmReset(''); setMessage({ tone: 'success', text: `Banco resetado. Uma cópia anterior foi guardada em ${result.safety_backup}.` }); refreshAll() },
    onError: error => setMessage({ tone: 'error', text: error.message }),
  })

  return <section className="panel database-panel"><div className="section-heading"><div><span className="eyebrow">Manutenção</span><h2>Banco de dados</h2></div></div>
    <p className="helper">Todas as operações abaixo ficam registradas em uma base separada (<code>auditoria.db</code>), que não é afetada por importação nem reset.</p>
    <div className="db-tabs" role="tablist" aria-label="Operações do banco">{([['backup', 'Fazer backup'], ['import', 'Importar banco'], ['reset', 'Resetar banco']] as const).map(([value, label]) => <button type="button" role="tab" key={value} aria-selected={tab === value} className={`db-tab ${tab === value ? 'active' : ''} ${value === 'reset' ? 'danger' : ''}`} onClick={() => setTab(value)}>{label}</button>)}</div>
    <div className="db-actions">
      {tab === 'backup' ? <div className="db-action"><h3>Fazer backup</h3><p className="helper">Baixa uma cópia completa do banco e guarda outra na pasta <code>data/backups</code> do servidor.</p><button className="primary-button" disabled={backup.isPending} onClick={() => backup.mutate()}>{backup.isPending ? 'Gerando…' : 'Fazer backup agora'}</button></div> : null}
      {tab === 'import' ? <div className="db-action"><h3>Importar banco</h3><p className="helper">Substitui todos os dados pelo conteúdo do backup. O banco atual é guardado antes.</p>
        {local ? <><label className="file-drop compact"><input type="file" accept=".db,.sqlite,.sqlite3" onChange={e => setFile(e.target.files?.[0] ?? null)} /><span>{file?.name ?? 'Escolher arquivo .db'}</span></label><button className="secondary-button" disabled={!file || importDb.isPending} onClick={async () => { if (await dialogs.confirm({ title: 'Importar banco', message: 'Importar este banco vai substituir TODOS os dados atuais. Continuar?', confirmLabel: 'Importar e substituir', danger: true })) importDb.mutate() }}>{importDb.isPending ? 'Importando…' : 'Importar banco'}</button></> : <div className="notice">Disponível apenas no computador servidor (<strong>localhost:8000</strong>).</div>}</div> : null}
      {tab === 'reset' ? <div className="db-action danger-zone"><h3>Resetar banco</h3><p className="helper">Apaga lançamentos, vales, descontos, pagamentos, faturas, importações e acertos. Mantém pessoas, categorias e configurações. Uma cópia é guardada antes.</p>
        {local ? <><label>Digite <strong>ZERAR</strong> para confirmar<input value={confirmReset} onChange={e => setConfirmReset(e.target.value)} autoComplete="off" /></label><button className="danger-button" disabled={confirmReset.trim().toUpperCase() !== 'ZERAR' || reset.isPending} onClick={() => reset.mutate()}>{reset.isPending ? 'Resetando…' : 'Resetar banco'}</button></> : <div className="notice">Disponível apenas no computador servidor (<strong>localhost:8000</strong>).</div>}</div> : null}
    </div>
    {message ? <div className={`notice ${message.tone}`} role={message.tone === 'error' ? 'alert' : 'status'}>{message.text}</div> : null}
    <details className="db-log" open><summary>Registro de operações ({audit.data?.length ?? 0})</summary>
      {audit.data?.length ? <div className="responsive-table"><table><thead><tr><th>Quando</th><th>Operação</th><th>Resultado</th><th>Detalhe</th><th>Origem</th></tr></thead><tbody>{audit.data.map(row => <tr key={row.id}><td data-label="Quando">{formatDateTime(row.at)}</td><td data-label="Operação"><strong>{row.action}</strong></td><td data-label="Resultado"><span className={`pay-badge ${row.status === 'ok' ? 'paid' : 'awaiting'}`}>{row.status === 'ok' ? 'Sucesso' : 'Erro'}</span></td><td data-label="Detalhe">{row.detail}</td><td data-label="Origem">{row.client}</td></tr>)}</tbody></table></div> : <p className="helper">Nenhuma operação registrada ainda.</p>}
    </details>
    {backups.data?.length ? <details className="db-log"><summary>Backups guardados no servidor ({backups.data.length})</summary><ul className="file-list">{backups.data.map(item => <li key={item.name}>{item.name} · {kb(item.size_bytes)} · {formatDateTime(item.created_at)}</li>)}</ul></details> : null}
  </section>
}
