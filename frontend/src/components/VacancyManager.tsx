import { useEffect, useState } from 'react'

import { ExternalLink, FilePlus2, Link2, Save } from 'lucide-react'

import type { VacancyData, VacancyFieldDefinition, VacancyItem } from '../types'

type VacancyManagerProps = {
  data: VacancyData | null
  onSave: (vacancyId: string | null, payload: {
    posting_code: string
    title_en: string
    title_ka: string
    description: string
    public_description: string
    employment_type: string
    location_text: string
    status: string
    open_positions: number
    salary_min: number
    salary_max: number
    department_id: string | null
    job_role_id: string | null
    closes_at: string | null
    public_slug: string
    external_form_url: string | null
    is_public: boolean
    application_form_schema: VacancyFieldDefinition[]
  }) => Promise<void>
}

const blankField = (): VacancyFieldDefinition => ({
  key: '',
  label: '',
  field_type: 'text',
  required: true,
  options: []
})

export function VacancyManager(props: VacancyManagerProps) {
  const [selectedId, setSelectedId] = useState<string>('new')
  const [busy, setBusy] = useState(false)
  const [form, setForm] = useState({
    posting_code: '',
    title_en: '',
    title_ka: '',
    description: '',
    public_description: '',
    employment_type: 'full_time',
    location_text: '',
    status: 'draft',
    open_positions: 1,
    salary_min: 0,
    salary_max: 0,
    department_id: '',
    job_role_id: '',
    closes_at: '',
    public_slug: '',
    external_form_url: '',
    is_public: true,
    application_form_schema: [blankField()]
  })

  useEffect(() => {
    const selected = props.data?.items.find((item) => item.id === selectedId)
    if (!selected) {
      setForm({
        posting_code: '',
        title_en: '',
        title_ka: '',
        description: '',
        public_description: '',
        employment_type: 'full_time',
        location_text: '',
        status: 'draft',
        open_positions: 1,
        salary_min: 0,
        salary_max: 0,
        department_id: '',
        job_role_id: '',
        closes_at: '',
        public_slug: '',
        external_form_url: '',
        is_public: true,
        application_form_schema: [blankField()]
      })
      return
    }
    setForm({
      posting_code: selected.posting_code,
      title_en: selected.title_en,
      title_ka: selected.title_ka,
      description: selected.description,
      public_description: selected.public_description ?? selected.description,
      employment_type: selected.employment_type,
      location_text: selected.location_text ?? '',
      status: selected.status,
      open_positions: selected.open_positions,
      salary_min: selected.salary_min,
      salary_max: selected.salary_max,
      department_id: props.data?.departments.find((item) => item.name_en === selected.department_name || item.name_ka === selected.department_name)?.id ?? '',
      job_role_id: props.data?.job_roles.find((item) => item.title_en === selected.job_role_name || item.title_ka === selected.job_role_name)?.id ?? '',
      closes_at: selected.closes_at ? selected.closes_at.slice(0, 16) : '',
      public_slug: selected.public_slug ?? '',
      external_form_url: selected.external_form_url ?? '',
      is_public: selected.is_public,
      application_form_schema: selected.application_form_schema.length ? selected.application_form_schema : [blankField()]
    })
  }, [props.data, selectedId])

  async function handleSave() {
    setBusy(true)
    try {
      await props.onSave(selectedId === 'new' ? null : selectedId, {
        ...form,
        department_id: form.department_id || null,
        job_role_id: form.job_role_id || null,
        closes_at: form.closes_at || null,
        external_form_url: form.external_form_url || null,
        application_form_schema: form.application_form_schema.filter((field) => field.key && field.label)
      })
      setSelectedId('new')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="panel-card">
      <div className="mb-5 flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.32em] text-slate-400">Vacancy Creator</p>
          <h2 className="mt-2 text-xl font-semibold text-slate-950">ვაკანსიები და public applications</h2>
          <p className="mt-1 text-sm text-slate-500">Google Form bridge ან internal form schema ორივე იმართება აქედან.</p>
        </div>
        <select className="input-shell min-w-[280px]" value={selectedId} onChange={(event) => setSelectedId(event.target.value)}>
          <option value="new">ახალი ვაკანსია</option>
          {(props.data?.items ?? []).map((item) => (
            <option key={item.id} value={item.id}>
              {item.posting_code} - {item.title_ka}
            </option>
          ))}
        </select>
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,0.95fr)_minmax(350px,0.85fr)]">
        <div className="space-y-4 rounded-xl border border-slate-200 bg-white p-5">
          <div className="grid gap-4 md:grid-cols-2">
            <input className="input-shell" value={form.posting_code} onChange={(event) => setForm((current) => ({ ...current, posting_code: event.target.value }))} placeholder="Posting Code" />
            <select className="input-shell" value={form.status} onChange={(event) => setForm((current) => ({ ...current, status: event.target.value }))}>
              <option value="draft">Draft</option>
              <option value="published">Published</option>
              <option value="closed">Closed</option>
              <option value="on_hold">On Hold</option>
            </select>
            <input className="input-shell" value={form.title_en} onChange={(event) => setForm((current) => ({ ...current, title_en: event.target.value }))} placeholder="English Title" />
            <input className="input-shell" value={form.title_ka} onChange={(event) => setForm((current) => ({ ...current, title_ka: event.target.value }))} placeholder="ქართული სათაური" />
            <select className="input-shell" value={form.department_id} onChange={(event) => setForm((current) => ({ ...current, department_id: event.target.value }))}>
              <option value="">Department</option>
              {(props.data?.departments ?? []).map((item) => <option key={item.id} value={item.id}>{item.name_ka ?? item.name_en}</option>)}
            </select>
            <select className="input-shell" value={form.job_role_id} onChange={(event) => setForm((current) => ({ ...current, job_role_id: event.target.value }))}>
              <option value="">Job Role</option>
              {(props.data?.job_roles ?? []).map((item) => <option key={item.id} value={item.id}>{item.title_ka ?? item.title_en}</option>)}
            </select>
            <input className="input-shell" value={form.location_text} onChange={(event) => setForm((current) => ({ ...current, location_text: event.target.value }))} placeholder="Location" />
            <input className="input-shell" type="number" value={form.open_positions} onChange={(event) => setForm((current) => ({ ...current, open_positions: Number(event.target.value) }))} placeholder="Open Positions" />
            <input className="input-shell" type="number" value={form.salary_min} onChange={(event) => setForm((current) => ({ ...current, salary_min: Number(event.target.value) }))} placeholder="Salary Min" />
            <input className="input-shell" type="number" value={form.salary_max} onChange={(event) => setForm((current) => ({ ...current, salary_max: Number(event.target.value) }))} placeholder="Salary Max" />
            <input className="input-shell" type="datetime-local" value={form.closes_at} onChange={(event) => setForm((current) => ({ ...current, closes_at: event.target.value }))} />
            <input className="input-shell" value={form.public_slug} onChange={(event) => setForm((current) => ({ ...current, public_slug: event.target.value }))} placeholder="Public Slug" />
            <input className="input-shell md:col-span-2" value={form.external_form_url} onChange={(event) => setForm((current) => ({ ...current, external_form_url: event.target.value }))} placeholder="Google Form URL (optional)" />
          </div>
          <textarea className="input-shell min-h-[120px]" value={form.description} onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))} placeholder="Internal Description" />
          <textarea className="input-shell min-h-[120px]" value={form.public_description} onChange={(event) => setForm((current) => ({ ...current, public_description: event.target.value }))} placeholder="Public Description" />

          <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
            <div className="mb-3 flex items-center justify-between">
              <div className="flex items-center gap-2 font-semibold text-slate-950">
                <FilePlus2 className="h-4 w-4 text-action-600" />
                Custom Application Form
              </div>
              <button type="button" className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700" onClick={() => setForm((current) => ({ ...current, application_form_schema: [...current.application_form_schema, blankField()] }))}>
                Add Field
              </button>
            </div>
            <div className="space-y-3">
              {form.application_form_schema.map((field, index) => (
                <div key={`${field.key}-${index}`} className="grid gap-3 rounded-lg border border-slate-200 bg-white p-3 md:grid-cols-[1fr_1fr_140px_88px_44px]">
                  <input className="input-shell" value={field.key} onChange={(event) => setForm((current) => ({ ...current, application_form_schema: current.application_form_schema.map((item, itemIndex) => itemIndex === index ? { ...item, key: event.target.value } : item) }))} placeholder="field_key" />
                  <input className="input-shell" value={field.label} onChange={(event) => setForm((current) => ({ ...current, application_form_schema: current.application_form_schema.map((item, itemIndex) => itemIndex === index ? { ...item, label: event.target.value } : item) }))} placeholder="ლეიბლი" />
                  <select className="input-shell" value={field.field_type} onChange={(event) => setForm((current) => ({ ...current, application_form_schema: current.application_form_schema.map((item, itemIndex) => itemIndex === index ? { ...item, field_type: event.target.value } : item) }))}>
                    <option value="text">text</option>
                    <option value="textarea">textarea</option>
                    <option value="email">email</option>
                    <option value="phone">phone</option>
                    <option value="number">number</option>
                    <option value="date">date</option>
                  </select>
                  <label className="flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-3 text-sm text-slate-600">
                    <input type="checkbox" checked={field.required} onChange={(event) => setForm((current) => ({ ...current, application_form_schema: current.application_form_schema.map((item, itemIndex) => itemIndex === index ? { ...item, required: event.target.checked } : item) }))} />
                    Req
                  </label>
                  <button type="button" className="rounded-2xl border border-rose-200 bg-rose-50 text-rose-600" onClick={() => setForm((current) => ({ ...current, application_form_schema: current.application_form_schema.filter((_, itemIndex) => itemIndex !== index) }))}>
                    ×
                  </button>
                </div>
              ))}
            </div>
          </div>

          <button type="button" className="brand-button inline-flex items-center gap-2 rounded-2xl px-4 py-3 font-semibold text-white" onClick={() => void handleSave()} disabled={busy}>
            <Save className="h-4 w-4" />
            {busy ? 'ინახება...' : 'ვაკანსიის შენახვა'}
          </button>
        </div>

        <div className="space-y-3">
          {(props.data?.items ?? []).map((item: VacancyItem) => (
            <button key={item.id} type="button" className={`w-full rounded-xl border p-4 text-left transition ${selectedId === item.id ? 'brand-border brand-soft border' : 'border-slate-200 bg-white hover:border-slate-300'}`} onClick={() => setSelectedId(item.id)}>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-xs uppercase tracking-[0.2em] text-slate-400">{item.posting_code}</p>
                  <h3 className="mt-2 font-semibold text-slate-950">{item.title_ka}</h3>
                  <p className="mt-1 text-sm text-slate-500">{item.department_name ?? '-'} • {item.application_count} applicants</p>
                </div>
                <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">{item.status}</span>
              </div>
              <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-500">
                {item.external_form_url ? <span className="rounded-full bg-amber-50 px-3 py-1 text-amber-700">Google Form</span> : <span className="rounded-full bg-emerald-50 px-3 py-1 text-emerald-700">Internal Form</span>}
                {item.public_url ? <span className="rounded-full bg-action-50 px-3 py-1 text-action-600">{item.public_slug}</span> : null}
              </div>
              {item.public_url ? <a className="mt-3 inline-flex items-center gap-2 text-sm font-semibold text-action-500" href={item.public_url} target="_blank" rel="noreferrer"><Link2 className="h-4 w-4" />Public link</a> : null}
              {item.external_form_url ? <a className="mt-2 inline-flex items-center gap-2 text-sm font-semibold text-slate-600" href={item.external_form_url} target="_blank" rel="noreferrer"><ExternalLink className="h-4 w-4" />Google Form</a> : null}
            </button>
          ))}
        </div>
      </div>
    </section>
  )
}
