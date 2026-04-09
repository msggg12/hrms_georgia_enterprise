import {
  Activity,
  AppWindow,
  BadgeCheck,
  BriefcaseBusiness,
  CalendarRange,
  ChevronLeft,
  CircleHelp,
  DollarSign,
  GitBranchPlus,
  HardDrive,
  LayoutDashboard,
  LogOut,
  MessagesSquare,
  Settings,
  Users
} from 'lucide-react'

import { ka } from '../i18n/ka'
import type { FeatureFlags } from '../types'
import type { TenantBranding } from '../tenantBranding'
import { classNames } from '../utils'
import { CompanyBadge } from './CompanyBadge'

const navigation = [
  { key: 'dashboard', label: ka.dashboard, icon: LayoutDashboard },
  { key: 'employees', label: ka.employees, icon: Users },
  { key: 'attendance', label: ka.attendance, icon: Activity, feature: 'attendance_enabled' },
  { key: 'leave', label: ka.leaveHub, icon: CalendarRange },
  { key: 'payroll', label: ka.payroll, icon: DollarSign, feature: 'payroll_enabled' },
  { key: 'ats', label: ka.ats, icon: BriefcaseBusiness, feature: 'ats_enabled' },
  { key: 'assets', label: ka.assets, icon: HardDrive, feature: 'assets_enabled' },
  { key: 'org_chart', label: 'ორგსტრუქტურა', icon: GitBranchPlus, feature: 'org_chart_enabled' },
  { key: 'okrs', label: ka.okrs, icon: BadgeCheck, feature: 'performance_enabled' },
  { key: 'team_chat', label: ka.teamChat, icon: MessagesSquare, feature: 'chat_enabled' },
  { key: 'settings', label: ka.settings, icon: Settings }
] as const

type SidebarProps = {
  collapsed: boolean
  activeKey: string
  branding: TenantBranding
  featureFlags: FeatureFlags
  allowedSections: string[]
  onSelect: (key: string) => void
  onToggle: () => void
  onLogout: () => void
  mobileOpen?: boolean
  onCloseMobile?: () => void
}

function StaticUserMenu(props: { collapsed: boolean; activeKey: string; onSelect: (key: string) => void }) {
  const rows = [
    { key: 'apps', label: 'Apps & Integration', icon: AppWindow },
    { key: 'settings', label: ka.settings, icon: Settings },
    { key: 'help', label: 'Help & Support', icon: CircleHelp }
  ]

  return (
    <div className="space-y-1">
      {rows.map((row) => {
        const Icon = row.icon
        const active = row.key === 'settings' && props.activeKey === 'settings'
        return (
          <button
            key={row.key}
            type="button"
            onClick={() => {
              if (row.key === 'settings') {
                props.onSelect('settings')
              }
            }}
            className={classNames(
              'flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition',
              active ? 'bg-slate-800 text-slate-50' : 'text-slate-500 hover:bg-slate-800/80 hover:text-slate-100'
            )}
          >
            <Icon className="h-[18px] w-[18px] shrink-0" />
            {!props.collapsed ? <span className="truncate">{row.label}</span> : null}
          </button>
        )
      })}
    </div>
  )
}

export function Sidebar(props: SidebarProps) {
  const items = navigation.filter((item) => props.allowedSections.includes(item.key) && (!item.feature || props.featureFlags[item.feature]))

  return (
    <aside
      className={classNames(
        'shell-dark shrink-0 flex-col border-r border-slate-700/60 bg-slate-900',
        props.collapsed ? 'w-[92px]' : 'w-[248px]',
        'max-lg:fixed max-lg:inset-y-0 max-lg:left-0 max-lg:z-50 max-lg:shadow-2xl max-lg:transition-transform',
        props.mobileOpen ? 'flex max-lg:translate-x-0' : 'hidden max-lg:-translate-x-full',
        'lg:flex lg:relative lg:translate-x-0'
      )}
    >
      <div className="flex min-h-[88px] items-center gap-2 border-b border-slate-700/60 px-4 py-4">
        <div className="min-w-0 flex-1">
          {!props.collapsed ? <CompanyBadge branding={props.branding} /> : <CompanyBadge branding={props.branding} compact />}
        </div>
        <button
          type="button"
          onClick={props.onToggle}
          className="shrink-0 rounded-xl border border-slate-600/80 bg-slate-800/80 p-2.5 text-slate-300 transition hover:bg-slate-800 hover:text-white"
        >
          <ChevronLeft className={classNames('h-4 w-4 transition', props.collapsed && 'rotate-180')} />
        </button>
      </div>

      <div className="flex-1 overflow-auto px-3 py-4">
        {!props.collapsed ? <div className="mb-3 px-2 text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-500">Menu</div> : null}
        <nav className="space-y-1">
          {items.map((item) => {
            const Icon = item.icon
            const active = props.activeKey === item.key
            return (
              <button
                key={item.key}
                type="button"
                onClick={() => {
                  props.onSelect(item.key)
                  props.onCloseMobile?.()
                }}
                className={classNames(
                  'flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition',
                  active
                    ? 'bg-[var(--brand-primary)] text-white shadow-md shadow-blue-900/20'
                    : 'text-slate-400 hover:bg-slate-800 hover:text-slate-100'
                )}
              >
                <Icon className={classNames('h-[18px] w-[18px] shrink-0', active ? 'text-white' : '')} />
                {!props.collapsed ? <span className="truncate">{item.label}</span> : null}
              </button>
            )
          })}
        </nav>

        <div className="mt-6 border-t border-slate-700/50 pt-4">
          {!props.collapsed ? <div className="mb-3 px-2 text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-500">User</div> : null}
          <StaticUserMenu collapsed={props.collapsed} activeKey={props.activeKey} onSelect={props.onSelect} />
        </div>
      </div>

      <div className="border-t border-slate-700/60 p-4">
        {!props.collapsed ? (
          <div className="space-y-3">
            <div className="flex items-center gap-3 rounded-2xl border border-slate-700/50 bg-slate-800/50 px-3 py-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-[var(--brand-primary)] text-sm font-semibold text-white">
                {props.branding.logoText}
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold text-slate-100">{props.branding.companyName}</p>
                <p className="truncate text-xs text-slate-500">Enterprise</p>
              </div>
            </div>
            <button
              type="button"
              className="flex w-full items-center justify-center gap-2 rounded-xl border border-slate-600 bg-slate-800 px-4 py-3 text-sm font-semibold text-slate-200 transition hover:bg-slate-700"
              onClick={props.onLogout}
            >
              <LogOut className="h-4 w-4" />
              გასვლა
            </button>
          </div>
        ) : (
          <button
            type="button"
            className="flex w-full items-center justify-center rounded-xl border border-slate-200 bg-white p-3 text-slate-700 transition hover:bg-slate-50"
            onClick={props.onLogout}
          >
            <LogOut className="h-4 w-4" />
          </button>
        )}
      </div>
    </aside>
  )
}
