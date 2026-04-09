import { useState } from 'react'

import { Download, LockKeyhole, Wallet } from 'lucide-react'

import type { PayrollHubData } from '../types'
import { formatMoney } from '../utils'

type PayrollHubProps = {
  data: PayrollHubData | null
  onMarkPaid: (timesheetId: string, payload: { payment_method: string; payment_reference: string | null; note: string | null }) => Promise<void>
}

export function PayrollHub(props: PayrollHubProps) {
  const [busyId, setBusyId] = useState('')

  async function handleMarkPaid(timesheetId: string) {
    setBusyId(timesheetId)
    try {
      await props.onMarkPaid(timesheetId, {
        payment_method: 'bank_transfer',
        payment_reference: `AUTO-${Date.now()}`,
        note: 'Locked from payroll hub'
      })
    } finally {
      setBusyId('')
    }
  }

  return (
    <section className="glass-panel p-5">
      <div className="mb-5 flex items-start justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.32em] text-action-400">Payroll History</p>
          <h2 className="mt-2 text-xl font-semibold text-navy-900">გადახდილი ხელფასები და payslips</h2>
          <p className="mt-1 text-sm text-slatepro-500">`Mark as Paid` აგენერირებს PDF payslip-ს და lock-ს ადებს timesheet ჩანაწერს.</p>
        </div>
        <div className="rounded-3xl border border-slatepro-100 bg-white px-4 py-3 text-sm font-semibold text-slatepro-700">
          {props.data?.year}-{`${props.data?.month ?? ''}`.padStart(2, '0')}
        </div>
      </div>

      <div className="grid gap-4">
        {(props.data?.items ?? []).map((item) => (
          <article key={item.id} className="rounded-[28px] border border-slatepro-100 bg-white p-4">
            <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
              <div>
                <p className="font-semibold text-navy-900">{item.employee_name} • {item.employee_number}</p>
                <div className="mt-2 flex flex-wrap gap-3 text-sm text-slatepro-500">
                  <span>Worked: {item.worked_hours}h</span>
                  <span>OT: {item.overtime_hours}h</span>
                  <span>Gross: {formatMoney(item.gross_pay)}</span>
                  <span>Net: {formatMoney(item.net_pay)}</span>
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-3">
                <span className={`rounded-full px-3 py-1 text-xs font-semibold ${item.status === 'locked' ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'}`}>
                  {item.status}
                </span>
                {item.payslip_url ? (
                  <a className="inline-flex items-center gap-2 rounded-2xl border border-slatepro-200 bg-white px-4 py-3 text-sm font-semibold text-slatepro-700" href={item.payslip_url} target="_blank" rel="noreferrer">
                    <Download className="h-4 w-4" />
                    PDF
                  </a>
                ) : null}
                {!item.payment_id ? (
                  <button type="button" className="brand-button inline-flex items-center gap-2 rounded-2xl px-4 py-3 font-semibold text-white" onClick={() => void handleMarkPaid(item.id)} disabled={busyId === item.id}>
                    <LockKeyhole className="h-4 w-4" />
                    {busyId === item.id ? 'მუშავდება...' : 'Mark as Paid'}
                  </button>
                ) : (
                  <div className="inline-flex items-center gap-2 rounded-2xl bg-emerald-50 px-4 py-3 text-sm font-semibold text-emerald-700">
                    <Wallet className="h-4 w-4" />
                    {item.payment_method ?? 'paid'}
                  </div>
                )}
              </div>
            </div>
          </article>
        ))}
      </div>
    </section>
  )
}
