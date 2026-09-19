const TOKEN_KEY = 'classroom_token'

export class ApiError extends Error {
  constructor(status, detail) {
    super(typeof detail === 'string' ? detail : JSON.stringify(detail))
    this.status = status
    this.detail = detail
  }
}

export function getToken() {
  try { return localStorage.getItem(TOKEN_KEY) } catch { return null }
}
export function setToken(token) {
  try { token ? localStorage.setItem(TOKEN_KEY, token) : localStorage.removeItem(TOKEN_KEY) } catch {}
}
export function authHeaders() {
  const t = getToken()
  return t ? { Authorization: `Bearer ${t}` } : {}
}

async function request(method, path, body) {
  const r = await fetch(path, {
    method,
    headers: { 'content-type': 'application/json', ...authHeaders() },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  const text = await r.text()
  const data = text ? JSON.parse(text) : null
  if (!r.ok) {
    if (r.status === 401) setToken(null)
    throw new ApiError(r.status, data?.detail ?? data ?? r.statusText)
  }
  return data
}

export const api = {
  get: (path) => request('GET', path),
  post: (path, body = {}) => request('POST', path, body),
  put: (path, body = {}) => request('PUT', path, body),
}
