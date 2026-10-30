export function Loading({ label = 'Carregando dados' }: { label?: string }) { return <div className="loading" role="status" aria-live="polite"><span></span>{label}…</div> }
export function ErrorState({ error }: { error: unknown }) { return <div className="notice error" role="alert"><strong>Algo não saiu como esperado</strong><p>{error instanceof Error ? error.message : 'Tente novamente.'}</p></div> }
export function EmptyState({ title, text }: { title: string; text: string }) { return <div className="empty"><span aria-hidden="true">○</span><h3>{title}</h3><p>{text}</p></div> }

