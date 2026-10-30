import { Navigate, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { MonthPage } from './features/month/MonthPage'
import { HistoryPage } from './features/history/HistoryPage'
import { InvoicePage } from './features/invoice/InvoicePage'
import { SettingsPage } from './features/settings/SettingsPage'
import { DashboardPage } from './features/dashboard/DashboardPage'
import { AccountsPage } from './features/accounts/AccountsPage'
import { LedgerPage } from './features/ledger/LedgerPage'

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<DashboardPage />} />
        <Route path="painel" element={<DashboardPage />} />
        <Route path="mes/:period" element={<MonthPage />} />
        <Route path="contas" element={<AccountsPage />} />
        <Route path="lancamentos" element={<LedgerPage />} />
        <Route path="historico" element={<HistoryPage />} />
        <Route path="fatura" element={<InvoicePage />} />
        <Route path="configuracoes" element={<SettingsPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
