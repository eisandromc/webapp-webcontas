import type { SVGProps } from 'react'

const Icon = ({ children, ...props }: SVGProps<SVGSVGElement>) => (
  <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>{children}</svg>
)
export const HomeIcon = () => <Icon><path d="m3 11 9-8 9 8"/><path d="M5 10v10h14V10M9 20v-6h6v6"/></Icon>
export const HistoryIcon = () => <Icon><path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5M12 7v5l3 2"/></Icon>
export const UploadIcon = () => <Icon><path d="M12 16V4m0 0L7 9m5-5 5 5"/><path d="M4 17v3h16v-3"/></Icon>
export const SettingsIcon = () => <Icon><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-4V21a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3 14H2.8v-4H3a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1A1.7 1.7 0 0 0 9 4.6 1.7 1.7 0 0 0 10 3v-.2h4V3a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2v4H21a1.7 1.7 0 0 0-1.6 1Z"/></Icon>
export const PlusIcon = () => <Icon><path d="M12 5v14M5 12h14"/></Icon>
export const TrashIcon = () => <Icon><path d="M4 7h16M9 7V4h6v3m-9 0 1 13h10l1-13M10 11v5m4-5v5"/></Icon>
export const EditIcon = () => <Icon><path d="m4 16-1 5 5-1L19 9l-4-4L4 16Z"/><path d="m13 7 4 4"/></Icon>
export const CheckIcon = () => <Icon><path d="m5 12 4 4L19 6"/></Icon>
export const ChartIcon = () => <Icon><path d="M4 20V10m6 10V4m6 16v-7m4 7H2"/></Icon>
export const ListIcon = () => <Icon><path d="M9 6h11M9 12h11M9 18h11"/><path d="M4 6h.01M4 12h.01M4 18h.01"/></Icon>
export const CalendarIcon = () => <Icon><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 10h18"/></Icon>
export const AccountsIcon = () => <Icon><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 10h18M8 15h3M15 15h1"/></Icon>
export const PrintIcon = () => <Icon><path d="M7 9V3h10v6"/><rect x="3" y="9" width="18" height="8" rx="2"/><path d="M7 14h10v7H7z"/></Icon>
export const PinIcon = () => <Icon><path d="m15 4 5 5-3 1-3 3 .5 4.5-1.5 1.5-4-4-5 5M9 9l-1-1 1.5-1.5L14 7"/></Icon>
export const ChevronIcon = ({ flipped }: { flipped?: boolean }) => <Icon style={{ transform: flipped ? 'scaleX(-1)' : undefined }}><path d="m14 6-6 6 6 6M19 5v14"/></Icon>
