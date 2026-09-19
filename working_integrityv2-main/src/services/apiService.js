// Reusable API service for handling essay and paper modes
// Supports multiple templates and can be easily extended for future use

class ApiService {
  constructor(baseUrl = '') {
    this.baseUrl = baseUrl;
  }

  // Extract document/paper ID from URL
  extractIdFromUrl() {
    const path = window.location.pathname;
    const matches = path.match(/\/editor\/(.+)/);
    return matches ? matches[1] : null;
  }

  // Generic fetch wrapper with error handling
  async makeRequest(endpoint, options = {}) {
    const url = `${this.baseUrl}${endpoint}`;
    
    const defaultOptions = {
      headers: {
        'Content-Type': 'application/json',
      },
    };

    const finalOptions = {
      ...defaultOptions,
      ...options,
      headers: {
        ...defaultOptions.headers,
        ...options.headers,
      },
    };

    try {
      const response = await fetch(url, finalOptions);
      
      if (!response.ok) {
        // Try to get detailed error message from response
        let errorMessage = `HTTP error! status: ${response.status}`;
        try {
          const errorData = await response.json();
          if (errorData.detail) {
            errorMessage += ` - ${errorData.detail}`;
          }
          // Create enhanced error object with status info
          const enhancedError = new Error(errorMessage);
          enhancedError.status = response.status;
          enhancedError.detail = errorData.detail || errorMessage;
          throw enhancedError;
        } catch (jsonError) {
          // If response is not JSON, use status text
          errorMessage += ` - ${response.statusText}`;
          const enhancedError = new Error(errorMessage);
          enhancedError.status = response.status;
          throw enhancedError;
        }
      }
      
      return await response.json();
    } catch (error) {
      console.error('API request failed:', error);
      throw error;
    }
  }

  // Essay API methods
  async saveEssayDraft(essayData) {
    const documentId = this.extractIdFromUrl();
    if (!documentId) {
      throw new Error('Document ID not found in URL');
    }

    const payload = {
      document_id: documentId,
      user_id: essayData.user_id || "string",
      title: essayData.title || "string",
      topic: essayData.topic || "string",
      word_count: essayData.word_count || 0,
      citation_style: essayData.citation_style || "string",
      references: essayData.references || "string",
      generated_essay: essayData.generated_essay || "string",
      entered_essay: essayData.entered_essay || "string"
    };

    return await this.makeRequest('/api/save-essay', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async loadEssayDraft(userId) {
    const documentId = this.extractIdFromUrl();
    if (!documentId) {
      throw new Error('Document ID not found in URL');
    }

    console.log('🔍 Loading essay draft:', { documentId, userId });

    return await this.makeRequest(`/api/retrieve-specific-essay?user_id=${userId}&document_id=${documentId}`, {
      method: 'GET',
    });
  }

  // Paper API methods
  async savePaperDraft(paperData) {
    const paperId = this.extractIdFromUrl();
    if (!paperId) {
      throw new Error('Paper ID not found in URL');
    }

    const payload = {
      user_id: String(paperData.user_id || "string"),
      topic: paperData.topic || "string",
      paper_id: String(paperId),
      citation_style: paperData.citation_style || "string",
      selected_references: paperData.selected_references || [],
      dialect: paperData.dialect || "US",
      word_count: paperData.word_count || 1000,
      reading_level: paperData.reading_level || "college",
      entered_content: paperData.entered_content || "string",
      gen_paper: paperData.gen_paper || "string",
      outline: paperData.outline || "string",
      references: paperData.references || "string"
    };

    return await this.makeRequest('/create_paper_draft', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async loadPaperDraft(userId) {
    const paperId = this.extractIdFromUrl();
    if (!paperId) {
      throw new Error('Paper ID not found in URL');
    }

    console.log('🔍 Loading paper draft:', { paperId, userId });

    return await this.makeRequest(`/api/retrieve-specific-paper-draft?paper_id=${String(paperId)}&user_id=${String(userId)}`, {
      method: 'GET',
    });
  }

  // Economics API methods
  async saveEconomicsDraft(economicsData) {
    const ecoId = this.extractIdFromUrl();
    if (!ecoId) {
      throw new Error('Economics document ID not found in URL');
    }

    const payload = {
      eco_id: String(ecoId),
      user_id: String(economicsData.user_id || "string"),
      concept_suggestions: economicsData.concept_suggestions || [],
      generated_outline: economicsData.generated_outline || "string",
      article: economicsData.article || "string"
    };

    return await this.makeRequest('/eco-docs/save-progress', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async loadEconomicsDraft(userId) {
    const ecoId = this.extractIdFromUrl();
    if (!ecoId) {
      throw new Error('Economics document ID not found in URL');
    }

    console.log('🔍 Loading economics draft:', { ecoId, userId });

    return await this.makeRequest(`/eco-docs/${String(ecoId)}?user_id=${String(userId)}`, {
      method: 'GET',
    });
  }

  async getUserEconomicsDocs(userId) {
    return await this.makeRequest(`/user/${String(userId)}/eco-docs`, {
      method: 'GET',
    });
  }

}

// Create singleton instance with backend URL
const BACKEND_URL = 'https://jfv6blghbfv5lr3wt6sho4kewe0mrifm.lambda-url.us-east-1.on.aws';
const apiService = new ApiService(BACKEND_URL);

// Auto-detect mode based on current context or URL
const detectMode = () => {
  // This can be extended to detect different template types
  // For now, we'll assume essay mode by default, but this can be configured
  const path = window.location.pathname;
  if (path.includes('paper')) return 'paper';
  if (path.includes('economics')) return 'economics';
  return 'essay'; // default mode
};

// Export both the class and instance
export { ApiService };
export default apiService;