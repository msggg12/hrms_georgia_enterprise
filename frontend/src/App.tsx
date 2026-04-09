import type { CSSProperties } from 'react'
import { useDeferredValue, useEffect, useMemo, useState } from 'react'

import { Bell, Fingerprint, Menu } from 'lucide-react'

import { deleteJson, getJson, login, logout, postForm, postJson, putJson, readToken } from './api'
import { AtsBoard } from './components/AtsBoard'
import { AttendanceModal } from './components/AttendanceModal'
import { CelebrationWidget } from './components/CelebrationWidget'
import { DeviceRegistryPanel } from './components/DeviceRegistryPanel'
import { EmployeeDrawer } from './components/EmployeeDrawer'
import { EmployeeGrid } from './components/EmployeeGrid'
import { HardwareSyncModal } from './components/HardwareSyncModal'
import { TopPerformers } from './components/TopPerformers'
import { LeaveCalculator } from './components/LeaveCalculator'
import { LiveFeed } from './components/LiveFeed'
import { MetricCards } from './components/MetricCards'
import { OrgChartPanel } from './components/OrgChartPanel'
import { PayrollHub } from './components/PayrollHub'
import { PersonalReportsPanel } from './components/PersonalReportsPanel'
import { PerformanceHub } from './components/PerformanceHub'
import { ShiftPlanner } from './components/ShiftPlanner'
import { ShiftBuilder } from './components/ShiftBuilder'
import { Sidebar } from './components/Sidebar'
import { ToastStack, type ToastItem } from './components/ToastStack'
import { SystemConfigPanel } from './components/SystemConfigPanel'
import { TeamChat } from './components/TeamChat'
import { VacancyManager } from './components/VacancyManager'
import { WarehousePanel } from './components/WarehousePanel'
import { WebPunchPanel } from './components/WebPunchPanel'
import { ka } from './i18n/ka'
import { resolveTenantBranding } from './tenantBranding'
import type {
  AnalyticsOverview,
  AtsCard,
  AtsBoardData,
  AttendanceHistoryItem,
  BootstrapData,
  CelebrationHubData,
  DeviceRegistryData,
  EmployeeDraft,
  EmployeeFormOptions,
  FeatureFlags,
  FeedEvent,
  GridItem,
  GridResponse,
  LeaveSelfServiceData,
  OrgChartData,
  PayrollHubData,
  PersonalReportsData,
  PerformanceHubData,
  ShiftAssignment,
  ShiftBuilderData,
  ShiftPlannerData,
  SystemConfigData,
  TeamChatConfig,
  VacancyData,
  WebPunchConfigData,
  WarehouseData,
  WeeklyAttendancePoint,
  WidgetData
} from './types'
import { defaultDraft, findShiftSegment } from './utils'

function formatDuration(seconds: number): string {
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const secs = seconds % 60
  return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`
}

type LoginState = {
  username: string
  password: string
}

type EmployeeDetail = {
  id: string
  legal_entity_id: string
  employee_number: string
  personal_number: string | null
  first_name: string
  last_name: string
  email: string | null
  mobile_phone: string | null
  hire_date: string
  department_id: string | null
  job_role_id: string | null
  manager_employee_id: string | null
  manager_name: string | null
  profile_photo_url: string | null
  default_device_user_id: string | null
  pay_policy_id: string | null
  base_salary: string | null
  hourly_rate_override: string | null
  is_pension_participant: boolean
}

type AuthMe = {
  employee_id: string
  legal_entity_id: string
  department_id: string | null
  role_codes: string[]
  permissions: string[]
  managed_department_ids: string[]
}

type AppSection = 'dashboard' | 'employees' | 'attendance' | 'leave' | 'payroll' | 'ats' | 'assets' | 'org_chart' | 'okrs' | 'team_chat' | 'settings'

const sectionCopy: Record<AppSection, { title: string; subtitle: string }> = {
  dashboard: { title: ka.dashboard, subtitle: ka.employeeHub },
  employees: { title: ka.employeeManagement, subtitle: ka.employeeHub },
  attendance: { title: ka.attendance, subtitle: ka.sectionAttendance },
  leave: { title: ka.leaveHub, subtitle: ka.requestLeave },
  payroll: { title: ka.payroll, subtitle: ka.sectionPayroll },
  ats: { title: ka.ats, subtitle: ka.sectionAts },
  assets: { title: ka.assets, subtitle: ka.sectionAssets },
  org_chart: { title: 'ორგსტრუქტურა', subtitle: 'უშუალო მენეჯერები და დამტკიცების იერარქია' },
  okrs: { title: ka.okrs, subtitle: ka.sectionOkrs },
  team_chat: { title: ka.teamChat, subtitle: ka.linkedAs },
  settings: { title: ka.settings, subtitle: ka.sectionSettings }
}

function shiftDateByMonths(baseDate: string, delta: number): string {
  const value = new Date(`${baseDate}T00:00:00`)
  value.setMonth(value.getMonth() + delta, 1)
  return value.toISOString().slice(0, 10)
}

function weekBucketKey(shiftDate: string): string {
  const value = new Date(`${shiftDate}T00:00:00`)
  const offset = (value.getDay() + 6) % 7
  value.setDate(value.getDate() - offset)
  return value.toISOString().slice(0, 10)
}

function summarizeWeeklyMinutes(assignments: ShiftAssignment[], employeeId: string): {
  weeklyMinutesMap: Record<string, number>
  maxWeeklyMinutes: number
} {
  const weeklyMinutesMap = assignments
    .filter((item) => item.employee_id === employeeId)
    .reduce<Record<string, number>>((acc, item) => {
      const key = weekBucketKey(item.shift_date)
      acc[key] = (acc[key] ?? 0) + item.planned_minutes
      return acc
    }, {})
  const maxWeeklyMinutes = Math.max(0, ...Object.values(weeklyMinutesMap))
  return { weeklyMinutesMap, maxWeeklyMinutes }
}

function rgbFromHex(hex: string): string {
  const normalized = hex.replace('#', '')
  if (normalized.length !== 6) {
    return '26 34 56'
  }
  const red = Number.parseInt(normalized.slice(0, 2), 16)
  const green = Number.parseInt(normalized.slice(2, 4), 16)
  const blue = Number.parseInt(normalized.slice(4, 6), 16)
  return `${red} ${green} ${blue}`
}

function moveCandidateLocally(current: AtsBoardData | null, applicationId: string, targetStage: string): AtsBoardData | null {
  if (!current) {
    return current
  }
  let movedCard: AtsCard | null = null
  const nextCards: AtsBoardData['cards'] = {}
  for (const column of current.columns) {
    nextCards[column.code] = (current.cards[column.code] ?? []).filter((card) => {
      if (card.id === applicationId) {
        movedCard = { ...card, stage_code: targetStage }
        return false
      }
      return true
    })
  }
  if (!movedCard) {
    return current
  }
  nextCards[targetStage] = [
    { ...movedCard, stage_code: targetStage },
    ...(nextCards[targetStage] ?? [])
  ]
  return { ...current, cards: nextCards }
}

function updateShiftPlannerLocally(
  current: ShiftPlannerData | null,
  employeeId: string,
  shiftPatternId: string,
  shiftDate: string
): ShiftPlannerData | null {
  if (!current) {
    return current
  }
  const pattern = current.patterns.find((item) => item.id === shiftPatternId)
  const segment = findShiftSegment(pattern, shiftDate)
  if (!pattern || !segment) {
    return current
  }
  const nextAssignments = current.assignments.filter((item) => !(item.employee_id === employeeId && item.shift_date === shiftDate))
  const assignment: ShiftAssignment = {
    assignment_id: `${employeeId}-${shiftDate}-${shiftPatternId}`,
    employee_id: employeeId,
    shift_date: shiftDate,
    shift_pattern_id: shiftPatternId,
    pattern_name: pattern.name,
    pattern_code: pattern.code,
    planned_minutes: segment.planned_minutes,
    start_time: segment.start_time,
    break_minutes: segment.break_minutes,
    crosses_midnight: segment.crosses_midnight,
    label: segment.label ?? pattern.name
  }
  nextAssignments.push(assignment)
  const nextEmployees = current.employees.map((employee) => {
    if (employee.id !== employeeId) {
      return employee
    }
    const { weeklyMinutesMap, maxWeeklyMinutes } = summarizeWeeklyMinutes(nextAssignments, employeeId)
    return { ...employee, weekly_minutes: maxWeeklyMinutes, weekly_minutes_map: weeklyMinutesMap }
  })
  return { ...current, assignments: nextAssignments, employees: nextEmployees }
}

function clearShiftLocally(current: ShiftPlannerData | null, employeeId: string, shiftDate: string): ShiftPlannerData | null {
  if (!current) {
    return current
  }
  const nextAssignments = current.assignments.filter((item) => !(item.employee_id === employeeId && item.shift_date === shiftDate))
  const nextEmployees = current.employees.map((employee) => {
    if (employee.id !== employeeId) {
      return employee
    }
    const { weeklyMinutesMap, maxWeeklyMinutes } = summarizeWeeklyMinutes(nextAssignments, employeeId)
    return { ...employee, weekly_minutes: maxWeeklyMinutes, weekly_minutes_map: weeklyMinutesMap }
  })
  return { ...current, assignments: nextAssignments, employees: nextEmployees }
}

export function App() {
  const fallbackBranding = resolveTenantBranding()
  const [token, setToken] = useState(readToken())
  const [activeSection, setActiveSection] = useState<AppSection>('dashboard')
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [toasts, setToasts] = useState<ToastItem[]>([])
  const [emailFilter, setEmailFilter] = useState('')
  const [phoneFilter, setPhoneFilter] = useState('')
  const [salaryMin, setSalaryMin] = useState('')
  const [salaryMax, setSalaryMax] = useState('')
  const [departmentFilter, setDepartmentFilter] = useState('')
  const [loginState, setLoginState] = useState<LoginState>({ username: 'superadmin', password: 'ChangeMe123!' })
  const [bootstrap, setBootstrap] = useState<BootstrapData | null>(null)
  const [currentUser, setCurrentUser] = useState<AuthMe | null>(null)
  const [summary, setSummary] = useState<WidgetData['summary'] | null>(null)
  const [grid, setGrid] = useState<GridResponse | null>(null)
  const [options, setOptions] = useState<EmployeeFormOptions | null>(null)
  const [feed, setFeed] = useState<FeedEvent[]>([])
  const [analytics, setAnalytics] = useState<AnalyticsOverview | null>(null)
  const [atsBoard, setAtsBoard] = useState<AtsBoardData | null>(null)
  const [shiftPlanner, setShiftPlanner] = useState<ShiftPlannerData | null>(null)
  const [celebrationData, setCelebrationData] = useState<CelebrationHubData | null>(null)
  const [leaveData, setLeaveData] = useState<LeaveSelfServiceData | null>(null)
  const [teamChatConfig, setTeamChatConfig] = useState<TeamChatConfig | null>(null)
  const [shiftBuilderData, setShiftBuilderData] = useState<ShiftBuilderData | null>(null)
  const [webPunchData, setWebPunchData] = useState<WebPunchConfigData | null>(null)
  const [vacancyData, setVacancyData] = useState<VacancyData | null>(null)
  const [warehouseData, setWarehouseData] = useState<WarehouseData | null>(null)
  const [weeklyAttendance, setWeeklyAttendance] = useState<WeeklyAttendancePoint[]>([])
  const [topElapsedSeconds, setTopElapsedSeconds] = useState(0)

  const latestValidWebPunch = useMemo(
    () => webPunchData?.recent_punches.find((item) => item.is_valid) ?? null,
    [webPunchData?.recent_punches],
  )
  const isTopCheckedIn = latestValidWebPunch?.direction === 'in'
  const topCheckInTime = useMemo(
    () => (isTopCheckedIn && latestValidWebPunch?.punch_ts ? new Date(latestValidWebPunch.punch_ts) : null),
    [isTopCheckedIn, latestValidWebPunch?.punch_ts],
  )
  const topWebPunchButtonLabel = isTopCheckedIn ? 'Web Check-Out' : 'Web Check-In'
  const topWebPunchTimerLabel = isTopCheckedIn ? 'Checked in' : 'Checked out'
  const [performanceHub, setPerformanceHub] = useState<PerformanceHubData | null>(null)

  useEffect(() => {
    if (!topCheckInTime) {
      setTopElapsedSeconds(0)
      return undefined
    }

    const updateTopElapsed = () => {
      setTopElapsedSeconds(Math.max(0, Math.floor((Date.now() - topCheckInTime.getTime()) / 1000)))
    }

    updateTopElapsed()
    const timer = window.setInterval(updateTopElapsed, 1000)
    return () => window.clearInterval(timer)
  }, [topCheckInTime])
  const [payrollHub, setPayrollHub] = useState<PayrollHubData | null>(null)
  const [systemConfig, setSystemConfig] = useState<SystemConfigData | null>(null)
  const [deviceRegistry, setDeviceRegistry] = useState<DeviceRegistryData | null>(null)
  const [orgChart, setOrgChart] = useState<OrgChartData | null>(null)
  const [personalReports, setPersonalReports] = useState<PersonalReportsData | null>(null)
  const [search, setSearch] = useState('')
  const [shiftSearch, setShiftSearch] = useState('')
  const deferredSearch = useDeferredValue(search)
  const deferredShiftSearch = useDeferredValue(shiftSearch)
  const [statusFilter, setStatusFilter] = useState('')
  const [sortBy, setSortBy] = useState<'employee_number' | 'full_name' | 'department_name' | 'job_title' | 'employment_status' | 'hire_date'>('employee_number')
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(12)
  const [shiftPage, setShiftPage] = useState(1)
  const [shiftMonthStart, setShiftMonthStart] = useState(() => {
    const today = new Date()
    today.setDate(1)
    return today.toISOString().slice(0, 10)
  })
  const [busy, setBusy] = useState(false)
  const [atsBusy, setAtsBusy] = useState(false)
  const [shiftBusy, setShiftBusy] = useState(false)
  const [importBusy, setImportBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [drawerMode, setDrawerMode] = useState<'create' | 'edit'>('create')
  const [drawerTab, setDrawerTab] = useState<'personal' | 'salary' | 'device'>('personal')
  const [draft, setDraft] = useState<EmployeeDraft>(defaultDraft(null))
  const [draftPhoto, setDraftPhoto] = useState<File | null>(null)
  const [attendanceOpen, setAttendanceOpen] = useState(false)
  const [attendanceEmployeeName, setAttendanceEmployeeName] = useState('')
  const [attendanceRows, setAttendanceRows] = useState<AttendanceHistoryItem[]>([])
  const [syncOpen, setSyncOpen] = useState(false)
  const [syncEmployee, setSyncEmployee] = useState<GridItem | null>(null)
  const [selectedDeviceIds, setSelectedDeviceIds] = useState<string[]>([])
  const featureFlags: FeatureFlags = bootstrap?.tenant.feature_flags ?? {
    attendance_enabled: true,
    payroll_enabled: true,
    ats_enabled: true,
    chat_enabled: true,
    assets_enabled: true,
    org_chart_enabled: true,
    performance_enabled: true
  }
  const branding = {
    companyName: bootstrap?.tenant.trade_name ?? fallbackBranding.companyName,
    logoText: bootstrap?.tenant.logo_text ?? fallbackBranding.logoText,
    primaryColor: bootstrap?.tenant.primary_color ?? fallbackBranding.primaryColor,
    primaryRgb: rgbFromHex(bootstrap?.tenant.primary_color ?? fallbackBranding.primaryColor)
  }
  const adminMode = Boolean(currentUser?.permissions.includes('employee.manage') || currentUser?.role_codes.includes('ADMIN'))
  const allowedSections: AppSection[] = adminMode
    ? ['dashboard', 'employees', 'attendance', 'leave', 'payroll', 'ats', 'assets', 'org_chart', 'okrs', 'team_chat', 'settings']
    : ['dashboard', 'leave', ...(featureFlags.chat_enabled ? ['team_chat' as const] : [])]
  const visibleSections = allowedSections.filter((section) => {
    const featureMap: Partial<Record<AppSection, boolean>> = {
      attendance: featureFlags.attendance_enabled,
      payroll: featureFlags.payroll_enabled,
      ats: featureFlags.ats_enabled,
      assets: featureFlags.assets_enabled,
      org_chart: featureFlags.org_chart_enabled,
      okrs: featureFlags.performance_enabled,
      team_chat: featureFlags.chat_enabled
    }
    return featureMap[section] ?? true
  })
  const topBarDate = new Intl.DateTimeFormat('en-US', {
    weekday: 'short',
    year: 'numeric',
    month: 'short',
    day: 'numeric'
  }).format(new Date())
  const topBarRole = currentUser?.role_codes[0] ?? 'EMPLOYEE'
  async function loadBootstrap() {
    setBootstrap(await getJson<BootstrapData>('/ux/bootstrap'))
  }

  async function loadEmployeeFormOptions() {
    const formOptions = await getJson<EmployeeFormOptions>('/ux/employee-form-options')
    setOptions(formOptions)
    return formOptions
  }

  async function loadWebPunchData() {
    const webPunch = await getJson<WebPunchConfigData>('/ux/web-punch-config')
    setWebPunchData(webPunch)
    return webPunch
  }

  async function loadStaticPanels() {
    const [
      bootstrapData,
      homeData,
      formOptions,
      analyticsData,
      atsData,
      celebrationHub,
      leaveSelfService,
      teamChat,
      shiftBuilder,
      webPunch,
      vacancies,
      warehouse,
      performanceData,
      payrollData,
      systemConfigData,
      deviceRegistryData,
      orgChartData,
      personalReportsData
    ] = await Promise.all([
      getJson<BootstrapData>('/ux/bootstrap'),
      getJson<WidgetData>('/ux/home-data'),
      loadEmployeeFormOptions(),
      getJson<AnalyticsOverview>('/ux/analytics-overview'),
      getJson<AtsBoardData>('/ux/ats-board'),
      getJson<CelebrationHubData>('/ux/celebration-hub'),
      getJson<LeaveSelfServiceData>('/ux/leave-self-service'),
      getJson<TeamChatConfig>('/ux/team-chat-config'),
      getJson<ShiftBuilderData>('/ux/shift-builder'),
      getJson<WebPunchConfigData>('/ux/web-punch-config'),
      getJson<VacancyData>('/ux/vacancies'),
      getJson<WarehouseData>('/ux/warehouse'),
      getJson<PerformanceHubData>('/ux/performance-hub'),
      getJson<PayrollHubData>('/ux/payroll-hub'),
      getJson<SystemConfigData>('/ux/system-config'),
      getJson<DeviceRegistryData>('/ux/device-registry'),
      getJson<OrgChartData>('/ux/org-chart'),
      getJson<PersonalReportsData>('/ux/personal-reports')
    ])
    setBootstrap(bootstrapData)
    setSummary(homeData.summary)
    setWeeklyAttendance(homeData.weekly_attendance)
    setAnalytics(analyticsData)
    setAtsBoard(atsData)
    setCelebrationData(celebrationHub)
    setLeaveData(leaveSelfService)
    setTeamChatConfig(teamChat)
    setShiftBuilderData(shiftBuilder)
    setWebPunchData(webPunch)
    setVacancyData(vacancies)
    setWarehouseData(warehouse)
    setPerformanceHub(performanceData)
    setPayrollHub(payrollData)
    setSystemConfig(systemConfigData)
    setDeviceRegistry(deviceRegistryData)
    setOrgChart(orgChartData)
    setPersonalReports(personalReportsData)
    setDraft((current) => (current.legal_entity_id ? current : defaultDraft(formOptions)))
  }

  async function loadSelfServicePanels() {
    const [bootstrapData, homeData, leaveSelfService, teamChat, personalReportsData] = await Promise.all([
      getJson<BootstrapData>('/ux/bootstrap'),
      getJson<WidgetData>('/ux/home-data'),
      getJson<LeaveSelfServiceData>('/ux/leave-self-service'),
      getJson<TeamChatConfig>('/ux/team-chat-config'),
      getJson<PersonalReportsData>('/ux/personal-reports')
    ])
    setBootstrap(bootstrapData)
    setSummary(homeData.summary)
    setWeeklyAttendance(homeData.weekly_attendance)
    setLeaveData(leaveSelfService)
    setTeamChatConfig(teamChat)
    setPersonalReports(personalReportsData)
    setGrid(null)
    setOptions(null)
    setFeed([])
  }

  async function loadLivePanels() {
    const liveFeed = await getJson<FeedEvent[]>('/ux/attendance-live-feed')
    setFeed(liveFeed)
  }

  async function loadAtsBoard() {
    setAtsBusy(true)
    try {
      setAtsBoard(await getJson<AtsBoardData>('/ux/ats-board'))
    } finally {
      setAtsBusy(false)
    }
  }

  async function loadShiftPlanner() {
    setShiftBusy(true)
    try {
      setShiftPlanner(await getJson<ShiftPlannerData>('/ux/shift-planner', {
        month_start: shiftMonthStart,
        search: deferredShiftSearch,
        page: shiftPage,
        page_size: 8
      }))
    } finally {
      setShiftBusy(false)
    }
  }

  async function loadAttendanceControlData() {
    const [builder, punch] = await Promise.all([
      getJson<ShiftBuilderData>('/ux/shift-builder'),
      getJson<WebPunchConfigData>('/ux/web-punch-config')
    ])
    setShiftBuilderData(builder)
    setWebPunchData(punch)
  }

  async function loadVacancyData() {
    setVacancyData(await getJson<VacancyData>('/ux/vacancies'))
  }

  async function loadWarehouseData() {
    setWarehouseData(await getJson<WarehouseData>('/ux/warehouse'))
  }

  async function loadPerformanceData() {
    setPerformanceHub(await getJson<PerformanceHubData>('/ux/performance-hub'))
  }

  async function loadPayrollData() {
    setPayrollHub(await getJson<PayrollHubData>('/ux/payroll-hub'))
  }

  async function loadSystemConfigData() {
    setSystemConfig(await getJson<SystemConfigData>('/ux/system-config'))
  }

  useEffect(() => {
    void loadBootstrap().catch(() => undefined)
  }, [])

  useEffect(() => {
    if (!token) {
      return
    }

    async function bootstrap() {
      let me: AuthMe
      try {
        me = await getJson<AuthMe>('/auth/me')
      } catch (err) {
        logout()
        setToken('')
        setCurrentUser(null)
        setError((err as Error).message)
        return
      }

      try {
        setCurrentUser(me)
        if (me.permissions.includes('employee.manage') || me.role_codes.includes('ADMIN')) {
          await Promise.all([loadStaticPanels(), loadLivePanels(), loadShiftPlanner()])
        } else {
          setActiveSection('dashboard')
          await loadSelfServicePanels()
        }
        setError('')
      } catch (err) {
        setError((err as Error).message)
      }
    }

    void bootstrap()
    let interval = 0
    if (adminMode) {
      interval = window.setInterval(() => {
        void loadLivePanels().catch((err: Error) => setError(err.message))
      }, 15000)
    }
    return () => {
      if (interval) {
        window.clearInterval(interval)
      }
    }
  }, [token, adminMode])

  useEffect(() => {
    if (!token || !adminMode) {
      return
    }

    async function loadGrid() {
      setBusy(true)
      try {
        const payload = await getJson<GridResponse>('/ux/employees-grid', {
          search: deferredSearch,
          status_filter: statusFilter,
          department_id: departmentFilter || null,
          email_contains: emailFilter || null,
          phone_contains: phoneFilter || null,
          salary_min: salaryMin ? Number(salaryMin) : null,
          salary_max: salaryMax ? Number(salaryMax) : null,
          sort_by: sortBy,
          sort_direction: sortDirection,
          page,
          page_size: pageSize
        })
        setGrid(payload)
        setError('')
      } catch (err) {
        setError((err as Error).message)
      } finally {
        setBusy(false)
      }
    }

    void loadGrid()
  }, [
    token,
    adminMode,
    deferredSearch,
    statusFilter,
    departmentFilter,
    emailFilter,
    phoneFilter,
    salaryMin,
    salaryMax,
    sortBy,
    sortDirection,
    page,
    pageSize
  ])

  useEffect(() => {
    if (!token || !notice) {
      return
    }
    setToasts((rows) => [...rows, { id: `ok-${Date.now()}`, tone: 'success', message: notice }])
    setNotice('')
  }, [token, notice])

  useEffect(() => {
    if (!token || !error) {
      return
    }
    setToasts((rows) => [...rows, { id: `err-${Date.now()}`, tone: 'error', message: error }])
    setError('')
  }, [token, error])

  useEffect(() => {
    setError('')
  }, [activeSection])

  useEffect(() => {
    if (!token || !adminMode) {
      return
    }
    void loadShiftPlanner().catch((err: Error) => setError(err.message))
  }, [token, adminMode, shiftMonthStart, deferredShiftSearch, shiftPage])

  useEffect(() => {
    const featureSectionMap: Array<[AppSection, boolean]> = [
      ['attendance', featureFlags.attendance_enabled],
      ['payroll', featureFlags.payroll_enabled],
      ['ats', featureFlags.ats_enabled],
      ['assets', featureFlags.assets_enabled],
      ['org_chart', featureFlags.org_chart_enabled],
      ['okrs', featureFlags.performance_enabled],
      ['team_chat', featureFlags.chat_enabled]
    ]
    const hiddenCurrentSection = featureSectionMap.find(([section, enabled]) => section === activeSection && !enabled)
    if (hiddenCurrentSection) {
      setActiveSection('dashboard')
    }
  }, [activeSection, featureFlags])

  async function handleLogin() {
    try {
      const response = await login(loginState.username, loginState.password)
      setToken(response.access_token)
      setNotice('')
      setError('')
    } catch (err) {
      setError((err as Error).message)
    }
  }

  function openCreateDrawer() {
    setDrawerMode('create')
    setDrawerTab('personal')
    setDraft(defaultDraft(options))
    setDraftPhoto(null)
    setDrawerOpen(true)
  }

  async function openEditDrawer(employee: GridItem) {
    const detail = await getJson<EmployeeDetail>(`/employees/${employee.id}`)
    setDrawerMode('edit')
    setDrawerTab('personal')
    setDraft({
      id: detail.id,
      legal_entity_id: detail.legal_entity_id,
      employee_number: detail.employee_number,
      personal_number: detail.personal_number ?? '',
      first_name: detail.first_name,
      last_name: detail.last_name,
      email: detail.email ?? '',
      mobile_phone: detail.mobile_phone ?? '',
      department_id: detail.department_id ?? '',
      job_role_id: detail.job_role_id ?? '',
      manager_employee_id: detail.manager_employee_id ?? '',
      manager_name: detail.manager_name ?? '',
      profile_photo_url: detail.profile_photo_url ?? '',
      hire_date: detail.hire_date,
      base_salary: detail.base_salary != null ? String(detail.base_salary) : '',
      pay_policy_id: detail.pay_policy_id ?? options?.pay_policies[0]?.id ?? '',
      hourly_rate_override: detail.hourly_rate_override ?? '',
      is_pension_participant: detail.is_pension_participant,
      default_device_user_id: detail.default_device_user_id ?? '',
      new_job_role_title_ka: '',
      new_job_role_title_en: '',
      new_job_role_is_managerial: false
    })
    setDraftPhoto(null)
    setDrawerOpen(true)
  }

  function openSyncModal(employee: GridItem) {
    setSyncEmployee(employee)
    setSelectedDeviceIds(options?.devices.map((device) => device.id) ?? [])
    setSyncOpen(true)
  }

  async function refreshAfterMutation() {
    const [homeData, gridData, orgChartData, personalReportsData] = await Promise.all([
      getJson<WidgetData>('/ux/home-data'),
      getJson<GridResponse>('/ux/employees-grid', {
        search: deferredSearch,
        status_filter: statusFilter,
        department_id: departmentFilter || null,
        email_contains: emailFilter || null,
        phone_contains: phoneFilter || null,
        salary_min: salaryMin ? Number(salaryMin) : null,
        salary_max: salaryMax ? Number(salaryMax) : null,
        sort_by: sortBy,
        sort_direction: sortDirection,
        page,
        page_size: pageSize
      }),
      getJson<OrgChartData>('/ux/org-chart'),
      getJson<PersonalReportsData>('/ux/personal-reports')
    ])
    setSummary(homeData.summary)
    setGrid(gridData)
    setOrgChart(orgChartData)
    setPersonalReports(personalReportsData)
  }

  async function importEmployees(file: File) {
    if (!options?.legal_entity_id) {
      setError('იურიდიული ერთეულის კონფიგურაცია ვერ მოიძებნა')
      return
    }

    setImportBusy(true)
    try {
      const form = new FormData()
      form.append('file', file)
      form.append('legal_entity_id', options.legal_entity_id)
      const response = await postForm<{ created_count: number; updated_count: number; skipped_count: number }>('/employees/import', form)
      await loadEmployeeFormOptions()
      await refreshAfterMutation()
      setNotice(`Import complete: ${response.created_count} created, ${response.updated_count} updated, ${response.skipped_count} skipped.`)
      setError('')
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setImportBusy(false)
    }
  }

  async function submitEmployee() {
    let jobRoleId = draft.job_role_id || null
    if (draft.new_job_role_title_ka.trim() || draft.new_job_role_title_en.trim()) {
      try {
        const role = await postJson<{ id: string }>('/job-roles', {
          legal_entity_id: draft.legal_entity_id,
          title_ka: draft.new_job_role_title_ka,
          title_en: draft.new_job_role_title_en || null,
          is_managerial: draft.new_job_role_is_managerial
        })
        jobRoleId = role.id
        await loadEmployeeFormOptions()
      } catch (err) {
        setError((err as Error).message)
        return
      }
    }

    const payload = {
      legal_entity_id: draft.legal_entity_id,
      employee_number: draft.employee_number,
      personal_number: draft.personal_number || null,
      first_name: draft.first_name,
      last_name: draft.last_name,
      email: draft.email || null,
      mobile_phone: draft.mobile_phone || null,
      department_id: draft.department_id || null,
      job_role_id: jobRoleId,
      manager_employee_id: draft.manager_employee_id || null,
      hire_date: draft.hire_date,
      base_salary: Number(draft.base_salary || 0),
      pay_policy_id: draft.pay_policy_id,
      hourly_rate_override: draft.hourly_rate_override ? Number(draft.hourly_rate_override) : null,
      is_pension_participant: draft.is_pension_participant,
      access_role_codes: ['EMPLOYEE'],
      default_device_user_id: draft.default_device_user_id || null
    }

    try {
      let employeeId = draft.id ?? ''
      if (drawerMode === 'create') {
        const response = await postJson<{ employee_id: string }>('/employees', payload)
        employeeId = response.employee_id
      } else if (draft.id) {
        await putJson(`/employees/${draft.id}`, {
          first_name: payload.first_name,
          last_name: payload.last_name,
          email: payload.email,
          mobile_phone: payload.mobile_phone,
          department_id: payload.department_id,
          job_role_id: payload.job_role_id,
          manager_employee_id: payload.manager_employee_id,
          base_salary: payload.base_salary,
          pay_policy_id: payload.pay_policy_id,
          hourly_rate_override: payload.hourly_rate_override,
          is_pension_participant: payload.is_pension_participant,
          default_device_user_id: payload.default_device_user_id
        })
        employeeId = draft.id
      }
      if (employeeId && draftPhoto) {
        const photoForm = new FormData()
        photoForm.append('photo', draftPhoto)
        await postForm(`/employees/${employeeId}/profile-photo`, photoForm)
      }
      setDrawerOpen(false)
      setDraftPhoto(null)
      await refreshAfterMutation()
      setNotice(drawerMode === 'create' ? 'თანამშრომელი დაემატა' : 'თანამშრომლის პროფილი განახლდა')
      setError('')
    } catch (err) {
      setError((err as Error).message)
    }
  }

  async function submitSync() {
    if (!syncEmployee) {
      return
    }
    try {
      await postJson(`/employees/${syncEmployee.id}/device-sync`, { device_ids: selectedDeviceIds })
      setSyncOpen(false)
      await loadLivePanels()
      setError('')
    } catch (err) {
      setError((err as Error).message)
    }
  }

  async function submitLeaveRequest(payload: { leave_type_id: string; start_date: string; end_date: string; reason: string }) {
    try {
      await postJson('/integrations/mattermost/leave-requests', payload)
      setLeaveData(await getJson<LeaveSelfServiceData>('/ux/leave-self-service'))
      setNotice('შვებულების მოთხოვნა გაიგზავნა')
      setError('')
    } catch (err) {
      setError((err as Error).message)
    }
  }

  async function submitSickLeave(payload: { start_date: string; end_date: string; reason: string; doctor_note: File | null }) {
    const form = new FormData()
    form.append('start_date', payload.start_date)
    form.append('end_date', payload.end_date)
    form.append('reason', payload.reason)
    if (payload.doctor_note) {
      form.append('doctor_note', payload.doctor_note)
    }
    try {
      await postForm('/ess/leave/sick', form)
      setLeaveData(await getJson<LeaveSelfServiceData>('/ux/leave-self-service'))
      setNotice('ბიულეტინი დარეგისტრირდა')
      setError('')
    } catch (err) {
      setError((err as Error).message)
    }
  }

  async function viewAttendance(employee: GridItem) {
    try {
      const rows = await getJson<AttendanceHistoryItem[]>(`/ux/employee-attendance/${employee.id}`)
      setAttendanceEmployeeName(`${employee.first_name} ${employee.last_name}`)
      setAttendanceRows(rows)
      setAttendanceOpen(true)
      setError('')
    } catch (err) {
      setError((err as Error).message)
    }
  }

  async function moveAtsCard(applicationId: string, targetStage: string) {
    const previousBoard = atsBoard
    setAtsBoard((current) => moveCandidateLocally(current, applicationId, targetStage))
    try {
      const card = previousBoard ? Object.values(previousBoard.cards).flat().find((item) => item.id === applicationId) : null
      const payload: Record<string, unknown> = { stage_code: targetStage }
      if (targetStage === 'HIRED') {
        const payPolicyId = options?.pay_policies[0]?.id
        if (!payPolicyId) {
          throw new Error('No pay policy configured for hire conversion')
        }
        payload.hire_payload = {
          hire_date: new Date().toISOString().slice(0, 10),
          pay_policy_id: payPolicyId,
          base_salary: card?.salary_max ?? card?.salary_min ?? 0,
          access_role_codes: ['EMPLOYEE']
        }
      }
      await postJson(`/ats/applications/${applicationId}/move`, payload)
      await loadAtsBoard()
      setError('')
    } catch (err) {
      setAtsBoard(previousBoard)
      setError((err as Error).message)
    }
  }

  async function assignShift(employeeId: string, shiftPatternId: string, shiftDate: string) {
    const previousPlanner = shiftPlanner
    setShiftPlanner((current) => updateShiftPlannerLocally(current, employeeId, shiftPatternId, shiftDate))
    try {
      const res = await postJson<{ over_40h_warning?: boolean }>('/ux/shift-planner/assignments', {
        employee_id: employeeId,
        shift_pattern_id: shiftPatternId,
        shift_date: shiftDate
      })
      await loadShiftPlanner()
      setError('')
      if (res.over_40h_warning) {
        setToasts((rows) => [
          ...rows,
          {
            id: `w-${Date.now()}`,
            tone: 'warning',
            message: 'გაფრთხილება: ამ კვირის გეგმილი საათები აღემატება 40 საათს.'
          }
        ])
      }
    } catch (err) {
      setShiftPlanner(previousPlanner)
      setError((err as Error).message)
    }
  }

  async function clearShift(employeeId: string, shiftDate: string) {
    const previousPlanner = shiftPlanner
    setShiftPlanner((current) => clearShiftLocally(current, employeeId, shiftDate))
    try {
      await deleteJson(`/ux/shift-planner/assignments/${employeeId}/${shiftDate}`)
      await loadShiftPlanner()
      setError('')
    } catch (err) {
      setShiftPlanner(previousPlanner)
      setError((err as Error).message)
    }
  }

  async function saveShiftPattern(
    patternId: string | null,
    payload: {
      code: string
      name: string
      pattern_type: string
      cycle_length_days: number
      timezone: string
      standard_weekly_hours: number
      early_check_in_grace_minutes: number
      late_check_out_grace_minutes: number
      grace_period_minutes: number
      segments: Array<{ day_index: number; start_time: string; end_time: string; break_minutes: number; label: string | null }>
    }
  ) {
    try {
      if (patternId) {
        await putJson(`/shifts/patterns/${patternId}`, payload)
      } else {
        await postJson('/shifts/patterns', payload)
      }
      await Promise.all([loadAttendanceControlData(), loadShiftPlanner()])
      setError('')
    } catch (err) {
      setError((err as Error).message)
      throw err
    }
  }

  async function submitWebPunch(payload: { direction: string; latitude: number | null; longitude: number | null }) {
    try {
      await postJson('/attendance/web-punch', payload)
      await Promise.all([loadAttendanceControlData(), loadLivePanels(), loadWebPunchData()])
      setError('')
    } catch (err) {
      setError((err as Error).message)
      throw err
    }
  }

  async function headerWebCheckIn() {
    try {
      const direction = isTopCheckedIn ? 'out' : 'in'
      await submitWebPunch({ direction, latitude: null, longitude: null })
      setNotice(direction === 'in' ? 'Web Check-In ჩაიწერა' : 'Web Check-Out ჩაიწერა')
    } catch {
      /* toast via submitWebPunch error path */
    }
  }

  async function saveVacancy(
    vacancyId: string | null,
    payload: {
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
      application_form_schema: Array<{ key: string; label: string; field_type: string; required: boolean; options: Array<{ label: string; value: string }> }>
    }
  ) {
    try {
      if (vacancyId) {
        await putJson(`/vacancies/${vacancyId}`, payload)
      } else {
        await postJson('/vacancies', payload)
      }
      await Promise.all([loadVacancyData(), loadAtsBoard()])
      setError('')
    } catch (err) {
      setError((err as Error).message)
      throw err
    }
  }

  async function saveInventoryItem(
    itemId: string | null,
    payload: {
      category_id: string | null
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
      assigned_department_id: string | null
      notes: string | null
    }
  ) {
    try {
      if (itemId) {
        await putJson(`/inventory/items/${itemId}`, payload)
      } else {
        await postJson('/inventory/items', payload)
      }
      await loadWarehouseData()
      setError('')
    } catch (err) {
      setError((err as Error).message)
      throw err
    }
  }

  async function assignInventoryItem(
    itemId: string,
    payload: {
      employee_id: string
      assigned_at: string
      expected_return_at: string | null
      condition_on_issue: string
      note: string | null
      employee_signature_name: string
    }
  ) {
    try {
      await postJson(`/inventory/items/${itemId}/assign`, payload)
      await loadWarehouseData()
      setError('')
    } catch (err) {
      setError((err as Error).message)
      throw err
    }
  }

  async function grantAccess(employee: GridItem) {
    try {
      const response = await postJson<{ username: string; temporary_password: string; invite_link: string }>(`/employees/${employee.id}/grant-access`, {})
      setNotice(`წვდომა გაიცა: ${response.username} / ${response.temporary_password}`)
      await refreshAfterMutation()
      setError('')
    } catch (err) {
      setError((err as Error).message)
    }
  }

  async function saveDeviceRegistryItem(
    deviceId: string | null,
    payload: {
      legal_entity_id: string
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
    }
  ) {
    try {
      if (deviceId) {
        await putJson(`/devices/registry/${deviceId}`, payload)
      } else {
        await postJson('/devices/registry', payload)
      }
      setDeviceRegistry(await getJson<DeviceRegistryData>('/ux/device-registry'))
      setNotice('მოწყობილობის რეესტრი განახლდა')
      setError('')
    } catch (err) {
      setError((err as Error).message)
      throw err
    }
  }

  async function createObjective(payload: {
    cycle_id: string
    scope: string
    title: string
    description: string | null
    department_id: string | null
    employee_id: string | null
    owner_employee_id: string | null
    weight: number
    key_result_title: string
    metric_unit: string
    target_value: number
  }) {
    try {
      const objectiveResponse = await postJson<{ objective_id: string }>('/performance/objectives', {
        cycle_id: payload.cycle_id,
        scope: payload.scope,
        title: payload.title,
        description: payload.description,
        department_id: payload.department_id,
        employee_id: payload.employee_id,
        owner_employee_id: payload.owner_employee_id,
        weight: payload.weight
      })
      await postJson('/performance/key-results', {
        objective_id: objectiveResponse.objective_id,
        title: payload.key_result_title,
        metric_unit: payload.metric_unit,
        start_value: 0,
        target_value: payload.target_value,
        current_value: 0
      })
      await loadPerformanceData()
      setError('')
    } catch (err) {
      setError((err as Error).message)
      throw err
    }
  }

  async function markPaid(timesheetId: string, payload: { payment_method: string; payment_reference: string | null; note: string | null }) {
    try {
      await postJson(`/payroll/timesheets/${timesheetId}/mark-paid`, payload)
      await loadPayrollData()
      setError('')
    } catch (err) {
      setError((err as Error).message)
      throw err
    }
  }

  async function saveSystemConfig(payload: {
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
  }) {
    if (!options?.legal_entity_id) {
      return
    }
    try {
      await putJson(`/system/config/${options.legal_entity_id}`, payload)
      await Promise.all([loadSystemConfigData(), loadStaticPanels()])
      setError('')
    } catch (err) {
      setError((err as Error).message)
      throw err
    }
  }

  async function saveEmployeeRoles(employeeId: string, roleCodes: string[]) {
    try {
      await putJson(`/rbac/employees/${employeeId}/roles`, { role_codes: roleCodes })
      await loadSystemConfigData()
      setError('')
    } catch (err) {
      setError((err as Error).message)
      throw err
    }
  }

  async function saveSubscriptions(payload: FeatureFlags) {
    if (!options?.legal_entity_id) {
      return
    }
    try {
      await putJson(`/system/tenants/${options.legal_entity_id}/subscriptions`, payload)
      await loadSystemConfigData()
      await loadBootstrap()
      setNotice('Tenant მოდულები განახლდა')
      setError('')
    } catch (err) {
      setError((err as Error).message)
      throw err
    }
  }

  async function createTenant(payload: {
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
  }) {
    try {
      const response = await postJson<{ legal_entity_id: string; admin_username: string }>('/system/tenants', payload)
      await loadSystemConfigData()
      setNotice(`კომპანია დაემატა. ადმინი: ${response.admin_username}`)
      setError('')
    } catch (err) {
      setError((err as Error).message)
      throw err
    }
  }

  async function saveTenantDomain(
    domainId: string | null,
    payload: { host: string; subdomain: string | null; is_primary: boolean; is_active: boolean }
  ) {
    if (!options?.legal_entity_id) {
      return
    }
    try {
      if (domainId) {
        await putJson(`/system/tenants/domains/${domainId}`, payload)
      } else {
        await postJson(`/system/tenants/${options.legal_entity_id}/domains`, payload)
      }
      await Promise.all([loadSystemConfigData(), loadBootstrap()])
      setNotice('Tenant domain განახლდა')
      setError('')
    } catch (err) {
      setError((err as Error).message)
      throw err
    }
  }

  function renderSection() {
    switch (activeSection) {
      case 'dashboard':
        return (
          <div className="space-y-6">
            <MetricCards summary={summary} weeklyAttendance={weeklyAttendance} onViewAttendance={() => setActiveSection('attendance')} />
            {adminMode ? (
              <>
                <div className="grid gap-6 xl:grid-cols-[minmax(0,1.15fr)_minmax(320px,0.85fr)]">
                  <LiveFeed feed={feed} />
                  <TopPerformers analytics={analytics} />
                </div>
                <CelebrationWidget data={celebrationData} />
              </>
            ) : (
              <PersonalReportsPanel data={personalReports} />
            )}
          </div>
        )
      case 'employees':
        return (
          <EmployeeGrid
            grid={grid}
            busy={busy}
            importBusy={importBusy}
            search={search}
            statusFilter={statusFilter}
            departmentFilter={departmentFilter}
            emailFilter={emailFilter}
            phoneFilter={phoneFilter}
            salaryMin={salaryMin}
            salaryMax={salaryMax}
            departments={options?.departments ?? []}
            sortBy={sortBy}
            sortDirection={sortDirection}
            onSearchChange={(value) => {
              setSearch(value)
              setPage(1)
            }}
            onStatusFilterChange={(value) => {
              setStatusFilter(value)
              setPage(1)
            }}
            onDepartmentFilterChange={(value) => {
              setDepartmentFilter(value)
              setPage(1)
            }}
            onEmailFilterChange={(value) => {
              setEmailFilter(value)
              setPage(1)
            }}
            onPhoneFilterChange={(value) => {
              setPhoneFilter(value)
              setPage(1)
            }}
            onSalaryMinChange={(value) => {
              setSalaryMin(value)
              setPage(1)
            }}
            onSalaryMaxChange={(value) => {
              setSalaryMax(value)
              setPage(1)
            }}
            onSortByChange={setSortBy}
            onToggleSortDirection={() => setSortDirection((current) => (current === 'asc' ? 'desc' : 'asc'))}
            onOpenCreate={openCreateDrawer}
            onOpenEdit={(employee) => void openEditDrawer(employee)}
            onOpenSync={openSyncModal}
            onGrantAccess={(employee) => void grantAccess(employee)}
            onViewAttendance={(employee) => void viewAttendance(employee)}
            onPageChange={setPage}
            onPageSizeChange={(size) => {
              setPageSize(size)
              setPage(1)
            }}
            onImport={(file) => void importEmployees(file)}
          />
        )
      case 'attendance':
        return (
          <div className="space-y-6">
            <ShiftBuilder data={shiftBuilderData} onSave={saveShiftPattern} />
            <WebPunchPanel data={webPunchData} onSubmit={submitWebPunch} />
            <ShiftPlanner
              data={shiftPlanner}
              busy={shiftBusy}
              search={shiftSearch}
              onSearchChange={(value) => {
                setShiftSearch(value)
                setShiftPage(1)
              }}
              onPreviousWeek={() => setShiftMonthStart((current) => shiftDateByMonths(current, -1))}
              onNextWeek={() => setShiftMonthStart((current) => shiftDateByMonths(current, 1))}
              onAssign={assignShift}
              onClear={clearShift}
              onPageChange={setShiftPage}
            />
            <LiveFeed feed={feed} />
          </div>
        )
      case 'payroll':
        return <PayrollHub data={payrollHub} onMarkPaid={markPaid} />
      case 'leave':
        return (
          <div className="space-y-6">
            <LeaveCalculator data={leaveData} onSubmit={submitLeaveRequest} onSubmitSick={submitSickLeave} />
            <PersonalReportsPanel data={personalReports} />
          </div>
        )
      case 'ats':
        return (
          <div className="space-y-6">
            <VacancyManager data={vacancyData} onSave={saveVacancy} />
            <AtsBoard board={atsBoard} busy={atsBusy} onMoveCard={moveAtsCard} />
          </div>
        )
      case 'assets':
        return <WarehousePanel data={warehouseData} onSaveItem={saveInventoryItem} onAssign={assignInventoryItem} />
      case 'org_chart':
        return <OrgChartPanel data={orgChart} />
      case 'okrs':
        return <PerformanceHub data={performanceHub} onCreateObjective={createObjective} />
      case 'team_chat':
        return <TeamChat config={teamChatConfig} />
      case 'settings':
        return (
          <div className="space-y-6">
            <SystemConfigPanel
              data={systemConfig}
              onSaveConfig={saveSystemConfig}
              onSaveRoles={saveEmployeeRoles}
              onSaveSubscriptions={saveSubscriptions}
              onCreateTenant={createTenant}
              onSaveDomain={saveTenantDomain}
            />
            <DeviceRegistryPanel
              data={deviceRegistry}
              legalEntityId={options?.legal_entity_id ?? ''}
              onSave={saveDeviceRegistryItem}
            />
          </div>
        )
      default:
        return null
    }
  }

  if (!token) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-50 px-6 py-12">
        <section className="grid w-full max-w-md gap-4 rounded-lg border border-slate-200 bg-white p-8 shadow-sm">
          <div>
            <p className="text-xs uppercase tracking-[0.34em] text-slate-400">{bootstrap?.tenant.trade_name ?? 'Georgia Enterprise HRMS'}</p>
            <h1 className="mt-3 text-3xl font-semibold text-slate-950">{ka.login}</h1>
            <p className="mt-2 text-sm text-slate-500">კორპორაციული HRMS პორტალი თანამშრომლების, attendance, approvals და payroll პროცესებისთვის.</p>
          </div>
          <input className="input-shell" value={loginState.username} onChange={(event) => setLoginState((current) => ({ ...current, username: event.target.value }))} placeholder={ka.username} />
          <input className="input-shell" type="password" value={loginState.password} onChange={(event) => setLoginState((current) => ({ ...current, password: event.target.value }))} placeholder={ka.password} />
          <button className="primary-btn" onClick={() => void handleLogin()}>
            {ka.login}
          </button>
          {error ? <p className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-600 break-words whitespace-pre-wrap">{error}</p> : null}
        </section>
      </main>
    )
  }

  return (
    <div
      className="min-h-screen bg-[var(--page-bg)] p-3 sm:p-4"
      style={
        {
          ['--brand-primary' as string]: branding.primaryColor,
          ['--brand-primary-rgb' as string]: branding.primaryRgb
        } as CSSProperties
      }
    >
      {mobileMenuOpen ? (
        <button
          type="button"
          className="fixed inset-0 z-40 bg-slate-950/60 lg:hidden"
          aria-label="დახურვა"
          onClick={() => setMobileMenuOpen(false)}
        />
      ) : null}
      <div className="page-layout-card flex min-h-[calc(100vh-24px)] overflow-hidden">
      <Sidebar
        collapsed={sidebarCollapsed}
        activeKey={activeSection}
        branding={branding}
        featureFlags={featureFlags}
        allowedSections={allowedSections}
        mobileOpen={mobileMenuOpen}
        onCloseMobile={() => setMobileMenuOpen(false)}
        onSelect={(key) => setActiveSection(key as AppSection)}
        onToggle={() => setSidebarCollapsed((current) => !current)}
        onLogout={() => {
          logout()
          setCurrentUser(null)
          setToken('')
        }}
      />

      <main className="flex min-w-0 flex-1 flex-col overflow-hidden bg-white">
        <header className="topbar-shell shrink-0 border-b border-slate-200 bg-white">
          <div className="flex items-center justify-between gap-4 px-4 py-3 sm:px-6">
            <div className="flex min-w-0 items-center gap-3">
              <button
                type="button"
                className="rounded-xl border border-slate-200 bg-white p-2.5 text-slate-600 lg:hidden"
                onClick={() => setMobileMenuOpen(true)}
              >
                <Menu className="h-5 w-5" />
              </button>
              <div className="min-w-0">
                <p className="truncate text-lg font-semibold tracking-[-0.02em] text-slate-900">{sectionCopy[activeSection].title}</p>
                <p className="truncate text-xs text-slate-500">
                  {branding.companyName} · {topBarRole} · {topBarDate}
                </p>
              </div>
            </div>
            <div className="flex shrink-0 items-center gap-2 sm:gap-3">
                <div className="hidden sm:flex sm:flex-col sm:text-right sm:text-xs sm:text-slate-500">
                {isTopCheckedIn ? `Checked in ${formatDuration(topElapsedSeconds)}` : 'Checked out'}
              </div>
              <button type="button" className="primary-btn px-3 py-2.5 text-sm sm:px-5" onClick={() => void headerWebCheckIn()}>
                <Fingerprint className="h-4 w-4" />
                <span className="hidden sm:inline">{topWebPunchButtonLabel}</span>
                <span className="sm:hidden">{isTopCheckedIn ? 'Check-Out' : 'Check-In'}</span>
              </button>
              <button type="button" className="flex h-10 w-10 items-center justify-center rounded-xl border border-slate-200 text-slate-500 transition hover:bg-slate-50">
                <Bell className="h-4 w-4" />
              </button>
            </div>
          </div>
        </header>

        <div className="page-shell">
          {renderSection()}

          <footer className="mt-10 border-t border-slate-100 pt-6 text-center text-xs leading-relaxed text-slate-500">
            <p>Made by Nika Datiashvili, Designed by Tamta Modebadze, Supported by ITGS Sulkhan Sulkhanishvili.</p>
            <p className="mt-1">© 2026 HRMS Georgia Enterprise. All Rights Reserved.</p>
          </footer>
        </div>
      </main>
      </div>

      <ToastStack items={toasts} onDismiss={(id) => setToasts((rows) => rows.filter((row) => row.id !== id))} />

      <EmployeeDrawer
        open={drawerOpen}
        mode={drawerMode}
        draft={draft}
        options={options}
        activeTab={drawerTab}
        selectedPhoto={draftPhoto}
        onChangeTab={setDrawerTab}
        onDraftChange={setDraft}
        onPhotoChange={setDraftPhoto}
        onClose={() => {
          setDrawerOpen(false)
          setDraftPhoto(null)
        }}
        onSubmit={() => void submitEmployee()}
      />

      <AttendanceModal
        open={attendanceOpen}
        employeeName={attendanceEmployeeName}
        rows={attendanceRows}
        onClose={() => setAttendanceOpen(false)}
      />

      <HardwareSyncModal
        open={syncOpen}
        employee={syncEmployee}
        devices={options?.devices ?? []}
        selectedDeviceIds={selectedDeviceIds}
        onToggleDevice={(deviceId) =>
          setSelectedDeviceIds((current) =>
            current.includes(deviceId) ? current.filter((item) => item !== deviceId) : [...current, deviceId]
          )
        }
        onClose={() => setSyncOpen(false)}
        onSubmit={() => void submitSync()}
      />
    </div>
  )
}
