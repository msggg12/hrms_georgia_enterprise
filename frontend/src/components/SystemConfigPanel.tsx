import { useEffect, useState } from 'react'

import { Building2, Globe2, Mail, MonitorCog, Palette, Route, Shield, ShieldCheck, Users2 } from 'lucide-react'

import type { FeatureFlags, SystemConfigData } from '../types'

type SystemConfigPanelProps = {
  data: SystemConfigData | null
  onSaveConfig: (payload: {
    trade_name: string | null
    logo_url: string | null
    logo_text: string | null
    primary_color: string
    standalone_chat_url: string | null
    allowed_web_punch_ips: string[]
    geofence_latitude: number | null
    geofence_longitude: number | null
    geofence_radius_meters: number | null
    income_tax_rate: number | null
    employee_pension_rate: number | null
    late_arrival_threshold_minutes: number
    require_asset_clearance_for_final_payroll: boolean
    default_onboarding_course_id: string | null
  }) => Promise<void>
  onSaveRoles: (employeeId: string, roleCodes: string[]) => Promise<void>
  onSaveSubscriptions: (payload: FeatureFlags) => Promise<void>
  onCreateTenant: (payload: {
    legal_name: string
    trade_name: string
    tax_id: string
    host: string | null
    subdomain: string | null
    admin_username: string
    admin_email: string
    admin_password: string
    admin_first_name: string
    admin_last_name: string
  }) => Promise<void>
  onSaveDomain: (domainId: string | null, payload: { host: string; subdomain: string | null; is_primary: boolean; is_active: boolean }) => Promise<void>
}

const emptyDomainForm = {
  host: '',
  subdomain: '',
  is_primary: false,
  is_active: true
}

const emptyTenantForm = {
  legal_name: '',
  trade_name: '',
  tax_id: '',
  host: '',
  subdomain: '',
  admin_username: '',
  admin_email: '',
  admin_password: 'ChangeMe123!',
  admin_first_name: 'Company',
  admin_last_name: 'Administrator'
}

const colorPresets = ['#0F172A', '#1E293B', '#243B53', '#1D4ED8', '#0F766E']

export function SystemConfigPanel(props: SystemConfigPanelProps) {
  const [busy, setBusy] = useState(false)
  const [selectedEmployeeId, setSelectedEmployeeId] = useState('')
  const [editingDomainId, setEditingDomainId] = useState<string | null>(null)
  const [domainForm, setDomainForm] = useState(emptyDomainForm)
  const [tenantForm, setTenantForm] = useState(emptyTenantForm)
  const [subscriptionForm, setSubscriptionForm] = useState<FeatureFlags>({
    attendance_enabled: true,
    payroll_enabled: true,
    ats_enabled: true,
    chat_enabled: true,
    assets_enabled: true,
    org_chart_enabled: true,
    performance_enabled: true
  })
  const [configForm, setConfigForm] = useState({
    trade_name: '',
    logo_url: '',
    logo_text: '',
    primary_color: '#0F172A',
    standalone_chat_url: '',
    allowed_web_punch_ips: '',
    geofence_latitude: '',
    geofence_longitude: '',
    geofence_radius_meters: '',
    income_tax_rate: '',
    employee_pension_rate: '',
    late_arrival_threshold_minutes: '15',
    require_asset_clearance_for_final_payroll: true,
    default_onboarding_course_id: ''
  })

  useEffect(() => {
    if (!props.data) {
      return
    }
    setConfigForm({
      trade_name: props.data.legal_entity?.trade_name ?? '',
      logo_url: props.data.config.logo_url ?? '',
      logo_text: props.data.config.logo_text ?? '',
      primary_color: props.data.config.primary_color,
      standalone_chat_url: props.data.config.standalone_chat_url ?? '',
      allowed_web_punch_ips: props.data.config.allowed_web_punch_ips.join(', '),
      geofence_latitude: props.data.config.geofence_latitude != null ? `${props.data.config.geofence_latitude}` : '',
      geofence_longitude: props.data.config.geofence_longitude != null ? `${props.data.config.geofence_longitude}` : '',
      geofence_radius_meters: props.data.config.geofence_radius_meters != null ? `${props.data.config.geofence_radius_meters}` : '',
      income_tax_rate: props.data.pay_policies[0] ? `${props.data.pay_policies[0].income_tax_rate}` : '',
      employee_pension_rate: props.data.pay_policies[0] ? `${props.data.pay_policies[0].employee_pension_rate}` : '',
      late_arrival_threshold_minutes: `${props.data.config.late_arrival_threshold_minutes}`,
      require_asset_clearance_for_final_payroll: props.data.config.require_asset_clearance_for_final_payroll,
      default_onboarding_course_id: props.data.config.default_onboarding_course_id ?? ''
    })
    setSubscriptionForm(props.data.subscriptions)
  }, [props.data])

  const selectedEmployee = props.data?.employees.find((item) => item.id === selectedEmployeeId) ?? null
  const canManageTenants = (props.data?.tenants.length ?? 0) > 0
  const requestHost = props.data?.access_context.request_host ?? 'unknown'
  const tenantScoped = props.data?.access_context.tenant_isolation_active ?? false

  async function handleSaveConfig() {
    setBusy(true)
    try {
      await props.onSaveConfig({
        trade_name: configForm.trade_name || null,
        logo_url: configForm.logo_url || null,
        logo_text: configForm.logo_text || null,
        primary_color: configForm.primary_color,
        standalone_chat_url: configForm.standalone_chat_url || null,
        allowed_web_punch_ips: configForm.allowed_web_punch_ips.split(',').map((item) => item.trim()).filter(Boolean),
        geofence_latitude: configForm.geofence_latitude ? Number(configForm.geofence_latitude) : null,
        geofence_longitude: configForm.geofence_longitude ? Number(configForm.geofence_longitude) : null,
        geofence_radius_meters: configForm.geofence_radius_meters ? Number(configForm.geofence_radius_meters) : null,
        income_tax_rate: configForm.income_tax_rate ? Number(configForm.income_tax_rate) : null,
        employee_pension_rate: configForm.employee_pension_rate ? Number(configForm.employee_pension_rate) : null,
        late_arrival_threshold_minutes: Number(configForm.late_arrival_threshold_minutes),
        require_asset_clearance_for_final_payroll: configForm.require_asset_clearance_for_final_payroll,
        default_onboarding_course_id: configForm.default_onboarding_course_id || null
      })
    } finally {
      setBusy(false)
    }
  }

  async function handleSaveSubscriptions() {
    setBusy(true)
    try {
      await props.onSaveSubscriptions(subscriptionForm)
    } finally {
      setBusy(false)
    }
  }

  async function handleSaveDomain() {
    setBusy(true)
    try {
      await props.onSaveDomain(editingDomainId, {
        host: domainForm.host.trim(),
        subdomain: domainForm.subdomain.trim() || null,
        is_primary: domainForm.is_primary,
        is_active: domainForm.is_active
      })
      setEditingDomainId(null)
      setDomainForm(emptyDomainForm)
    } finally {
      setBusy(false)
    }
  }

  async function handleCreateTenant() {
    setBusy(true)
    try {
      await props.onCreateTenant({
        legal_name: tenantForm.legal_name.trim(),
        trade_name: tenantForm.trade_name.trim(),
        tax_id: tenantForm.tax_id.trim(),
        host: tenantForm.host.trim() || null,
        subdomain: tenantForm.subdomain.trim() || null,
        admin_username: tenantForm.admin_username.trim(),
        admin_email: tenantForm.admin_email.trim(),
        admin_password: tenantForm.admin_password,
        admin_first_name: tenantForm.admin_first_name.trim(),
        admin_last_name: tenantForm.admin_last_name.trim()
      })
      setTenantForm(emptyTenantForm)
    } finally {
      setBusy(false)
    }
  }

  async function toggleRole(roleCode: string) {
    if (!selectedEmployee) {
      return
    }
    const nextRoles = selectedEmployee.role_codes.includes(roleCode)
      ? selectedEmployee.role_codes.filter((item) => item !== roleCode)
      : [...selectedEmployee.role_codes, roleCode]
    setBusy(true)
    try {
      await props.onSaveRoles(selectedEmployee.id, nextRoles)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="space-y-6">
      <section className="panel-card">
        <div className="mb-5 flex items-start justify-between gap-4">
          <div>
            <p className="section-kicker">Platform Setup</p>
            <h2 className="section-title">კომპანიები, დომენები და იზოლაცია</h2>
            <p className="mt-2 max-w-3xl text-sm text-slate-500">
              ერთი სერვერი შეიძლება ემსახურებოდეს რამდენიმე კომპანიას, მაგრამ მონაცემთა იზოლაცია ირთვება მხოლოდ
              კომპანიის host/subdomain-ით. პირდაპირი IP მხოლოდ პლატფორმის ადმინისტრირებისთვის არის მოსახერხებელი.
            </p>
          </div>
          <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm font-semibold text-slate-700">
            {props.data?.legal_entity?.trade_name ?? 'Entity'}
          </div>
        </div>

        <div className="grid gap-4 xl:grid-cols-[minmax(0,1.15fr)_minmax(360px,0.85fr)]">
          <div className="rounded-lg border border-slate-200 bg-white p-5">
            <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
              <Building2 className="h-4 w-4 text-slate-600" />
              მრავალკომპანიური რეჟიმი
            </div>
            <div className={`mt-4 rounded-lg border px-4 py-4 text-sm ${tenantScoped ? 'border-emerald-200 bg-emerald-50 text-emerald-800' : 'border-amber-200 bg-amber-50 text-amber-800'}`}>
              <p className="font-semibold">{tenantScoped ? 'კომპანიის იზოლაცია აქტიურია' : 'ახლა გახსნილი გაქვთ სერვერის პირდაპირი IP'}</p>
              <p className="mt-1 break-words">მიმდინარე host: {requestHost}</p>
              <p className="mt-2">
                {tenantScoped
                  ? 'ამ მისამართზე ხედავთ მხოლოდ ამ კომპანიის მონაცემებს და მის მომხმარებლებს.'
                  : 'ამ რეჟიმში პლატფორმის ადმინისტრატორი შეგიძლიათ, მაგრამ სხვადასხვა კომპანიის განცალკევებული ხედი host/subdomain-ით უნდა გახსნათ.'}
              </p>
            </div>

            <div className="mt-4 grid gap-3 md:grid-cols-3">
              <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-4">
                <p className="text-xs uppercase tracking-[0.18em] text-slate-400">ნაბიჯი 1</p>
                <p className="mt-2 text-sm font-semibold text-slate-900">დაამატე კომპანია</p>
                <p className="mt-1 text-sm text-slate-500">Legal name, tax ID, admin მომხმარებელი და host.</p>
              </div>
              <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-4">
                <p className="text-xs uppercase tracking-[0.18em] text-slate-400">ნაბიჯი 2</p>
                <p className="mt-2 text-sm font-semibold text-slate-900">გაუწერე host</p>
                <p className="mt-1 text-sm text-slate-500">მაგალითად: <code>company2.test.hr</code> ან საჯარო DNS host.</p>
              </div>
              <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-4">
                <p className="text-xs uppercase tracking-[0.18em] text-slate-400">ნაბიჯი 3</p>
                <p className="mt-2 text-sm font-semibold text-slate-900">შედით კომპანიის მისამართზე</p>
                <p className="mt-1 text-sm text-slate-500">ახალი admin მხოლოდ საკუთარი კომპანიის მონაცემებს მართავს.</p>
              </div>
            </div>
          </div>

          <div className="rounded-lg border border-slate-200 bg-white p-5">
            <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
              <Users2 className="h-4 w-4 text-slate-600" />
              კომპანიების სია
            </div>
            <div className="mt-4 space-y-3">
              {(props.data?.tenants ?? []).map((tenant) => (
                <div key={tenant.id} className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate font-semibold text-slate-900">{tenant.trade_name}</p>
                      <p className="mt-1 text-sm text-slate-500">{tenant.legal_name}</p>
                    </div>
                    <span className="subtle-badge">{tenant.employee_count} თანამშრომელი</span>
                  </div>
                  <div className="mt-3 grid gap-2 text-sm text-slate-600">
                    <p className="break-words"><span className="font-semibold text-slate-900">Host:</span> {tenant.primary_host ?? 'ჯერ არ არის მიბმული'}</p>
                    <p><span className="font-semibold text-slate-900">Tax ID:</span> {tenant.tax_id}</p>
                    <p><span className="font-semibold text-slate-900">Login:</span> {tenant.login_count}</p>
                  </div>
                </div>
              ))}
              {!props.data?.tenants.length ? (
                <div className="rounded-lg border border-dashed border-slate-200 px-4 py-6 text-sm text-slate-500">
                  აქ tenant სია მხოლოდ superadmin-ს უჩანს.
                </div>
              ) : null}
            </div>
          </div>
        </div>

        {canManageTenants ? (
          <div className="mt-6 rounded-lg border border-slate-200 bg-white p-5">
            <div className="mb-4 flex items-center gap-2 text-sm font-semibold text-slate-900">
              <Globe2 className="h-4 w-4 text-slate-600" />
              ახალი კომპანიის დამატება
            </div>
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              <input className="input-shell" value={tenantForm.legal_name} onChange={(event) => setTenantForm((current) => ({ ...current, legal_name: event.target.value }))} placeholder="იურიდიული სახელი" />
              <input className="input-shell" value={tenantForm.trade_name} onChange={(event) => setTenantForm((current) => ({ ...current, trade_name: event.target.value }))} placeholder="სავაჭრო სახელი" />
              <input className="input-shell" value={tenantForm.tax_id} onChange={(event) => setTenantForm((current) => ({ ...current, tax_id: event.target.value }))} placeholder="Tax ID" />
              <input className="input-shell" value={tenantForm.host} onChange={(event) => setTenantForm((current) => ({ ...current, host: event.target.value }))} placeholder="company2.test.hr" />
              <input className="input-shell" value={tenantForm.subdomain} onChange={(event) => setTenantForm((current) => ({ ...current, subdomain: event.target.value }))} placeholder="company2" />
              <input className="input-shell" value={tenantForm.admin_username} onChange={(event) => setTenantForm((current) => ({ ...current, admin_username: event.target.value }))} placeholder="admin username" />
              <input className="input-shell" value={tenantForm.admin_email} onChange={(event) => setTenantForm((current) => ({ ...current, admin_email: event.target.value }))} placeholder="admin@company2.ge" />
              <input className="input-shell" type="password" value={tenantForm.admin_password} onChange={(event) => setTenantForm((current) => ({ ...current, admin_password: event.target.value }))} placeholder="დროებითი პაროლი" />
              <input className="input-shell" value={tenantForm.admin_first_name} onChange={(event) => setTenantForm((current) => ({ ...current, admin_first_name: event.target.value }))} placeholder="ადმინის სახელი" />
              <input className="input-shell" value={tenantForm.admin_last_name} onChange={(event) => setTenantForm((current) => ({ ...current, admin_last_name: event.target.value }))} placeholder="ადმინის გვარი" />
            </div>
            <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
              <p className="text-sm text-slate-500">თუ host არ შეიყვანეთ და მხოლოდ subdomain ჩაწერეთ, სისტემა შექმნის ფორმატს <code>subdomain.test.hr</code>.</p>
              <button type="button" className="primary-btn" onClick={() => void handleCreateTenant()} disabled={busy}>
                {busy ? 'ინახება...' : 'კომპანიის დამატება'}
              </button>
            </div>
          </div>
        ) : null}
      </section>

      <section className="panel-card">
        <div className="mb-5 flex items-start justify-between gap-4">
          <div>
            <p className="section-kicker">Entity Settings</p>
            <h2 className="section-title">ბრენდინგი, წესები და ინფრასტრუქტურა</h2>
          </div>
          <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm font-semibold text-slate-700">
            {props.data?.legal_entity?.trade_name ?? 'Entity'}
          </div>
        </div>

        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(390px,0.9fr)]">
          <div className="space-y-6">
            <div className="rounded-lg border border-slate-200 bg-white p-5">
              <div className="mb-4 flex items-center gap-2 font-semibold text-slate-900">
                <Palette className="h-4 w-4 text-slate-700" />
                ბრენდინგი და ოპერაციული წესები
              </div>
              <div className="grid gap-4 md:grid-cols-2">
                <input className="input-shell" value={configForm.trade_name} onChange={(event) => setConfigForm((current) => ({ ...current, trade_name: event.target.value }))} placeholder="Trade name" />
                <input className="input-shell" value={configForm.logo_text} onChange={(event) => setConfigForm((current) => ({ ...current, logo_text: event.target.value }))} placeholder="Logo text" />
                <input className="input-shell md:col-span-2" value={configForm.logo_url} onChange={(event) => setConfigForm((current) => ({ ...current, logo_url: event.target.value }))} placeholder="Logo URL" />
                <input className="input-shell" type="color" value={configForm.primary_color} onChange={(event) => setConfigForm((current) => ({ ...current, primary_color: event.target.value }))} />
                <input className="input-shell" value={configForm.standalone_chat_url} onChange={(event) => setConfigForm((current) => ({ ...current, standalone_chat_url: event.target.value }))} placeholder="Mattermost URL" />
                <input className="input-shell md:col-span-2" value={configForm.allowed_web_punch_ips} onChange={(event) => setConfigForm((current) => ({ ...current, allowed_web_punch_ips: event.target.value }))} placeholder="Office IP-ები, მძიმით" />
                <input className="input-shell" value={configForm.geofence_latitude} onChange={(event) => setConfigForm((current) => ({ ...current, geofence_latitude: event.target.value }))} placeholder="Latitude" />
                <input className="input-shell" value={configForm.geofence_longitude} onChange={(event) => setConfigForm((current) => ({ ...current, geofence_longitude: event.target.value }))} placeholder="Longitude" />
                <input className="input-shell" value={configForm.geofence_radius_meters} onChange={(event) => setConfigForm((current) => ({ ...current, geofence_radius_meters: event.target.value }))} placeholder="Radius (m)" />
                <input className="input-shell" value={configForm.late_arrival_threshold_minutes} onChange={(event) => setConfigForm((current) => ({ ...current, late_arrival_threshold_minutes: event.target.value }))} placeholder="დაგვიანების ლიმიტი" />
                <input className="input-shell" value={configForm.income_tax_rate} onChange={(event) => setConfigForm((current) => ({ ...current, income_tax_rate: event.target.value }))} placeholder="Income tax" />
                <input className="input-shell" value={configForm.employee_pension_rate} onChange={(event) => setConfigForm((current) => ({ ...current, employee_pension_rate: event.target.value }))} placeholder="Pension rate" />
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                {colorPresets.map((color) => (
                  <button
                    key={color}
                    type="button"
                    className="h-9 w-9 rounded-full border border-slate-200"
                    style={{ backgroundColor: color }}
                    onClick={() => setConfigForm((current) => ({ ...current, primary_color: color }))}
                    aria-label={`Use color ${color}`}
                  />
                ))}
              </div>
              <label className="mt-4 flex items-center gap-2 text-sm text-slate-600">
                <input type="checkbox" checked={configForm.require_asset_clearance_for_final_payroll} onChange={(event) => setConfigForm((current) => ({ ...current, require_asset_clearance_for_final_payroll: event.target.checked }))} />
                საბოლოო payroll-მდე asset clearance სავალდებულოა
              </label>
              <button type="button" className="primary-btn mt-4" onClick={() => void handleSaveConfig()} disabled={busy}>
                {busy ? 'ინახება...' : 'კონფიგურაციის შენახვა'}
              </button>
            </div>

            <div className="rounded-lg border border-slate-200 bg-white p-5">
              <div className="mb-4 flex items-center gap-2 font-semibold text-slate-900">
                <Mail className="h-4 w-4 text-slate-700" />
                SMTP / ელფოსტა
              </div>
              <div className={`rounded-lg border px-4 py-3 text-sm ${props.data?.smtp.configured ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : 'border-amber-200 bg-amber-50 text-amber-700'}`}>
                {props.data?.smtp.configured ? 'SMTP გამართულია' : 'SMTP ჯერ გამართული არ არის'}
              </div>
              <div className="mt-4 grid gap-3 md:grid-cols-2">
                <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3">
                  <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Host</p>
                  <p className="mt-2 font-semibold text-slate-900">{props.data?.smtp.host ?? '-'}</p>
                </div>
                <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3">
                  <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Port / TLS</p>
                  <p className="mt-2 font-semibold text-slate-900">{props.data?.smtp.port ?? '-'} / {props.data?.smtp.use_tls ? 'TLS' : 'No TLS'}</p>
                </div>
                <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3">
                  <p className="text-xs uppercase tracking-[0.18em] text-slate-400">From</p>
                  <p className="mt-2 font-semibold text-slate-900">{props.data?.smtp.from_email ?? '-'}</p>
                </div>
                <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3">
                  <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Managed In</p>
                  <p className="mt-2 font-semibold text-slate-900">{props.data?.smtp.managed_in ?? '.env'}</p>
                </div>
              </div>
            </div>
          </div>

          <div className="space-y-4">
            <div className="rounded-lg border border-slate-200 bg-white p-5">
              <div className="flex items-center gap-2 font-semibold text-slate-900">
                <MonitorCog className="h-4 w-4 text-slate-700" />
                Edge middleware / Windows
              </div>
              <div className="mt-4 space-y-3 text-sm text-slate-600">
                <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3">
                  <p className="font-semibold text-slate-900">Central URL</p>
                  <p className="mt-1 break-words">{props.data?.edge_middleware.public_base_url}</p>
                </div>
                <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3">
                  <p className="font-semibold text-slate-900">Windows files</p>
                  <p className="mt-1"><code>deployment\\edge.env.windows.example</code></p>
                  <p className="mt-1"><code>deployment\\start-edge-windows.cmd</code></p>
                </div>
                <div className="rounded-lg border border-slate-950 bg-slate-950 px-4 py-4 text-xs text-slate-100">
                  <code className="whitespace-pre-wrap">copy deployment\\edge.env.windows.example .env.edge{'\n'}deployment\\start-edge-windows.cmd</code>
                </div>
                <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3">
                  Dahua reader სხვა ქსელში თუა, middleware უნდა გაეშვას იმავე LAN-ში, სადაც reader ჩანს.
                </div>
              </div>
            </div>

            <div className="rounded-lg border border-slate-200 bg-white p-5">
              <div className="flex items-center gap-2 font-semibold text-slate-900">
                <ShieldCheck className="h-4 w-4 text-slate-700" />
                მოდულები
              </div>
              <div className="mt-4 grid gap-3">
                {Object.entries(subscriptionForm).map(([key, value]) => (
                  <label key={key} className="flex items-center justify-between rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700">
                    <span>{key}</span>
                    <input
                      type="checkbox"
                      checked={value}
                      onChange={(event) => setSubscriptionForm((current) => ({ ...current, [key as keyof FeatureFlags]: event.target.checked }))}
                    />
                  </label>
                ))}
              </div>
              <button type="button" className="muted-btn mt-4" onClick={() => void handleSaveSubscriptions()} disabled={busy}>
                მოდულების შენახვა
              </button>
            </div>

            <div className="rounded-lg border border-slate-200 bg-white p-5">
              <div className="flex items-center gap-2 font-semibold text-slate-900">
                <Route className="h-4 w-4 text-slate-700" />
                მიმდინარე კომპანიის დომენები
              </div>
              <div className="mt-4 space-y-3">
                {(props.data?.domains ?? []).map((domain) => (
                  <button
                    key={domain.id}
                    type="button"
                    className="flex w-full items-center justify-between rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-left"
                    onClick={() => {
                      setEditingDomainId(domain.id)
                      setDomainForm({
                        host: domain.host,
                        subdomain: domain.subdomain ?? '',
                        is_primary: domain.is_primary,
                        is_active: domain.is_active
                      })
                    }}
                  >
                    <div>
                      <div className="font-medium text-slate-900">{domain.host}</div>
                      <div className="mt-1 text-xs text-slate-500">{domain.subdomain ?? 'subdomain არაა მითითებული'}</div>
                    </div>
                    <span className={`rounded-full px-2 py-1 text-[11px] font-semibold ${domain.is_primary ? 'bg-slate-900 text-white' : 'bg-slate-200 text-slate-700'}`}>
                      {domain.is_primary ? 'Primary' : 'Secondary'}
                    </span>
                  </button>
                ))}
              </div>
              <div className="mt-4 grid gap-3">
                <input className="input-shell" value={domainForm.host} onChange={(event) => setDomainForm((current) => ({ ...current, host: event.target.value }))} placeholder="company.test.hr" />
                <input className="input-shell" value={domainForm.subdomain} onChange={(event) => setDomainForm((current) => ({ ...current, subdomain: event.target.value }))} placeholder="company" />
                <label className="flex items-center gap-2 text-sm text-slate-600">
                  <input type="checkbox" checked={domainForm.is_primary} onChange={(event) => setDomainForm((current) => ({ ...current, is_primary: event.target.checked }))} />
                  Primary domain
                </label>
                <label className="flex items-center gap-2 text-sm text-slate-600">
                  <input type="checkbox" checked={domainForm.is_active} onChange={(event) => setDomainForm((current) => ({ ...current, is_active: event.target.checked }))} />
                  Active domain
                </label>
                <button type="button" className="muted-btn" onClick={() => void handleSaveDomain()} disabled={busy}>
                  დომენის შენახვა
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="panel-card">
        <div className="mb-5 flex items-center gap-3">
          <Shield className="h-5 w-5 text-slate-700" />
          <h2 className="section-title">როლები და წვდომები</h2>
        </div>
        <div className="grid gap-6 xl:grid-cols-[300px_minmax(0,1fr)]">
          <div className="rounded-lg border border-slate-200 bg-white p-4">
            <select className="input-shell w-full" value={selectedEmployeeId} onChange={(event) => setSelectedEmployeeId(event.target.value)}>
              <option value="">აირჩიეთ თანამშრომელი</option>
              {(props.data?.employees ?? []).map((employee) => (
                <option key={employee.id} value={employee.id}>
                  {employee.employee_number} - {employee.full_name}
                </option>
              ))}
            </select>
          </div>
          <div className="rounded-lg border border-slate-200 bg-white p-5">
            {selectedEmployee ? (
              <div className="space-y-3">
                <p className="font-semibold text-slate-900">{selectedEmployee.full_name}</p>
                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                  {(props.data?.roles ?? []).map((role) => {
                    const active = selectedEmployee.role_codes.includes(role.code)
                    return (
                      <button key={role.id} type="button" className={`rounded-lg border px-4 py-3 text-left text-sm font-semibold transition ${active ? 'border-slate-900 bg-slate-900 text-white' : 'border-slate-200 bg-slate-50 text-slate-700'}`} onClick={() => void toggleRole(role.code)} disabled={busy}>
                        <div>{role.name_ka}</div>
                        <div className="mt-1 text-xs uppercase tracking-[0.18em] opacity-80">{role.code}</div>
                      </button>
                    )
                  })}
                </div>
              </div>
            ) : (
              <p className="text-sm text-slate-500">აირჩიეთ თანამშრომელი, ვისაც role-ებს გადაანაწილებთ.</p>
            )}
          </div>
        </div>
      </section>
    </section>
  )
}
