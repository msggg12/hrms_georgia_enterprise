import { useEffect, useState } from 'react'

import { CalendarRange, FileUp, PlusCircle } from 'lucide-react'

import { ka } from '../i18n/ka'
import type { LeaveSelfServiceData } from '../types'

type LeaveCalculatorProps = {
  data: LeaveSelfServiceData | null
  onSubmit: (payload: { leave_type_id: string; start_date: string; end_date: string; reason: string }) => Promise<void>
  onSubmitSick: (payload: { start_date: string; end_date: string; reason: string; doctor_note: File | null }) => Promise<void>
}

export function LeaveCalculator(props: LeaveCalculatorProps) {
  const defaultLeaveType = props.data?.primary_leave_type?.id ?? props.data?.leave_types[0]?.id ?? ''
  const [leaveTypeId, setLeaveTypeId] = useState(defaultLeaveType)
  const [startDate, setStartDate] = useState(new Date().toISOString().slice(0, 10))
  const [endDate, setEndDate] = useState(new Date().toISOString().slice(0, 10))
  const [reason, setReason] = useState('')
  const [sickReason, setSickReason] = useState('')
  const [doctorNote, setDoctorNote] = useState<File | null>(null)

  const total = (props.data?.available_days ?? 0) + (props.data?.used_days ?? 0)
  const progress = total ? Math.max(0, Math.min(100, ((props.data?.available_days ?? 0) / total) * 100)) : 0

  useEffect(() => {
    if (defaultLeaveType) {
      setLeaveTypeId(defaultLeaveType)
    }
  }, [defaultLeaveType])

  return (
    <article className="space-y-6">
      <section className="panel-card">
        <div className="mb-5 flex items-center justify-between">
          <div>
            <h2 className="section-title">{ka.leaveHub}</h2>
            <p className="mt-1 text-sm text-slate-500">{ka.requestLeave}</p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3 text-indigo-700">
            <CalendarRange className="h-5 w-5" />
          </div>
        </div>

        <div className="rounded-[28px] border border-slate-200 bg-slate-50 px-5 py-5">
          <div className="flex items-end justify-between gap-4">
            <div>
              <p className="text-xs uppercase tracking-[0.18em] text-slate-400">{ka.availableDays}</p>
              <p className="mt-2 text-4xl font-semibold text-slate-950">{props.data?.available_days?.toFixed(1) ?? '0.0'}</p>
            </div>
            <div className="grid gap-2 text-right text-sm text-slate-500">
              <span>{ka.earnedDays}: <strong className="text-slate-950">{props.data?.earned_days?.toFixed(1) ?? '0.0'}</strong></span>
              <span>{ka.usedDays}: <strong className="text-slate-950">{props.data?.used_days?.toFixed(1) ?? '0.0'}</strong></span>
            </div>
          </div>
          <div className="mt-4 h-3 overflow-hidden rounded-full bg-slate-200">
            <div className="h-full rounded-full" style={{ width: `${progress}%`, backgroundColor: 'var(--brand-primary)' }} />
          </div>
          <p className="mt-3 text-sm text-slate-500">
            {ka.availableDays} vs {ka.usedDays} • {props.data?.months_worked ?? 0} months • {props.data?.statutory_earned_days?.toFixed(1) ?? '0.0'} statutory days
          </p>
        </div>
      </section>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(420px,0.95fr)]">
        <section className="panel-card space-y-3">
          <h3 className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-400">{ka.requestHistory}</h3>
          {(props.data?.requests ?? []).map((item) => (
            <div key={item.id} className="rounded-3xl border border-slate-200 bg-white px-4 py-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="font-semibold text-slate-950">{item.leave_type_name}</p>
                  <p className="mt-1 text-sm text-slate-500">{item.start_date} - {item.end_date}</p>
                </div>
                <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">{item.status}</span>
              </div>
              <p className="mt-3 text-sm text-slate-600">{item.reason}</p>
            </div>
          ))}
        </section>

        <section className="space-y-6">
          <section className="panel-card">
            <h3 className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-400">{ka.requestLeave}</h3>
            <div className="mt-4 grid gap-4">
              <select className="input-shell" value={leaveTypeId} onChange={(event) => setLeaveTypeId(event.target.value)}>
                {(props.data?.leave_types ?? []).map((item) => (
                  <option key={item.id} value={item.id}>{item.name_ka}</option>
                ))}
              </select>
              <input className="input-shell" type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} />
              <input className="input-shell" type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} />
              <textarea className="input-shell min-h-[120px]" value={reason} onChange={(event) => setReason(event.target.value)} placeholder={ka.leaveReason} />
              <button
                type="button"
                className="primary-btn"
                disabled={!leaveTypeId || !reason.trim()}
                onClick={() => void props.onSubmit({ leave_type_id: leaveTypeId, start_date: startDate, end_date: endDate, reason })}
              >
                <PlusCircle className="h-4 w-4" />
                {ka.requestLeave}
              </button>
            </div>
          </section>

          <section className="panel-card">
            <h3 className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-400">ბიულეტინი</h3>
            <div className="mt-4 grid gap-4">
              <input className="input-shell" type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} />
              <input className="input-shell" type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} />
              <textarea className="input-shell min-h-[120px]" value={sickReason} onChange={(event) => setSickReason(event.target.value)} placeholder="ექიმის ცნობის კომენტარი / მიზეზი" />
              <label className="flex items-center gap-3 rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-4 py-3 text-sm text-slate-600">
                <FileUp className="h-4 w-4 text-slate-500" />
                <span>{doctorNote ? doctorNote.name : 'ატვირთეთ ექიმის ცნობა (არასავალდებულო)'}</span>
                <input className="hidden" type="file" onChange={(event) => setDoctorNote(event.target.files?.[0] ?? null)} />
              </label>
              <button
                type="button"
                className="rounded-2xl border border-slate-200 bg-white px-4 py-3 font-semibold text-slate-700 transition hover:bg-slate-50"
                disabled={!sickReason.trim()}
                onClick={() => void props.onSubmitSick({ start_date: startDate, end_date: endDate, reason: sickReason, doctor_note: doctorNote })}
              >
                ბიულეტინის გაგზავნა
              </button>
            </div>
          </section>
        </section>
      </div>
    </article>
  )
}
