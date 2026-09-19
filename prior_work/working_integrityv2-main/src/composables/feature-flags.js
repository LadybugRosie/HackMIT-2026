/**
 * Runtime feature flags mirrored from the backend (GET /api/config).
 *
 * integrityLegacyMode is the STUDENT-VISIBILITY revert switch:
 *   false (default) -> students see no integrity signals; student PDF is
 *                      clean content only.
 *   true            -> students see their INDIVIDUAL integrity signals
 *                      (typing trust, stylometry, AI) again. Flip the backend
 *                      INTEGRITY_LEGACY_MODE env var; no rebuild required.
 *
 * The composite trust score has been removed from the product entirely and
 * cannot be restored by this flag.
 *
 * Note: the backend is the source of truth and already strips fields per this
 * flag. The frontend flag is defense-in-depth + controls display layout.
 */
import { ref } from 'vue'
import axios from 'axios'
import { getApiUrl } from '@/utils/api-url'

export const integrityLegacyMode = ref(false)

let _loaded = false

export async function loadFeatureFlags() {
  if (_loaded) return
  try {
    const { data } = await axios.get(`${getApiUrl()}/api/config`, { timeout: 8000 })
    integrityLegacyMode.value = !!data?.integrity_legacy_mode
    _loaded = true
  } catch (e) {
    // Fail safe: keep NEW behavior (hide integrity) if config can't be reached.
    console.warn('[feature-flags] /api/config fetch failed; defaulting to new integrity behavior', e)
  }
}

export function useFeatureFlags() {
  return { integrityLegacyMode, loadFeatureFlags }
}
