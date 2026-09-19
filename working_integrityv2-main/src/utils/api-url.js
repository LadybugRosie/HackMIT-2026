/**
 * API URL Configuration
 * Smart detection of backend URL for production deployments
 * 
 * Works for millions of students - no manual configuration needed
 */

// Production backend URL
const PRODUCTION_BACKEND = 'https://backend-production-5b99.up.railway.app'

// Development fallback
const DEV_BACKEND = 'http://localhost:8000'

/**
 * Get the correct API URL based on environment
 * 
 * Priority:
 * 1. VITE_INTEGRITY_API environment variable (if set)
 * 2. Production URL (if running on railway.app or editorrah.com)
 * 3. Development fallback (localhost)
 */
export function getApiUrl() {
  // 1. Check if explicitly set via environment variable
  const envUrl = import.meta.env.VITE_INTEGRITY_API
  if (envUrl && envUrl !== 'http://localhost:8000') {
    return envUrl.replace(/\/+$/, '')
  }
  
  // 2. Detect production environment from window.location
  if (typeof window !== 'undefined') {
    const hostname = window.location.hostname
    
    // Production domains
    if (
      hostname.includes('railway.app') ||
      hostname.includes('editorrah.com') ||
      hostname === 'editorrah.com' ||
      hostname === 'www.editorrah.com'
    ) {
      return PRODUCTION_BACKEND
    }
  }
  
  // 3. Fallback to env variable or localhost for development
  return (envUrl || DEV_BACKEND).replace(/\/+$/, '')
}

// Export default API URL
export const API_URL = getApiUrl()
