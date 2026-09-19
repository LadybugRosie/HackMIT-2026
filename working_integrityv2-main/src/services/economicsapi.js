// IB Economics IA Generator API Service (Railway only)
const RAILWAY_BASE_URL = 'https://web-production-7dcee.up.railway.app';

class EconomicsApiService {
  constructor(baseUrl = RAILWAY_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  // Internal: POST JSON with retry and timeout
  async postJsonWithRetry(url, payload, { retries = 2, timeoutMs = 15000 } = {}) {
    let lastError;
    for (let attempt = 0; attempt <= retries; attempt++) {
      const controller = new AbortController();
      const id = setTimeout(() => controller.abort(), timeoutMs);
      try {
        const response = await fetch(url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
          signal: controller.signal,
        });
        clearTimeout(id);
        if (!response.ok) {
          const text = await response.text();
          // Do not retry for 4xx (except 429), retry for 5xx and network aborts
          const status = response.status;
          const isRetryable = status >= 500 || status === 429;
          const err = new Error(`HTTP ${status}: ${text}`);
          err.status = status;
          if (isRetryable && attempt < retries) {
            await new Promise(r => setTimeout(r, 500 * (attempt + 1)));
            continue;
          }
          throw err;
        }
        return await response.json();
      } catch (err) {
        clearTimeout(id);
        lastError = err;
        // Retry on network errors/aborts
        const isAbort = err.name === 'AbortError';
        const isNetwork = err instanceof TypeError || /Failed to fetch/i.test(String(err));
        if ((isAbort || isNetwork) && attempt < retries) {
          await new Promise(r => setTimeout(r, 500 * (attempt + 1)));
          continue;
        }
        throw err;
      }
    }
    throw lastError || new Error('Unknown network error');
  }

  // Railway: Suggest concepts with query-param-based payload
  async suggestConceptsRailway(payload) {
    const url = `${RAILWAY_BASE_URL}/suggest-concepts`;
    try {
      console.log('📡 Calling Railway suggest-concepts with payload:', payload);
      const data = await this.postJsonWithRetry(url, payload, { retries: 2, timeoutMs: 15000 });
      console.log('✅ Railway suggest-concepts response:', data);
      return data;
    } catch (err) {
      console.error('❌ Railway suggest-concepts failed:', err);
      throw err;
    }
  }

  // Railway: Generate complete IA
  async generateCompleteIARailway(payload) {
    const url = `${RAILWAY_BASE_URL}/generate-complete-ia`;
    try {
      console.log('📡 Calling Railway generate-complete-ia with payload:', payload);
      // Complete IA can take longer; allow more time and retries
      const data = await this.postJsonWithRetry(url, payload, { retries: 3, timeoutMs: 90000 });
      console.log('✅ Railway generate-complete-ia response:', data);
      return data;
    } catch (err) {
      console.error('❌ Railway generate-complete-ia failed:', err);
      throw err;
    }
  }
}

// Create singleton instance
const economicsApi = new EconomicsApiService();

export default economicsApi;