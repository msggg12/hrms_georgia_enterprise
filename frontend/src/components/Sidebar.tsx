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
              'flex w-full items-center gap-3 rounded-xl px-3 py-3 text-sm transition',
              active ? 'bg-slate-100 text-slate-900' : 'text-slate-500 hover:bg-slate-50 hover:text-slate-900'
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
        'hidden shrink-0 border-r border-slate-200 bg-white lg:flex lg:flex-col',
        props.collapsed ? 'w-[92px]' : 'w-[228px]'
      )}
    >
      <div className="flex h-[86px] items-center justify-between border-b border-slate-200 px-5">
        {!props.collapsed ? <CompanyBadge branding={props.branding} /> : <CompanyBadge branding={props.branding} compact />}
        <button
          type="button"
          onClick={props.onToggle}
          className="rounded-xl border border-slate-200 bg-white p-2.5 text-slate-500 transition hover:bg-slate-50 hover:text-slate-900"
        >
          <ChevronLeft className={classNames('h-4 w-4 transition', props.collapsed && 'rotate-180')} />
        </button>
      </div>

      <div className="flex-1 overflow-auto px-4 py-5">
        {!props.collapsed ? <div className="mb-4 px-2 text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-400">Menu</div> : null}
        <nav className="space-y-1">
          {items.map((item) => {
            const Icon = item.icon
            const active = props.activeKey === item.key
            return (
              <button
                key={item.key}
                type="button"
                onClick={() => props.onSelect(item.key)}
                className={classNames(
                  'flex w-full items-center gap-3 rounded-xl px-3 py-3 text-sm transition',
                  active ? 'bg-slate-100 text-slate-950' : 'text-slate-500 hover:bg-slate-50 hover:text-slate-900'
                )}
              >
                <Icon className={classNames('h-[18px] w-[18px] shrink-0', active && 'text-[var(--brand-primary)]')} />
                {!props.collapsed ? <span className="truncate">{item.label}</span> : null}
              </button>
            )
          })}
        </nav>

        <div className="mt-8 border-t border-slate-100 pt-5">
          {!props.collapsed ? <div className="mb-4 px-2 text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-400">User</div> : null}
          <StaticUserMenu collapsed={props.collapsed} activeKey={props.activeKey} onSelect={props.onSelect} />
        </div>
      </div>

      <div className="border-t border-slate-200 p-4">
        {!props.collapsed ? (
          <div className="space-y-3">
            <div className="flex items-center gap-3 rounded-2xl bg-slate-50 px-3 py-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-violet-100 text-sm font-semibold text-violet-700">
                {props.branding.logoText}
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold text-slate-900">{props.branding.companyName}</p>
                <p className="truncate text-xs text-slate-500">Enterprise Workspace</p>
              </div>
            </div>
            <button
              type="button"
              className="flex w-full items-center justify-center gap-2 rounded-xl border border-slate-200 px-4 py-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
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
