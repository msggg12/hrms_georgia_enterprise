import { BadgeCheck, BriefcaseBusiness, Fingerprint, Users } from 'lucide-react'

import { ka } from '../i18n/ka'
import type { Summary, WeeklyAttendancePoint } from '../types'

function StatTile(props: { label: string; value: number; icon: typeof Users; tone: string; delta: string }) {
  const Icon = props.icon

  return (
    <div className="rounded-[18px] border border-slate-100 bg-white p-4">
      <div className="flex items-start justify-between gap-3">
        <div className={`flex h-11 w-11 items-center justify-center rounded-2xl ${props.tone}`}>
          <Icon className="h-5 w-5" />
        </div>
        <span className="rounded-full bg-emerald-50 px-2 py-1 text-[11px] font-semibold text-emerald-600">{props.delta}</span>
      </div>
      <p className="mt-5 text-[30px] font-semibold tracking-[-0.03em] text-slate-900">{props.value}</p>
      <p className="mt-1 text-sm text-slate-500">{props.label}</p>
    </div>
  )
}

export function MetricCards(props: { summary: Summary | null; weeklyAttendance?: WeeklyAttendancePoint[]; onViewAttendance?: () => void }) {
  const summary = props.summary ?? {
    active_employees: 0,
    terminated_employees: 0,
    pending_approvals: 0,
    online_devices: 0
  }
  const weeklyAttendance = props.weeklyAttendance ?? []
  const maxCount = Math.max(1, ...weeklyAttendance.map((item) => item.count))
  const chartSeries = weeklyAttendance.length > 0 ? weeklyAttendance.map((item) => item.count) : [0, 0, 0, 0, 0, 0, 0]
  const labels = weeklyAttendance.length > 0 ? weeklyAttendance.map((item) => item.label) : ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

  return (
    <section className="grid gap-6 xl:grid-cols-[minmax(0,1.1fr)_320px]">
      <article className="panel-card p-5">
        <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
          <div className="grid flex-1 gap-4 sm:grid-cols-2">
            <StatTile label={ka.activeEmployees} value={summary.active_employees} icon={Users} tone="bg-amber-50 text-amber-500" delta="30%" />
            <StatTile label={ka.terminatedEmployees} value={summary.terminated_employees} icon={BriefcaseBusiness} tone="bg-sky-50 text-sky-500" delta="22%" />
            <StatTile label={ka.pendingApprovals} value={summary.pending_approvals} icon={BadgeCheck} tone="bg-indigo-50 text-indigo-500" delta="18%" />
            <div className="rounded-[18px] border border-slate-100 bg-white p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-pink-50 text-pink-500">
                  <Fingerprint className="h-5 w-5" />
                </div>
                <span className="rounded-full bg-emerald-50 px-2 py-1 text-[11px] font-semibold text-emerald-600">12%</span>
              </div>
              <p className="mt-5 text-[30px] font-semibold tracking-[-0.03em] text-slate-900">{summary.online_devices}</p>
              <p className="mt-1 text-sm text-slate-500">{ka.onlineEmployees}</p>
              <button type="button" onClick={props.onViewAttendance} className="mt-4 text-xs font-semibold text-indigo-600 hover:text-indigo-700" hidden={!props.onViewAttendance}>
                {ka.viewCheckIns}
              </button>
            </div>
          </div>

          <div className="min-w-0 rounded-[22px] border border-slate-100 bg-white px-5 py-4 xl:w-[43%]">
            <div className="mb-5 flex items-center justify-between">
              <div>
                <h3 className="text-lg font-semibold text-slate-900">Employee Tracker</h3>
                <p className="mt-1 text-sm text-slate-500">This week</p>
              </div>
              <div className="rounded-xl border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-600">This week</div>
            </div>
            <div className="flex h-36 items-end gap-3">
              {chartSeries.map((value, index) => (
                <div key={index} className="flex flex-1 flex-col items-center gap-2">
                  <div className="flex w-full flex-col justify-end overflow-hidden rounded-t-xl bg-indigo-100" style={{ height: `${Math.max(18, (value / maxCount) * 100)}px` }}>
                    <div className="w-full rounded-t-xl bg-indigo-700" style={{ height: `${Math.max(18, (value / maxCount) * 100)}px` }} />
                  </div>
                  <span className="text-xs text-slate-400">{labels[index]}</span>
                  <span className="text-[11px] text-slate-500">{value}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </article>

      <article className="panel-card p-5">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold text-slate-900">Upcoming Schedule</h3>
            <p className="mt-1 text-sm text-slate-500">Today</p>
          </div>
          <div className="rounded-xl border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-600">Today</div>
        </div>
        <div className="mt-5 space-y-4">
          {[
            { badge: 'Critical', title: 'Team Briefing', owner: 'Manager queue', time: '09:00 - 09:30', tone: 'rose' },
            { badge: 'Urgent', title: 'Compensation Review', owner: 'Payroll approval', time: '10:30 - 12:00', tone: 'amber' },
            { badge: 'Routine', title: 'Administrative Tasks', owner: 'Daily operations', time: '12:00 - 13:00', tone: 'emerald' }
          ].map((item) => (
            <div key={item.title} className={`rounded-r-2xl border-l-2 bg-white pl-4 ${item.tone === 'rose' ? 'border-l-rose-300' : item.tone === 'amber' ? 'border-l-amber-300' : 'border-l-emerald-300'}`}>
              <div className={`mb-2 inline-flex rounded-full px-2 py-0.5 text-[10px] font-semibold ${item.tone === 'rose' ? 'bg-rose-50 text-rose-500' : item.tone === 'amber' ? 'bg-amber-50 text-amber-500' : 'bg-emerald-50 text-emerald-500'}`}>
                {item.badge}
              </div>
              <p className="font-semibold text-slate-900">{item.title}</p>
              <p className="mt-1 text-sm text-slate-500">{item.owner}</p>
              <p className="mt-2 text-xs text-slate-400">{item.time}</p>
            </div>
          ))}
        </div>
      </article>
    </section>
  )
}
