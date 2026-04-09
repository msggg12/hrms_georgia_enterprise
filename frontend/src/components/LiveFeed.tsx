import { MoreVertical, WifiOff } from 'lucide-react'

import { ka } from '../i18n/ka'
import type { FeedEvent } from '../types'
import { formatDateTime, initials } from '../utils'

function toneClasses(event: FeedEvent): string {
  if (event.device_status === 'offline') {
    return 'bg-rose-50 text-rose-600'
  }
  if (event.direction === 'out') {
    return 'bg-amber-50 text-amber-600'
  }
  return 'bg-emerald-50 text-emerald-600'
}

export function LiveFeed(props: { feed: FeedEvent[] }) {
  return (
    <article className="panel-card p-5">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">{ka.monitoringCenter}</h2>
          <p className="mt-1 text-sm text-slate-500">{ka.liveAttendanceFeed} — device / სისტემური ჩანაწერები</p>
        </div>
      </div>

      <div className="mt-5 space-y-4">
        {props.feed.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-slate-200 px-4 py-10 text-center text-sm text-slate-500">{ka.noEvents}</div>
        ) : null}

        {props.feed.slice(0, 5).map((event) => (
          <div key={`${event.event_type}-${event.event_id}`} className="flex items-start gap-3 rounded-2xl border border-slate-100 bg-white p-3">
            <div className="flex h-11 w-11 items-center justify-center overflow-hidden rounded-full bg-slate-100 text-sm font-semibold text-slate-700">
              {event.device_status === 'offline' ? <WifiOff className="h-4 w-4" /> : initials(event.first_name, event.last_name)}
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate font-semibold text-slate-900">
                    {event.device_status === 'offline'
                      ? `${ka.deviceOffline}: ${event.device_name}`
                      : `${event.first_name ?? ''} ${event.last_name ?? ''}`}
                  </p>
                  <p className="mt-1 truncate text-sm text-slate-500">
                    {event.device_status === 'offline'
                      ? event.host
                      : `${event.direction === 'out' ? ka.exit : ka.entry} • ${event.employee_number ?? '-'} • ${event.device_name}`}
                  </p>
                </div>
                <button type="button" className="text-slate-400">
                  <MoreVertical className="h-4 w-4" />
                </button>
              </div>
              <div className="mt-3 flex items-center gap-3">
                <span className={`rounded-full px-2 py-1 text-[11px] font-semibold ${toneClasses(event)}`}>
                  {event.device_status === 'offline' ? 'Device' : event.direction === 'out' ? 'OUT' : 'IN'}
                </span>
                <span className="text-xs text-slate-400">{formatDateTime(event.ts)}</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </article>
  )
}
