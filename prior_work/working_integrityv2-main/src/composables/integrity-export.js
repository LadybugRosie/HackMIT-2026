import { useStore } from './store'
import axios from 'axios'
import { useAlert } from './dialog'
import { getApiUrl } from '@/utils/api-url'

const INTEGRITY_API = getApiUrl()

export const useIntegrityExport = () => {
  const { integrity } = useStore()
  
  /**
   * Check if export is allowed based on integrity trust score
   * @param {number} minTrust - Minimum trust score required (default: 60)
   * @returns {Promise<boolean>} - True if export is allowed
   */
  const checkExportAllowed = async (minTrust = 60) => {
    // If no integrity session, allow export
    if (!integrity?.value?.active) {
      return true
    }
    
    try {
      const response = await axios.post(`${INTEGRITY_API}/api/integrity/export/check`, {
        session_id: integrity.value.sessionId,
        doc_id: integrity.value.docId,
        min_trust: minTrust
      })
      
      const { ok, trust, reason } = response.data
      
      if (!ok) {
        // Show blocking dialog
        useAlert({
          theme: 'warning',
          header: 'Export Blocked',
          body: `Export is currently blocked due to low trust score. Current Trust Score: ${trust}%. Reason: ${reason}. To proceed with export, please delete or rewrite the external content to improve your trust score above ${minTrust}%.`,
          confirmBtn: 'Understood'
        })
        
        return false
      }
      
      return true
    } catch (error) {
      console.error('Failed to check export permission:', error)
      
      // On error, show warning but allow export
      useAlert({
        theme: 'warning',
        header: 'Integrity Check Failed',
        body: 'Could not verify document integrity. Export will proceed.',
        confirmBtn: 'Continue'
      })
      
      return true
    }
  }
  
  /**
   * Wrap an export function with integrity check
   * @param {Function} exportFn - The export function to wrap
   * @param {number} minTrust - Minimum trust score required
   * @returns {Function} - Wrapped export function
   */
  const withIntegrityCheck = (exportFn, minTrust = 60) => {
    return async (...args) => {
      const allowed = await checkExportAllowed(minTrust)
      if (allowed) {
        return exportFn(...args)
      }
    }
  }
  
  return {
    checkExportAllowed,
    withIntegrityCheck
  }
}
