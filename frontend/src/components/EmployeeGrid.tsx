import { Activity, ArrowDownUp, Fingerprint, KeyRound, LoaderCircle, PencilLine, Search, Upload, UserPlus } from 'lucide-react'

import { ka } from '../i18n/ka'
import type { GridItem, GridResponse, OptionItem } from '../types'
import { formatMoney, initials, statusBadge } from '../utils'

type GridSortBy = 'employee_number' | 'full_name' | 'department_name' | 'job_title' | 'employment_status' | 'hire_date'

type EmployeeGridProps = {
  grid: GridResponse | null
  busy: boolean
  importBusy: boolean
  search: string
  statusFilter: string
  departmentFilter: string
  emailFilter: string
  phoneFilter: string
  salaryMin: string
  salaryMax: string
  departments: OptionItem[]
  sortBy: GridSortBy
  sortDirection: 'asc' | 'desc'
  onSearchChange: (value: string) => void
  onStatusFilterChange: (value: string) => void
  onDepartmentFilterChange: (value: string) => void
  onEmailFilterChange: (value: string) => void
  onPhoneFilterChange: (value: string) => void
  onSalaryMinChange: (value: string) => void
  onSalaryMaxChange: (value: string) => void
  onSortByChange: (value: GridSortBy) => void
  onToggleSortDirection: () => void
  onOpenCreate: () => void
  onOpenEdit: (employee: GridItem) => void
  onOpenSync: (employee: GridItem) => void
  onGrantAccess: (employee: GridItem) => void
  onViewAttendance: (employee: GridItem) => void
  onPageChange: (page: number) => void
  onPageSizeChange: (pageSize: number) => void
  onImport: (file: File) => void
}

function employeeStatusLabel(status: string): string {
  if (status === 'active') {
    return ka.active
  }
  if (status === 'suspended') {
    return ka.suspended
  }
  if (status === 'terminated') {
    return ka.terminated
  }
  return status
}

export function EmployeeGrid(props: EmployeeGridProps) {
  const shownCount = props.grid?.items.length ?? 0
  const totalCount = props.grid?.total ?? 0
  const currentPage = props.grid?.page ?? 1
  const pageCount = props.grid?.page_count ?? 1

  return (
    <section className="space-y-6">
      <article className="panel-card p-4 sm:p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <h2 className="text-xl font-semibold tracking-[-0.03em] text-slate-900">{ka.employeeManagement}</h2>
            <p className="mt-1 text-sm text-slate-500">ფილტრები: სახელი, დეპარტამენტი, ტელეფონი, ელფოსტა, ხელფასი.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <label className="muted-btn cursor-pointer text-sm">
              <input
                type="file"
                accept=".csv,text/csv"
                className="hidden"
                disabled={props.importBusy}
                onChange={(event) => {
                  const file = event.target.files?.[0]
                  if (file) {
                    props.onImport(file)
                  }
                  event.currentTarget.value = ''
                }}
              />
              {props.importBusy ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
              SmartPSS CSV
            </label>
            <button type="button" onClick={props.onOpenCreate} className="primary-btn text-sm">
              <UserPlus className="h-4 w-4" />
              {ka.addEmployee}
            </button>
          </div>
        </div>

        <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          <select
            className="input-shell text-sm"
            value={props.departmentFilter}
            onChange={(event) => props.onDepartmentFilterChange(event.target.value)}
          >
            <option value="">ყველა დეპარტამენტი</option>
            {props.departments.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name_ka ?? d.name_en}
              </option>
            ))}
          </select>
          <input
            className="input-shell text-sm"
            value={props.emailFilter}
            onChange={(event) => props.onEmailFilterChange(event.target.value)}
            placeholder={ka.email}
          />
          <input
            className="input-shell text-sm"
            value={props.phoneFilter}
            onChange={(event) => props.onPhoneFilterChange(event.target.value)}
            placeholder={ka.phone}
          />
          <input
            className="input-shell text-sm"
            value={props.salaryMin}
            onChange={(event) => props.onSalaryMinChange(event.target.value)}
            placeholder="ხელფასი მინ (GEL)"
            inputMode="numeric"
          />
          <input
            className="input-shell text-sm"
            value={props.salaryMax}
            onChange={(event) => props.onSalaryMaxChange(event.target.value)}
            placeholder="ხელფასი მაქს (GEL)"
            inputMode="numeric"
          />
        </div>
      </article>

      <article className="table-shell">
        <div className="flex flex-col gap-4 border-b border-slate-100 px-5 py-5 xl:flex-row xl:items-center xl:justify-between">
          <div>
            <h3 className="text-xl font-semibold text-slate-900">Employees List</h3>
            <p className="mt-1 text-sm text-slate-500">Full employee directory with manager, salary and access status.</p>
          </div>
          <div className="flex flex-col gap-3 sm:flex-row">
            <div className="relative min-w-0 sm:w-[260px]">
              <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input className="input-shell w-full pl-11" value={props.search} onChange={(event) => props.onSearchChange(event.target.value)} placeholder={ka.search} />
            </div>
            <select className="input-shell sm:w-[170px]" value={props.statusFilter} onChange={(event) => props.onStatusFilterChange(event.target.value)}>
              <option value="">{ka.allStatuses}</option>
              <option value="active">{ka.active}</option>
              <option value="suspended">{ka.suspended}</option>
              <option value="terminated">{ka.terminated}</option>
            </select>
            <select className="input-shell sm:w-[190px]" value={props.sortBy} onChange={(event) => props.onSortByChange(event.target.value as GridSortBy)}>
              <option value="employee_number">{ka.employeeNumber}</option>
              <option value="full_name">{ka.fullName}</option>
              <option value="department_name">{ka.department}</option>
              <option value="job_title">{ka.role}</option>
              <option value="employment_status">{ka.status}</option>
              <option value="hire_date">{ka.hireDate}</option>
            </select>
            <button type="button" className="muted-btn" onClick={props.onToggleSortDirection}>
              <ArrowDownUp className="h-4 w-4" />
              {props.sortDirection === 'asc' ? ka.sortAsc : ka.sortDesc}
            </button>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="min-w-full text-left">
            <thead className="border-b border-slate-100 bg-slate-50/70">
              <tr className="text-xs uppercase tracking-[0.18em] text-slate-400">
                <th className="px-5 py-4 font-semibold">სახელი და კონტაქტი</th>
                <th className="px-5 py-4 font-semibold">{ka.role}</th>
                <th className="px-5 py-4 font-semibold">{ka.department}</th>
                <th className="px-5 py-4 font-semibold">Boss</th>
                <th className="px-5 py-4 font-semibold">{ka.salary}</th>
                <th className="px-5 py-4 font-semibold">{ka.status}</th>
                <th className="px-5 py-4 font-semibold">Actions</th>
              </tr>
            </thead>
            <tbody>
              {(props.grid?.items ?? []).map((employee) => (
                <tr key={employee.id} className="border-b border-slate-100 last:border-b-0">
                  <td className="px-5 py-4">
                    <div className="flex items-center gap-3">
                      <div className="flex h-11 w-11 items-center justify-center overflow-hidden rounded-full bg-slate-100 text-sm font-semibold text-slate-700">
                        {employee.profile_photo_url ? (
                          <img src={employee.profile_photo_url} alt="" className="h-full w-full object-cover" />
                        ) : (
                          initials(employee.first_name, employee.last_name)
                        )}
                      </div>
                      <div className="min-w-0">
                        <p className="truncate font-semibold text-slate-900">{employee.first_name} {employee.last_name}</p>
                        <p className="truncate text-sm text-slate-500">{employee.email ?? '-'}</p>
                        <p className="truncate text-xs text-slate-400">{employee.mobile_phone ?? '—'}</p>
                      </div>
                    </div>
                  </td>
                  <td className="px-5 py-4 text-sm text-slate-600">{employee.job_title ?? 'Position not set'}</td>
                  <td className="px-5 py-4 text-sm text-slate-600">{employee.department_name ?? '-'}</td>
                  <td className="px-5 py-4 text-sm text-slate-600">{employee.manager_name ?? 'Not assigned'}</td>
                  <td className="px-5 py-4 text-sm font-semibold text-slate-900">{formatMoney(employee.base_salary)}</td>
                  <td className="px-5 py-4">
                    <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${statusBadge(employee.employment_status)}`}>
                      {employeeStatusLabel(employee.employment_status)}
                    </span>
                  </td>
                  <td className="px-5 py-4">
                    <div className="flex flex-wrap gap-2">
                      <button type="button" className="muted-btn px-3 py-2 text-xs" onClick={() => props.onOpenEdit(employee)}>
                        <PencilLine className="h-3.5 w-3.5" />
                        Edit
                      </button>
                      <button type="button" className="muted-btn px-3 py-2 text-xs" onClick={() => props.onViewAttendance(employee)}>
                        <Activity className="h-3.5 w-3.5" />
                        Attendance
                      </button>
                      <button type="button" className="muted-btn px-3 py-2 text-xs" onClick={() => props.onOpenSync(employee)}>
                        <Fingerprint className="h-3.5 w-3.5" />
                        Sync
                      </button>
                      <button type="button" className="muted-btn px-3 py-2 text-xs" onClick={() => props.onGrantAccess(employee)}>
                        <KeyRound className="h-3.5 w-3.5" />
                        Access
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {!props.grid?.items.length && !props.busy ? (
          <div className="px-6 py-16 text-center text-sm text-slate-500">{ka.noEvents}</div>
        ) : null}

        <div className="flex flex-col gap-4 border-t border-slate-100 px-5 py-4 md:flex-row md:items-center md:justify-between">
          <div className="flex flex-wrap items-center gap-3 text-sm text-slate-500">
            {props.busy ? <LoaderCircle className="h-4 w-4 animate-spin" /> : null}
            <span>Showing {shownCount} of {totalCount} employees</span>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <label className="text-sm text-slate-500">{ka.rowsPerPage}</label>
            <select className="input-shell" value={props.grid?.page_size ?? 12} onChange={(event) => props.onPageSizeChange(Number(event.target.value))}>
              {[8, 12, 20, 40].map((size) => (
                <option key={size} value={size}>{size}</option>
              ))}
            </select>
            <span className="text-sm text-slate-500">{ka.page} {currentPage} / {pageCount}</span>
            <button type="button" className="muted-btn px-3 py-2.5" onClick={() => props.onPageChange(Math.max(currentPage - 1, 1))}>
              {ka.previous}
            </button>
            <button type="button" className="muted-btn px-3 py-2.5" onClick={() => props.onPageChange(Math.min(currentPage + 1, pageCount))}>
              {ka.next}
            </button>
          </div>
        </div>
      </article>
    </section>
  )
}
