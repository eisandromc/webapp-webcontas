import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from 'react'
import { Modal } from './Modal'

type DialogOptions = { title: string; message: ReactNode; confirmLabel?: string; cancelLabel?: string; danger?: boolean }
type Request = DialogOptions & { kind: 'alert' | 'confirm' }
type Dialogs = { confirm: (options: DialogOptions) => Promise<boolean>; alert: (options: DialogOptions) => Promise<void> }

const DialogContext = createContext<Dialogs | null>(null)

/** Substitui alert/confirm do navegador por modais do app. Use `await dialogs.confirm({...})`. */
export function DialogProvider({ children }: { children: ReactNode }) {
  const [request, setRequest] = useState<Request | null>(null)
  const resolver = useRef<((value: boolean) => void) | null>(null)
  const open = useCallback((next: Request) => new Promise<boolean>(resolve => {
    resolver.current?.(false)
    resolver.current = resolve
    setRequest(next)
  }), [])
  const finish = (value: boolean) => {
    resolver.current?.(value)
    resolver.current = null
    setRequest(null)
  }
  const api = useRef<Dialogs>({
    confirm: options => open({ ...options, kind: 'confirm' }),
    alert: options => open({ ...options, kind: 'alert' }).then(() => undefined),
  })
  return <DialogContext.Provider value={api.current}>
    {children}
    <Modal open={!!request} title={request?.title ?? ''} onClose={() => finish(false)}>
      {request ? <div className="dialog-form">
        <div className="dialog-message">{request.message}</div>
        <div className="dialog-actions">
          {request.kind === 'confirm' ? <button type="button" className="ghost-button" onClick={() => finish(false)}>{request.cancelLabel ?? 'Cancelar'}</button> : null}
          <button type="button" autoFocus className={request.danger ? 'danger-button' : 'primary-button'} onClick={() => finish(true)}>{request.confirmLabel ?? (request.kind === 'alert' ? 'OK' : 'Confirmar')}</button>
        </div>
      </div> : null}
    </Modal>
  </DialogContext.Provider>
}

export function useDialogs() {
  const dialogs = useContext(DialogContext)
  if (!dialogs) throw new Error('useDialogs precisa estar dentro de DialogProvider.')
  return dialogs
}
