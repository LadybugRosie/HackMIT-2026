// Document service for handling content persistence and retrieval
// Works with both essay and paper modes

import apiService from './apiService.js';

class DocumentService {
  constructor() {
    this.currentMode = 'essay'; // default mode
    this.autoSaveInterval = null;
    this.pendingData = {};
    this.isLoading = false;
    this.isSaving = false;
  }

  // Set the current mode (essay, paper, or other future templates)
  setMode(mode) {
    this.currentMode = mode;
    // Store mode in localStorage for persistence
    localStorage.setItem('currentEditorMode', mode);
    console.log(`DocumentService mode set to: ${mode}`);
  }

  // Auto-detect mode from URL or context - make it more robust
  detectAndSetMode() {
    // First try to get mode from URL params
    const urlParams = new URLSearchParams(window.location.search);
    const urlMode = urlParams.get('mode');
    
    if (urlMode && (urlMode === 'essay' || urlMode === 'paper' || urlMode === 'paper-template' || urlMode === 'economics' || urlMode === 'microeconomics' || urlMode === 'macroeconomics' || urlMode === 'globaleconomics')) {
      const normalizedMode = urlMode === 'paper-template' ? 'paper' : urlMode;
      this.setMode(normalizedMode);
      return;
    }
    
    // Check localStorage for current mode
    const storedMode = localStorage.getItem('currentEditorMode');
    if (storedMode && (storedMode === 'essay' || storedMode === 'paper' || storedMode === 'economics' || storedMode === 'microeconomics' || storedMode === 'macroeconomics' || storedMode === 'globaleconomics')) {
      this.setMode(storedMode);
      return;
    }
    
    // Fallback to path checking
    const path = window.location.pathname;
    if (path.includes('paper')) {
      this.setMode('paper');
    } else if (path.includes('microeconomics')) {
      this.setMode('microeconomics');
    } else if (path.includes('macroeconomics')) {
      this.setMode('macroeconomics');
    } else if (path.includes('globaleconomics')) {
      this.setMode('globaleconomics');
    } else if (path.includes('economics')) {
      this.setMode('economics');
    } else {
      this.setMode('essay');
    }
  }

  // Check if current mode is any economics template
  isEconomicsMode() {
    return ['economics', 'microeconomics', 'macroeconomics', 'globaleconomics'].includes(this.currentMode);
  }

  // Get current user ID (this should be implemented based on your auth system)
  getCurrentUserId() {
    // First try to get from URL params
    const urlParams = new URLSearchParams(window.location.search);
    const urlUserId = urlParams.get('user_id');
    
    if (urlUserId) {
      return urlUserId;
    }
    
    // Fallback to localStorage
    return localStorage.getItem('user_id') || 'default_user';
  }

  // Save document based on current mode
  async saveDocument(data) {
    if (this.isSaving) {
      console.log('Save already in progress, skipping...');
      return;
    }

    this.isSaving = true;
    try {
      const userId = this.getCurrentUserId();
      const documentData = {
        user_id: userId,
        ...data,
      };

      let result;
      if (this.currentMode === 'paper') {
        result = await this.savePaperWithCreation(documentData);
      } else if (this.currentMode === 'essay') {
        result = await this.saveEssayWithCreation(documentData);
      } else if (this.isEconomicsMode()) {
        result = await this.saveEconomicsWithCreation(documentData);
      } else {
        throw new Error(`Unsupported mode: ${this.currentMode}`);
      }

      console.log(`${this.currentMode} document saved successfully:`, result);
      return result;
    } catch (error) {
      console.error(`Failed to save ${this.currentMode} document:`, error);
      throw error;
    } finally {
      this.isSaving = false;
    }
  }

  // Helper method to save paper with creation handling
  async savePaperWithCreation(documentData) {
    return await apiService.savePaperDraft(documentData);
  }

  // Helper method to save essay with creation handling
  async saveEssayWithCreation(documentData) {
    try {
      return await apiService.saveEssayDraft(documentData);
    } catch (error) {
      if (error.message && (error.message.includes('No document found') || error.message.includes('404'))) {
        console.log('📝 Essay document not found, treating as new document');
        // For essays, the save endpoint should handle creation
        throw new Error(`Essay document not found. This might be a new document that hasn't been properly initialized. Error: ${error.message}`);
      }
      throw error;
    }
  }

  // Helper method to save economics with creation handling
  async saveEconomicsWithCreation(documentData) {
    return await apiService.saveEconomicsDraft(documentData);
  }

  // Load document based on current mode
  async loadDocument() {
    if (this.isLoading) {
      console.log('Load already in progress, skipping...');
      return null;
    }

    this.isLoading = true;
    try {
      const userId = this.getCurrentUserId();
      
      let result;
      if (this.currentMode === 'paper') {
        result = await apiService.loadPaperDraft(userId);
      } else if (this.currentMode === 'essay') {
        result = await apiService.loadEssayDraft(userId);
      } else if (this.isEconomicsMode()) {
        result = await apiService.loadEconomicsDraft(userId);
      } else {
        throw new Error(`Unsupported mode: ${this.currentMode}`);
      }

      console.log(`${this.currentMode} document loaded successfully:`, result);
      
      // Handle essay API response format
      if (this.currentMode === 'essay' && result && result.document) {
        return result.document;
      }
      
      // Handle paper API response format  
      if (this.currentMode === 'paper' && result && result.paper) {
        return result.paper;
      }
      
      // Handle economics API response format  
      if (this.isEconomicsMode() && result && result.doc) {
        return result.doc;
      }
      
      return result;
    } catch (error) {
      console.error(`Failed to load ${this.currentMode} document:`, error);
      // Don't throw error to prevent breaking the editor, just log it
      return null;
    } finally {
      this.isLoading = false;
    }
  }

  // Save content specifically (for editor integration)
  async saveContent(content) {
    let data;
    if (this.currentMode === 'essay') {
      data = {
        entered_essay: content,
      };
    } else if (this.currentMode === 'paper') {
      data = {
        entered_content: content,
      };
    } else if (this.isEconomicsMode()) {
      data = {
        article: content,
      };
    }

    return await this.saveDocument(data);
  }

  // Save references/suggestions (left sidebar content)
  async saveReferences(references) {
    let data;
    if (this.currentMode === 'paper') {
      data = {
        selected_references: Array.isArray(references) ? references : [references],
        references: typeof references === 'string' ? references : JSON.stringify(references),
      };
    } else if (this.isEconomicsMode()) {
      // For economics: save the 5 concept suggestions generated on page load
      data = {
        concept_suggestions: Array.isArray(references) ? references : [references],
      };
    } else {
      data = {
        references: typeof references === 'string' ? references : JSON.stringify(references),
      };
    }

    return await this.saveDocument(data);
  }

  // Save concept suggestions for economics (left sidebar - generated on page load)
  async saveConceptSuggestions(suggestions) {
    if (!this.isEconomicsMode()) {
      console.warn('saveConceptSuggestions is only supported in economics modes');
      return;
    }

    const data = {
      concept_suggestions: Array.isArray(suggestions) ? suggestions : [suggestions],
    };

    return await this.saveDocument(data);
  }

  // Save generated content (right sidebar content after generation)
  async saveGeneratedContent(generatedContent) {
    let data;
    if (this.currentMode === 'paper') {
      data = {
        gen_paper: generatedContent,
      };
    } else if (this.currentMode === 'economics') {
      // For economics mode, generated outline from selected concept
      data = {
        generated_outline: typeof generatedContent === 'string' ? generatedContent : JSON.stringify(generatedContent),
      };
    } else {
      data = {
        generated_essay: generatedContent,
      };
    }

    return await this.saveDocument(data);
  }

  // Save generated outline for economics (right sidebar - generated from selected concept)
  async saveGeneratedOutline(outline) {
    if (this.currentMode !== 'economics') {
      console.warn('saveGeneratedOutline is only supported in economics mode');
      return;
    }

    const data = {
      generated_outline: typeof outline === 'string' ? outline : JSON.stringify(outline),
    };

    return await this.saveDocument(data);
  }

  // Save outline (for paper mode)
  async saveOutline(outline) {
    if (this.currentMode !== 'paper') {
      console.warn('Outline saving is only supported in paper mode');
      return;
    }

    const data = {
      outline: typeof outline === 'string' ? outline : JSON.stringify(outline),
    };

    return await this.saveDocument(data);
  }

  // Save outline with references (for paper mode)
  async saveOutlineWithReferences(outline, references) {
    if (this.currentMode !== 'paper') {
      console.warn('Outline and references saving is only supported in paper mode');
      return;
    }

    const data = {
      outline: typeof outline === 'string' ? outline : JSON.stringify(outline),
      selected_references: Array.isArray(references) ? references : [references],
      references: typeof references === 'string' ? references : JSON.stringify(references),
    };

    return await this.saveDocument(data);
  }

  // Save comprehensive data (all fields)
  async saveAll(allData) {
    return await this.saveDocument(allData);
  }

  // Save both entered and generated content (for essay mode)
  async saveBothContents(enteredContent, generatedContent) {
    if (this.currentMode !== 'essay') {
      console.warn('saveBothContents is only supported in essay mode');
      return;
    }

    const data = {
      entered_essay: enteredContent,
      generated_essay: generatedContent,
    };

    return await this.saveDocument(data);
  }

  // Start auto-save functionality
  startAutoSave(interval = 30000) { // 30 seconds default
    if (this.autoSaveInterval) {
      clearInterval(this.autoSaveInterval);
    }

    this.autoSaveInterval = setInterval(() => {
      if (Object.keys(this.pendingData).length > 0) {
        console.log('Auto-saving pending data...');
        this.saveDocument(this.pendingData);
        this.pendingData = {};
      }
    }, interval);
  }

  // Stop auto-save
  stopAutoSave() {
    if (this.autoSaveInterval) {
      clearInterval(this.autoSaveInterval);
      this.autoSaveInterval = null;
    }
  }

  // Queue data for auto-save
  queueForAutoSave(data) {
    this.pendingData = { ...this.pendingData, ...data };
  }

  // Initialize service
  init() {
    this.detectAndSetMode();
    console.log(`DocumentService initialized in ${this.currentMode} mode`);
  }
}

// Create singleton instance
const documentService = new DocumentService();

export default documentService;