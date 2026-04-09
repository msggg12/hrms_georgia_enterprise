import { useState } from 'react'

import { Globe, MapPinned, ShieldCheck } from 'lucide-react'

import type { WebPunchConfigData } from '../types'
import { formatDateTime } from '../utils'

type WebPunchPanelProps = {
  data: WebPunchConfigData | null
  onSubmit: (payload: { direction: string; latitude: number | null; longitude: number | null }) => Promise<void>
}

export function WebPunchPanel(props: WebPunchPanelProps) {
  const [direction, setDirection] = useState('in')
  const [latitude, setLatitude] = useState('')
  const [longitude, setLongitude] = useState('')
  const [busy, setBusy] = useState(false)

  async function handleSubmit() {
    setBusy(true)
    try {
      await props.onSubmit({
        direction,
        latitude: latitude ? Number(latitude) : null,
        longitude: longitude ? Number(longitude) : null
      })
      setLatitude('')
      setLongitude('')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="glass-panel p-5">
      <div className="mb-5 flex items-center justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.32em] text-action-400">Web Punch</p>
          <h2 className="mt-2 text-xl font-semibold text-navy-900">ოფისის web check-in</h2>
          <p className="mt-1 text-sm text-slatepro-500">Punch ჩაიწერება მხოლოდ allowed IP ან geofence პოლიტიკის დაკმაყოფილების შემთხვევაში.</p>
        </div>
        <div className="rounded-3xl border border-emerald-100 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4" />
            <span>{props.data?.config.allowed_web_punch_ips.length ? 'IP allowlist active' : 'Geofence mode or pending config'}</span>
          </div>
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,0.85fr)_minmax(320px,1fr)]">
        <div className="rounded-[28px] border border-slatepro-100 bg-white p-5">
          <div className="grid gap-4 md:grid-cols-3">
            <select className="input-shell" value={direction} onChange={(event) => setDirection(event.target.value)}>
              <option value="in">Entry</option>
              <option value="out">Exit</option>
            </select>
            <input className="input-shell" value={latitude} onChange={(event) => setLatitude(event.target.value)} placeholder="Latitude" />
            <input className="input-shell" value={longitude} onChange={(event) => setLongitude(event.target.value)} placeholder="Longitude" />
          </div>
          <button type="button" className="brand-button mt-4 rounded-2xl px-4 py-3 font-semibold text-white" onClick={() => void handleSubmit()} disabled={busy}>
            {busy ? 'იგზავნება...' : 'Punch გაგზავნა'}
          </button>
        </div>

        <div className="space-y-3">
          <div className="rounded-[28px] border border-slatepro-100 bg-white p-4">
            <div className="flex items-center gap-2 text-sm font-semibold text-navy-900">
              <Globe className="h-4 w-4 text-action-400" />
              Allowed IPs
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              {props.data?.config.allowed_web_punch_ips.length ? props.data.config.allowed_web_punch_ips.map((item) => (
                <span key={item} className="rounded-full bg-slatepro-100 px-3 py-1 text-xs font-semibold text-slatepro-600">{item}</span>
              )) : <span className="text-sm text-slatepro-500">IP allowlist არ არის მითითებული.</span>}
            </div>
          </div>
          <div className="rounded-[28px] border border-slatepro-100 bg-white p-4">
            <div className="flex items-center gap-2 text-sm font-semibold text-navy-900">
              <MapPinned className="h-4 w-4 text-action-400" />
              Geofence
            </div>
            <p className="mt-3 text-sm text-slatepro-500">
              {props.data?.config.geofence_latitude != null
                ? `${props.data.config.geofence_latitude}, ${props.data.config.geofence_longitude} • ${props.data.config.geofence_radius_meters}m`
                : 'Geofence ჯერ არ არის მითითებული.'}
            </p>
          </div>
        </div>
      </div>

      <div className="mt-6 rounded-[28px] border border-slatepro-100 bg-white p-5">
        <h3 className="text-sm font-semibold text-navy-900">ბოლო web punch-ები</h3>
        <div className="mt-4 space-y-3">
          {(props.data?.recent_punches ?? []).map((item) => (
            <div key={item.id} className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slatepro-100 px-4 py-3">
              <div>
                <p className="font-semibold text-navy-900">{item.direction.toUpperCase()} • {formatDateTime(item.punch_ts)}</p>
                <p className="text-sm text-slatepro-500">{item.validation_reason ?? '-'}</p>
              </div>
              <span className={`rounded-full px-3 py-1 text-xs font-semibold ${item.is_valid ? 'bg-emerald-50 text-emerald-700' : 'bg-rose-50 text-rose-700'}`}>
                {item.is_valid ? 'Valid' : 'Rejected'}
              </span>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
