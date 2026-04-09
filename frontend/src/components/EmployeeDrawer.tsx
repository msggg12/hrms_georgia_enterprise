import { useEffect, useState } from 'react'

import { Camera, ChevronRight, DollarSign, Fingerprint, PlusCircle, Users } from 'lucide-react'

import { ka } from '../i18n/ka'
import type { EmployeeDraft, EmployeeFormOptions } from '../types'
import { classNames, validateEmployeeDraft } from '../utils'

type DrawerTab = 'personal' | 'salary' | 'device'

type EmployeeDrawerProps = {
  open: boolean
  mode: 'create' | 'edit'
  draft: EmployeeDraft
  options: EmployeeFormOptions | null
  activeTab: DrawerTab
  selectedPhoto: File | null
  onChangeTab: (tab: DrawerTab) => void
  onDraftChange: (draft: EmployeeDraft) => void
  onPhotoChange: (file: File | null) => void
  onClose: () => void
  onSubmit: () => void
}

function FieldError(props: { message?: string }) {
  if (!props.message) {
    return null
  }
  return <p className="mt-2 text-xs font-medium text-rose-600">{props.message}</p>
}

function DrawerTabs(props: { activeTab: DrawerTab; onChange: (tab: DrawerTab) => void }) {
  const tabs = [
    { key: 'personal' as const, label: ka.personalInfo, icon: Users },
    { key: 'salary' as const, label: ka.salaryInfo, icon: DollarSign },
    { key: 'device' as const, label: ka.biometricAssignment, icon: Fingerprint }
  ]
  return (
    <div className="flex gap-2 rounded-lg bg-slate-100 p-1">
      {tabs.map((tab) => {
        const Icon = tab.icon
        const active = props.activeTab === tab.key
        return (
          <button
            key={tab.key}
            type="button"
            onClick={() => props.onChange(tab.key)}
            className={classNames(
              'flex flex-1 items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm font-semibold transition',
              active ? 'bg-white text-slate-950 ring-1 ring-slate-200' : 'text-slate-500 hover:text-slate-900'
            )}
          >
            <Icon className="h-4 w-4" />
            {tab.label}
          </button>
        )
      })}
    </div>
  )
}

export function EmployeeDrawer(props: EmployeeDrawerProps) {
  const errors = validateEmployeeDraft(props.draft)
  const hasErrors = Object.keys(errors).length > 0
  const [previewUrl, setPreviewUrl] = useState('')
  const [rolePanelOpen, setRolePanelOpen] = useState(false)

  useEffect(() => {
    if (!props.selectedPhoto) {
      setPreviewUrl('')
      return
    }
    const nextUrl = URL.createObjectURL(props.selectedPhoto)
    setPreviewUrl(nextUrl)
    return () => URL.revokeObjectURL(nextUrl)
  }, [props.selectedPhoto])

  useEffect(() => {
    if (props.open) {
      setRolePanelOpen(Boolean(props.draft.new_job_role_title_ka || props.draft.new_job_role_title_en))
    }
  }, [props.open, props.draft.new_job_role_title_ka, props.draft.new_job_role_title_en])

  if (!props.open) {
    return null
  }

  const managerLabel = props.options?.managers.find((manager) => manager.id === props.draft.manager_employee_id)?.full_name ?? props.draft.manager_name ?? ''
  const photoUrl = previewUrl || props.draft.profile_photo_url || ''
  const showNewRolePanel = rolePanelOpen || Boolean(props.draft.new_job_role_title_ka || props.draft.new_job_role_title_en)

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-slate-950/45">
      <div className="h-full w-full max-w-2xl overflow-y-auto border-l border-slate-200 bg-white px-6 py-6 shadow-panel">
        <div className="mb-5 flex items-center justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.24em] text-slate-400">{props.mode === 'create' ? ka.addEmployee : ka.editEmployee}</p>
            <h2 className="mt-2 text-2xl font-semibold text-slate-950">{props.mode === 'create' ? ka.create : ka.editEmployee}</h2>
          </div>
          <button type="button" className="rounded-lg border border-slate-200 p-3 text-slate-500 transition hover:bg-slate-50" onClick={props.onClose}>
            <ChevronRight className="h-4 w-4 rotate-180" />
          </button>
        </div>

        <DrawerTabs activeTab={props.activeTab} onChange={props.onChangeTab} />

        <div className="mt-6 grid gap-4">
          {props.activeTab === 'personal' ? (
            <div className="grid gap-4">
              <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
                  <div className="flex h-24 w-24 items-center justify-center overflow-hidden rounded-xl border border-slate-200 bg-white">
                    {photoUrl ? (
                      <img src={photoUrl} alt="Employee profile" className="h-full w-full object-cover" />
                    ) : (
                      <Camera className="h-6 w-6 text-slate-300" />
                    )}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-semibold text-slate-950">პროფილის ფოტო</p>
                    <p className="mt-1 text-sm text-slate-500">Dahua-სთვის გამოიყენეთ მხოლოდ JPG ან JPEG ფაილი.</p>
                    <div className="mt-3 flex flex-wrap gap-3">
                      <label className="primary-btn cursor-pointer">
                        <input
                          type="file"
                          accept=".jpg,.jpeg,image/jpeg"
                          className="hidden"
                          onChange={(event) => props.onPhotoChange(event.target.files?.[0] ?? null)}
                        />
                        JPG ატვირთვა
                      </label>
                      {props.selectedPhoto ? (
                        <button type="button" className="muted-btn" onClick={() => props.onPhotoChange(null)}>
                          სურათის გასუფთავება
                        </button>
                      ) : null}
                    </div>
                  </div>
                </div>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <input className="input-shell" placeholder={ka.employeeNumber} value={props.draft.employee_number} onChange={(event) => props.onDraftChange({ ...props.draft, employee_number: event.target.value })} disabled={props.mode === 'edit'} />
                  <FieldError message={errors.employee_number} />
                </div>
                <div>
                  <input className="input-shell" placeholder={ka.personalNumber} value={props.draft.personal_number} onChange={(event) => props.onDraftChange({ ...props.draft, personal_number: event.target.value })} disabled={props.mode === 'edit'} />
                  <FieldError message={errors.personal_number} />
                </div>
                <div>
                  <input className="input-shell" placeholder={ka.name} value={props.draft.first_name} onChange={(event) => props.onDraftChange({ ...props.draft, first_name: event.target.value })} />
                  <FieldError message={errors.first_name} />
                </div>
                <div>
                  <input className="input-shell" placeholder={ka.fullName} value={props.draft.last_name} onChange={(event) => props.onDraftChange({ ...props.draft, last_name: event.target.value })} />
                  <FieldError message={errors.last_name} />
                </div>
                <div>
                  <input className="input-shell" placeholder={ka.email} value={props.draft.email} onChange={(event) => props.onDraftChange({ ...props.draft, email: event.target.value })} />
                  <FieldError message={errors.email} />
                </div>
                <div>
                  <input className="input-shell" placeholder={ka.phone} value={props.draft.mobile_phone} onChange={(event) => props.onDraftChange({ ...props.draft, mobile_phone: event.target.value })} />
                  <FieldError message={errors.mobile_phone} />
                </div>
                <input className="input-shell" type="date" value={props.draft.hire_date} onChange={(event) => props.onDraftChange({ ...props.draft, hire_date: event.target.value })} disabled={props.mode === 'edit'} />
                <select className="input-shell" value={props.draft.department_id} onChange={(event) => props.onDraftChange({ ...props.draft, department_id: event.target.value })}>
                  <option value="">დეპარტამენტის არჩევა</option>
                  {props.options?.departments.map((department) => (
                    <option key={department.id} value={department.id}>{department.name_ka ?? department.name_en}</option>
                  ))}
                </select>
                <div className="md:col-span-2">
                  <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_auto]">
                    <select className="input-shell" value={props.draft.job_role_id} onChange={(event) => props.onDraftChange({ ...props.draft, job_role_id: event.target.value })}>
                      <option value="">პოზიციის არჩევა</option>
                      {props.options?.job_roles.map((role) => (
                        <option key={role.id} value={role.id}>{role.title_ka ?? role.title_en}</option>
                      ))}
                    </select>
                    <button type="button" className="muted-btn" onClick={() => setRolePanelOpen(true)}>
                      <PlusCircle className="h-4 w-4" />
                      ახალი პოზიცია
                    </button>
                  </div>
                  {showNewRolePanel ? (
                    <div className="mt-3 grid gap-3 rounded-xl border border-slate-200 bg-slate-50 p-4 md:grid-cols-2">
                      <input className="input-shell" placeholder="ახალი პოზიცია ქართულად" value={props.draft.new_job_role_title_ka} onChange={(event) => props.onDraftChange({ ...props.draft, new_job_role_title_ka: event.target.value })} />
                      <input className="input-shell" placeholder="New position in English" value={props.draft.new_job_role_title_en} onChange={(event) => props.onDraftChange({ ...props.draft, new_job_role_title_en: event.target.value })} />
                      <label className="flex items-center gap-3 rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700 md:col-span-2">
                        <input type="checkbox" checked={props.draft.new_job_role_is_managerial} onChange={(event) => props.onDraftChange({ ...props.draft, new_job_role_is_managerial: event.target.checked })} />
                        ეს პოზიცია ხელმძღვანელ პოზიციად ჩაითვალოს
                      </label>
                    </div>
                  ) : null}
                </div>
                <div className="md:col-span-2">
                  <select className="input-shell" value={props.draft.manager_employee_id} onChange={(event) => props.onDraftChange({ ...props.draft, manager_employee_id: event.target.value })}>
                    <option value="">ხელმძღვანელის არჩევა</option>
                    {props.options?.managers.map((manager) => (
                      <option key={manager.id} value={manager.id}>{manager.full_name}</option>
                    ))}
                  </select>
                  <p className="mt-2 text-sm text-slate-500">
                    {managerLabel ? `ამ თანამშრომლის უფროსი: ${managerLabel}` : 'თუ თანამშრომელს უფროსი ჰყავს, მიუთითეთ აქ.'}
                  </p>
                </div>
              </div>
            </div>
          ) : null}

          {props.activeTab === 'salary' ? (
            <div className="grid gap-4 md:grid-cols-2">
              <input className="input-shell" placeholder={ka.salary} value={props.draft.base_salary} onChange={(event) => props.onDraftChange({ ...props.draft, base_salary: event.target.value })} />
              <input className="input-shell" placeholder={ka.hourlyRate} value={props.draft.hourly_rate_override} onChange={(event) => props.onDraftChange({ ...props.draft, hourly_rate_override: event.target.value })} />
              <select className="input-shell md:col-span-2" value={props.draft.pay_policy_id} onChange={(event) => props.onDraftChange({ ...props.draft, pay_policy_id: event.target.value })}>
                {props.options?.pay_policies.map((policy) => (
                  <option key={policy.id} value={policy.id}>{policy.code} - {policy.name}</option>
                ))}
              </select>
              <label className="flex items-center gap-3 rounded-lg border border-slate-200 px-4 py-3 text-sm text-slate-700 md:col-span-2">
                <input type="checkbox" checked={props.draft.is_pension_participant} onChange={(event) => props.onDraftChange({ ...props.draft, is_pension_participant: event.target.checked })} />
                {ka.pensionParticipant}
              </label>
            </div>
          ) : null}

          {props.activeTab === 'device' ? (
            <div className="grid gap-4">
              <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
                Dahua სახის ტერმინალებისთვის თანამშრომლის პროფილის ფოტო ატვირთეთ JPG ფორმატში პერსონალურ ჩანართში.
              </div>
              <input className="input-shell" placeholder={ka.deviceUserId} value={props.draft.default_device_user_id} onChange={(event) => props.onDraftChange({ ...props.draft, default_device_user_id: event.target.value })} />
              <div className="grid gap-3">
                {props.options?.devices.map((device) => (
                  <div key={device.id} className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
                    <div className="flex items-center justify-between gap-4">
                      <div>
                        <p className="font-semibold text-slate-950">{device.device_name}</p>
                        <p className="mt-1 text-sm text-slate-500">{device.brand} - {device.host}</p>
                      </div>
                      <Fingerprint className="h-5 w-5 text-slate-500" />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </div>

        {hasErrors ? (
          <div className="mt-6 rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 break-words whitespace-pre-wrap">
            გთხოვთ, შეასწოროთ სავალდებულო ველები და შემდეგ შეინახოთ ჩანაწერი.
          </div>
        ) : null}

        <div className="mt-8 flex items-center justify-end gap-3">
          <button type="button" className="muted-btn" onClick={props.onClose}>
            {ka.cancel}
          </button>
          <button type="button" className="primary-btn" onClick={props.onSubmit} disabled={hasErrors}>
            {ka.save}
          </button>
        </div>
      </div>
    </div>
  )
}
