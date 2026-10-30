const parseError = async (response: Response) => {
  try {
    const data = await response.json()
    return typeof data.detail === 'string' ? data.detail : 'Não foi possível concluir a operação.'
  } catch {
    return 'Não foi possível concluir a operação.'
  }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers)
  if (init?.body && !(init.body instanceof FormData)) headers.set('Content-Type', 'application/json')
  const response = await fetch(path, { ...init, headers })
  if (!response.ok) throw new Error(await parseError(response))
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export const json = (value: unknown) => JSON.stringify(value)

export function formatMoney(cents: number) {
  return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(cents / 100)
}

export function parseMoney(value: string) {
  const cleaned = value.replace(/[^\d.,-]/g, '')
  // Vírgula é o separador decimal; sem vírgula, "12.50" (um ponto e até 2 casas) também é decimal.
  const normalized = cleaned.includes(',')
    ? cleaned.replace(/\./g, '').replace(',', '.')
    : /^-?\d*\.\d{1,2}$/.test(cleaned) ? cleaned : cleaned.replace(/\./g, '')
  const result = Number(normalized)
  return normalized && Number.isFinite(result) ? Math.round(result * 100) : Number.NaN
}

export function formatDate(value?: string | null) {
  if (!value) return '—'
  const [year, month, day] = value.split('-').map(Number)
  return new Intl.DateTimeFormat('pt-BR', { timeZone: 'UTC' }).format(new Date(Date.UTC(year, month - 1, day)))
}

export function formatPeriod(period: string) {
  const [year, month] = period.split('-').map(Number)
  const text = new Intl.DateTimeFormat('pt-BR', { month: 'long', year: 'numeric', timeZone: 'UTC' }).format(new Date(Date.UTC(year, month - 1, 1)))
  return text.charAt(0).toUpperCase() + text.slice(1).toLowerCase()
}

export function formatMonthName(period: string) {
  return formatPeriod(period).split(' ')[0]
}

export function formatDateTime(value?: string | null) {
  if (!value) return ''
  return new Intl.DateTimeFormat('pt-BR', { dateStyle: 'short', timeStyle: 'short' }).format(new Date(value))
}
