export type Person = { id: number; name: string; active: boolean; position: number; is_primary: boolean }
export type Category = { slug: string; name: string; color: string; entry_count?: number }
export type Bootstrap = { periods: string[]; current_period: string; people: Person[]; categories: Category[] }
export type PersonMonth = {
  person_id: number
  name: string
  percentage_bp: number
  position: number
  part_cents: number
  discount_cents: number
  extra_cents: number
  paid_cents: number
  balance_cents: number
  accumulated_cents: number
  is_primary: boolean
  settlement_status: 'paid' | 'pending'
  received_at?: string | null
}
export type Entry = {
  id: number
  date?: string | null
  description: string
  amount_cents: number
  category_slug: string
  origin: string
  paid_by_person_id?: number | null
  paid_by_name?: string | null
  installment_current?: number | null
  installment_total?: number | null
}
export type Adjustment = { id: number; kind: 'vale' | 'desconto'; description: string; amount_cents: number; distribution: 'proportional' | 'equal' | 'person'; person_id?: number | null; person_name?: string | null }
export type Payment = { id: number; person_id: number; person_name: string; date?: string | null; amount_cents: number; note?: string | null }
export type Summary = { expenses_cents: number; vales_cents: number; cost_cents: number; discounts_cents: number; net_cents: number }
export type InvoiceImport = { id: number; filename: string; item_count: number; amount_cents: number }
export type MonthStatus = 'processing' | 'awaiting' | 'paid'
export type MonthData = { period: string; reference_period: string; registered: boolean; closed: boolean; status: MonthStatus; primary_person_id?: number | null; start_date: string; end_date: string; summary: Summary; people: PersonMonth[]; entries: Entry[]; adjustments: Adjustment[]; payments: Payment[]; invoice_imports: InvoiceImport[] }
export type HistoryItem = Summary & { period: string; start_date?: string; end_date?: string; people: PersonMonth[] }
export type InvoiceItem = {
  id: number; date?: string | null; description: string; amount_cents: number; category_slug: string
  included: boolean; suggested_exclude: boolean; confidence: number; imported: boolean; in_period: boolean
  installment_current?: number | null; installment_total?: number | null
}
export type InvoiceDraft = {
  id: number; filename: string; total_cents?: number | null; parsed_sum_cents: number; selected_sum_cents: number
  difference_cents?: number | null; imported_at?: string | null; outside_range_count: number; range_start?: string | null; range_end?: string | null; items: InvoiceItem[]
}
export type LedgerItem = { id:number; kind:'entry'|'vale'|'desconto'|'payment'; period:string; date?:string|null; description:string; amount_cents:number; category_slug?:string|null; origin:string; person_name?:string|null }
export type Participant = {
  person_id:number;name:string;is_primary:boolean;part_cents:number;paid_cents:number;open_cents:number;to_receive_cents?:number
  months:{period:string;part_cents:number;paid_cents:number;outstanding_cents:number;accumulated_open_cents:number;settled:boolean}[]
}
export type DashboardData = {
  participants:Participant[]
  months:{period:string;expenses_cents:number;net_cents:number;discounts_cents:number}[]
  total_expenses_cents:number;average_monthly_cents:number;latest_expenses_cents:number;trend_percent?:number|null
  categories:{slug:string;name:string;color:string;amount_cents:number}[]
  top_costs:{description:string;amount_cents:number;months:number}[]
  recurring:{description:string;amount_cents:number;months:number}[]
  insights:{title:string;text:string;tone:string;amount_cents?:number}[]
}
export type MonthSuggestion = { period: string; reference_period: string; start_date: string; end_date: string; registered: boolean; people: string[] }
export type AccountMonth = {
  period: string; reference_period: string; cost_cents: number; net_cents: number; closed: boolean; status: MonthStatus; primary_person_id?: number | null
  start_date: string; end_date: string; counts: { entries: number; adjustments: number; payments: number }
  people: { person_id: number; name: string; is_primary: boolean; status: 'paid' | 'pending'; received_at?: string | null; part_cents: number }[]
}
export const statusLabels: Record<MonthStatus, string> = { processing: 'Em processamento', awaiting: 'Aguardando pagamento', paid: 'Pago' }
