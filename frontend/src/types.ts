export type Summary = {
  active_employees: number
  terminated_employees: number
  pending_approvals: number
  online_devices: number
}

export type WidgetData = {
  summary: Summary
}

export type GridItem = {
  id: string
  employee_number: string
  first_name: string
  last_name: string
  email: string | null
  mobile_phone: string | null
  hire_date: string
  employment_status: string
  department_name: string | null
  job_title: string | null
  manager_name: string | null
  profile_photo_url: string | null
  base_salary: string | number
  hourly_rate_override: string | number
  has_login_access: boolean
}

export type GridResponse = {
  items: GridItem[]
  total: number
  page: number
  page_size: number
  page_count: number
}

export type OptionItem = {
  id: string
  name_en?: string
  name_ka?: string
  title_en?: string
  title_ka?: string
  code?: string
  name?: string
  full_name?: string
  device_name?: string
  brand?: string
  host?: string
}

export type EmployeeFormOptions = {
  legal_entity_id: string
  departments: OptionItem[]
  job_roles: OptionItem[]
  pay_policies: OptionItem[]
  managers: OptionItem[]
  devices: OptionItem[]
}

export type FeatureFlags = {
  attendance_enabled: boolean
  payroll_enabled: boolean
  ats_enabled: boolean
  chat_enabled: boolean
  assets_enabled: boolean
  org_chart_enabled: boolean
  performance_enabled: boolean
}

export type BootstrapData = {
  tenant: {
    legal_entity_id: string | null
    trade_name: string
    logo_url: string | null
    logo_text: string
    primary_color: string
    standalone_chat_url: string | null
    feature_flags: FeatureFlags
  }
}

export type FeedEvent = {
  event_type: 'attendance' | 'device' | 'web_punch'
  event_id: string
  ts: string
  direction: string
  employee_id: string | null
  first_name: string | null
  last_name: string | null
  employee_number: string | null
  device_name: string
  host: string
  device_status: string | null
}

export type TopPerformerRow = {
  employee_id: string
  full_name: string
  score: number
  status: 'present' | 'late' | 'absent'
}

export type AnalyticsOverview = {
  weekly_hours_trend: Array<{ label: string; worked_hours: number }>
  staff_presence_ratio: {
    present: number
    away: number
    total: number
  }
  top_performers: TopPerformerRow[]
}

export type NodeItem = {
  node_code: string
  node_role: string
  base_url: string | null
  region: string | null
  last_heartbeat_at: string | null
  metadata?: Record<string, unknown>
  service_name: string | null
  status: string | null
  details?: Record<string, unknown>
}

export type MonitoringData = {
  devices: Array<{
    id: string
    device_name: string
    brand: string
    host: string
    port: number
    last_seen_at: string | null
    connectivity: string
  }>
  nodes: NodeItem[]
}

export type AtsColumn = {
  code: string
  name_en: string
  name_ka: string
}

export type AtsCard = {
  id: string
  stage_code: string
  actual_stage_code: string
  first_name: string
  last_name: string
  email: string | null
  phone: string | null
  city: string | null
  posting_code: string
  job_title: string
  department_name: string | null
  applied_at: string | null
  owner_name: string
  salary_min: number | null
  salary_max: number | null
}

export type AtsBoardData = {
  legal_entity_id: string
  columns: AtsColumn[]
  cards: Record<string, AtsCard[]>
}

export type ShiftPatternSegment = {
  day_index: number
  start_time: string
  planned_minutes: number
  break_minutes: number
  crosses_midnight: boolean
  label: string | null
}

export type ShiftPattern = {
  id: string
  code: string
  name: string
  pattern_type: string
  cycle_length_days: number
  standard_weekly_hours: number
  segments: ShiftPatternSegment[]
}

export type ShiftEmployee = {
  id: string
  employee_number: string
  first_name: string
  last_name: string
  department_name: string | null
  job_title: string | null
  weekly_minutes: number
  weekly_minutes_map: Record<string, number>
  can_edit?: boolean
}

export type ShiftAssignment = {
  assignment_id: string
  employee_id: string
  shift_date: string
  shift_pattern_id: string
  pattern_name: string
  pattern_code: string
  planned_minutes: number
  start_time: string
  break_minutes: number
  crosses_midnight: boolean
  label: string
}

export type ShiftPlannerData = {
  month_start: string
  month_end: string
  calendar_title: string
  days: Array<{ date: string; label: string; day_index: number }>
  patterns: ShiftPattern[]
  employees: ShiftEmployee[]
  assignments: ShiftAssignment[]
  total: number
  page: number
  page_size: number
  page_count: number
  user_can_edit_shifts?: boolean
}

export type AttendanceHistoryItem = {
  id: string | number
  event_ts: string
  direction: string
  verify_mode: string | null
  device_name: string | null
  work_date?: string
  weekly_minutes?: number
  overtime_minutes?: number
  late_minutes?: number
  is_late?: boolean
  is_overtime?: boolean
  highlight_tags?: string[]
}

export type CelebrationItem = {
  id: string
  first_name: string
  last_name: string
  date: string | null
  day_of_month: number
  years_completed?: number
}

export type CelebrationHubData = {
  month: number
  birthdays: CelebrationItem[]
  anniversaries: CelebrationItem[]
}

export type TeamChatConfig = {
  linked: boolean
  mattermost_user_id: string | null
  mattermost_username: string | null
  server_base_url: string | null
  default_team: string | null
  preferred_channel: string | null
  channel_url: string | null
}

export type LeaveTypeOption = {
  id: string
  code: string
  name_en: string
  name_ka: string
  is_paid: boolean
  annual_allowance_days: number
}

export type LeaveRequestHistoryItem = {
  id: string
  start_date: string
  end_date: string
  requested_days: number
  status: string
  reason: string
  leave_type_name: string
}

export type LeaveSelfServiceData = {
  employee_id: string
  employee_name: string
  hire_date: string
  current_year: number
  months_worked: number
  statutory_earned_days: number
  earned_days: number
  used_days: number
  available_days: number
  opening_days: number
  adjusted_days: number
  primary_leave_type: {
    id: string
    name_en: string
    name_ka: string
    annual_allowance_days: number
  } | null
  leave_types: LeaveTypeOption[]
  requests: LeaveRequestHistoryItem[]
}

export type EmployeeDraft = {
  id?: string
  legal_entity_id: string
  employee_number: string
  personal_number: string
  first_name: string
  last_name: string
  email: string
  mobile_phone: string
  department_id: string
  job_role_id: string
  manager_employee_id: string
  hire_date: string
  base_salary: string
  pay_policy_id: string
  hourly_rate_override: string
  is_pension_participant: boolean
  default_device_user_id: string
  manager_name?: string
  profile_photo_url?: string
  new_job_role_title_ka: string
  new_job_role_title_en: string
  new_job_role_is_managerial: boolean
}

export type ShiftBuilderSegment = {
  day_index: number
  start_time: string
  end_time: string
  planned_minutes: number
  break_minutes: number
  crosses_midnight: boolean
  label: string | null
}

export type ShiftBuilderPattern = {
  id: string
  code: string
  name: string
  pattern_type: string
  cycle_length_days: number
  timezone: string
  standard_weekly_hours: number
  early_check_in_grace_minutes: number
  late_check_out_grace_minutes: number
  grace_period_minutes: number
  assignment_count: number
  segments: ShiftBuilderSegment[]
}

export type ShiftBuilderData = {
  patterns: ShiftBuilderPattern[]
}

export type WebPunchRecord = {
  id: string
  punch_ts: string
  direction: string
  source_ip: string | null
  latitude: number | null
  longitude: number | null
  is_valid: boolean
  validation_reason: string | null
}

export type WebPunchConfigData = {
  config: {
    allowed_web_punch_ips: string[]
    geofence_latitude: number | null
    geofence_longitude: number | null
    geofence_radius_meters: number | null
  }
  recent_punches: WebPunchRecord[]
}

export type AttendanceOverrideItem = {
  id: string
  employee_id: string
  employee_number: string
  first_name: string
  last_name: string
  session_id: string | null
  work_date: string
  flag_type: string
  severity: string
  details: string
  check_in_ts: string | null
  check_out_ts: string | null
  review_status: string | null
}

export type VacancyFieldOption = {
  label: string
  value: string
}

export type VacancyFieldDefinition = {
  key: string
  label: string
  field_type: string
  required: boolean
  options: VacancyFieldOption[]
}

export type VacancyItem = {
  id: string
  posting_code: string
  title_en: string
  title_ka: string
  description: string
  public_description: string | null
  employment_type: string
  status: string
  open_positions: number
  location_text: string | null
  public_slug: string | null
  external_form_url: string | null
  is_public: boolean
  application_form_schema: VacancyFieldDefinition[]
  salary_min: number
  salary_max: number
  closes_at: string | null
  department_name: string | null
  job_role_name: string | null
  application_count: number
  public_url: string | null
}

export type VacancyData = {
  items: VacancyItem[]
  departments: OptionItem[]
  job_roles: OptionItem[]
}

export type WarehouseItem = {
  id: string
  asset_tag: string
  asset_name: string
  brand: string | null
  model: string | null
  serial_number: string | null
  current_condition: string
  current_status: string
  purchase_date: string | null
  purchase_cost: number
  currency_code: string
  notes: string | null
  category_name: string | null
  assigned_employee_name: string | null
  active_assignment_id: string | null
}

export type WarehouseData = {
  categories: OptionItem[]
  employees: OptionItem[]
  items: WarehouseItem[]
}

export type PerformanceCycle = {
  id: string
  code: string
  title: string
  year: number
  quarter: number
  start_date: string
  end_date: string
}

export type PerformanceObjective = {
  id: string
  title: string
  scope: string
  weight: number
  department_name: string | null
  employee_name: string | null
  owner_name: string | null
  cycle_title: string
  key_result_count: number
  progress_percent: number
}

export type CapacityItem = {
  employee_id: string
  employee_name: string
  employee_number: string
  planned_hours: number
  objective_count: number
  utilization_score: number
  risk_band: string
}

export type PerformanceHubData = {
  cycles: PerformanceCycle[]
  objectives: PerformanceObjective[]
  heatmap: CapacityItem[]
  employees: OptionItem[]
}

export type PayrollHubItem = {
  id: string
  employee_id: string
  employee_number: string
  employee_name: string
  status: string
  gross_pay: number
  net_pay: number
  worked_hours: number
  overtime_hours: number
  payment_id: string | null
  paid_at: string | null
  payment_method: string | null
  payment_reference: string | null
  payslip_file_name: string | null
  payslip_url: string | null
}

export type PayrollHubData = {
  year: number
  month: number
  items: PayrollHubItem[]
}

export type DeviceRegistryItem = {
  id: string
  legal_entity_id: string
  tenant_name: string | null
  brand: string
  transport: string
  device_type: string
  device_name: string
  model: string
  serial_number: string
  host: string
  port: number
  api_base_url: string | null
  username: string | null
  password_ciphertext: string | null
  device_timezone: string
  is_active: boolean
  poll_interval_seconds: number
  metadata: Record<string, unknown>
  last_seen_at: string | null
}

export type DeviceRegistryData = {
  tenants: Array<{
    id: string
    trade_name: string
  }>
  items: DeviceRegistryItem[]
}

export type OrgChartNode = {
  id: string
  employee_number: string
  full_name: string
  manager_id: string | null
  manager_name: string | null
  department_name: string | null
  role_title: string | null
}

export type OrgChartData = {
  nodes: OrgChartNode[]
}

export type PersonalReportMovementItem = {
  id: string
  event_ts: string
  direction: string
  device_name: string
  source_type: string
}

export type PersonalReportsData = {
  movement_log: PersonalReportMovementItem[]
  summary: {
    month_start: string
    late_days: number
    overtime_hours: number
  }
  lateness_overtime_report: AttendanceHistoryItem[]
}

export type SystemConfigData = {
  legal_entity: {
    id: string
    legal_name: string
    trade_name: string
    tax_id: string
    timezone: string
    currency_code: string
  } | null
  access_context: {
    request_host: string | null
    tenant_isolation_active: boolean
  }
  tenants: Array<{
    id: string
    legal_name: string
    trade_name: string
    tax_id: string
    timezone: string
    currency_code: string
    primary_host: string | null
    employee_count: number
    login_count: number
  }>
  config: {
    logo_url: string | null
    logo_text: string | null
    primary_color: string
    standalone_chat_url: string | null
    allowed_web_punch_ips: string[]
    geofence_latitude: number | null
    geofence_longitude: number | null
    geofence_radius_meters: number | null
    late_arrival_threshold_minutes: number
    require_asset_clearance_for_final_payroll: boolean
    default_onboarding_course_id: string | null
  }
  pay_policies: Array<{
    id: string
    code: string
    name: string
    income_tax_rate: number
    employee_pension_rate: number
  }>
  roles: Array<{
    id: string
    code: string
    name_en: string
    name_ka: string
  }>
  employees: Array<{
    id: string
    employee_number: string
    full_name: string
    role_codes: string[]
  }>
  mattermost: {
    enabled: boolean
    server_base_url: string | null
    default_team: string | null
    hr_channel: string | null
    general_channel: string | null
    it_channel: string | null
  } | null
  subscriptions: FeatureFlags
  domains: Array<{
    id: string
    host: string
    subdomain: string | null
    is_primary: boolean
    is_active: boolean
  }>
  smtp: {
    configured: boolean
    host: string | null
    port: number
    username: string | null
    from_email: string | null
    use_tls: boolean
    managed_in: string
  }
  edge_middleware: {
    compose_file: string
    public_base_url: string
    device_workers_enabled: boolean
    ops_workers_enabled: boolean
  }
}
