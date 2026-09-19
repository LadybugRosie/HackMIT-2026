import { reactive, readonly } from 'vue'
import { api, authHeaders, getToken, setToken } from '../lib/api.js'

const state = reactive({ user: null, loaded: false })
let loading = null

async function load() {
  if (state.loaded) return state.user
  if (!loading) {
    loading = (async () => {
      if (getToken()) {
        try { state.user = await api.get('/api/auth/me') } catch { state.user = null }
      }
      state.loaded = true
      return state.user
    })()
  }
  return loading
}

function apply(res) {
  setToken(res.token)
  state.user = res.user
  state.loaded = true
  return res.user
}

export function useAuth() {
  return {
    state: readonly(state),
    load,
    headers: authHeaders,
    home: (user = state.user) => (user ? `/${user.role}` : '/'),
    async login(email, password) { return apply(await api.post('/api/auth/login', { email, password })) },
    async signup(body) { return apply(await api.post('/api/auth/signup', body)) },
    async logout() {
      try { await api.post('/api/auth/logout') } catch {}
      setToken(null)
      state.user = null
    },
  }
}
