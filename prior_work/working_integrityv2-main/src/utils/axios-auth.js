/**
 * Axios Auth Interceptor
 * Automatically adds Authorization: Bearer header to all outgoing requests.
 * This moves sensitive tokens out of URL query params and into headers,
 * preventing them from leaking in logs, browser history, and referrer headers.
 */
import axios from 'axios'

export function setupAxiosAuthInterceptor() {
  axios.interceptors.request.use((config) => {
    const token = localStorage.getItem('auth_token')
    if (token) {
      // Set Authorization header on every request
      config.headers = config.headers || {}
      config.headers['Authorization'] = `Bearer ${token}`
    }
    return config
  })
}
