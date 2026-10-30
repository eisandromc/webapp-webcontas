import { useEffect, useId, useRef, type ReactNode } from 'react'

export function Modal({ open, title, onClose, children }: { open: boolean; title: string; onClose: () => void; children: ReactNode }) {
  const ref = useRef<HTMLDialogElement>(null)
  const titleId = useId()
  useEffect(() => {
    const dialog = ref.current
    if (!dialog) return
    if (open && !dialog.open) dialog.showModal()
    if (!open && dialog.open) dialog.close()
  }, [open])
  return <dialog ref={ref} onCancel={onClose} onClose={onClose} aria-labelledby={titleId}><div className="dialog-head"><h2 id={titleId}>{title}</h2><button className="icon-button" onClick={onClose} aria-label="Fechar">×</button></div>{children}</dialog>
}
