export type LoginResponse = {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

const TOKEN_KEY = 'hrms_access_token'

export function readToken(): string {
  return localStorage.getItem(TOKEN_KEY) ?? ''
}

export function writeToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

function buildQuery(params?: Record<string, string | number | null | undefined>): string {
  if (!params) {
    return ''
  }
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== null && value !== undefined && `${value}` !== '') {
      search.set(key, `${value}`)
    }
  }
  const encoded = search.toString()
  return encoded ? `?${encoded}` : ''
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = readToken()
  const headers = new Headers(init?.headers)
  if (!(init?.body instanceof FormData) && !headers.has('Content-Type') && init?.method && init.method !== 'GET') {
    headers.set('Content-Type', 'application/json')
  }
  if (token && !path.startsWith('/auth/login')) {
    headers.set('Authorization', `Bearer ${token}`)
  }
  const response = await fetch(path, { ...init, headers })
  if (!response.ok) {
    if (response.status === 401) {
      logout()
    }
    const contentType = response.headers.get('content-type') ?? ''
    if (contentType.includes('application/json')) {
      const payload = (await response.json()) as { detail?: string; message?: string }
      throw new Error(compactErrorMessage(payload.detail ?? payload.message ?? response.statusText))
    }
    const payload = await response.text()
    throw new Error(compactErrorMessage(payload || response.statusText))
  }
  if (response.status === 204) {
    return undefined as T
  }
  return response.json() as Promise<T>
}

function compactErrorMessage(input: string): string {
  const text = input.trim()
  if (!text) {
    return 'მოთხოვნა ვერ შესრულდა'
  }
  const normalized = text.replace(/\s+/g, ' ')
  const lower = normalized.toLowerCase()
  if (lower.includes('duplicate key value')) {
    return 'ასეთი ჩანაწერი უკვე არსებობს'
  }
  if (lower.includes('foreign key constraint')) {
    return 'მითითებული ჩანაწერი ვერ მოიძებნა'
  }
  if (lower.includes('not-null constraint')) {
    return 'სავალდებულო ველი ცარიელია'
  }
  if (lower.includes('device serial is not registered')) {
    return 'მოწყობილობის სერიული ნომერი რეგისტრირებული არ არის'
  }
  if (lower.includes('tenant') && lower.includes('host')) {
    return 'კომპანიის ჰოსტი უკვე გამოყენებულია'
  }
  if (normalized.length <= 160) {
    return normalized
  }
  return `${normalized.slice(0, 157)}...`
}

export async function login(username: string, password: string): Promise<LoginResponse> {
  const payload = await request<LoginResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password })
  })
  writeToken(payload.access_token)
  return payload
}

export function logout(): void {
  localStorage.removeItem(TOKEN_KEY)
}

export function getJson<T>(path: string, params?: Record<string, string | number | null | undefined>): Promise<T> {
  return request<T>(`${path}${buildQuery(params)}`)
}

export function postJson<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(path, {
    method: 'POST',
    body: body === undefined ? undefined : JSON.stringify(body)
  })
}

export function postForm<T>(path: string, body: FormData): Promise<T> {
  return request<T>(path, {
    method: 'POST',
    body
  })
}

export function putJson<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: 'PUT',
    body: JSON.stringify(body)
  })
}

export function deleteJson<T>(path: string): Promise<T> {
  return request<T>(path, {
    method: 'DELETE'
  })
}
