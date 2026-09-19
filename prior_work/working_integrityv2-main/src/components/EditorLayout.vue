<template>

  <div class="editor-fullscreen">

    <div class="editor-content-area">

      <!-- Left Sidebar -->

      <aside v-if="selectedMode !== 'none'" class="sidebar left scrollable-sidebar minimal-sidebar" :class="{ 'left-hidden': leftHidden }" style="padding: 14px;">

        <!-- Essay Mode Controls -->
        <template v-if="selectedMode === 'essay'">
          <div class="card citation-card">
            <div class="section-title" style="display: flex; align-items: center; justify-content: space-between;">
              <span>Citation Format</span>
              <span class="toc-tab-close" @click="toggleLeftSidebar">✕</span>
            </div>
            <select v-model="selectedFormat" class="dropdown">
              <option disabled value="">Select Format</option>
              <option v-for="format in formats" :key="format" :value="format">{{ format }}</option>
            </select>
          </div>
        </template>

        <!-- TOK Essay Mode Controls -->
        <template v-else-if="selectedMode === 'tok-essay'">
          <div class="card">
            <div class="section-title" style="display: flex; align-items: center; justify-content: space-between;">
              <span>TOK Essay Details</span>
              <span class="toc-tab-close" @click="toggleLeftSidebar">✕</span>
            </div>
            
            <!-- Title Field -->
            <!-- <div class="form-field">
              <label for="tokTitle" class="field-label">Title</label>
              <input 
                id="tokTitle"
                v-model="tokEssay.title" 
                type="text" 
                class="dropdown" 
                placeholder="Enter the prescribed TOK essay title..."
              />
            </div>
             -->
            <!-- AOK1 Field -->
            <div class="form-field">
              <label for="tokAok1" class="field-label">Area of Knowledge 1</label>
              <input 
                id="tokAok1"
                v-model="tokEssay.aok1" 
                type="text" 
                class="dropdown" 
                placeholder="e.g., History"
              />
            </div>
            
            <!-- AOK2 Field -->
            <div class="form-field">
              <label for="tokAok2" class="field-label">Area of Knowledge 2</label>
              <input 
                id="tokAok2"
                v-model="tokEssay.aok2" 
                type="text" 
                class="dropdown" 
                placeholder="e.g., Natural Sciences"
              />
            </div>
          </div>

          <div class="card">
            <div class="section-title">Citation Style</div>
            <select v-model="tokEssay.citationStyle" class="dropdown">
              <option disabled value="">Select Citation Style</option>
              <option value="APA">APA (American Psychological Association)</option>
              <option value="MLA">MLA (Modern Language Association)</option>
              <option value="Chicago">Chicago (Chicago Manual of Style)</option>
              <option value="Harvard">Harvard</option>
              <option value="Vancouver">Vancouver</option>
              <option value="IEEE">IEEE (Institute of Electrical and Electronics Engineers)</option>
              <option value="AMA">AMA (American Medical Association)</option>
              <option value="ACS">ACS (American Chemical Society)</option>
              <option value="CSE">CSE (Council of Science Editors)</option>
              <option value="Bluebook">Bluebook</option>
            </select>
          </div>
        </template>

        <!-- TOK Journal Mode Controls -->
        <template v-else-if="selectedMode === 'tok'">
          <div class="card">
            <div class="section-title" style="display: flex; align-items: center; justify-content: space-between;">
              <span>TOK Journal Details</span>
              <span class="toc-tab-close" @click="toggleLeftSidebar">✕</span>
            </div>
            
            <!-- Title Field
            <div class="form-field">
              <label for="tokJournalTitle" class="field-label">Journal Title</label>
              <input 
                id="tokJournalTitle"
                v-model="tokJournal.title" 
                type="text" 
                class="dropdown" 
                placeholder="Enter your TOK journal title..."
              />
            </div> -->
            
            <!-- Instructions Field -->
            <div class="form-field">
              <label for="tokJournalInstructions" class="field-label">Instructions</label>
              <textarea 
                id="tokJournalInstructions"
                v-model="tokJournal.instructions" 
                class="dropdown" 
                placeholder="Make it simple and reflective, suitable for a high school journal..."
                rows="3"
                style="resize: vertical; height: auto; min-height: 80px;"
              ></textarea>
            </div>
            
            <!-- Citation Style -->
            <div class="form-field">
              <label for="tokJournalCitation" class="field-label">Citation Style</label>
              <select v-model="tokJournal.citationStyle" class="dropdown">
                <option disabled value="">Select Citation Style</option>
                <option value="APA">APA (American Psychological Association)</option>
                <option value="MLA">MLA (Modern Language Association)</option>
                <option value="Chicago">Chicago (Chicago Manual of Style)</option>
                <option value="Harvard">Harvard</option>
                <option value="Vancouver">Vancouver</option>
                <option value="IEEE">IEEE (Institute of Electrical and Electronics Engineers)</option>
                <option value="AMA">AMA (American Medical Association)</option>
                <option value="ACS">ACS (American Chemical Society)</option>
                <option value="CSE">CSE (Council of Science Editors)</option>
                <option value="Bluebook">Bluebook</option>
              </select>
            </div>
          </div>
        </template>

        <!-- TOK Exhibition Mode Controls -->
        <template v-else-if="selectedMode === 'tok-exhibition'">
          <div class="card">
            <div class="section-title" style="display: flex; align-items: center; justify-content: space-between;">
              <span>TOK Exhibition</span>
              <span class="toc-tab-close" @click="toggleLeftSidebar">✕</span>
            </div>
            
            <!-- Select Prompt -->
            <div v-if="tokExhibition.currentStep === 1" class="exhibition-step">
              <h4 class="step-title">Select TOK Prompt</h4>
              
              <!-- Loading Prompts -->
              <div v-if="tokExhibition.isLoadingPrompts" class="loading">
                Loading available prompts...
              </div>
              
              <!-- Prompt Selection -->
              <div v-else-if="tokExhibition.availablePrompts.length > 0" class="form-field">
                <label class="field-label">Choose from Official TOK Prompts</label>
                <select 
                  v-model="tokExhibition.selectedPromptNumber" 
                  class="dropdown"
                >
                  <option disabled :value="null">Choose a prompt...</option>
                  <option 
                    v-for="(prompt, index) in tokExhibition.availablePrompts" 
                    :key="index"
                    :value="index + 1"
                  >
                    {{ getTokPromptOptionLabel(index, prompt) }}
                  </option>
                </select>
                
                <!-- Show full selected prompt -->
                <div v-if="tokExhibition.selectedPromptNumber" class="selected-prompt">
                  <strong>Selected Prompt:</strong>
                  <p>{{ tokExhibition.availablePrompts[tokExhibition.selectedPromptNumber - 1] }}</p>
                </div>
                
                <!-- Next Step Button -->
                <button 
                  @click="suggestTokExhibitionObjects"
                  :disabled="!tokExhibition.selectedPromptNumber || tokExhibition.isLoadingObjects"
                  class="generate-essay-btn"
                  style="margin-top: 15px;"
                >
                  <span v-if="tokExhibition.isLoadingObjects">Fetching objects...</span>
                  <span v-else>Get Object Suggestions</span>
                </button>
              </div>
              
              <!-- Error state -->
              <div v-else class="loading">
                Failed to load prompts. Please refresh the page.
              </div>
            </div>
            
            <!-- Select Objects -->
            <div v-if="tokExhibition.currentStep === 2" class="exhibition-step">
              <h4 class="step-title">Select 3 Objects</h4>
              
              <div class="selected-prompt-display">
                <strong>Prompt:</strong> {{ tokExhibition.selectedPrompt }}
              </div>
              
              <!-- Suggested Objects -->
              <div v-if="tokExhibition.suggestedObjects.length > 0" class="objects-section">
                <div class="form-field">
                  <label class="field-label">Suggested Objects (Select exactly 3)</label>
                  <div class="objects-grid">
                    <div 
                      v-for="(object, index) in tokExhibition.suggestedObjects" 
                      :key="index"
                      class="object-item"
                      :class="{ 'selected': tokExhibition.selectedObjects.includes(object) }"
                      @click="toggleObjectSelection(object)"
                    >
                      <div class="object-content">
                        <h5>{{ object.title || object.name || `Object ${index + 1}` }}</h5>
                        <p>{{ object.description || object.summary || 'No description available' }}</p>
                      </div>
                      <div class="object-selection">
                        <input 
                          type="checkbox" 
                          :checked="tokExhibition.selectedObjects.includes(object)"
                          @click.stop
                          @change="toggleObjectSelection(object)"
                        />
                      </div>
                    </div>
                  </div>
                </div>
                
                <!-- Selected Objects Count -->
                <div class="selection-info">
                  Selected: {{ tokExhibition.selectedObjects.length }}/3 objects
                </div>
                
                <!-- Refresh Objects Button -->
                <button 
                  @click="refreshTokExhibitionObjects"
                  :disabled="tokExhibition.isLoadingObjects"
                  class="generate-essay-btn secondary"
                  style="background: #6b7280; margin-bottom: 10px;"
                >
                  <span v-if="tokExhibition.isLoadingObjects">Refreshing...</span>
                  <span v-else>Get Different Objects</span>
                </button>
              </div>
              
              <!-- Navigation Buttons -->
              <div class="step-navigation">
                <button 
                  @click="tokExhibition.currentStep = 1"
                  class="generate-essay-btn secondary"
                  style="background: #6b7280; margin-right: 10px;"
                >
                  ← Back to Prompts
                </button>
                <button 
                  @click="fetchTokExhibitionReferences"
                  :disabled="tokExhibition.selectedObjects.length !== 3"
                  class="generate-essay-btn"
                >
                  Next: Get References
                </button>
              </div>
            </div>
            
            <!-- Select References -->
            <div v-if="tokExhibition.currentStep === 3" class="exhibition-step">
              <h4 class="step-title">Select References</h4>
              
              <!-- Selected Objects Summary -->
              <div class="selected-summary">
                <strong>Selected Objects:</strong>
                <ul>
                  <li v-for="(object, index) in tokExhibition.selectedObjects" :key="index">
                    {{ object.title || object.name || `Object ${index + 1}` }}
                  </li>
                </ul>
              </div>
              
              <!-- References Selection -->
              <div v-if="tokExhibition.exhibitionReferences.length > 0" class="form-field">
                <label class="field-label">Available References</label>
                <div class="references-list" style="max-height: 300px; overflow-y: auto;">
                  <div 
                    v-for="(ref, index) in tokExhibition.exhibitionReferences" 
                    :key="index"
                    class="reference-item exhibition-ref"
                    :class="{ 'selected': tokExhibition.selectedExhibitionReferences.includes(ref) }"
                    @click="toggleReferenceSelection(ref)"
                  >
                    <div class="ref-content">
                      <h6>{{ ref.title || ref.name || 'Untitled Reference' }}</h6>
                      <p class="ref-authors">{{ ref.author || ref.authors || 'Unknown Author' }}</p>
                      <p class="ref-year">{{ getRefYear(ref) }}</p>
                    </div>
                    <input 
                      type="checkbox" 
                      :checked="tokExhibition.selectedExhibitionReferences.includes(ref)"
                      @click.stop
                      @change="toggleReferenceSelection(ref)"
                    />
                  </div>
                </div>
                
                <div class="selection-info">
                  Selected: {{ tokExhibition.selectedExhibitionReferences.length }} references
                </div>
              </div>
              
              <!-- Citation Format -->
              <div class="form-field">
                <label class="field-label">Citation Format</label>
                <select v-model="tokExhibition.citationFormat" class="dropdown">
                  <option value="APA7">APA7 (American Psychological Association 7th Edition)</option>
                  <option value="MLA8">MLA8 (Modern Language Association 8th Edition)</option>
                </select>
              </div>
              
              <!-- Navigation Buttons -->
              <div class="step-navigation">
                <button 
                  @click="tokExhibition.currentStep = 2"
                  class="generate-essay-btn secondary"
                  style="background: #6b7280; margin-right: 10px;"
                >
                  ← Back to Objects
                </button>
                <button 
                  @click="generateTokExhibitionEssay"
                  :disabled="tokExhibition.selectedExhibitionReferences.length === 0 || tokExhibition.isGeneratingEssay"
                  class="generate-essay-btn"
                >
                  <span v-if="tokExhibition.isGeneratingEssay">Generating Essay...</span>
                  <span v-else>Generate Exhibition Essay</span>
                </button>
              </div>
            </div>
            
            <!-- Essay Generated -->
            <div v-if="tokExhibition.currentStep === 4" class="exhibition-step">
              <h4 class="step-title">✅ Exhibition Essay Generated!</h4>
              
              <p class="success-message">
                Your TOK Exhibition essay has been generated successfully. 
                Check the right sidebar to view and edit the content.
              </p>
              
              <button 
                @click="resetTokExhibition"
                class="generate-essay-btn secondary"
                style="background: #6b7280;"
              >
                Start New Exhibition
              </button>
            </div>
          </div>
        </template>

        <!-- Paper Template Mode Controls -->
        <template v-else-if="selectedMode === 'paper-template'">
          <div class="card">
            <div class="section-title" style="display: flex; align-items: center; justify-content: space-between;">
              <span>Citation Style</span>
              <span class="toc-tab-close" @click="toggleLeftSidebar">✕</span>
            </div>
            <select v-model="paperTemplate.citationStyle" class="dropdown">
              <option disabled value="">Select Citation Style</option>
              <option value="APA">APA (American Psychological Association)</option>
              <option value="MLA">MLA (Modern Language Association)</option>
              <option value="Chicago">Chicago (Chicago Manual of Style)</option>
              <option value="Harvard">Harvard</option>
              <option value="Vancouver">Vancouver</option>
              <option value="IEEE">IEEE (Institute of Electrical and Electronics Engineers)</option>
              <option value="AMA">AMA (American Medical Association)</option>
              <option value="ACS">ACS (American Chemical Society)</option>
              <option value="CSE">CSE (Council of Science Editors)</option>
             
            </select>
          </div>

          <div class="card">
            <div class="section-title">Dialect</div>
            <select v-model="paperTemplate.dialect" class="dropdown">
              <option disabled value="">Select Dialect</option>
              <option value="UK">UK</option>
              <option value="USA">USA</option>
              <option value="AUS">AUS</option>
            </select>
          </div>

          <div class="card">
            <div class="section-title">Reading Level</div>
            <select v-model="paperTemplate.readingLevel" class="dropdown">
              <option disabled value="">Select Reading Level</option>
              <option value="Grade 5">Grade 5</option>
              <option value="Grade 6">Grade 6</option>
              <option value="Grade 7">Grade 7</option>
              <option value="Grade 8">Grade 8</option>
              <option value="Grade 9">Grade 9</option>
              <option value="Grade 10">Grade 10</option>
              <option value="Grade 11">Grade 11</option>
              <option value="Grade 12">Grade 12</option>
              <option value="Undergraduate">Undergraduate</option>
              <option value="Postgraduate">Postgraduate</option>
              <option value="PhD">PhD</option>
            </select>
          </div>

          <div class="card">
            <div class="section-title">Number of Subheadings</div>
            <div class="custom-word-count-input">
              <input v-model="paperTemplate.numSubheadings" type="number" min="1" max="10" placeholder="Enter number of subheadings..." />
            </div>
          </div>
        </template>

        <!-- Blank Template Mode Controls -->
        <template v-else-if="selectedMode === 'blank-template'">
          <div class="card">
            <div class="section-title" style="display: flex; align-items: center; justify-content: space-between;">
              <span>Citation Style</span>
              <span class="toc-tab-close" @click="toggleLeftSidebar">✕</span>
            </div>
            <select v-model="blankTemplate.citationStyle" class="dropdown">
              <option disabled value="">Select Citation Style</option>
              <option value="APA">APA (American Psychological Association)</option>
              <option value="MLA">MLA (Modern Language Association)</option>
              <option value="Chicago">Chicago (Chicago Manual of Style)</option>
              <option value="Harvard">Harvard</option>
              <option value="Vancouver">Vancouver</option>
              <option value="IEEE">IEEE (Institute of Electrical and Electronics Engineers)</option>
              <option value="AMA">AMA (American Medical Association)</option>
              <option value="ACS">ACS (American Chemical Society)</option>
              <option value="CSE">CSE (Council of Science Editors)</option>
              <option value="Bluebook">Bluebook</option>
            </select>
          </div>

          <div class="card">
            <div class="section-title">Dialect</div>
            <select v-model="blankTemplate.dialect" class="dropdown">
              <option disabled value="">Select Dialect</option>
              <option value="UK">UK</option>
              <option value="USA">USA</option>
              <option value="AUS">AUS</option>
            </select>
          </div>

          <div class="card">
            <div class="section-title">Reading Level</div>
            <select v-model="blankTemplate.readingLevel" class="dropdown">
              <option disabled value="">Select Reading Level</option>
              <option value="Grade 5">Grade 5</option>
              <option value="Grade 6">Grade 6</option>
              <option value="Grade 7">Grade 7</option>
              <option value="Grade 8">Grade 8</option>
              <option value="Grade 9">Grade 9</option>
              <option value="Grade 10">Grade 10</option>
              <option value="Grade 11">Grade 11</option>
              <option value="Grade 12">Grade 12</option>
              <option value="Undergraduate">Undergraduate</option>
              <option value="Postgraduate">Postgraduate</option>
              <option value="PhD">PhD</option>
            </select>
          </div>

          <div class="card">
            <div class="section-title">Number of Subheadings</div>
            <div class="custom-word-count-input">
              <input v-model="blankTemplate.numSubheadings" type="number" min="1" max="10" placeholder="Enter number of subheadings..." />
            </div>
          </div>
        </template>

        <!-- References and Word Count (shown in all modes except none, tok-exhibition, and economics) -->
        <template v-if="selectedMode !== 'none' && selectedMode !== 'tok-exhibition' && !['microeconomics', 'macroeconomics', 'globaleconomics'].includes(selectedMode)">
        <div class="card references-card">

          <div class="section-title references-header">

            References

            <span class="selected-count">{{ selectedReferences.length }} selected</span>

          </div>

          <!-- Search Bar (only for blank template mode) -->
          <div v-if="selectedMode === 'blank-template'" class="search-section">
            <div class="search-input-container">
              <input 
                v-model="searchTopic"
                type="text" 
                placeholder="Enter topic to search for references..."
                class="search-input"
                @keyup.enter="searchReferences"
              />
              <button 
                @click="searchReferences"
                :disabled="isSearching || !searchTopic.trim()"
                class="search-btn"
              >
                <span v-if="isSearching">Searching...</span>
                <span v-else>Search</span>
              </button>
            </div>
          </div>

          <!-- Enhanced Loading State -->
          <div v-if="loading || isSearching || isLoadingReferences" class="references-loading-container">
            <div class="loading-spinner-container">
              <div class="loading-spinner"></div>
              <div class="loading-text">{{ isSearching ? 'Searching for references...' : (isLoadingReferences ? 'Generating references...' : 'Loading references...') }}</div>
            </div>
            <!-- Skeleton Loader -->
            <div class="skeleton-loader-container">
              <div v-for="n in 3" :key="n" class="skeleton-reference-card">
                <div class="skeleton-title"></div>
                <div class="skeleton-authors"></div>
                <div class="skeleton-year"></div>
                <div class="skeleton-abstract"></div>
              </div>
            </div>
          </div>

          <ul v-else class="references-list">

            <li v-for="ref in references" :key="ref.reference_id" class="reference-item">

              <label class="ref-checkbox-label">

                <input type="checkbox" :checked="selectedReferences.includes(ref.reference_id)" @change="toggleGeneralReferenceSelection(ref)" class="ref-checkbox" />

                <div class="ref-card">

                  <div class="ref-title-row">

                    <span class="ref-title"><b>Title:</b> {{ ref.title || ref.TitleName }}</span>

                  </div>

                  <div class="ref-authors"><b>Authors:</b> {{ ref.author || ref.AuthorName }}</div>

                  <div class="ref-year"><b>Published:</b> {{ getRefYear(ref) }}</div>

                  <a class="ref-abstract" @click.prevent="openAbstractDialog(ref)">View Abstract</a>

                </div>

              </label>

            </li>

          </ul>

        </div>

        <div class="card word-count-card">

          <div class="section-title">

            Word Count

          </div>

          <div class="custom-word-count-input">

            <input 
              id="customWordCount" 
              v-model="currentWordCount" 
              type="number" 
              min="0" 
              placeholder="Enter word count..." 
            />

          </div>

        </div>
        </template>

        <!-- Instructions section (only for Paper Template and Blank Template modes) -->
        <template v-if="selectedMode === 'paper-template'">
          <div class="card">
            <div class="section-title">Instructions</div>
            
            <!-- Instruction Type Selection -->
            <div class="instruction-type-selector">
              <label class="radio-option">
                <input 
                  type="radio" 
                  v-model="paperTemplate.instructionType" 
                  value="text" 
                  class="radio-input"
                />
                <span class="radio-label">Text</span>
              </label>
              <label class="radio-option">
                <input 
                  type="radio" 
                  v-model="paperTemplate.instructionType" 
                  value="pdf" 
                  class="radio-input"
                />
                <span class="radio-label">PDF</span>
              </label>
            </div>

            <!-- Text Input -->
            <div v-if="paperTemplate.instructionType === 'text'" class="instruction-input">
              <textarea 
                v-model="paperTemplate.instructions" 
                class="dropdown" 
                placeholder="Enter your instructions..."
                rows="3"
                style="resize: vertical; height: auto; min-height: 80px;"
              ></textarea>
            </div>

            <!-- PDF Upload -->
            <div v-else-if="paperTemplate.instructionType === 'pdf'" class="instruction-input">
              <input 
                type="file" 
                @change="handlePdfUpload"
                accept=".pdf"
                class="dropdown"
              />
              <div v-if="paperTemplate.pdfText" class="pdf-preview">
                <small>PDF content extracted successfully.</small>
              </div>
            </div>
          </div>
        </template>

        <!-- Instructions section (only for Blank Template mode) -->
        <template v-if="selectedMode === 'blank-template'">
          <div class="card">
            <div class="section-title">Instructions</div>
            
            <!-- Instruction Type Selection -->
            <div class="instruction-type-selector">
              <label class="radio-option">
                <input 
                  type="radio" 
                  v-model="blankTemplate.instructionType" 
                  value="text" 
                  class="radio-input"
                />
                <span class="radio-label">Text</span>
              </label>
              <label class="radio-option">
                <input 
                  type="radio" 
                  v-model="blankTemplate.instructionType" 
                  value="pdf" 
                  class="radio-input"
                />
                <span class="radio-label">PDF</span>
              </label>
            </div>

            <!-- Text Input -->
            <div v-if="blankTemplate.instructionType === 'text'" class="instruction-input">
              <textarea 
                v-model="blankTemplate.instructions" 
                class="dropdown" 
                placeholder="Enter your instructions..."
                rows="3"
                style="resize: vertical; height: auto; min-height: 80px;"
              ></textarea>
            </div>

            <!-- PDF Upload -->
            <div v-else-if="blankTemplate.instructionType === 'pdf'" class="instruction-input">
              <input 
                type="file" 
                @change="handleBlankPdfUpload"
                accept=".pdf"
                class="dropdown"
              />
              <div v-if="blankTemplate.pdfText" class="pdf-preview">
                <small>PDF content extracted successfully.</small>
              </div>
            </div>
          </div>
        </template>

        <!-- Generate buttons (conditional based on mode) -->
        <template v-if="selectedMode === 'essay'">
          <button class="generate-essay-btn" @click="generateEssay" :disabled="isGenerating || !canGenerateEssay">
            <span v-if="isGenerating">Generating...</span>
            <span v-else>Generate Outline</span>
          </button>
        </template>
        
        <template v-else-if="selectedMode === 'tok-essay'">
          <button class="generate-essay-btn" @click="generateTokEssay" :disabled="isGenerating || !canGenerateTokEssay">
            <span v-if="isGenerating">Generating...</span>
            <span v-else>Generate Outline</span>
          </button>
        </template>
        
        <template v-else-if="selectedMode === 'tok'">
          <button class="generate-essay-btn" @click="generateTokJournal" :disabled="isGenerating || !canGenerateTokJournal">
            <span v-if="isGenerating">Generating...</span>
            <span v-else>Generate Journal</span>
          </button>
        </template>
        
        <template v-else-if="selectedMode === 'paper-template'">
          <button class="generate-essay-btn" @click="generateOutline" :disabled="isGeneratingOutline || !canGenerateOutline">
            <span v-if="isGeneratingOutline">Generating...</span>
            <span v-else>Generate Outline</span>
          </button>
        </template>
        
        <template v-else-if="selectedMode === 'blank-template'">
          <button class="generate-essay-btn" @click="generateBlankOutline" :disabled="isGeneratingBlankOutline || !canGenerateBlankOutline">
            <span v-if="isGeneratingBlankOutline">Generating...</span>
            <span v-else>Generate Outline</span>
          </button>
        </template>

        <!-- IB Economics Mode Controls -->
        <template v-else-if="selectedMode === 'microeconomics' || selectedMode === 'macroeconomics' || selectedMode === 'globaleconomics'">
          <div class="card">
            <div class="section-title" style="display: flex; align-items: center; justify-content: space-between;">
              <span>Economics Unit</span>
              <span class="toc-tab-close" @click="toggleLeftSidebar">✕</span>
            </div>
            <select v-model="ibEconomics.economicsUnit" class="dropdown" disabled>
              <option v-if="selectedMode === 'microeconomics'" value="microeconomics">Microeconomics</option>
              <option v-if="selectedMode === 'macroeconomics'" value="macroeconomics">Macroeconomics</option>
              <option v-if="selectedMode === 'globaleconomics'" value="global_economy">Global Economy</option>
            </select>
          </div>

          <!-- Article & Meta from Railway response -->
          <div class="card">
            <div class="section-title">Article Details</div>
            <div class="meta">
              <div v-if="ibEconomics.articleTitle"><strong>Title:</strong> {{ ibEconomics.articleTitle }}</div>
              <div v-if="ibEconomics.articleUrl">
                <strong>URL:</strong>
                <a :href="ibEconomics.articleUrl" target="_blank" rel="noopener">{{ ibEconomics.articleUrl }}</a>
              </div>
              <div v-if="ibEconomics.articleDate"><strong>Date:</strong> {{ ibEconomics.articleDate }}</div>
              <div v-if="ibEconomics.studentName"><strong>Student:</strong> {{ ibEconomics.studentName }}</div>
              <div v-if="ibEconomics.schoolName"><strong>School:</strong> {{ ibEconomics.schoolName }}</div>
              <div v-if="ibEconomics.citationStyle"><strong>Citation Style:</strong> {{ ibEconomics.citationStyle.toUpperCase() }}</div>
              <div v-if="ibEconomics.message" class="info">{{ ibEconomics.message }}</div>
            </div>
          </div>

          <div class="card">
            <div class="section-title">Article</div>
            <textarea 
              v-model="ibEconomics.article" 
              class="dropdown" 
              placeholder="Paste your economics article here..."
              rows="4"
              style="resize: vertical; height: auto; min-height: 100px;"
            ></textarea>
          </div>

          <div class="card">
            <div class="section-title">Citation Style</div>
            <select v-model="ibEconomics.citationStyle" class="dropdown">
              <option value="apa">APA</option>
              <option value="mla">MLA</option>
              <option value="chicago">Chicago</option>
            </select>
          </div>

          <!-- Concept Suggestions -->
          <div class="card">
            <div class="section-title">
              <span>Economic Concepts</span>
              <span v-if="ibEconomics.selectedConcepts.length > 0" class="selected-count">{{ ibEconomics.selectedConcepts.length }}/5 selected</span>
            </div>
            
            <div v-if="isLoadingSuggestions" class="loading-state">
              <div class="loading-spinner"></div>
              <div class="loading-text">Loading concepts...</div>
            </div>
            
            <div v-else-if="ibEconomics.suggestions.length > 0" class="concept-suggestions">
              <div 
                v-for="(suggestion, index) in ibEconomics.suggestions" 
                :key="index"
                class="concept-item"
                :class="{ 
                  'selected': ibEconomics.selectedConcepts.includes(suggestion.concept),
                  'disabled': !ibEconomics.selectedConcepts.includes(suggestion.concept) && ibEconomics.selectedConcepts.length >= 5
                }"
                @click="toggleConcept(suggestion.concept)"
              >
                <div class="concept-name">{{ suggestion.concept }}</div>
                <div class="concept-score">Score: {{ (suggestion.relevance_score * 100).toFixed(0) }}%</div>
                <div class="concept-explanation">{{ suggestion.explanation }}</div>
              </div>
            </div>
            
            <div v-else class="empty-concepts">
              <p>Economic concepts will load automatically when the article is provided.</p>
            </div>
          </div>

          <!-- Removed old outline generation button -->

          <!-- Generate Complete IA Button -->
          <button 
            class="generate-essay-btn" 
            @click="generateCompleteIA" 
            :disabled="isGeneratingCompleteIA || ibEconomics.selectedConcepts.length === 0"
            style="margin-top: 10px; background:#16a34a;"
          >
            <span v-if="isGeneratingCompleteIA">
              <span class="loading-spinner" style="margin-right:8px;"></span>
              Generating Complete IA...
            </span>
            <span v-else>
              Generate Complete IA
            </span>
          </button>
        </template>

      </aside>

      <!-- Left Sidebar Toggle Button (visible when sidebar is hidden) -->

      <div v-if="selectedMode !== 'none' && leftHidden" class="left-sidebar-toggle-btn" @click="toggleLeftSidebar">

        ☰

      </div>



      <!-- Main Editor Area -->

      <main class="main-editor">

        <slot />

      </main>



     <!-- Right Sidebar -->
<template v-if="selectedMode === 'essay'">
  <aside class="sidebar right toc-sidebar" :class="{ 'toc-hidden': tocHidden }">
    <div class="toc-tab-header">
      <!-- Two tabs -->
      <span 
        class="toc-tab" 
        :class="{ 'active': activeRightTab === 'toc' }"
        @click="activeRightTab = 'toc'"
      >
        Table Of Content
      </span>
      
      <span 
        class="toc-tab" 
        :class="{ 'active': activeRightTab === 'plagChecker' }"
        @click="activeRightTab = 'plagChecker'"
      >
        Plag Checker
      </span>

      <span class="toc-tab-close" @click="toggleTocSidebar">✕</span>
    </div>

    <div class="toc-card-outer">
      <div class="toc-card-inner">
        <!-- Table of Content Tab (your existing content) -->
        <div v-if="activeRightTab === 'toc'">
          <div class="toc-title">Table Of Content</div>
          <div class="toc-content">
            <div v-if="isGenerating" class="loading">Generating essay...</div>
            <div v-else-if="essayContent.length > 0" class="toc-sections">
              <div v-for="(section, idx) in essayContent" :key="section.title" class="toc-section">
                <div class="toc-section-header" @click="toggleSection(idx)">
                  <span class="toc-section-title">{{ section.title }}</span>
                  <span class="toc-section-arrow" :class="{ expanded: section.expanded }">&#8250;</span>
                  <button class="toc-section-copy" @click.stop="copySectionContent(idx)">
                    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                  </button>
                </div>
                <div v-if="section.expanded" class="toc-section-content" v-html="section.content"></div>
              </div>
            </div>
            <div v-else class="toc-placeholder">No essay generated yet.</div>
          </div>
        </div>

        <!-- Plagiarism Checker Tab -->
        <div v-if="activeRightTab === 'plagChecker'">
          <div class="toc-title">Plagiarism Checker</div>
          <div class="toc-content">
            <button 
              class="plag-checker-btn" 
              @click="checkPlagiarism"
              :disabled="isCheckingPlagiarism"
            >
              <span v-if="!isCheckingPlagiarism">Check for Plagiarism</span>
              <span v-else>Checking...</span>
            </button>
            
            <div v-if="plagiarismResult" class="plagiarism-result">
              <h4>Results:</h4>
              <div v-html="plagiarismResult"></div>
            </div>
            
            <div v-if="plagiarismError" class="plagiarism-error">
              {{ plagiarismError }}
            </div>
          </div>
        </div>
      </div>
    </div>
  </aside>
      </template>

      <!-- TOK Essay Mode - Table of Contents -->
      <template v-if="selectedMode === 'tok-essay'">
        <aside class="sidebar right toc-sidebar" :class="{ 'toc-hidden': tocHidden }">
          <div class="toc-tab-header">
            <!-- Two tabs -->
            <span 
              class="toc-tab" 
              :class="{ 'active': activeRightTab === 'toc' }"
              @click="activeRightTab = 'toc'"
            >
              TOK Essay Outline
            </span>
            
            <span 
              class="toc-tab" 
              :class="{ 'active': activeRightTab === 'plagChecker' }"
              @click="activeRightTab = 'plagChecker'"
            >
              Plag Checker
            </span>

            <span class="toc-tab-close" @click="toggleTocSidebar">✕</span>
          </div>

          <div class="toc-card-outer">
            <div class="toc-card-inner">
              <!-- TOK Essay Outline Tab -->
              <div v-if="activeRightTab === 'toc'">
                <div class="toc-header-with-copy">
                  <div class="toc-title">TOK Essay Outline</div>
                  <button 
                    v-if="essayContent.length > 0" 
                    class="copy-all-btn"
                    @click="copyEntireEssayOutline"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <rect width="14" height="14" x="8" y="8" rx="2" ry="2"/>
                      <path d="m4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>
                    </svg>
                    Copy All
                  </button>
                </div>
                <div class="toc-content">
                  <!-- Enhanced TOK Essay Outline Loading -->
                  <div v-if="isGenerating" class="tok-outline-loading-container">
                    <div class="loading-spinner-container">
                      <div class="loading-spinner"></div>
                      <div class="loading-text">Generating TOK essay outline...</div>
                    </div>
                    <!-- TOK Essay Skeleton Loader -->
                    <div class="skeleton-tok-outline-container">
                      <div class="skeleton-tok-section">
                        <div class="skeleton-section-title"></div>
                        <div class="skeleton-section-content"></div>
                        <div class="skeleton-section-content short"></div>
                      </div>
                      <div class="skeleton-tok-section">
                        <div class="skeleton-section-title"></div>
                        <div class="skeleton-section-content"></div>
                      </div>
                      <div class="skeleton-tok-section">
                        <div class="skeleton-section-title"></div>
                        <div class="skeleton-section-content"></div>
                        <div class="skeleton-section-content short"></div>
                      </div>
                    </div>
                  </div>
                  <div v-else-if="essayContent.length > 0" class="toc-sections">
                    <div v-for="(section, idx) in essayContent" :key="section.title" class="toc-section">
                      <div class="toc-section-header" @click="toggleSection(idx)">
                        <span class="toc-section-title">{{ section.title }}</span>
                        <span class="toc-section-arrow" :class="{ expanded: section.expanded }">&#8250;</span>
                        <button class="toc-section-copy" @click.stop="copySectionContent(idx)">
                          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                        </button>
                      </div>
                      <div v-if="section.expanded" class="toc-section-content" v-html="section.content"></div>
                    </div>
                  </div>
                  <div v-else class="toc-placeholder">No TOK essay outline generated yet.</div>
                </div>
              </div>

              <!-- Plagiarism Checker Tab -->
              <div v-if="activeRightTab === 'plagChecker'">
                <div class="toc-title">Plagiarism Checker</div>
                <div class="toc-content">
                  <button 
                    class="plag-checker-btn" 
                    @click="checkPlagiarism"
                    :disabled="isCheckingPlagiarism"
                  >
                    <span v-if="!isCheckingPlagiarism">Check for Plagiarism</span>
                    <span v-else>Checking...</span>
                  </button>
                  
                  <div v-if="plagiarismResult" class="plagiarism-result">
                    <h4>Results:</h4>
                    <div v-html="plagiarismResult"></div>
                  </div>
                  
                  <div v-if="plagiarismError" class="plagiarism-error">
                    {{ plagiarismError }}
                  </div>
                </div>
              </div>
            </div>
          </div>

        </aside>
      </template>

      <!-- TOK Journal Mode - Table of Contents -->
      <template v-if="selectedMode === 'tok'">
        <aside class="sidebar right toc-sidebar" :class="{ 'toc-hidden': tocHidden }">
          <div class="toc-tab-header">
            <!-- Two tabs -->
            <span 
              class="toc-tab" 
              :class="{ 'active': activeRightTab === 'toc' }"
              @click="activeRightTab = 'toc'"
            >
              TOK Journal
            </span>
            
            <span 
              class="toc-tab" 
              :class="{ 'active': activeRightTab === 'plagChecker' }"
              @click="activeRightTab = 'plagChecker'"
            >
              Plag Checker
            </span>

            <span class="toc-tab-close" @click="toggleTocSidebar">✕</span>
          </div>

          <div class="toc-card-outer">
            <div class="toc-card-inner">
              <!-- TOK Journal Tab -->
              <div v-if="activeRightTab === 'toc'">
                <div class="toc-header-with-copy">
                  <div class="toc-title">TOK Journal Entry</div>
                  <button 
                    v-if="essayContent.length > 0" 
                    class="copy-all-btn"
                    @click="copyEntireEssayOutline"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <rect width="14" height="14" x="8" y="8" rx="2" ry="2"/>
                      <path d="m4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>
                    </svg>
                    Copy All
                  </button>
                </div>
                <div class="toc-content">
                  <div v-if="isGenerating" class="loading">Generating TOK journal entry...</div>
                  <div v-else-if="essayContent.length > 0" class="toc-sections">
                    <div v-for="(section, idx) in essayContent" :key="section.title" class="toc-section">
                      <div class="toc-section-header" @click="toggleSection(idx)">
                        <span class="toc-section-title">{{ section.title }}</span>
                        <span class="toc-section-arrow" :class="{ expanded: section.expanded }">&#8250;</span>
                        <button class="toc-section-copy" @click.stop="copySectionContent(idx)">
                          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                        </button>
                      </div>
                      <div v-if="section.expanded" class="toc-section-content" v-html="section.content"></div>
                    </div>
                  </div>
                  <div v-else class="toc-placeholder">No TOK journal generated yet.</div>
                </div>
              </div>

              <!-- Plagiarism Checker Tab -->
              <div v-if="activeRightTab === 'plagChecker'">
                <div class="toc-title">Plagiarism Checker</div>
                <div class="toc-content">
                  <button 
                    class="plag-checker-btn" 
                    @click="checkPlagiarism"
                    :disabled="isCheckingPlagiarism"
                  >
                    <span v-if="!isCheckingPlagiarism">Check for Plagiarism</span>
                    <span v-else>Checking...</span>
                  </button>
                  
                  <div v-if="plagiarismResult" class="plagiarism-result">
                    <h4>Results:</h4>
                    <div v-html="plagiarismResult"></div>
                  </div>
                  
                  <div v-if="plagiarismError" class="plagiarism-error">
                    {{ plagiarismError }}
                  </div>
                </div>
              </div>
            </div>
          </div>

        </aside>
      </template>

      <!-- TOK Exhibition Mode - Right Sidebar -->
      <template v-if="selectedMode === 'tok-exhibition'">
        <aside class="sidebar right toc-sidebar" :class="{ 'toc-hidden': tocHidden }">
          <div class="toc-tab-header">
            <!-- Two tabs -->            
            <span 
              class="toc-tab" 
              :class="{ 'active': activeRightTab === 'essay' }"
              @click="activeRightTab = 'essay'"
            >
              Exhibition Essay
            </span>
            
            <span 
              class="toc-tab" 
              :class="{ 'active': activeRightTab === 'plagChecker' }"
              @click="activeRightTab = 'plagChecker'"
            >
              Plag Checker
            </span>

            <span class="toc-tab-close" @click="toggleTocSidebar">✕</span>
          </div>

          <div class="toc-card-outer">
            <div class="toc-card-inner">
              <!-- Essay Content Tab -->
              <div v-if="activeRightTab === 'essay'">
                <div class="toc-header-with-copy">
                  <div class="toc-title">Exhibition Essay</div>
                  <button 
                    v-if="essayContent.length > 0" 
                    class="copy-all-btn"
                    @click="copyEntireEssayOutline"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <rect width="14" height="14" x="8" y="8" rx="2" ry="2"/>
                      <path d="m4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>
                    </svg>
                    Copy All
                  </button>
                </div>
                <div class="toc-content">
                  <div v-if="tokExhibition.isGeneratingEssay" class="loading">Generating TOK Exhibition essay...</div>
                  <div v-else-if="essayContent.length > 0" class="toc-sections">
                    <div v-for="(section, idx) in essayContent" :key="section.title" class="toc-section">
                      <div class="toc-section-header" @click="toggleSection(idx)">
                        <span class="toc-section-title">{{ section.title }}</span>
                        <span class="toc-section-arrow" :class="{ expanded: section.expanded }">&#8250;</span>
                        <button class="toc-section-copy" @click.stop="copySectionContent(idx)">
                          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                        </button>
                      </div>
                      <div v-if="section.expanded" class="toc-section-content" v-html="section.content"></div>
                    </div>
                  </div>
                  <div v-else class="toc-placeholder">
                    Complete the exhibition process to generate your essay.
                  </div>
                </div>
              </div>

              <!-- Plagiarism Checker Tab -->
              <div v-if="activeRightTab === 'plagChecker'">
                <div class="toc-title">Plagiarism Checker</div>
                <div class="toc-content">
                  <button 
                    class="plag-checker-btn" 
                    @click="checkPlagiarism"
                    :disabled="isCheckingPlagiarism"
                  >
                    <span v-if="!isCheckingPlagiarism">Check for Plagiarism</span>
                    <span v-else>Checking...</span>
                  </button>
                  
                  <div v-if="plagiarismResult" class="plagiarism-result">
                    <h4>Results:</h4>
                    <div v-html="plagiarismResult"></div>
                  </div>
                  
                  <div v-if="plagiarismError" class="plagiarism-error">
                    {{ plagiarismError }}
                  </div>
                </div>
              </div>
            </div>
          </div>

        </aside>
      </template>

<!-- Paper Template Mode - Paper Outline Sidebar -->
<template v-else-if="selectedMode === 'paper-template'">
  <PaperOutlineRightSidebar 
    ref="outlineSidebarRef"
    :toc-hidden="tocHidden"
    :outline-data="outlineData"
    :generated-paper="generatedPaperData"
    :is-generating="isGeneratingOutline"
    @toggle-sidebar="toggleTocSidebar"
    @refine-outline="handleRefineOutline"
    @generate-full-paper="handleGenerateFullPaper"
    @clear-generated-paper="clearGeneratedPaper"
  />
</template>

<!-- Blank Template Mode - Paper Outline Sidebar -->
<template v-else-if="selectedMode === 'blank-template'">
  <PaperOutlineRightSidebar 
    :toc-hidden="tocHidden"
    :outline-data="outlineData"
    :generated-paper="generatedPaperData"
    :is-generating="isGeneratingBlankOutline"
    @toggle-sidebar="toggleTocSidebar"
    @refine-outline="handleRefineBlankOutline"
    @generate-full-paper="handleGenerateFullPaper"
    @clear-generated-paper="clearGeneratedPaper"
  />
</template>

<!-- IB Economics Mode - Outline Sidebar -->
<template v-else-if="selectedMode === 'microeconomics' || selectedMode === 'macroeconomics' || selectedMode === 'globaleconomics'">
  <aside class="sidebar right toc-sidebar" :class="{ 'toc-hidden': tocHidden }">
    <div class="toc-tab-header">
      <span 
        class="toc-tab" 
        :class="{ 'active': activeRightTab === 'toc' }"
        @click="activeRightTab = 'toc'"
      >
        Economics Outline
      </span>
      
      <span 
        class="toc-tab" 
        :class="{ 'active': activeRightTab === 'plagChecker' }"
        @click="activeRightTab = 'plagChecker'"
      >
        Plag Checker
      </span>

      <span class="toc-tab-close" @click="toggleTocSidebar">✕</span>
    </div>

    <div class="toc-card-outer">
      <div class="toc-card-inner">
        <!-- Economics Outline Tab -->
        <div v-if="activeRightTab === 'toc'">
          <div class="toc-header-with-copy">
            <div class="toc-title">Economics IA</div>
            <button 
              v-if="economicsIASections.length > 0" 
              class="copy-all-btn"
              @click="copyEntireEconomicsIA"
              :title="'Copy entire IA'"
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <rect width="14" height="14" x="8" y="8" rx="2" ry="2"/>
                <path d="m4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>
              </svg>
              Copy All
            </button>
          </div>
          
          <div class="toc-content">
            <div v-if="isGeneratingCompleteIA" class="generating-state">
              <div class="loading-spinner"></div>
              <div class="loading-text">Generating Complete IA...</div>
            </div>

            <!-- Render Complete IA as collapsible sections (like essay/paper) -->
            <div v-else-if="economicsIASections.length > 0" class="toc-sections">
              <div v-for="(section, idx) in economicsIASections" :key="section.title + '-' + idx" class="toc-section">
                <div class="toc-section-header" @click="toggleIaSection(idx)">
                  <span class="toc-section-title">{{ section.title }}</span>
                  <span class="toc-section-arrow" :class="{ expanded: section.expanded }">&#8250;</span>
                  <button class="toc-section-copy" @click.stop="copyIaSectionContent(idx)">
                    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                  </button>
                </div>
                <div v-if="section.expanded" class="toc-section-content" v-html="section.content"></div>
              </div>
            </div>

            <!-- Fallback: prompt to generate Complete IA -->
            <div v-else class="empty-state">
              <div class="empty-message">
                <p>No Complete IA generated yet.</p>
                <p class="empty-hint">Select key concepts on the left and click "Generate Complete IA".</p>
              </div>
            </div>
          </div>
        </div>

        <!-- Plagiarism Checker Tab -->
        <div v-if="activeRightTab === 'plagChecker'">
          <div class="toc-title">Plagiarism Checker</div>
          <div class="toc-content">
            <button 
              class="plag-checker-btn" 
              @click="checkPlagiarism"
              :disabled="isCheckingPlagiarism"
            >
              <span v-if="!isCheckingPlagiarism">Check for Plagiarism</span>
              <span v-else>Checking...</span>
            </button>

            <!-- Plagiarism Results -->
            <div v-if="plagiarismResults" class="plag-results">
              <div class="plag-score" :class="getPlagiarismScoreClass(plagiarismResults.overall_score)">
                <div class="score-label">Plagiarism Score</div>
                <div class="score-value">{{ plagiarismResults.overall_score }}%</div>
              </div>
              
              <div v-if="plagiarismResults.matches && plagiarismResults.matches.length > 0" class="plag-matches">
                <div class="matches-title">Potential Matches Found:</div>
                <div v-for="(match, index) in plagiarismResults.matches" :key="index" class="match-item">
                  <div class="match-text">{{ match.text }}</div>
                  <div class="match-source">{{ match.source }}</div>
                  <div class="match-similarity">{{ match.similarity }}% similarity</div>
                </div>
              </div>
              
              <div v-else class="no-matches">
                No significant matches found.
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </aside>
</template>

<!-- Toggle button for hidden right sidebar -->
<div v-if="tocHidden" class="sidebar-toggle-btn" @click="toggleTocSidebar">
  ☰
</div>

    </div>

    <!-- Abstract Dialog -->
    <div v-if="showAbstractDialog" class="abstract-dialog-overlay" @click="closeAbstractDialog">
      <div class="abstract-dialog" @click.stop>
        <div class="abstract-dialog-header">
          <h3 class="abstract-dialog-title">Abstract</h3>
          <button class="abstract-dialog-close" @click="closeAbstractDialog">✕</button>
        </div>
        <div class="abstract-dialog-content">
          <div class="abstract-text">
            <p>{{ selectedReference?.Abstract || 'Abstract content not available.' }}</p>
          </div>
        </div>
      </div>
    </div>

    <div v-if="showCopyToast" class="copy-toast">Content copied to clipboard</div>

    <!-- Save confirmation dialog -->
    <SaveConfirmationDialog 
      :show-dialog="showSaveDialog"
      @save="handleDialogSave"
      @dont-save="handleDialogDontSave"
      @cancel="handleDialogCancel"
    />

  </div>

</template>



<script setup>

import { ref, onMounted, onBeforeUnmount, computed, nextTick, watch } from 'vue'
import PaperOutlineRightSidebar from './PaperOutlineRightSidebar.vue'
import SaveConfirmationDialog from './SaveConfirmationDialog.vue'
import economicsApi from "../services/economicsapi.js"
import documentService from '../services/documentService.js'

// Mode management - read from query params
const selectedMode = ref('none') // 'none' for no sidebars, 'essay', 'paper-template', 'tok-essay', 'tok', or 'tok-exhibition'

// Function to get mode from query parameters
function getModeFromQueryParams() {
  const urlParams = new URLSearchParams(window.location.search);
  const selectmodule = urlParams.get('selectmodule');
  
  // BULLETPROOF: Store URL params for main website integration
  window.originalUrlParams = {
    selectmodule: selectmodule,
    user_id: urlParams.get('user_id'),
    document_id: urlParams.get('document_id') || urlParams.get('paper_id') || urlParams.get('sessionId'),
    topic: urlParams.get('topic'),
    referrer: document.referrer
  };
  console.log('🔗 URL params stored for main website integration:', window.originalUrlParams);
  
  // Valid modes: 'essay', 'paper', 'tok_essay', 'tok', 'blank', 'tok-exhibition', or economics modes
  if (selectmodule === 'essay') {
    console.log('Mode detected: essay');
    return 'essay';
  } else if (selectmodule === 'paper') {
    console.log('Mode detected: paper-template');
    return 'paper-template';
  } else if (selectmodule === 'blank') {
    return 'blank-template';
  } else if (selectmodule === 'tok_essay') {
    console.log('Mode detected: tok-essay');
    return 'tok-essay';
  } else if (selectmodule === 'tok') {
    console.log('Mode detected: tok');
    return 'tok';
  } else if (selectmodule === 'tok-exhibition') {
    console.log('Mode detected: tok-exhibition');
    return 'tok-exhibition';
  } else if (selectmodule === 'microeconomics') {
    return 'microeconomics';
  } else if (selectmodule === 'macroeconomics') {
    return 'macroeconomics';
  } else if (selectmodule === 'globaleconomics') {
    return 'globaleconomics';
  }
  
  return 'none'; // Default to no sidebars mode
}

// Function to get user_id from query parameters
function getUserIdFromQueryParams() {
  const urlParams = new URLSearchParams(window.location.search);
  let userId = urlParams.get('user_id') || '';
  
  // Clean up user_id - remove any query param contamination
  if (userId.includes('?')) {
    userId = userId.split('?')[0];
  }
  
  console.log('Getting user ID from query params:', userId);
  console.log('Full URL:', window.location.href);
  
  // If no user ID found, log the full URL for debugging
  if (!userId) {
    console.error('❌ No user_id found in query params. Full URL:', window.location.href);
    console.log('Available query params:', Array.from(urlParams.entries()));
  }
  
  return userId;
}

// Function to get article from query parameters
function getArticleFromQueryParams() {
  const urlParams = new URLSearchParams(window.location.search);
  return urlParams.get('article') || '';
}

// Helper: get any query param safely
function getQueryParam(name, fallback = '') {
  try {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get(name) || fallback;
  } catch (_) {
    return fallback;
  }
}

// Build Railway payload from query params + current selections
function buildEconomicsRailwayPayload(includeKeyConcepts = false) {
  const payload = {
    selectmodule: getQueryParam('selectmodule'),
    user_id: getUserIdFromQueryParams(),
    article: getQueryParam('article'),
    article_title: getQueryParam('article_title'),
    article_url: getQueryParam('article_url'),
    article_date: getQueryParam('article_date'),
    student_name: getQueryParam('student_name'),
    school_name: getQueryParam('school_name'),
    citations_style: 'apa',
    citation_style: 'apa'
  };
  // Map selectmodule to API's expected economics_unit
  const moduleVal = (payload.selectmodule || '').toLowerCase();
  const unitMap = {
    microeconomics: 'microeconomics',
    macroeconomics: 'macroeconomics',
    globaleconomics: 'global_economy',
    global_economy: 'global_economy'
  };
  payload.economics_unit = unitMap[moduleVal] || 'microeconomics';
  if (includeKeyConcepts) {
    payload.key_concept = ibEconomics.value.selectedConcepts.join(', ');
  }
  return payload;
}

// Function to get document_id or paper_id from URL path
function getIdFromPath() {
  const path = window.location.pathname;
  console.log('Getting ID from path:', path);
  
  // Extract the ID from paths like '/editor/123' or '/editor/dcad0eb0-2ae7-4590-8058-03f1ba405cb9'
  const match = path.match(/\/editor\/([^\/\?]+)/);
  const id = match ? match[1] : '1'; // Default to '1' if no ID found
  
  console.log('Extracted ID from path:', id);
  
  // If no ID found, log the full URL for debugging
  if (!match) {
    console.error('❌ No ID found in URL path. Full URL:', window.location.href);
  }
  
  return id;
}

// Essay mode variables
const selectedFormat = ref('')
const essayData = ref({
  title: '',
  references: [],
  generatedEssay: ''
})

// Paper mode variables  
const paperData = ref({
  topic: '',
  references: [],
  outline: {},
  citationStyle: '',
  generatedPaper: '',
  dialect: 'US',
  readingLevel: 'college'
})
const formats = [
  'APA (American Psychological Association)',
  'MLA (Modern Language Association)',
  'Chicago (Chicago Manual of Style)',
  'Harvard',
  'Vancouver',
  'IEEE (Institute of Electrical and Electronics Engineers)',
  'AMA (American Medical Association)',
  'ACS (American Chemical Society)',
  'CSE (Council of Science Editors)',
  'Bluebook'
]

// Paper template mode variables
const paperTemplate = ref({
  citationStyle: '',
  dialect: '',
  readingLevel: '',
  numSubheadings: '',
  instructionType: 'text', // 'text' or 'pdf'
  instructions: '',
  pdfText: ''
})

const isGeneratingOutline = ref(false)

// Blank template mode variables
const blankTemplate = ref({
  citationStyle: '',
  dialect: '',
  readingLevel: '',
  numSubheadings: '',
  instructionType: 'text', // 'text' or 'pdf'
  instructions: '',
  pdfText: ''
})

const isGeneratingBlankOutline = ref(false)
const searchTopic = ref('')
const isSearching = ref(false)
const outlineData = ref('')
const generatedPaperData = ref('')
const outlineSidebarRef = ref(null)

// IB Economics IA mode variables
const ibEconomics = ref({
  economicsUnit: '',
  article: '',
  citationStyle: 'apa',
  suggestions: [],
  selectedConcepts: [],
  outline: null,
  // Railway response fields
  articleTitle: '',
  articleUrl: '',
  articleDate: '',
  studentName: '',
  schoolName: '',
  message: ''
})

const isLoadingSuggestions = ref(false)
const isGeneratingEconomicsOutline = ref(false)
// Holds the Complete IA response from Railway
const economicsCompleteIA = ref(null)
// Loader for Complete IA generation
const isGeneratingCompleteIA = ref(false)
// Collapsible sections for Complete IA rendering
const economicsIASections = ref([])

// TOK essay mode variables
const tokEssay = ref({
  title: '',
  aok1: '',
  aok2: '',
  citationStyle: '',
  wordCount: 1700
})

// TOK journal mode variables
const tokJournal = ref({
  title: '',
  instructions: '',
  citationStyle: ''
})

// TOK Exhibition mode variables
const tokExhibition = ref({
  availablePrompts: [],
  selectedPrompt: null,
  selectedPromptNumber: null,
  suggestedObjects: [],
  selectedObjects: [],
  exhibitionReferences: [],
  selectedExhibitionReferences: [],
  citationFormat: 'APA7',
  currentStep: 1, // 1: prompts, 2: objects, 3: references, 4: generate
  isLoadingPrompts: false,
  isLoadingObjects: false,
  isLoadingReferences: false,
  isGeneratingEssay: false
})

// Helper: format TOK prompt dropdown label to avoid double numbering like "34. 34. Question"
function getTokPromptOptionLabel(index, prompt) {
  try {
    const displayIndex = index + 1;
    const stripped = String(prompt).replace(/^\s*\d+\s*\.\s*/, '');
    const label = `${displayIndex}. ${stripped}`;
    return label.length > 80 ? label.substring(0, 80) + '...' : label;
  } catch (_) {
    return `${index + 1}. ${prompt}`;
  }
}

// Economics IA mode variables
const economics = ref({
  article: '',
  unit: '',
  citationStyle: 'apa',
  currentStep: 1, // 1: get concepts, 2: generate outline, 3: generate commentary
  loading: false,
  suggestedConcepts: [],
  selectedConcept: '',
  outline: null,
  commentary: null,
  error: null
})

// Safeguard: list container for outline sections used by template and copy function
// Ensures expressions like `economicsOutlines.length` do not throw when rendering
const economicsOutlines = ref([])

const references = ref([])

const loading = ref(true)
const isLoadingReferences = ref(false)

const customWordCount = ref('')

const selectedReferences = ref([])

// Add this line to define isGenerating
const isGenerating = ref(false)

// Add canGenerateEssay computed property
const canGenerateEssay = computed(() => {
  return (
    selectedFormat.value &&
    selectedReferences.value.length > 0 &&
    customWordCount.value &&
    !isNaN(Number(customWordCount.value)) &&
    Number(customWordCount.value) > 0
  );
});

// Add canGenerateOutline computed property for paper template
const canGenerateOutline = computed(() => {
  const hasValidInstructions = 
    (paperTemplate.value.instructionType === 'text' && paperTemplate.value.instructions.trim()) ||
    (paperTemplate.value.instructionType === 'pdf' && paperTemplate.value.pdfText);
    
  return (
    paperTemplate.value.citationStyle &&
    paperTemplate.value.dialect &&
    paperTemplate.value.readingLevel &&
    paperTemplate.value.numSubheadings &&
    !isNaN(Number(paperTemplate.value.numSubheadings)) &&
    Number(paperTemplate.value.numSubheadings) > 0 &&
    customWordCount.value &&
    !isNaN(Number(customWordCount.value)) &&
    Number(customWordCount.value) > 0 &&
    hasValidInstructions
  );
});

// Add canGenerateBlankOutline computed property for blank template
const canGenerateBlankOutline = computed(() => {
  const hasValidInstructions = 
    (blankTemplate.value.instructionType === 'text' && blankTemplate.value.instructions.trim()) ||
    (blankTemplate.value.instructionType === 'pdf' && blankTemplate.value.pdfText);
    
  return (
    blankTemplate.value.citationStyle &&
    selectedReferences.value.length > 0 &&
    currentWordCount.value &&
    !isNaN(Number(currentWordCount.value)) &&
    Number(currentWordCount.value) > 0 &&
    hasValidInstructions &&
    searchTopic.value.trim() // Ensure there's a search topic
  );
});

// Add canGenerateTokEssay computed property for TOK essay template
const canGenerateTokEssay = computed(() => {
  return (
    
    tokEssay.value.aok1.trim() &&
    tokEssay.value.aok2.trim() &&
    tokEssay.value.citationStyle &&
    tokEssay.value.wordCount &&
    !isNaN(Number(tokEssay.value.wordCount)) &&
    Number(tokEssay.value.wordCount) > 0 &&
    selectedReferences.value.length > 0
  );
});

// Add canGenerateTokJournal computed property for TOK journal template
const canGenerateTokJournal = computed(() => {
  return (
   
    tokJournal.value.instructions.trim() &&
    tokJournal.value.citationStyle &&
    currentWordCount.value &&
    !isNaN(Number(currentWordCount.value)) &&
    Number(currentWordCount.value) > 0 &&
    selectedReferences.value.length > 0
  );
});

// IB Economics computed properties
const canGetSuggestions = computed(() => {
  return (
    ibEconomics.value.article.trim() &&
    ibEconomics.value.economicsUnit
  );
});

const canGenerateEconomicsOutline = computed(() => {
  return (
    ibEconomics.value.article.trim() &&
    ibEconomics.value.economicsUnit &&
    ibEconomics.value.selectedConcepts.length > 0 &&
    ibEconomics.value.citationStyle
  );
});

// Computed property for word count input
const currentWordCount = computed({
  get() {
    if (selectedMode.value === 'tok-essay') {
      return tokEssay.value.wordCount;
    } else {
      return customWordCount.value;
    }
  },
  set(value) {
    if (selectedMode.value === 'tok-essay') {
      tokEssay.value.wordCount = value;
    } else {
      customWordCount.value = value;
    }
  }
});

// DISABLED: Watch selectedReferences to prevent automatic database updates on selection changes
// This was causing selected references to be saved to database immediately on selection
// Now selection is UI-only and doesn't affect stored reference set
/*
watch(selectedReferences, (newSelectedRefs) => {
  console.log('🚫 DISABLED: selectedReferences watcher - selection is now UI-only');
  // Original logic commented out to prevent database updates on selection
  /*
  if (newSelectedRefs && newSelectedRefs.length > 0) {
    const fullReferenceObjects = newSelectedRefs.map(refId => {
      const ref = references.value.find(r => r.reference_id === refId);
      return ref ? {
        reference_id: ref.reference_id,
        AuthorName: ref.AuthorName || '',
        TitleName: ref.TitleName || '',
        Publisher: ref.Publisher || '',
        Year: ref.Year || '',
        Abstract: ref.Abstract || '',
        DOI: ref.DOI || '',
        URL: ref.URL || ''
      } : null;
    }).filter(ref => ref !== null);
    
    // Update both paperData and essayData references for saving
    if (selectedMode.value === 'paper-template') {
      paperData.value.references = fullReferenceObjects;
    } else if (selectedMode.value === 'essay') {
      essayData.value.references = fullReferenceObjects;
    }
    
    console.log(`📚 References updated for ${selectedMode.value} mode:`, fullReferenceObjects.length, 'references');
  }
}, { deep: true });
*/

// Add essayContent ref for parsed essay sections
const essayContent = ref([])  
// Abstract dialog state
const showAbstractDialog = ref(false)
const selectedReference = ref(null)

function openAbstractDialog(ref) {
  selectedReference.value = ref;
  showAbstractDialog.value = true;
}

function closeAbstractDialog() {
  showAbstractDialog.value = false;
  selectedReference.value = null;
}


// PDF upload handler
async function handlePdfUpload(event) {
  const file = event.target.files[0]
  if (!file) return

  try {
    // For now, we'll just extract text using a simple method
    // In a real implementation, you might use a PDF parsing library
    const formData = new FormData()
    formData.append('file', file)
    
    // Placeholder for PDF text extraction
    // You can implement actual PDF parsing here
    paperTemplate.value.pdfText = `PDF content extracted from ${file.name} (placeholder)`
    
  } catch (error) {
    console.error('Error processing PDF:', error)
    alert('Failed to process PDF file.')
  }
}

// Generate outline function
async function generateOutline() {
  if (!canGenerateOutline.value) return
  
  isGeneratingOutline.value = true
  
  try {
    // Get selected references data - API expects array of strings, not objects
    const selectedRefsData = selectedReferences.value.map(refId => {
      const ref = references.value.find(r => r.reference_id === refId);
      // Format as string instead of object
      return `${ref.AuthorName}. (${ref.Year}). ${ref.TitleName}. ${ref.Publisher || 'Publisher not specified'}.`;
    });
    
    // Generate topic from selected references or use a default
    const topic = selectedReferences.value.length > 0 
      ? selectedReferences.value.map(refId => {
          const ref = references.value.find(r => r.reference_id === refId);
          return ref.TitleName;
        }).join(', ')
      : "Impact of Artificial Intelligence on Modern Education";
    
    // Get instructions based on the selected type
    const instructionContent = paperTemplate.value.instructionType === 'text' 
      ? paperTemplate.value.instructions
      : paperTemplate.value.pdfText;
    
    // Use the instructions as-is, or empty string if none provided (API accepts empty string)
    const finalInstructions = instructionContent || "";
    
    const payload = {
      topic: topic,
      instructions: finalInstructions,
      citation_style: paperTemplate.value.citationStyle,
      selected_references: selectedRefsData,
      num_subheadings: parseInt(paperTemplate.value.numSubheadings),
      dialect: paperTemplate.value.dialect,
      word_count: parseInt(customWordCount.value),
      reading_level: paperTemplate.value.readingLevel,
      additional_notes: "Use recent studies from 2020 onwards."
    }
    
    console.log('Sending payload to API:', JSON.stringify(payload, null, 2))
    
    const response = await fetch('https://jfv6blghbfv5lr3wt6sho4kewe0mrifm.lambda-url.us-east-1.on.aws/generate_outline', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify(payload)
    })
    
    console.log('Response status:', response.status)
    console.log('Response headers:', response.headers)
    
    if (!response.ok) {
      const errorText = await response.text()
      console.error('Error response:', errorText)
      throw new Error(`HTTP error! status: ${response.status}, message: ${errorText}`)
    }
    
    const data = await response.json()
    console.log('API response:', data)
    console.log('data.outline type:', typeof data.outline)
    console.log('data.outline value:', data.outline)
    console.log('data.outline length/size:', typeof data.outline === 'string' ? data.outline.length : Object.keys(data.outline || {}).length)
    
    outlineData.value = data.outline || ''
    
    // Update paperData.value.outline for saving - don't parse as JSON since outline is text/HTML
    paperData.value.outline = data.outline || ''
    
    // Update paperData.value.generatedPaper with the outline content
    paperData.value.generatedPaper = data.outline || ''
    
    // Update paperData.value.references with complete reference set for saving  
    paperData.value.references = references.value.map(ref => ({
      reference_id: ref.reference_id,
      AuthorName: ref.AuthorName || '',
      TitleName: ref.TitleName || '',
      Publisher: ref.Publisher || '',
      Year: ref.Year || '',
      Abstract: ref.Abstract || '',
      DOI: ref.DOI || '',
      URL: ref.URL || ''
    })) // Save complete reference set, not just selected ones
    
    // Only show error if outline is truly missing or empty - improved logic
    const outlineExists = data.outline && (
      (typeof data.outline === 'string' && data.outline.trim().length > 0) ||
      (typeof data.outline === 'object' && Object.keys(data.outline).length > 0)
    );
      
    if (!outlineExists) {
      console.warn('No outline data received from API')
      alert('No outline data received from the API. Please try again.')
      return; // Exit early if no outline
    }
    
    // If we reach here, outline was generated successfully
    console.log('✅ Outline generated successfully - content verified')
    
    // BULLETPROOF: Save the outline immediately after generation with retry
    try {
      await saveDocument();
      console.log('✅ Outline saved to database after generation');
      
      // Verify save worked by checking if data was stored
      if (!outlineData.value || outlineData.value.trim() === '') {
        console.error('⚠️ Outline data seems empty after save - retrying...');
        // Retry save once more
        await saveDocument();
      }
    } catch (saveError) {
      console.error('⚠️ Failed to save outline after generation - CRITICAL:', saveError);
      // Try alternative save method as fallback
      try {
        if (selectedMode.value === 'paper-template') {
          await savePaperDocument();
          console.log('✅ Outline saved via fallback method');
        }
      } catch (fallbackError) {
        console.error('❌ All save methods failed for outline - USER DATA AT RISK:', fallbackError);
        alert('Critical: Failed to save generated outline. Please copy your content and refresh the page.');
      }
    }
    
  } catch (error) {
    console.error('Error generating outline:', error)
    
    // More specific error messages
    if (error.name === 'TypeError' && error.message.includes('Failed to fetch')) {
      alert('Network error: Unable to connect to the API. Please check your internet connection and try again.')
    } else if (error.message.includes('HTTP error')) {
      alert(`API Error: ${error.message}`)
    } else {
      alert('Failed to generate outline. Please try again. Check the console for more details.')
    }
  } finally {
    isGeneratingOutline.value = false
  }
}

// Handle refine outline request from child component
async function handleRefineOutline(instructions) {
  if (!instructions.trim() || !outlineData.value) return
  
  isGeneratingOutline.value = true
  
  try {
    // Get selected references data
    const selectedRefsData = selectedReferences.value.map(refId => {
      const ref = references.value.find(r => r.reference_id === refId);
      return `${ref.AuthorName}. (${ref.Year}). ${ref.TitleName}. ${ref.Publisher || 'Publisher not specified'}.`;
    });
    
    // Generate topic from selected references or use a default
    const topic = selectedReferences.value.length > 0 
      ? selectedReferences.value.map(refId => {
          const ref = references.value.find(r => r.reference_id === refId);
          return ref.TitleName;
        }).join(', ')
      : "Impact of Artificial Intelligence on Modern Education";
    
    // Get original instructions
    const originalInstructions = paperTemplate.value.instructionType === 'text' 
      ? paperTemplate.value.instructions
      : paperTemplate.value.pdfText;
    
    // Combine original instructions with refinement instructions
    const combinedInstructions = originalInstructions 
      ? `${originalInstructions}\n\nAdditional refinements: ${instructions}`
      : `Refinements: ${instructions}`;
    
    const payload = {
      topic: topic,
      instructions: combinedInstructions,
      citation_style: paperTemplate.value.citationStyle,
      selected_references: selectedRefsData,
      num_subheadings: Number.isNaN(parseInt(paperTemplate.value.numSubheadings)) ? 0 : parseInt(paperTemplate.value.numSubheadings),
      dialect: paperTemplate.value.dialect,
      word_count: Number.isNaN(parseInt(customWordCount.value)) ? 0 : parseInt(customWordCount.value),
      reading_level: paperTemplate.value.readingLevel,
      additional_notes: `Refine the existing outline based on: ${instructions}`,
      current_outline: outlineData.value // Pass current outline for refinement context
    }
    
    console.log('Refining outline with instructions:', instructions)
    console.log('Sending payload to API:', JSON.stringify(payload, null, 2))
    
    const response = await fetch('https://jfv6blghbfv5lr3wt6sho4kewe0mrifm.lambda-url.us-east-1.on.aws/generate_outline', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify(payload)
    })
    
    if (!response.ok) {
      const errorText = await response.text()
      console.error('Error response:', errorText)
      throw new Error(`HTTP error! status: ${response.status}, message: ${errorText}`)
    }
    
    const data = await response.json()
    console.log('API response:', data)
    
    // Update the outline with refined content
    outlineData.value = data.outline || ''
    
    // Update paperData.value.outline for saving
    // Outline returned by API is plain text/HTML; do NOT JSON.parse
    paperData.value.outline = data.outline || ''
    
    // Update paperData.value.generatedPaper with the outline content
    paperData.value.generatedPaper = data.outline || ''
    
    // Update paperData.value.references with complete reference set for saving  
    paperData.value.references = references.value.map(ref => ({
      reference_id: ref.reference_id,
      AuthorName: ref.AuthorName || '',
      TitleName: ref.TitleName || '',
      Publisher: ref.Publisher || '',
      Year: ref.Year || '',
      Abstract: ref.Abstract || '',
      DOI: ref.DOI || '',
      URL: ref.URL || ''
    })) // Save complete reference set, not just selected ones
    
    // Only show error if outline is truly missing or empty
    if (!data.outline || (typeof data.outline === 'string' && data.outline.trim() === '')) {
      console.warn('No refined outline data received from API')
      alert('No refined outline data received from the API. Please try again.')
    } else {
      console.log('✅ Refined outline generated successfully')
      
      // BULLETPROOF: Save the refined outline immediately after generation with retry
      try {
        await saveDocument();
        console.log('✅ Refined outline saved to database after generation');
        
        // Verify save worked
        if (!outlineData.value || outlineData.value.trim() === '') {
          console.error('⚠️ Refined outline data seems empty after save - retrying...');
          await saveDocument();
        }
      } catch (saveError) {
        console.error('⚠️ Failed to save refined outline after generation - CRITICAL:', saveError);
        try {
          if (selectedMode.value === 'paper-template') {
            await savePaperDocument();
            console.log('✅ Refined outline saved via fallback method');
          }
        } catch (fallbackError) {
          console.error('❌ All save methods failed for refined outline - USER DATA AT RISK:', fallbackError);
          alert('Critical: Failed to save refined outline. Please copy your content and refresh the page.');
        }
      }
    }
    
  } catch (error) {
    console.error('Error refining outline:', error)
    
    if (error.name === 'TypeError' && error.message.includes('Failed to fetch')) {
      alert('Network error: Unable to connect to the API. Please check your internet connection and try again.')
    } else if (error.message.includes('HTTP error')) {
      alert(`API Error: ${error.message}`)
    } else {
      alert('Failed to refine outline. Please try again. Check the console for more details.')
    }
  } finally {
    isGeneratingOutline.value = false
    // Reset refining state in child component
    if (outlineSidebarRef.value) {
      outlineSidebarRef.value.setRefining(false)
    }
  }
}

// Handle generate full paper request from child component
async function handleGenerateFullPaper(outlineContent) {
  if (!outlineContent || !outlineContent.trim()) return
  
  try {
    // Get selected references data
    const selectedRefsData = selectedReferences.value.map(refId => {
      const ref = references.value.find(r => r.reference_id === refId);
      return `${ref.AuthorName}. (${ref.Year}). ${ref.TitleName}. ${ref.Publisher || 'Publisher not specified'}.`;
    });
    
    // Generate topic from selected references or use a default
    const topic = selectedReferences.value.length > 0 
      ? selectedReferences.value.map(refId => {
          const ref = references.value.find(r => r.reference_id === refId);
          return ref.TitleName;
        }).join(', ')
      : "Impact of Artificial Intelligence on Modern Education";
    
    // Get original instructions
    const originalInstructions = paperTemplate.value.instructionType === 'text' 
      ? paperTemplate.value.instructions
      : paperTemplate.value.pdfText;
    
    const payload = {
      topic: topic,
      instructions: originalInstructions || '',
      citation_style: paperTemplate.value.citationStyle,
      selected_references: selectedRefsData,
      num_subheadings: Number.isNaN(parseInt(paperTemplate.value.numSubheadings)) ? 0 : parseInt(paperTemplate.value.numSubheadings),
      dialect: paperTemplate.value.dialect,
      word_count: Number.isNaN(parseInt(customWordCount.value)) ? 0 : parseInt(customWordCount.value),
      reading_level: paperTemplate.value.readingLevel,
      additional_notes: '',
      outline: outlineContent,
      include_subheadings: true
    }
    
    console.log('Generating full paper with outline:', outlineContent)
    console.log('Sending payload to API:', JSON.stringify(payload, null, 2))
    
    // Set generating state in child component
    if (outlineSidebarRef.value) {
      outlineSidebarRef.value.setGeneratingPaper(true)
    }
    
    const response = await fetch('https://jfv6blghbfv5lr3wt6sho4kewe0mrifm.lambda-url.us-east-1.on.aws/generate_paper', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify(payload)
    })
    
    if (!response.ok) {
      const errorText = await response.text()
      console.error('Error response:', errorText)
      throw new Error(`HTTP error! status: ${response.status}, message: ${errorText}`)
    }
    
    const data = await response.json()
    console.log('Full paper API response:', data)
    
    // Display the generated paper in the sidebar
    if (data.paper) {
      // Store the generated paper for sidebar display
      generatedPaperData.value = data.paper
      
      // Update paperData for saving
      paperData.value.generatedPaper = data.paper
      
      console.log('✅ Full paper generated and displayed in sidebar')
      
      // Save the document with the new paper content
      try {
        await saveDocument();
        console.log('✅ Full paper saved to database after generation');
      } catch (saveError) {
        console.error('⚠️ Failed to save full paper after generation:', saveError);
        alert('Paper generated successfully but failed to save. Please manually save the document.');
      }
    } else {
      console.warn('No paper content received from API')
      alert('No paper content was received from the API. Please try again.')
    }
    
  } catch (error) {
    console.error('Error generating full paper:', error)
    
    if (error.name === 'TypeError' && error.message.includes('Failed to fetch')) {
      alert('Network error: Unable to connect to the API. Please check your internet connection and try again.')
    } else if (error.message.includes('HTTP error')) {
      alert(`API Error: ${error.message}`)
    } else {
      alert('Failed to generate full paper. Please try again. Check the console for more details.')
    }
  } finally {
    // Reset generating state in child component
    if (outlineSidebarRef.value) {
      outlineSidebarRef.value.setGeneratingPaper(false)
    }
  }
}

// Handle clear generated paper request from child component
function clearGeneratedPaper() {
  generatedPaperData.value = ''
  console.log('✅ Generated paper cleared, returning to outline view')
}

// Search for references (for blank template)
async function searchReferences() {
  if (!searchTopic.value.trim()) return
  
  isSearching.value = true
  references.value = []
  selectedReferences.value = []
  
  try {
    const response = await fetch(`${backend_url}/generate_references`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        topic: [searchTopic.value.trim()]
      })
    })
    
    if (!response.ok) {
      throw new Error('Failed to fetch references')
    }
    
    const data = await response.json()
    references.value = data.references || []
  } catch (error) {
    console.error('Error fetching references:', error)
    alert('Failed to fetch references. Please try again.')
  } finally {
    isSearching.value = false
  }
}

// Handle PDF upload for blank template
async function handleBlankPdfUpload(event) {
  const file = event.target.files[0]
  if (!file) return
  
  try {
    const formData = new FormData()
    formData.append('pdf', file)
    
    const response = await fetch(`${backend_url}/extract_pdf_text`, {
      method: 'POST',
      body: formData
    })
    
    if (!response.ok) {
      throw new Error('Failed to extract PDF text')
    }
    
    const data = await response.json()
    blankTemplate.value.pdfText = data.text || ''
  } catch (error) {
    console.error('Error extracting PDF text:', error)
    alert('Failed to extract text from PDF')
  }
}

// Generate outline for blank template
async function generateBlankOutline() {
  if (!canGenerateBlankOutline.value) return
  
  isGeneratingBlankOutline.value = true
  
  try {
    // Get selected references data
    const selectedRefsData = selectedReferences.value.map(refId => {
      const ref = references.value.find(r => r.reference_id === refId)
      return `${ref.AuthorName}. (${ref.Year}). ${ref.TitleName}. ${ref.Publisher || 'Publisher not specified'}.`
    })
    
    // Use search topic as the paper topic
    const topic = searchTopic.value.trim()
    
    // Get instructions based on the selected type
    const instructionContent = blankTemplate.value.instructionType === 'text' 
      ? blankTemplate.value.instructions
      : blankTemplate.value.pdfText
    
    const payload = {
      topic: topic,
      instructions: instructionContent || '',
      citation_style: blankTemplate.value.citationStyle,
      dialect: blankTemplate.value.dialect || 'US',
      word_count: parseInt(currentWordCount.value) || 1000,
      reading_level: blankTemplate.value.readingLevel || 'college',
      num_subheadings: parseInt(blankTemplate.value.numSubheadings) || 3,
      references: selectedRefsData
    }
    
    const response = await fetch(`${backend_url}/generate_paper_outline`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload)
    })
    
    if (!response.ok) {
      throw new Error('Failed to generate outline')
    }
    
    const data = await response.json()
    outlineData.value = data.outline_content || data.outline || ''
    
  } catch (error) {
    console.error('Error generating blank outline:', error)
    alert('Failed to generate outline. Please try again.')
  } finally {
    isGeneratingBlankOutline.value = false
  }
}

// Handle refine outline request for blank template
async function handleRefineBlankOutline(instructions) {
  if (!instructions.trim() || !outlineData.value) return
  
  isGeneratingBlankOutline.value = true
  
  try {
    // Get selected references data
    const selectedRefsData = selectedReferences.value.map(refId => {
      const ref = references.value.find(r => r.reference_id === refId)
      return `${ref.AuthorName}. (${ref.Year}). ${ref.TitleName}. ${ref.Publisher || 'Publisher not specified'}.`
    })
    
    const topic = searchTopic.value.trim()
    
    // Get original instructions
    const originalInstructions = blankTemplate.value.instructionType === 'text' 
      ? blankTemplate.value.instructions
      : blankTemplate.value.pdfText
    
    const payload = {
      topic: topic,
      instructions: originalInstructions || '',
      refinement_instructions: instructions,
      citation_style: blankTemplate.value.citationStyle,
      dialect: blankTemplate.value.dialect || 'US',
      word_count: parseInt(currentWordCount.value) || 1000,
      reading_level: blankTemplate.value.readingLevel || 'college',
      num_subheadings: parseInt(blankTemplate.value.numSubheadings) || 3,
      references: selectedRefsData,
      current_outline: outlineData.value
    }
    
    const response = await fetch(`${backend_url}/refine_paper_outline`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload)
    })
    
    if (!response.ok) {
      throw new Error('Failed to refine outline')
    }
    
    const data = await response.json()
    outlineData.value = data.refined_outline || data.outline_content || ''
    
  } catch (error) {
    console.error('Error refining blank outline:', error)
    alert('Failed to refine outline. Please try again.')
  } finally {
    isGeneratingBlankOutline.value = false
  }
}

async function generateTokEssay() {
  if (!canGenerateTokEssay.value) return;
  
  isGenerating.value = true;
  essayContent.value = []; // Clear previous essay
  
  try {
    // Get selected references data
    const selectedRefsData = selectedReferences.value.map(refId => {
      const ref = references.value.find(r => r.reference_id === refId);
      const refData = {
        title: ref.TitleName,
        authors: ref.AuthorName,
        year: ref.Year
      };
      
      // Link removed from payload
      
      return refData;
    });
     const urlParams = new URLSearchParams(window.location.search);
    const topicParam = urlParams.get('topic');
    
    // Use topic from query param or fallback to default
    const topic = topicParam ? topicParam : "artificial intelligence";
    
    const payload = {
      user_id: getUserIdFromQueryParams(),
      title: topic,
      aok1: tokEssay.value.aok1,
      aok2: tokEssay.value.aok2,
      word_count: parseInt(tokEssay.value.wordCount),
      citation_style: tokEssay.value.citationStyle,
      references: selectedRefsData
    };
    
    console.log('Sending TOK essay payload to API:', JSON.stringify(payload, null, 2));

    const response = await fetch('https://jfv6blghbfv5lr3wt6sho4kewe0mrifm.lambda-url.us-east-1.on.aws/tok-essay', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload)
    });
    
    if (!response.ok) {
      const errorText = await response.text();
      console.error('Error response:', errorText);
      throw new Error(`HTTP error! status: ${response.status}, message: ${errorText}`);
    }
    
    const data = await response.json();
    console.log('TOK essay API response:', data);
    console.log('Available keys in response:', Object.keys(data));
    
    // Try different possible response formats
    let essayHtml = '';
    if (data.essay) {
      essayHtml = data.essay;
    } else if (data.content) {
      essayHtml = data.content;
    } else if (data.outline) {
      essayHtml = data.outline;
    } else if (data.result) {
      essayHtml = data.result;
    } else if (typeof data === 'string') {
      essayHtml = data;
    } else {
      // If none of the expected keys exist, log the full response
      console.log('Unexpected response format, full data:', data);
      essayHtml = JSON.stringify(data);
    }
    
    console.log('Essay HTML to parse:', essayHtml);
    
    // Parse the HTML essay content
    parseEssayContent(essayHtml);
    
    // Persist TOK Essay to database immediately after generation
    try {
      await saveTokEssayDocument();
      console.log('✅ TOK Essay saved to database after generation');
    } catch (saveError) {
      console.error('⚠️ Failed to save TOK Essay after generation:', saveError);
    }
    
  } catch (error) {
    console.error('Error generating TOK essay:', error);
    
    if (error.name === 'TypeError' && error.message.includes('Failed to fetch')) {
      alert('Network error: Unable to connect to the API. Please check your internet connection and try again.');
    } else if (error.message.includes('HTTP error')) {
      alert(`API Error: ${error.message}`);
    } else {
      alert('Failed to generate TOK essay. Please try again. Check the console for more details.');
    }
  } finally {
    isGenerating.value = false;
  }
}

async function generateTokJournal() {
  if (!canGenerateTokJournal.value) return;
  
  isGenerating.value = true;
  essayContent.value = []; // Clear previous content
  
  try {
    // Get selected references data for TOK journal
    const selectedRefsData = selectedReferences.value.map(refId => {
      const ref = references.value.find(r => r.reference_id === refId);
      
      const refData = {
        title: ref.TitleName || '',
        authors: ref.AuthorName || '',
        year: ref.Year || ''
      };
      
      return refData;
    });
    
    // Get topic from selected references for the journal
    const topic = selectedReferences.value.length > 0 
      ? selectedReferences.value.map(refId => {
          const ref = references.value.find(r => r.reference_id === refId);
          return ref.TitleName;
        }).join(', ')
      : "The Role of Imagination in Knowledge";
    
    const payload = {
      user_id: getUserIdFromQueryParams(),
      topic: topic,
      instructions: tokJournal.value.instructions,
      citation_style: tokJournal.value.citationStyle,
      num_words: parseInt(currentWordCount.value),
      references: selectedRefsData
    };
    
    console.log('Sending TOK journal payload to API:', JSON.stringify(payload, null, 2));
    
    const response = await fetch(' https://jfv6blghbfv5lr3wt6sho4kewe0mrifm.lambda-url.us-east-1.on.aws/journal', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload)
    });
    
    if (!response.ok) {
      const errorText = await response.text();
      console.error('Error response:', errorText);
      throw new Error(`HTTP error! status: ${response.status}, message: ${errorText}`);
    }
    
    const data = await response.json();
    console.log('TOK journal API response:', data);
    console.log('Available keys in response:', Object.keys(data));
    
    // Parse the journal response
    let journalHtml = '';
    if (data.journal) {
      journalHtml = data.journal;
    } else if (data.content) {
      journalHtml = data.content;
    } else if (data.result) {
      journalHtml = data.result;
    } else if (typeof data === 'string') {
      journalHtml = data;
    } else {
      console.log('Unexpected response format, full data:', data);
      journalHtml = JSON.stringify(data);
    }
    
    console.log('Journal HTML to parse:', journalHtml);
    
    // Parse the journal content
    parseEssayContent(journalHtml);
    
    // Persist TOK Journal to database immediately after generation
    try {
      await saveTokJournalDocument();
      console.log('✅ TOK Journal saved to database after generation');
    } catch (saveError) {
      console.error('⚠️ Failed to save TOK Journal after generation:', saveError);
    }
    
  } catch (error) {
    console.error('Error generating TOK journal:', error);
    
    if (error.name === 'TypeError' && error.message.includes('Failed to fetch')) {
      alert('Network error: Unable to connect to the API. Please check your internet connection and try again.');
    } else if (error.message.includes('HTTP error')) {
      alert(`API Error: ${error.message}`);
    } else {
      alert('Failed to generate TOK journal. Please try again. Check the console for more details.');
    }
  } finally {
    isGenerating.value = false;
  }
}

// TOK Exhibition API Functions
const baseExhibitionUrl = 'https://jfv6blghbfv5lr3wt6sho4kewe0mrifm.lambda-url.us-east-1.on.aws';

async function fetchTokExhibitionPrompts() {
  try {
    console.log('🚀 STARTING: fetchTokExhibitionPrompts');
    tokExhibition.value.isLoadingPrompts = true;
    
    console.log('🌐 Fetching TOK Exhibition prompts from:', `${baseExhibitionUrl}/prompts`);
    console.log('🔍 Current mode:', selectedMode.value);
    
    const response = await fetch(`${baseExhibitionUrl}/prompts`, {
      method: 'GET'
    });
    
    console.log('Response status:', response.status);
    console.log('Response ok:', response.ok);
    
    if (!response.ok) {
      const errorText = await response.text();
      console.error('Error response body:', errorText);
      throw new Error(`HTTP error! status: ${response.status}, message: ${errorText}`);
    }
    
    const data = await response.json();
    console.log('Raw response data:', data);
    console.log('Data type:', typeof data);
    console.log('Data length:', Array.isArray(data) ? data.length : 'Not an array');
    
    // Handle different possible response formats
    if (Array.isArray(data)) {
      tokExhibition.value.availablePrompts = data;
    } else if (data.prompts && Array.isArray(data.prompts)) {
      tokExhibition.value.availablePrompts = data.prompts;
    } else if (data.data && Array.isArray(data.data)) {
      tokExhibition.value.availablePrompts = data.data;
    } else if (typeof data === 'object') {
      // Handle object format like {0: 'prompt1', 1: 'prompt2', ...}
      tokExhibition.value.availablePrompts = Object.values(data);
    } else {
      console.error('Unexpected response format:', data);
      throw new Error('Unexpected response format from prompts API');
    }
    
    console.log('TOK Exhibition prompts set to:', tokExhibition.value.availablePrompts);
    
  } catch (error) {
    console.error('Error fetching TOK Exhibition prompts:', error);
    
    // More specific error messages
    if (error.name === 'TypeError' && error.message.includes('Failed to fetch')) {
      alert('Network error: Unable to connect to the API. Please check your internet connection and try again.');
    } else if (error.message.includes('HTTP error')) {
      alert(`API Error: ${error.message}`);
    } else {
      alert('Failed to fetch prompts. Please check the console for more details.');
    }
  } finally {
    tokExhibition.value.isLoadingPrompts = false;
  }
}

async function suggestTokExhibitionObjects() {
  try {
    tokExhibition.value.isLoadingObjects = true;
    
    const payload = {
      prompt_number: tokExhibition.value.selectedPromptNumber
    };
    
    const response = await fetch(`${baseExhibitionUrl}/suggest-objects`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload)
    });
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    const data = await response.json();
    tokExhibition.value.suggestedObjects = data.suggested_objects || [];
    tokExhibition.value.selectedPrompt = data.prompt;
    tokExhibition.value.currentStep = 2;
    console.log('TOK Exhibition objects suggested:', data);
    
    // Save progress after getting object suggestions
    try {
      await saveTokExhibitionDocument();
      console.log('✅ TOK Exhibition progress saved after object suggestions');
    } catch (saveError) {
      console.error('⚠️ Failed to save TOK Exhibition progress after object suggestions:', saveError);
    }
    
  } catch (error) {
    console.error('Error suggesting TOK Exhibition objects:', error);
    alert('Failed to suggest objects. Please try again.');
  } finally {
    tokExhibition.value.isLoadingObjects = false;
  }
}

async function refreshTokExhibitionObjects() {
  try {
    tokExhibition.value.isLoadingObjects = true;
    
    const payload = {
      prompt_number: tokExhibition.value.selectedPromptNumber
    };
    
    const response = await fetch(`${baseExhibitionUrl}/refresh-objects`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload)
    });
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    const data = await response.json();
    tokExhibition.value.suggestedObjects = data.suggested_objects || [];
    console.log('TOK Exhibition objects refreshed:', data);
    
  } catch (error) {
    console.error('Error refreshing TOK Exhibition objects:', error);
    alert('Failed to refresh objects. Please try again.');
  } finally {
    tokExhibition.value.isLoadingObjects = false;
  }
}

async function fetchTokExhibitionReferences() {
  try {
    tokExhibition.value.isLoadingReferences = true;
    
    const payload = {
      prompt: tokExhibition.value.selectedPrompt,
      objects: tokExhibition.value.selectedObjects,
      reference_preferences: {
        preferred_types: ["philosophical_work", "tok_concept"],
        time_period: "contemporary"
      }
    };
    
    const response = await fetch(`${baseExhibitionUrl}/get-references`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload)
    });
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    const data = await response.json();
    tokExhibition.value.exhibitionReferences = data.suggested_references || [];
    tokExhibition.value.currentStep = 3;
    console.log('TOK Exhibition references fetched:', data);
    
    // Save progress after getting references
    try {
      await saveTokExhibitionDocument();
      console.log('✅ TOK Exhibition progress saved after fetching references');
    } catch (saveError) {
      console.error('⚠️ Failed to save TOK Exhibition progress after fetching references:', saveError);
    }
    
  } catch (error) {
    console.error('Error fetching TOK Exhibition references:', error);
    alert('Failed to fetch references. Please try again.');
  } finally {
    tokExhibition.value.isLoadingReferences = false;
  }
}

async function generateTokExhibitionEssay() {
  try {
    tokExhibition.value.isGeneratingEssay = true;
    essayContent.value = []; // Clear previous content
    
    // Validate required data
    if (!tokExhibition.value.selectedPrompt) {
      throw new Error('No prompt selected');
    }
    if (!tokExhibition.value.selectedObjects || tokExhibition.value.selectedObjects.length !== 3) {
      throw new Error('Must select exactly 3 objects');
    }
    if (!tokExhibition.value.selectedExhibitionReferences || tokExhibition.value.selectedExhibitionReferences.length === 0) {
      throw new Error('Must select at least 1 reference');
    }
    
    const payload = {
      user_id: getUserIdFromQueryParams(),
      prompt: tokExhibition.value.selectedPrompt,
      objects: tokExhibition.value.selectedObjects,
      selected_references: tokExhibition.value.selectedExhibitionReferences,
      citation_format: tokExhibition.value.citationFormat
    };
    
    console.log('🚀 Generating TOK Exhibition essay with payload:', payload);
    console.log('📊 Payload validation:');
    console.log('- Prompt:', !!payload.prompt, '(length:', payload.prompt?.length, ')');
    console.log('- Objects:', payload.objects?.length);
    console.log('- References:', payload.selected_references?.length);
    console.log('- Citation format:', payload.citation_format);
    
    const response = await fetch(`${baseExhibitionUrl}/generate-essay-exhibition`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload)
    });
    
    console.log('📡 Response status:', response.status);
    console.log('📡 Response headers:', Object.fromEntries(response.headers.entries()));
    
    if (!response.ok) {
      const errorText = await response.text();
      console.error('❌ Error response body:', errorText);
      throw new Error(`HTTP error! status: ${response.status} - ${errorText}`);
    }
    
    const data = await response.json();
    console.log('TOK Exhibition essay generated:', data);
    
    // Parse the essay response
    let essayHtml = '';
    if (data.essay) {
      essayHtml = data.essay;
    } else if (data.content) {
      essayHtml = data.content;
    } else if (typeof data === 'string') {
      essayHtml = data;
    } else {
      console.log('Unexpected response format, full data:', data);
      essayHtml = JSON.stringify(data);
    }
    
    // Parse the essay content
    parseEssayContent(essayHtml);
    tokExhibition.value.currentStep = 4;
    
    // Save the generated essay immediately
    try {
      await saveTokExhibitionDocument();
      console.log('✅ TOK Exhibition essay saved to database after generation');
    } catch (saveError) {
      console.error('⚠️ Failed to save TOK Exhibition essay after generation:', saveError);
    }
    
  } catch (error) {
    console.error('Error generating TOK Exhibition essay:', error);
    alert('Failed to generate essay. Please try again.');
  } finally {
    tokExhibition.value.isGeneratingEssay = false;
  }
}

// Helper functions for TOK Exhibition
function toggleObjectSelection(object) {
  const index = tokExhibition.value.selectedObjects.findIndex(obj => 
    (obj.title || obj.name) === (object.title || object.name)
  );
  
  if (index > -1) {
    // Remove object
    tokExhibition.value.selectedObjects.splice(index, 1);
  } else if (tokExhibition.value.selectedObjects.length < 3) {
    // Add object (max 3)
    tokExhibition.value.selectedObjects.push(object);
  }
  
  // Save progress after object selection change
  saveTokExhibitionDocument().catch(error => {
    console.error('⚠️ Failed to save TOK Exhibition progress after object selection:', error);
  });
}

function toggleReferenceSelection(reference) {
  const index = tokExhibition.value.selectedExhibitionReferences.findIndex(ref => 
    (ref.title || ref.name) === (reference.title || reference.name)
  );
  
  if (index > -1) {
    // Remove reference
    tokExhibition.value.selectedExhibitionReferences.splice(index, 1);
  } else {
    // Add reference
    tokExhibition.value.selectedExhibitionReferences.push(reference);
  }
  
  // Save progress after reference selection change
  saveTokExhibitionDocument().catch(error => {
    console.error('⚠️ Failed to save TOK Exhibition progress after reference selection:', error);
  });
}

function resetTokExhibition() {
  tokExhibition.value.selectedPrompt = null;
  tokExhibition.value.selectedPromptNumber = null;
  tokExhibition.value.suggestedObjects = [];
  tokExhibition.value.selectedObjects = [];
  tokExhibition.value.exhibitionReferences = [];
  tokExhibition.value.selectedExhibitionReferences = [];
  tokExhibition.value.currentStep = 1;
  essayContent.value = [];
}

// IB Economics functions
async function getEconomicsSuggestions() {
  // Always attempt Railway call on economics modes
  try {
    isLoadingSuggestions.value = true;
    console.log('🔄 Getting economics concept suggestions from Railway...');
    
    // Ensure local state has basic params for UI
    ibEconomics.value.economicsUnit = ibEconomics.value.economicsUnit || getQueryParam('selectmodule');
    ibEconomics.value.article = ibEconomics.value.article || getQueryParam('article');

    const response = await economicsApi.suggestConceptsRailway(buildEconomicsRailwayPayload(false));

    if (response && response.success) {
      // Map response to local state
      ibEconomics.value.suggestions = Array.isArray(response.suggested_concepts) ? response.suggested_concepts : [];
      ibEconomics.value.conceptSuggestions = ibEconomics.value.suggestions;
      ibEconomics.value.article = response.article || ibEconomics.value.article;
      ibEconomics.value.articleTitle = response.article_title || '';
      ibEconomics.value.articleUrl = response.article_url || '';
      ibEconomics.value.articleDate = response.article_date || '';
      ibEconomics.value.studentName = response.student_name || '';
      ibEconomics.value.schoolName = response.school_name || '';
      ibEconomics.value.citationStyle = response.citation_style || ibEconomics.value.citationStyle;
      ibEconomics.value.message = response.message || '';
      // Unit from response if present
      if (response.economics_unit) {
        ibEconomics.value.economicsUnit = response.economics_unit;
      }

      console.log('✅ Railway concepts loaded:', ibEconomics.value.suggestions.length);

      // Persist suggestions
      try {
        await saveEconomicsDocument();
        console.log('✅ Concept suggestions saved to database for future use');
      } catch (saveError) {
        console.warn('⚠️ Failed to save concept suggestions:', saveError);
      }
    } else {
      throw new Error(response?.message || 'Failed to get concept suggestions');
    }
  } catch (error) {
    console.error('Error getting concept suggestions (Railway):', error);
    alert('Failed to get concept suggestions. Please check your query parameters and try again.');
  } finally {
    isLoadingSuggestions.value = false;
  }
}

async function generateCompleteIA() {
  try {
    if (!ibEconomics.value.selectedConcepts || ibEconomics.value.selectedConcepts.length === 0) {
      alert('Please select at least one key concept before generating the complete IA.');
      return;
    }
    console.log('🧠 Generating Complete IA via Railway...');
    isGeneratingCompleteIA.value = true;
    const payload = buildEconomicsRailwayPayload(true);
    const response = await economicsApi.generateCompleteIARailway(payload);
    if (response && response.success) {
      economicsCompleteIA.value = response.complete_ia || null;
      // Build collapsible sections for right sidebar from the complete IA
      economicsIASections.value = buildEconomicsIASections(economicsCompleteIA.value);
      console.log('✅ Complete IA generated');
    } else {
      throw new Error(response?.message || 'Failed to generate complete IA');
    }
  } catch (err) {
    console.error('Error generating complete IA:', err);
    alert('Failed to generate the complete IA. Please try again.');
  } finally {
    isGeneratingCompleteIA.value = false;
  }
}

function buildEconomicsIASections(ia) {
  if (!ia) return [];
  const sections = [];
  // Cover Page
  if (ia.cover_page) {
    const c = ia.cover_page;
    const coverHtml = `
      <p><strong>Title:</strong> ${c.article_title || ''}</p>
      <p><strong>URL:</strong> ${c.article_url ? `<a href="${c.article_url}" target="_blank" rel="noopener">${c.article_url}</a>` : ''}</p>
      <p><strong>Article Date:</strong> ${c.article_publication_date || ''}</p>
      <p><strong>Commentary Written:</strong> ${c.commentary_written_date || ''}</p>
      <p><strong>Economics Unit:</strong> ${c.economics_unit || ''}</p>
      <p><strong>Key Concept:</strong> ${c.key_concept || ''}</p>
      <p><strong>Student:</strong> ${c.student_name || ''}</p>
      <p><strong>School:</strong> ${c.school_name || ''}</p>
      <p><strong>Word Count:</strong> ${c.word_count || ''}</p>
    `;
    sections.push({ title: 'Cover Page', content: coverHtml, expanded: true });
  }
  // Article Section
  if (ia.article_section) {
    const a = ia.article_section;
    const highlights = Array.isArray(a.highlighted_sections) ? a.highlighted_sections.map(h => `<li>${h}</li>`).join('') : '';
    const articleHtml = `
      ${a.full_article ? `<h4>Full Article</h4><p style="white-space: pre-wrap;">${a.full_article}</p>` : ''}
      ${highlights ? `<h4>Highlighted Sections</h4><ul class="diagram-list">${highlights}</ul>` : ''}
      ${a.relevance_explanation ? `<h4>Relevance</h4><p>${a.relevance_explanation}</p>` : ''}
    `;
    sections.push({ title: 'Article Section', content: articleHtml, expanded: false });
  }
  // Commentary subsections
  if (ia.commentary) {
    const cm = ia.commentary;
    if (cm.introduction) {
      sections.push({ title: 'Commentary: Introduction', content: `<p style="white-space: pre-wrap;">${cm.introduction}</p>`, expanded: false });
    }
    if (cm.diagram1_explanation || cm.diagram1_details) {
      const d = cm.diagram1_details || {};
      const curves = Array.isArray(d.curves) ? d.curves.map(x=>`<li>${x}</li>`).join('') : '';
      const kps = Array.isArray(d.key_points) ? d.key_points.map(x=>`<li>${x}</li>`).join('') : '';
      const arrows = Array.isArray(d.arrows) ? d.arrows.map(x=>`<li>${x.direction || x.additionalProp1 || JSON.stringify(x)}</li>`).join('') : '';
      const shaded = Array.isArray(d.shaded_areas) ? d.shaded_areas.map(x=>`<li>${x.label || x.additionalProp1 || JSON.stringify(x)}</li>`).join('') : '';
      const data = Array.isArray(d.data_from_article) ? d.data_from_article.map(x=>`<li>${x}</li>`).join('') : '';
      const diagHtml = `
        ${cm.diagram1_explanation ? `<p style="white-space: pre-wrap;">${cm.diagram1_explanation}</p>` : ''}
        ${d.title ? `<div class="diagram-title"><strong>${d.title}</strong></div>` : ''}
        ${d.description ? `<p>${d.description}</p>` : ''}
        ${d.axes_labels ? `<p><strong>Axes:</strong> X: ${d.axes_labels.x || d.axes_labels.additionalProp1 || ''}, Y: ${d.axes_labels.y || d.axes_labels.additionalProp2 || ''}</p>` : ''}
        ${curves ? `<p><strong>Curves:</strong></p><ul class="diagram-list">${curves}</ul>` : ''}
        ${kps ? `<p><strong>Key Points:</strong></p><ul class="diagram-list">${kps}</ul>` : ''}
        ${arrows ? `<p><strong>Arrows:</strong></p><ul class="diagram-list">${arrows}</ul>` : ''}
        ${shaded ? `<p><strong>Shaded Areas:</strong></p><ul class="diagram-list">${shaded}</ul>` : ''}
        ${d.explanation ? `<p><strong>Explanation:</strong> ${d.explanation}</p>` : ''}
        ${d.figure_caption ? `<p><strong>Caption:</strong> ${d.figure_caption}</p>` : ''}
        ${data ? `<p><strong>Data from Article:</strong></p><ul class="diagram-list">${data}</ul>` : ''}
      `;
      sections.push({ title: 'Commentary: Diagram 1', content: diagHtml, expanded: false });
    }
    if (cm.analysis) {
      sections.push({ title: 'Commentary: Analysis', content: `<p style="white-space: pre-wrap;">${cm.analysis}</p>`, expanded: false });
    }
    if (cm.diagram2_explanation || cm.diagram2_details) {
      const d = cm.diagram2_details || {};
      const curves = Array.isArray(d.curves) ? d.curves.map(x=>`<li>${x}</li>`).join('') : '';
      const kps = Array.isArray(d.key_points) ? d.key_points.map(x=>`<li>${x}</li>`).join('') : '';
      const arrows = Array.isArray(d.arrows) ? d.arrows.map(x=>`<li>${x.direction || x.additionalProp1 || JSON.stringify(x)}</li>`).join('') : '';
      const shaded = Array.isArray(d.shaded_areas) ? d.shaded_areas.map(x=>`<li>${x.label || x.additionalProp1 || JSON.stringify(x)}</li>`).join('') : '';
      const data = Array.isArray(d.data_from_article) ? d.data_from_article.map(x=>`<li>${x}</li>`).join('') : '';
      const diagHtml = `
        ${cm.diagram2_explanation ? `<p style="white-space: pre-wrap;">${cm.diagram2_explanation}</p>` : ''}
        ${d.title ? `<div class="diagram-title"><strong>${d.title}</strong></div>` : ''}
        ${d.description ? `<p>${d.description}</p>` : ''}
        ${d.axes_labels ? `<p><strong>Axes:</strong> X: ${d.axes_labels.x || d.axes_labels.additionalProp1 || ''}, Y: ${d.axes_labels.y || d.axes_labels.additionalProp2 || ''}</p>` : ''}
        ${curves ? `<p><strong>Curves:</strong></p><ul class="diagram-list">${curves}</ul>` : ''}
        ${kps ? `<p><strong>Key Points:</strong></p><ul class="diagram-list">${kps}</ul>` : ''}
        ${arrows ? `<p><strong>Arrows:</strong></p><ul class="diagram-list">${arrows}</ul>` : ''}
        ${shaded ? `<p><strong>Shaded Areas:</strong></p><ul class="diagram-list">${shaded}</ul>` : ''}
        ${d.explanation ? `<p><strong>Explanation:</strong> ${d.explanation}</p>` : ''}
        ${d.figure_caption ? `<p><strong>Caption:</strong> ${d.figure_caption}</p>` : ''}
        ${data ? `<p><strong>Data from Article:</strong></p><ul class="diagram-list">${data}</ul>` : ''}
      `;
      sections.push({ title: 'Commentary: Diagram 2', content: diagHtml, expanded: false });
    }
    if (cm.evaluation) {
      sections.push({ title: 'Commentary: Evaluation', content: `<p style=\"white-space: pre-wrap;\">${cm.evaluation}</p>`, expanded: false });
    }
    if (cm.conclusion) {
      sections.push({ title: 'Commentary: Conclusion', content: `<p style=\"white-space: pre-wrap;\">${cm.conclusion}</p>`, expanded: false });
    }
  }
  // References and Word Count
  if (ia.references) {
    const r = ia.references;
    const add = Array.isArray(r.additional_sources) ? r.additional_sources.map(x=>`<li>${x}</li>`).join('') : '';
    const refHtml = `
      ${r.article_citation ? `<p><strong>Article Citation:</strong> ${r.article_citation}</p>` : ''}
      ${add ? `<h4>Additional Sources</h4><ul class=\"evaluation-list\">${add}</ul>` : ''}
      ${r.citation_style ? `<p><strong>Citation Style:</strong> ${r.citation_style}</p>` : ''}
    `;
    sections.push({ title: 'References', content: refHtml, expanded: false });
  }
  if (ia.total_word_count) {
    sections.push({ title: 'Total Word Count', content: `<p>${ia.total_word_count}</p>`, expanded: false });
  }
  return sections;
}

function toggleIaSection(idx) {
  const s = economicsIASections.value[idx];
  if (!s) return;
  s.expanded = !s.expanded;
}

async function copyIaSectionContent(idx) {
  const s = economicsIASections.value[idx];
  if (!s) return;
  try {
    await navigator.clipboard.writeText(s.content.replace(/<[^>]+>/g, ''));
  } catch (e) {
    console.error('Copy failed:', e);
  }
}

async function copyEntireEconomicsIA() {
  try {
    const html = economicsIASections.value.map(s => `<h3>${s.title}</h3>${s.content}`).join('\n');
    await navigator.clipboard.writeText(html.replace(/<[^>]+>/g, ''));
  } catch (e) {
    console.error('Copy all failed:', e);
  }
}

function toggleConcept(conceptName) {
  const selectedConcepts = ibEconomics.value.selectedConcepts;
  const index = selectedConcepts.indexOf(conceptName);
  
  if (index > -1) {
    // Remove if already selected
    selectedConcepts.splice(index, 1);
  } else if (selectedConcepts.length < 5) {
    // Add if under limit
    selectedConcepts.push(conceptName);
  }
  
  console.log('Selected concepts:', selectedConcepts);
}

async function generateEconomicsOutline() {
  if (!canGenerateEconomicsOutline.value) return;
  
  try {
    isGeneratingEconomicsOutline.value = true;
    console.log('Generating economics outline...');
    
    const response = await economicsApi.generateOutline(
      ibEconomics.value.article,
      ibEconomics.value.economicsUnit,
      ibEconomics.value.selectedConcepts.join(', '), // Send multiple concepts
      ibEconomics.value.citationStyle,
      getUserIdFromQueryParams(),
      getIdFromPath() // eco_id from document URL
    );
    
    if (response.success) {
      // Use the raw API response directly without mapping
      ibEconomics.value.outline = response.outline;
      console.log('Economics outline generated:', response.outline);
      
      // Save generated outline to database
      try {
        await saveEconomicsDocument();
        console.log('✅ Generated outline saved to database');
      } catch (saveError) {
        console.warn('⚠️ Failed to save generated outline:', saveError);
      }
    } else {
      throw new Error(response.message || 'Failed to generate outline');
    }
  } catch (error) {
    console.error('Error generating economics outline:', error);
    alert('Failed to generate economics outline. Please try again.');
  } finally {
    isGeneratingEconomicsOutline.value = false;
  }
}

async function generateEssay() {
  if (!canGenerateEssay.value) return;
  
  isGenerating.value = true;
  essayContent.value = []; // Clear previous essay
  
  try {
    // Get selected references data
    const selectedRefsData = selectedReferences.value.map(refId => {
      const ref = references.value.find(r => r.reference_id === refId);
      return {
        AuthorName: ref.AuthorName,
        TitleName: ref.TitleName,
        Year: ref.Year,
        Publisher: ref.Publisher || ""
      };
    });
    
    // Combine all selected reference titles for topic
    const topic = selectedRefsData.map(r => r.TitleName).join(', ');
    
    const payload = {
      topic: topic,
      selected_references: selectedRefsData,
      citationStyle: selectedFormat.value,
      wordCount: parseInt(customWordCount.value)
    };
    
    const response = await fetch('https://jfv6blghbfv5lr3wt6sho4kewe0mrifm.lambda-url.us-east-1.on.aws/api/generate-essay', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload)
    });
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    const data = await response.json();
    
    // Parse the HTML essay content
    parseEssayContent(data.essay);
    
    // Store the generated essay content for saving
    essayData.value.generatedEssay = data.essay;
    console.log('✅ Generated essay content stored for saving');
    
    // Save the essay immediately after generation
    try {
      await saveDocument();
      console.log('✅ Essay saved to database after generation');
    } catch (saveError) {
      console.error('⚠️ Failed to save essay after generation:', saveError);
    }
    
  } catch (error) {
    console.error('Error generating essay:', error);
    alert('Failed to generate essay. Please try again.');
  } finally {
    isGenerating.value = false;
  }
}

function parseEssayContent(htmlContent) {
  console.log('Parsing essay content:', htmlContent);
  
  if (!htmlContent || htmlContent.trim() === '') {
    console.log('No content to parse');
    essayContent.value = [];
    return;
  }
  
  // Additional check: Don't parse minimal content that shouldn't create sections
  const trimmedContent = htmlContent.trim();
  
  // For TOK mode, be more lenient with content structure
  const isTokMode = selectedMode.value.includes('tok');
  const hasValidStructure = trimmedContent.includes('<h3>') || 
                           trimmedContent.includes('## ') || 
                           trimmedContent.includes('Introduction') || 
                           trimmedContent.includes('Conclusion') ||
                           trimmedContent.includes('**') || // Markdown bold headers
                           trimmedContent.includes('Journal Entry') ||
                           trimmedContent.includes('TOK');
  
  if (trimmedContent.length < 200 || (!isTokMode && !hasValidStructure)) {
    console.log('Content too minimal or lacks proper structure, not creating sections');
    essayContent.value = [];
    return;
  }
  
  // For TOK journal, if content doesn't have clear sections, create one section
  if (isTokMode && !hasValidStructure) {
    console.log('TOK content: Creating single section for journal content');
    essayContent.value = [{
      title: 'TOK Journal Entry',
      content: trimmedContent,
      expanded: true
    }];
    return;
  }

  const sections = [];

  // 0) Pre-clean: remove standalone Word Count lines and stray empty headers
  let contentToParse = htmlContent
    // Remove lines like "(Word Count: 950)" or "Word Count: 950"
    .replace(/^\s*\(?\s*Word\s*Count\s*:\s*\d+\s*\)?\s*$/gmi, '')
    // Remove lines that are just header markers like "##" with no title
    .replace(/^\s*#{1,6}\s*$/gmi, '')
    .trim();

  // 1) Handle Markdown ATX headers first ("# Title", "## Title", etc.)
  const atxHeaderPattern = /^#{1,6}\s+(.+)$/m;
  if (atxHeaderPattern.test(contentToParse)) {
    const lines = contentToParse.split(/\n+/);
    let currentSection = null;

    const headerRegex = /^#{1,6}\s+(.+)$/;
    const isWordCountLine = (line) => /^(\(?\s*)?Word\s*Count\s*:\s*\d+(\s*\)\s*)?$/i.test(line.trim());

    for (let rawLine of lines) {
      const line = rawLine.trim();
      if (!line) continue;

      const headerMatch = line.match(headerRegex);
      if (headerMatch && headerMatch[1] && headerMatch[1].trim()) {
        // Close previous section if it has content
        if (currentSection && currentSection.content.trim()) {
          currentSection.content = ensureCompleteSentences(currentSection.content);
          if (currentSection.content.trim()) {
            sections.push(currentSection);
          }
        }

        // Start new section
        const cleanTitle = headerMatch[1].replace(/#+\s*$/g, '').trim();
        currentSection = {
          title: cleanTitle || 'Section',
          content: '',
          expanded: false
        };
      } else {
        // Skip word count meta lines inside content
        if (isWordCountLine(line)) continue;
        if (currentSection) {
          currentSection.content += line + '\n';
        } else {
          // If content appears before any header, create a default section
          currentSection = {
            title: 'Introduction',
            content: line + '\n',
            expanded: false
          };
        }
      }
    }

    // Push the last section
    if (currentSection && currentSection.content.trim()) {
      currentSection.content = ensureCompleteSentences(currentSection.content);
      if (currentSection.content.trim()) {
        sections.push(currentSection);
      }
    }

    if (sections.length > 0) {
      essayContent.value = sections;
      return;
    }
  }
  
  // First, try to detect Markdown-style headers (**text**)
  const markdownHeaderPattern = /\*\*(.*?)\*\*/g;
  const markdownHeaders = htmlContent.match(markdownHeaderPattern);
  
  if (markdownHeaders && markdownHeaders.length > 1) {
    console.log('Found Markdown headers, splitting by **text** pattern');
    console.log('Markdown headers found:', markdownHeaders);
    
    // Split content by **header** patterns
    const parts = contentToParse.split(/\*\*(.*?)\*\*/);
    
    console.log('Split parts:', parts.length);
    
    // parts[0] is content before first header (if any)
    // parts[1] is first header text, parts[2] is content after first header
    // parts[3] is second header text, parts[4] is content after second header, etc.
    
    for (let i = 1; i < parts.length; i += 2) {
      const title = parts[i] ? parts[i].trim() : '';
      const content = parts[i + 1] ? parts[i + 1].trim() : '';
      
      if (title) {
        const section = {
          title: title,
          content: ensureCompleteSentences(content),
          expanded: false
        };
        
        if (section.content.trim()) {
          sections.push(section);
        }
        
        console.log(`Section: "${title}"`);
        console.log(`Content length: ${content.length}`);
      }
    }
  } else {
    // Try HTML headers
    const h3Pattern = /<h3[^>]*>(.*?)<\/h3>/gi;
    const h2Pattern = /<h2[^>]*>(.*?)<\/h2>/gi;
    const h1Pattern = /<h1[^>]*>(.*?)<\/h1>/gi;
    
    let headerPattern = null;
    let headerTag = '';
    
    if (htmlContent.match(h3Pattern)) {
      headerPattern = h3Pattern;
      headerTag = 'h3';
    } else if (htmlContent.match(h2Pattern)) {
      headerPattern = h2Pattern;
      headerTag = 'h2';
    } else if (htmlContent.match(h1Pattern)) {
      headerPattern = h1Pattern;
      headerTag = 'h1';
    }
    
    if (headerPattern) {
      console.log(`Found ${headerTag} headers, splitting by them`);
      
      const regex = new RegExp(`<${headerTag}[^>]*>(.*?)<\/${headerTag}>`, 'gi');
      const parts = contentToParse.split(regex);
      
      for (let i = 1; i < parts.length; i += 2) {
        const title = parts[i] ? parts[i].trim() : '';
        const content = parts[i + 1] ? parts[i + 1].trim() : '';
        
        if (title) {
          const tempDiv = document.createElement('div');
          tempDiv.innerHTML = title;
          const cleanTitle = tempDiv.textContent || tempDiv.innerText || title;
          
          const section = {
            title: cleanTitle,
            content: ensureCompleteSentences(content),
            expanded: false
          };
          
          if (section.content.trim()) {
            sections.push(section);
          }
          
          console.log(`Section: "${cleanTitle}"`);
          console.log(`Content length: ${content.length}`);
        }
      }
    } else {
      console.log('No HTML or Markdown headers found, trying to split by text patterns');
      
      // Split by lines and look for heading patterns
      const lines = contentToParse.split(/\n+/);
      let currentSection = null;
      
      for (let line of lines) {
        line = line.trim();
        if (!line) continue;
        
        // Check if this line looks like a heading
        const isHeading = (
          // All caps and short (likely a heading)
          (line === line.toUpperCase() && line.length < 100 && line.length > 3) ||
          // Ends with colon
          line.endsWith(':') ||
          // Starts with numbers (1., 2., etc.)
          /^\d+\.\s/.test(line) ||
          // Common TOK essay section patterns
          /^(Introduction|Body|Conclusion|Analysis|Evaluation|Perspective|Knowledge Question|Development)/i.test(line)
        );
        
        if (isHeading) {
          // Save previous section
          if (currentSection && currentSection.content.trim()) {
            currentSection.content = ensureCompleteSentences(currentSection.content);
            if (currentSection.content.trim()) {
              sections.push(currentSection);
            }
          }
          
          // Start new section
          const cleanTitle = line.replace(/[:\d\.]/g, '').trim();
          currentSection = {
            title: cleanTitle || 'Section',
            content: '',
            expanded: false
          };
          
          console.log(`Found potential heading: "${cleanTitle}"`);
        } else if (currentSection) {
          // Add content to current section
          currentSection.content += line + '\n';
        } else {
          // No current section, create default one
          currentSection = {
            title: 'Introduction',
            content: line + '\n',
            expanded: false
          };
        }
      }
      
      // Don't forget the last section
      if (currentSection && currentSection.content.trim()) {
        currentSection.content = ensureCompleteSentences(currentSection.content);
        if (currentSection.content.trim()) {
          sections.push(currentSection);
        }
      }
    }
  }
  
  // If we still have no sections, create a single default section
  if (sections.length === 0) {
    console.log('No sections found, creating single default section');
    const content = ensureCompleteSentences(htmlContent);
    if (content.trim()) {
      sections.push({
        title: 'TOK Essay Content',
        content: content,
        expanded: false
      });
    }
  }
  
  console.log('Final parsed sections:', sections.length);
  sections.forEach((section, index) => {
    console.log(`Section ${index}: "${section.title}" (${section.content.length} chars)`);
  });
  
  // FALLBACK: If no sections were created but we have content (especially for TOK), create a single section
  if (sections.length === 0 && htmlContent && htmlContent.trim().length > 50) {
    console.log('🔄 FALLBACK: No sections parsed, creating single section for content');
    const fallbackTitle = selectedMode.value === 'tok' ? 'TOK Journal Entry' : 
                          selectedMode.value === 'tok-essay' ? 'TOK Essay' :
                          selectedMode.value === 'tok-exhibition' ? 'TOK Exhibition' : 'Generated Content';
    
    sections.push({
      title: fallbackTitle,
      content: htmlContent.trim(),
      expanded: true
    });
    console.log('✅ Created fallback section with', htmlContent.trim().length, 'characters');
  }
  
  essayContent.value = sections;
}

function ensureCompleteSentences(htmlContent) {
  if (!htmlContent.trim()) return htmlContent;
  
  console.log('Ensuring complete sentences for:', htmlContent.substring(0, 100));
  
  // Create a temporary div to work with the HTML
  const tempDiv = document.createElement('div');
  tempDiv.innerHTML = htmlContent;
  
  // Get the text content to analyze sentences
  const textContent = tempDiv.textContent || tempDiv.innerText || '';
  
  // Find sentence boundaries - more comprehensive regex
  // Matches sentences ending with ., !, or ? followed by:
  // - whitespace and capital letter
  // - end of string
  // - quotation marks and then whitespace/capital/end
  const sentenceRegex = /[.!?]+(?:\s*["']?\s*(?:[A-Z]|$))/g;
  const sentences = [];
  let lastIndex = 0;
  let match;
  
  while ((match = sentenceRegex.exec(textContent)) !== null) {
    const sentence = textContent.substring(lastIndex, match.index + match[0].length - (match[0].match(/[A-Z]$/) ? 1 : 0)).trim();
    if (sentence && sentence.length > 10) { // Only include substantial sentences
      sentences.push(sentence);
    }
    lastIndex = match.index + match[0].length - (match[0].match(/[A-Z]$/) ? 1 : 0);
  }
  
  // Check for remaining incomplete text
  const remainingText = textContent.substring(lastIndex).trim();
  
  console.log('Found complete sentences:', sentences.length);
  console.log('Remaining incomplete text length:', remainingText.length);
  
  if (sentences.length === 0) {
    // If no complete sentences found, return empty or the original if it's short
    return textContent.length < 100 ? htmlContent : '';
  }
  
  // Reconstruct HTML with only complete sentences
  const completeSentencesText = sentences.join(' ');
  
  // If we're cutting off significant content, try to preserve HTML structure
  if (completeSentencesText.length < textContent.length * 0.7 && remainingText.length > 30) {
    const reconstructed = reconstructHtmlWithCompleteSentences(htmlContent, completeSentencesText);
    console.log('Reconstructed HTML with complete sentences');
    return reconstructed;
  }
  
  console.log('Returning complete sentences text wrapped in paragraph');
  // Wrap in paragraph tags to maintain structure
  return `<p>${completeSentencesText}</p>`;
}

function reconstructHtmlWithCompleteSentences(originalHtml, completeSentencesText) {
  // Simple approach: if we have a significant truncation, 
  // wrap the complete sentences in proper HTML tags
  const tempDiv = document.createElement('div');
  tempDiv.innerHTML = originalHtml;
  
  // Get all paragraph tags and other block elements
  const paragraphs = tempDiv.querySelectorAll('p, div, span, strong, em, i, b');
  
  if (paragraphs.length > 0) {
    // Try to preserve the structure by checking each paragraph
    let result = '';
    let remainingText = completeSentencesText;
    
    paragraphs.forEach(para => {
      const paraText = para.textContent || para.innerText || '';
      if (remainingText.includes(paraText.substring(0, 50))) {
        // This paragraph is likely included in our complete sentences
        if (remainingText.length >= paraText.length) {
          result += para.outerHTML;
          remainingText = remainingText.substring(paraText.length).trim();
        }
      }
    });
    
    return result || `<p>${completeSentencesText}</p>`;
  }
  
  return `<p>${completeSentencesText}</p>`;
}

function toggleSection(index) {
  essayContent.value[index].expanded = !essayContent.value[index].expanded;
}

// Copy section content to clipboard
async function copySectionContent(idx) {
  const section = essayContent.value[idx];
  // Create a temporary element to strip HTML tags for plain text copy
  const tempDiv = document.createElement('div');
  tempDiv.innerHTML = section.content;
  const text = tempDiv.innerText;
  try {
    await navigator.clipboard.writeText(text);
    showCopyToast.value = true;
    if (copyToastTimeout) clearTimeout(copyToastTimeout);
    copyToastTimeout = setTimeout(() => {
      showCopyToast.value = false;
    }, 1500);
  } catch (e) {
    alert('Failed to copy!');
  }
}

// Copy entire essay outline to clipboard
async function copyEntireEssayOutline() {
  if (essayContent.value.length === 0) return;
  
  let fullContent = 'Generated Content\n\n';
  
  essayContent.value.forEach((section, index) => {
    fullContent += `${index + 1}. ${section.title}\n`;
    
    // Get plain text content from section
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = section.content;
    const plainTextContent = tempDiv.textContent || tempDiv.innerText || '';
    
    if (plainTextContent.trim()) {
      fullContent += `${plainTextContent.trim()}\n\n`;
    }
  });
  
  try {
    await navigator.clipboard.writeText(fullContent.trim());
    showCopyToast.value = true;
    if (copyToastTimeout) clearTimeout(copyToastTimeout);
    copyToastTimeout = setTimeout(() => {
      showCopyToast.value = false;
    }, 1500);
    console.log('✅ Entire content copied to clipboard');
  } catch (e) {
    console.error('❌ Failed to copy entire content:', e);
    // Fallback for older browsers
    const textArea = document.createElement('textarea');
    textArea.value = fullContent.trim();
    document.body.appendChild(textArea);
    textArea.select();
    document.execCommand('copy');
    document.body.removeChild(textArea);
    alert('Content copied to clipboard!');
  }
}

// Copy entire economics outline to clipboard
async function copyEntireEconomicsOutline() {
  if (!ibEconomics.value.outline) return;
  
  let fullContent = 'Economics Outline\n\n';
  const o = ibEconomics.value.outline;
  
  // Helper to append labeled sections safely
  const appendSection = (label, value) => {
    if (!value) return;
    const text = Array.isArray(value) ? value.join('\n') : String(value);
    if (text.trim()) {
      fullContent += `${label}\n${text.trim()}\n\n`;
    }
  };
  
  appendSection('Main Issue', o.main_issue);
  appendSection('Theory Application', o.theory_application);
  appendSection('Key Economic Terminology', o.terminology);
  appendSection('Stakeholders', o.stakeholders);
  appendSection('Evaluation Points', o.evaluation_points);
  appendSection('Suggested Diagrams', o.diagrams);
  appendSection('Key Concept Integration', o.concept_integration);
  
  try {
    await navigator.clipboard.writeText(fullContent.trim());
    showCopyToast.value = true;
    if (copyToastTimeout) clearTimeout(copyToastTimeout);
    copyToastTimeout = setTimeout(() => {
      showCopyToast.value = false;
    }, 1500);
    console.log('✅ Entire economics outline copied to clipboard');
  } catch (e) {
    console.error('❌ Failed to copy economics outline:', e);
    // Fallback for older browsers
    const textArea = document.createElement('textarea');
    textArea.value = fullContent.trim();
    document.body.appendChild(textArea);
    textArea.select();
    document.execCommand('copy');
    document.body.removeChild(textArea);
  }
}


onMounted(async () => {
  try {
    console.log('🚀 EditorLayout mounting - START');
    
    // Initialize mode from query parameters
    selectedMode.value = getModeFromQueryParams();
    console.log('🎯 DETECTED MODE:', selectedMode.value);
    console.log('🎯 URL search params:', window.location.search);
    console.log('🎯 selectmodule param:', new URLSearchParams(window.location.search).get('selectmodule'));
    console.log('🎯 BEFORE TOPIC CACHE CHECK');

    // 🚀 TOPIC-SPECIFIC REFERENCE LOADING: Try cache first, then database
    const currentTopic = getTopicFromQueryParams();
    const documentKey = getDocumentKey();
    
    console.log('🎯 Current topic on mount:', currentTopic);
    console.log('🎯 Document key:', documentKey);
    
    // Clear references for fresh start
    references.value = [];
    selectedReferences.value = [];
    console.log('📂 Cleared references for fresh start with topic:', currentTopic);

    // Initialize mode from query parameters
    selectedMode.value = getModeFromQueryParams();
    
    // Initialize economics data from query parameters if in economics mode
    if (['microeconomics', 'macroeconomics', 'globaleconomics'].includes(selectedMode.value)) {
      const economicsUnitMap = {
        'microeconomics': 'microeconomics',
        'macroeconomics': 'macroeconomics',
        'globaleconomics': 'global_economy'
      };
      ibEconomics.value.economicsUnit = economicsUnitMap[selectedMode.value];
      ibEconomics.value.article = getArticleFromQueryParams();
      
      // Auto-fetch concept suggestions will be handled in processEconomicsData after database fetch
      if (ibEconomics.value.article.trim()) {
        console.log('Article found for economics template:', ibEconomics.value.article.substring(0, 50) + '...');
        console.log('ℹ️ Concept suggestions will be loaded from database or generated after fetch completes');
      }
    }

    // Initialize document service with the detected mode
    const serviceMode = selectedMode.value === 'paper-template' ? 'paper' : selectedMode.value;
    documentService.setMode(serviceMode);
    documentService.init();
    
    // Set appropriate default right tab based on mode
    console.log('🔍 Mode check: selectedMode.value =', selectedMode.value);
    console.log('🔍 Mode check: selectedMode.value === "tok-exhibition" =', selectedMode.value === 'tok-exhibition');
    
    if (selectedMode.value === 'tok-exhibition') {
      activeRightTab.value = 'essay';
      console.log('🎯 TOK EXHIBITION MODE CONFIRMED: Data will be loaded via fetchSavedData');
      // Note: TOK Exhibition data loading is handled by fetchSavedData() -> fetchTokData()
      // Prompts will be loaded from database or fetched if needed after data loading completes
    } else if (['microeconomics', 'macroeconomics', 'globaleconomics'].includes(selectedMode.value)) {
      activeRightTab.value = 'toc';
    } else {
      console.log('⏭️ Not TOK Exhibition mode, current mode:', selectedMode.value);
    }

    // Setup save event listeners for essay, paper, and TOK modes
    if (selectedMode.value === 'essay' || selectedMode.value === 'paper-template' || 
        selectedMode.value === 'tok-exhibition' || selectedMode.value.includes('tok')) {
      setupAutoSaveEventListeners();
    } else {
      console.log('⏭️ Skipping event listeners for unsupported modes');
    }

    // Fetch saved data for supported modes (including TOK)
    if (selectedMode.value === 'essay' || selectedMode.value === 'paper-template' || 
        ['tok-essay', 'tok', 'tok-exhibition'].includes(selectedMode.value)) {
      try {
        console.log('🚀 Fetching saved data for mode:', selectedMode.value);
        console.log('📍 URL:', window.location.href);
        console.log('📍 Document ID:', getIdFromPath());
        console.log('📍 User ID:', getUserIdFromQueryParams());
        await fetchSavedData();
        
        // Debug: Check if references were loaded from database (for essay/paper modes)
        if (selectedMode.value === 'essay' || selectedMode.value === 'paper-template') {
          console.log('📊 After fetchSavedData - references.value.length:', references.value.length);
          if (references.value.length > 0) {
            console.log('✅ References loaded from database:', references.value.length, 'references');
          }
        } else {
          console.log('✅ TOK mode fetch completed');
        }
        
      } catch (error) {
        console.error('❌ Error fetching saved data:', error);
      }
    } else {
      console.log('⏭️ MODE NOT SUPPORTED for fetch operations:', selectedMode.value);
      console.log('✅ Mode initialized without database fetch');
    }

    // Wait a small moment to ensure all data processing is complete before checking references
    await new Promise(resolve => setTimeout(resolve, 100));
    
    // Re-check references after the delay to ensure data was properly loaded
    console.log('🔍 Final reference check - references.value.length:', references.value.length);
    
    // Only generate references for paper and essay modes, and only if none were loaded from database
    console.log('🔍 DEBUG: Checking if API call needed...');
    console.log('🔍 references.value.length:', references.value.length);
    console.log('🔍 selectedMode.value:', selectedMode.value);
    console.log('🔍 Current Topic:', getTopicFromQueryParams());
    console.log('🔍 Current Document Key:', getDocumentKey());
    console.log('🔍 Last Generated Topic Key:', lastGeneratedTopicKey);
    
    // BULLETPROOF: Only call API if no references AND this topic hasn't been generated yet  
    const topicForApiCheck = getTopicFromQueryParams();
    if (lastGeneratedTopicKey !== topicForApiCheck && references.value.length === 0 && (selectedMode.value === 'essay' || selectedMode.value === 'paper-template' || selectedMode.value === 'tok-essay' || selectedMode.value === 'tok' || selectedMode.value === 'blank-template')) {
      console.log('📚 No saved references found for topic:', topicForApiCheck, '- calling generate_references API ONCE for', selectedMode.value, 'mode');
      lastGeneratedTopicKey = topicForApiCheck; // Mark this topic as generated
      isLoadingReferences.value = true; // Start reference loading
      try {
        // Use current topic
        const topic = [getTopicFromQueryParams()];
        
        // Call the generate_references API
        const response = await fetch('https://jfv6blghbfv5lr3wt6sho4kewe0mrifm.lambda-url.us-east-1.on.aws/generate_references', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            topic: topic
          })
        });

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        
        // Extract references from the API response
        references.value = data.references || [];
        console.log('✅ Generated', references.value.length, 'references from API for topic:', getTopicFromQueryParams());
        
        // IMMEDIATELY save to localStorage for topic isolation
        if (references.value.length > 0) {
          const topicKey = `references_${getUserIdFromQueryParams()}_${getIdFromPath()}_${getTopicFromQueryParams()}`;
          localStorage.setItem(topicKey, JSON.stringify(references.value));
          console.log('💾 TOPIC ISOLATION: Saved', references.value.length, 'references for topic:', getTopicFromQueryParams());
        }
        
        // IMMEDIATELY save references to database using existing endpoints
        if (references.value.length > 0) {
          console.log('💾 Immediately saving', references.value.length, 'references to database for future loads...');
          console.log('📚 Sample reference:', references.value[0]);
          try {
            if (selectedMode.value === 'essay') {
              await saveEssayDocument();
              console.log('✅ References saved to essay database');
            } else if (selectedMode.value === 'paper-template') {
              await savePaperDocument();
              console.log('✅ References saved to paper database');
            }
          } catch (saveError) {
            console.error('❌ Failed to save references to database:', saveError);
          }
        } else {
          console.log('❌ No references to save - references.value is empty');
        }
        
      } catch (error) {
        console.error('❌ Error fetching references:', error);
        references.value = [];
      } finally {
        // API call completed, hide reference loader
        isLoadingReferences.value = false;
        loading.value = false;
      }
    } else if (references.value.length > 0) {
      console.log('✅ Using', references.value.length, 'references from database - no API call needed');
    } else if (selectedMode.value !== 'essay' && selectedMode.value !== 'paper-template') {
      console.log('⏭️ Skipping reference generation for mode:', selectedMode.value);
    }
    
    // Only set loading to false if we're not going to make an API call for references
    if (lastGeneratedTopicKey === currentTopic || references.value.length > 0 || (selectedMode.value !== 'essay' && selectedMode.value !== 'paper-template' && selectedMode.value !== 'tok-essay' && selectedMode.value !== 'tok' && selectedMode.value !== 'tok-exhibition' && selectedMode.value !== 'blank-template')) {
      loading.value = false;
    }
    // If we need to make an API call, both loading and isLoadingReferences will be set to false after the API call completes

  } catch (error) {
    console.error('Critical error in EditorLayout onMounted:', error);
    loading.value = false;
  }
})



// Toggle left sidebar visibility

const leftHidden = ref(false)

function toggleLeftSidebar() {
  leftHidden.value = !leftHidden.value
  // No auto-save on sidebar toggle
}



// Toggle right sidebar visibility

const tocHidden = ref(false)

function toggleTocSidebar() {
  tocHidden.value = !tocHidden.value
  
  // Save document when closing sidebar (user might be done editing)
  if (!tocHidden.value && (selectedMode.value === 'essay' || selectedMode.value === 'paper-template')) {
    console.log('Right sidebar closed, saving document...');
    saveDocument();
  }
}

const showCopyToast = ref(false)
let copyToastTimeout = null

// plag checker in editor 

const activeRightTab = ref('toc');
const isCheckingPlagiarism = ref(false);
const plagiarismResult = ref(null);
const plagiarismError = ref(null);

// Auto-save functionality removed - now only saves on specific events
console.log('Debounced auto-save removed - saving only on specific events');

const saveDocument = async () => {
  // Save for all supported modes including economics templates
  console.log(`Saving document in ${selectedMode.value} mode using document service...`);
  
  try {
    console.log(`Saving document in ${selectedMode.value} mode using new document service...`);
    
    // Get current editor content
    const content = getEditorContent();
    
    // Prepare comprehensive data based on mode
    let saveData = {};
    
    if (selectedMode.value === 'essay') {
      // Use complete reference set - don't filter by selection
      const refsToSave = essayData.value.references && essayData.value.references.length > 0 
        ? essayData.value.references 
        : references.value; // Save complete reference set, not just selected ones
        
      saveData = {
        title: essayData.value.title || getTopicFromQueryParams(),
        word_count: parseInt(customWordCount.value) || 0,
        citation_style: selectedFormat.value || "APA",
        references: JSON.stringify(refsToSave || []),
        generated_essay: essayData.value.generatedEssay || "",
        entered_essay: content
      };
      console.log('💾 SAVING essay with generated_essay:', essayData.value.generatedEssay?.length || 0);
      console.log('💾 SAVING essay with references:', refsToSave?.length || 0);
    } else if (selectedMode.value === 'paper-template') {
      // Use complete reference set - don't filter by selection
      const refsToSave = paperData.value.references && paperData.value.references.length > 0 
        ? paperData.value.references 
        : references.value; // Save complete reference set, not just selected ones
        
      saveData = {
        topic: paperData.value.topic || getTopicFromQueryParams(),
        word_count: parseInt(customWordCount.value) || 1000,
        citation_style: paperData.value.citationStyle || "APA",
        selected_references: refsToSave || [],
        dialect: paperData.value.dialect || "US",
        reading_level: paperData.value.readingLevel || "college",
        entered_content: content,
        gen_paper: outlineData.value || "",
        outline: JSON.stringify(paperData.value.outline || {}),
        references: JSON.stringify(refsToSave || [])
      };
      console.log('💾 SAVING paper with references:', refsToSave?.length || 0);
    } else if (selectedMode.value === 'tok') {
      saveData = {
        title: getTopicFromQueryParams(),
        entered_essay: content,
        citation_style: tokJournal.value.citationStyle || "APA"
      };
    } else if (['microeconomics', 'macroeconomics', 'globaleconomics'].includes(selectedMode.value)) {
      saveData = {
        concept_suggestions: ibEconomics.value.conceptSuggestions || [],
        generated_outline: ibEconomics.value.outline || '',
        article: ibEconomics.value.article || content
      };
    }
    
    // Use document service to save
    await documentService.saveDocument(saveData);
    
    console.log('Document saved successfully to database using new service');
  } catch (error) {
    console.error('Error saving document with new service:', error);
    
    // Fallback to old method if new service fails
    console.log('Attempting fallback to old save methods...');
    try {
      if (selectedMode.value === 'essay') {
        await saveEssayDocument();
      } else if (selectedMode.value === 'paper-template') {
        await savePaperDocument();
      } else if (selectedMode.value === 'tok-exhibition') {
        await saveTokExhibitionDocument();
        console.log('✅ TOK Exhibition content saved via fallback method');
      } else if (selectedMode.value.includes('tok')) {
        // For TOK modes, use the new save-progress API
        if (typeof window.saveTokProgress === 'function') {
          await window.saveTokProgress();
          console.log('✅ TOK content saved via fallback method');
        } else {
          console.warn('saveTokProgress function not available in fallback');
        }
      } else if (['microeconomics', 'macroeconomics', 'globaleconomics'].includes(selectedMode.value)) {
        await saveEconomicsDocument();
      }
      console.log('Fallback save successful');
    } catch (fallbackError) {
      console.error('Fallback save also failed:', fallbackError);
      throw fallbackError;
    }
  }
};

// Save TOK Essay document progress (TOK unified endpoint)
const saveTokEssayDocument = async () => {
  const enteredContent = getEditorContent();
  const generatedContent = essayContent.value.map(section => 
    `<h3>${section.title}</h3>${section.content}`
  ).join('');

  const tokId = getIdFromPath(); // Extract id from URL path
  const userId = getUserIdFromQueryParams();

  // Prepare selected references similar to essay mode: store full objects as JSON strings if available
  let selectedRefs = [];
  try {
    if (Array.isArray(references.value) && Array.isArray(selectedReferences.value) && selectedReferences.value.length > 0) {
      const byId = new Map(references.value.map(r => [r.reference_id || r.id || r._id || r.TitleName, r]));
      selectedRefs = selectedReferences.value.map(id => {
        const obj = byId.get(id) || id;
        return typeof obj === 'string' ? obj : JSON.stringify(obj);
      });
    }
  } catch (e) {
    console.warn('Failed to prepare selected references for TOK Essay save:', e);
  }

  const payload = {
    tok_id: tokId,
    user_id: userId,
    data: {
      title: getTopicFromQueryParams(),
      aok1: tokEssay.value.aok1 || '',
      aok2: tokEssay.value.aok2 || '',
      citation_style: tokEssay.value.citationStyle || '',
      word_count: parseInt(tokEssay.value.wordCount) || 1700,
      // Save full reference list like essay/paper
      references: (() => { try { return JSON.stringify(references.value || []); } catch { return '[]'; } })(),
      selected_references: selectedRefs,
      // Save generated and entered content
      generated_outline: outlineData?.value || '',
      generated_essay: generatedContent,
      entered_content: enteredContent
    }
  };

  const response = await fetch('https://jfv6blghbfv5lr3wt6sho4kewe0mrifm.lambda-url.us-east-1.on.aws/save-progress', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  const result = await response.json();
  console.log('TOK Essay saved successfully:', result);
  return result;
};

// Function to load content with retry mechanism
const loadContentWithRetry = (maxRetries = 5, delay = 500) => {
  let attempts = 0;
  
  const tryLoad = () => {
    attempts++;
    if (window.loadEditorContentFromDatabase && typeof window.loadEditorContentFromDatabase === 'function') {
      try {
        window.loadEditorContentFromDatabase();
        console.log(`Content loaded successfully on attempt ${attempts}`);
        return;
      } catch (error) {
        console.warn(`Failed to load content on attempt ${attempts}:`, error);
      }
    }
    
    if (attempts < maxRetries) {
      setTimeout(tryLoad, delay);
    } else {
      console.error('Failed to load content after maximum retries');
    }
  };
  
  // Start first attempt after a brief delay
  setTimeout(tryLoad, 200);
};

// Function to manually reload saved data (useful for debugging)
const reloadSavedData = async () => {
  console.log('Manually reloading saved data...');
  // Reset flag to allow manual reload
  isFetching = false;
  
  try {
    await fetchSavedData();
    
    // After fetching, try to load into editor
    if (window.editorContentFromDatabase) {
      console.log('Reloaded content, attempting to load into editor...');
      setTimeout(() => {
        if (window.loadEditorContentFromDatabase) {
          window.loadEditorContentFromDatabase();
        } else {
          loadContentWithRetry();
        }
      }, 500);
    }
  } catch (error) {
    console.error('Error manually reloading data:', error);
  }
};

// Make the reload function available globally for debugging
window.reloadSavedData = reloadSavedData;

// Test function to check what's happening
window.testDataFetch = async () => {
  console.log('🧪 Testing data fetch...');
  console.log('Current mode:', selectedMode.value);
  console.log('Current URL:', window.location.href);
  
  const urlParams = new URLSearchParams(window.location.search);
  console.log('All URL params:', Array.from(urlParams.entries()));
  
  const sessionId = urlParams.get('sessionId') || urlParams.get('document_id') || urlParams.get('paper_id');
  const user_id = urlParams.get('user_id') || '';
  
  console.log('Session ID:', sessionId);
  console.log('User ID:', user_id);
  
  if (sessionId && user_id) {
    console.log('✅ Parameters found, testing fetch...');
    try {
      await fetchSavedData();
    } catch (error) {
      console.error('❌ Test fetch failed:', error);
    }
  } else {
    console.log('❌ Missing parameters for fetch');
  }
};

// Test API endpoints directly
window.testAPIEndpoints = async () => {
  console.log('🧪 Testing API endpoints...');
  
  const urlParams = new URLSearchParams(window.location.search);
  const sessionId = urlParams.get('sessionId') || urlParams.get('document_id') || urlParams.get('paper_id');
  const user_id = urlParams.get('user_id') || '';
  
  if (!sessionId || !user_id) {
    console.log('❌ Missing parameters for API test');
    return;
  }
  
  // Test essay endpoint
  if (selectedMode.value === 'essay') {
    console.log('📝 Testing essay endpoint...');
    const essayUrl = new URL(`${backend_url}/api/retrieve-specific-essay`);
    essayUrl.searchParams.append('document_id', sessionId);
    essayUrl.searchParams.append('user_id', user_id);
    
    try {
      const response = await fetch(essayUrl.toString());
      console.log('Essay API response status:', response.status);
      if (response.ok) {
        const data = await response.json();
        console.log('Essay API response data:', data);
      } else {
        const errorText = await response.text();
        console.log('Essay API error:', errorText);
      }
    } catch (error) {
      console.error('Essay API fetch error:', error);
    }
  }
  
  // Test paper endpoint
  if (selectedMode.value === 'paper-template') {
    console.log('📄 Testing paper endpoint...');
    const paperUrl = new URL(`${backend_url}/api/retrieve-specific-paper-draft`);
    paperUrl.searchParams.append('paper_id', sessionId);
    paperUrl.searchParams.append('user_id', user_id);
    
    try {
      const response = await fetch(paperUrl.toString());
      console.log('Paper API response status:', response.status);
      if (response.ok) {
        const data = await response.json();
        console.log('Paper API response data:', data);
      } else {
        const errorText = await response.text();
        console.log('Paper API error:', errorText);
      }
    } catch (error) {
      console.error('Paper API fetch error:', error);
    }
  }
};

// Test mode detection
window.testModeDetection = () => {
  console.log('🧪 Testing mode detection...');
  console.log('Current URL:', window.location.href);
  
  const urlParams = new URLSearchParams(window.location.search);
  const selectmodule = urlParams.get('selectmodule');
  
  console.log('selectmodule param:', selectmodule);
  console.log('getModeFromQueryParams result:', getModeFromQueryParams());
  console.log('selectedMode.value:', selectedMode.value);
  
  // Test all possible modes
  const testModes = ['essay', 'paper', 'tok_essay', 'tok', 'tok-exhibition'];
  testModes.forEach(mode => {
    const testUrl = new URL(window.location.href);
    testUrl.searchParams.set('selectmodule', mode);
    console.log(`Mode '${mode}' would result in:`, getModeFromQueryParams.call({}, testUrl.searchParams));
  });
};

// Test the complete flow: fetch + load
window.testCompleteFlow = async () => {
  console.log('🚀 Testing complete flow: fetch + load...');
  
  // Step 1: Fetch data
  console.log('\n1️⃣ Fetching data from database...');
  await fetchSavedData();
  
  // Step 2: Wait a bit for content to be stored
  setTimeout(() => {
    console.log('\n2️⃣ Checking if content was fetched...');
    if (window.editorContentFromDatabase) {
      console.log('✅ Content fetched successfully!');
      console.log('Content length:', window.editorContentFromDatabase.length);
      
      // Step 3: Load content into editor
      console.log('\n3️⃣ Loading content into editor...');
      const success = window.manualLoadContent();
      if (success) {
        console.log('🎉 Complete flow successful! Content should now be visible in editor.');
      } else {
        console.log('❌ Content loading failed');
      }
    } else {
      console.log('❌ No content was fetched');
    }
  }, 2000);
};

// Check editor content loader availability
window.checkEditorLoader = () => {
  console.log('🔍 Checking editor content loader...');
  console.log('window.editorContentFromDatabase exists:', !!window.editorContentFromDatabase);
  console.log('window.loadEditorContentFromDatabase exists:', !!window.loadEditorContentFromDatabase);
  
  if (window.editorContentFromDatabase) {
    console.log('Content length:', window.editorContentFromDatabase.length);
    console.log('Content preview:', window.editorContentFromDatabase.substring(0, 200) + '...');
  }
  
  if (window.loadEditorContentFromDatabase) {
    console.log('Loader function type:', typeof window.loadEditorContentFromDatabase);
  }
  
  // Check if editor elements exist
  const editorElements = [
    '.main-editor .ProseMirror',
    '.ProseMirror',
    '.umo-editor .ProseMirror'
  ];
  
  editorElements.forEach(selector => {
    const element = document.querySelector(selector);
    console.log(`Editor element '${selector}':`, !!element);
    if (element) {
      console.log(`Content length: ${element.innerHTML.length}`);
    }
  });
};

// Simple content loader function
window.manualLoadContent = () => {
  console.log('🔧 Loading content into editor...');
  
  if (!window.editorContentFromDatabase) {
    console.log('❌ No content available to load');
    return false;
  }
  
  console.log('Content to load:', window.editorContentFromDatabase.substring(0, 200) + '...');
  
  // Try multiple editor selectors
  const editorSelectors = [
    '.main-editor .ProseMirror',
    '.ProseMirror',
    '.umo-editor .ProseMirror',
    '[data-editor="true"]',
    '.tiptap',
    '.editor-content',
    '.content-editor'
  ];
  
  let editorElement = null;
  for (const selector of editorSelectors) {
    editorElement = document.querySelector(selector);
    if (editorElement) {
      console.log(`✅ Found editor element: ${selector}`);
      break;
    }
  }
  
  if (!editorElement) {
    console.log('❌ No editor element found');
    return false;
  }
  
  try {
    // Try to set the content
    if (editorElement.innerHTML !== undefined) {
      editorElement.innerHTML = window.editorContentFromDatabase;
      console.log('✅ Content loaded into editor via innerHTML');
      return true;
    } else if (editorElement.textContent !== undefined) {
      editorElement.textContent = window.editorContentFromDatabase;
      console.log('✅ Content loaded into editor via textContent');
      return true;
    } else {
      console.log('❌ Cannot set content on editor element');
      return false;
    }
  } catch (error) {
    console.error('❌ Error loading content:', error);
    return false;
  }
};

// Test content loading step by step
window.testContentLoading = () => {
  console.log('🧪 Testing content loading step by step...');
  
  // Step 1: Check if content exists
  console.log('\n1️⃣ Checking content availability...');
  if (window.editorContentFromDatabase) {
    console.log('✅ Content exists, length:', window.editorContentFromDatabase.length);
    console.log('Content preview:', window.editorContentFromDatabase.substring(0, 200) + '...');
  } else {
    console.log('❌ No content available');
    return;
  }
  
  // Step 2: Check editor elements
  console.log('\n2️⃣ Checking editor elements...');
  const editorSelectors = [
    '.main-editor .ProseMirror',
    '.ProseMirror',
    '.umo-editor .ProseMirror',
    '[data-editor="true"]',
    '.tiptap',
    '.editor-content',
    '.content-editor'
  ];
  
  editorSelectors.forEach(selector => {
    const element = document.querySelector(selector);
    if (element) {
      console.log(`✅ Found: ${selector}`);
      console.log(`   Current content length: ${element.innerHTML.length}`);
      console.log(`   Current content preview: ${element.innerHTML.substring(0, 100)}...`);
    } else {
      console.log(`❌ Not found: ${selector}`);
    }
  });
  
  // Step 3: Try manual loading
  console.log('\n3️⃣ Trying manual content loading...');
  const success = window.manualLoadContent();
  if (success) {
    console.log('✅ Content loading test successful!');
  } else {
    console.log('❌ Content loading test failed');
  }
};

// Run all debug tests
window.runAllDebugTests = async () => {
  console.log('🚀 Running all debug tests...');
  console.log('=====================================');
  
  // Test 1: Mode detection
  console.log('\n1️⃣ Testing mode detection...');
  window.testModeDetection();
  
  // Test 2: Check editor loader
  console.log('\n2️⃣ Checking editor loader...');
  window.checkEditorLoader();
  
  // Test 3: Test data fetch
  console.log('\n3️⃣ Testing data fetch...');
  await window.testDataFetch();
  
  // Test 4: Test API endpoints
  console.log('\n4️⃣ Testing API endpoints...');
  await window.testAPIEndpoints();
  
  // Test 5: Test complete flow
  console.log('\n5️⃣ Testing complete flow...');
  await window.testCompleteFlow();
  
  console.log('\n=====================================');
  console.log('✅ All debug tests completed!');
  console.log('\n📋 Available debug functions:');
  console.log('- window.testModeDetection()');
  console.log('- window.checkEditorLoader()');
  console.log('- window.testDataFetch()');
  console.log('- window.testAPIEndpoints()');
  console.log('- window.testCompleteFlow()');
  console.log('- window.reloadSavedData()');
  console.log('- window.runAllDebugTests()');
  console.log('- window.saveDocumentFromEditor()');
};

// Function to save document from editor (called by EditorPage)
window.saveDocumentFromEditor = async (content) => {
  console.log('💾 saveDocumentFromEditor called with content length:', content?.length || 0);
  
  if (!content) {
    console.log('⚠️ No content to save');
    return;
  }
  
  // Update the cached content
  window.editorContentFromDatabase = content;
  
  // Save to database based on current mode
  try {
    if (selectedMode.value === 'essay' || selectedMode.value === 'paper-template' || selectedMode.value === 'tok') {
      console.log('🔄 Saving document to database...');
      await saveDocument();
      console.log('✅ Document saved to database successfully');
    }
  } catch (error) {
    console.error('❌ Error saving document to database:', error);
    throw error;
  }
};

// Function to fix URL parameters
window.fixURLParameters = () => {
  console.log('🔧 Fixing URL parameters...');
  
  const currentUrl = new URL(window.location.href);
  const currentParams = new URLSearchParams(currentUrl.search);
  
  console.log('Current URL params:', Array.from(currentParams.entries()));
  
  // Add missing selectmodule parameter
  if (!currentParams.has('selectmodule')) {
    currentParams.set('selectmodule', 'essay');
    console.log('Added selectmodule=essay');
  }
  
  // Check if we have document_id or paper_id
  if (!currentParams.has('document_id') && !currentParams.has('paper_id')) {
    const pathId = getIdFromPath();
    if (pathId) {
      currentParams.set('document_id', pathId);
      console.log(`Added document_id=${pathId}`);
    }
  }
  
  // Update the URL
  currentUrl.search = currentParams.toString();
  console.log('New URL:', currentUrl.toString());
  
  // Reload the page with correct parameters
  if (currentUrl.toString() !== window.location.href) {
    console.log('Reloading page with correct parameters...');
    window.location.href = currentUrl.toString();
  } else {
    console.log('URL already has correct parameters');
  }
};

// Function to manually test data fetch with current parameters
window.testDataFetchWithCurrentParams = async () => {
  console.log('🧪 Testing data fetch with current parameters...');
  
  // Get current parameters
  const urlParams = new URLSearchParams(window.location.search);
  const sessionId = urlParams.get('sessionId') || urlParams.get('document_id') || urlParams.get('paper_id') || getIdFromPath();
  const user_id = urlParams.get('user_id') || '';
  
  console.log('Using session ID:', sessionId);
  console.log('Using user ID:', user_id);
  console.log('Current mode:', selectedMode.value);
  
  if (!sessionId || !user_id) {
    console.log('❌ Missing required parameters');
    return;
  }
  
  try {
    console.log('🚀 Starting manual data fetch...');
    await fetchSavedData();
    console.log('✅ Manual data fetch completed');
  } catch (error) {
    console.error('❌ Manual data fetch failed:', error);
  }
};

const getEditorContent = () => {
  console.log('🔍 Getting editor content...');
  
  // BULLETPROOF: Try multiple methods to get content, with backup caching
  let content = '';
  
  // First: try to get content from the editor instance directly (most reliable)
  if (window.getEditorHTMLContent && typeof window.getEditorHTMLContent === 'function') {
    try {
      const editorContent = window.getEditorHTMLContent();
      if (editorContent && editorContent.trim()) {
        console.log('✅ Got content from editor instance, length:', editorContent.length);
        // BULLETPROOF: Cache this content as backup
        window.lastKnownEditorContent = editorContent;
        window.lastContentTimestamp = Date.now();
        return editorContent;
      }
    } catch (error) {
      console.warn('⚠️ Error getting content from editor instance:', error);
    }
  }
  
  // Secondary: try to get content from the DOM (real-time editor content)
  const editorElement = document.querySelector('.main-editor .ProseMirror');
  if (editorElement && editorElement.innerHTML.trim()) {
    console.log('✅ Got content from main editor DOM, length:', editorElement.innerHTML.length);
    return editorElement.innerHTML;
  }
  
  // Try other possible editor selectors
  const alternativeSelectors = [
    '.ProseMirror',
    '[data-editor="true"]',
    '.tiptap',
    '.editor-content',
    '.umo-editor .ProseMirror'
  ];
  
  for (const selector of alternativeSelectors) {
    const element = document.querySelector(selector);
    if (element && element.innerHTML.trim()) {
      console.log('✅ Got content from alternative selector:', selector, 'length:', element.innerHTML.length);
      return element.innerHTML;
    }
  }
  
  // Fallback: get content from database cache if DOM is empty
  if (window.editorContentFromDatabase && window.editorContentFromDatabase.trim()) {
    console.log('✅ Got content from database cache, length:', window.editorContentFromDatabase.length);
    return window.editorContentFromDatabase;
  }
  
  // BULLETPROOF FALLBACK: Use cached content if available (within last 5 minutes)
  if (window.lastKnownEditorContent && window.lastContentTimestamp && 
      (Date.now() - window.lastContentTimestamp) < 300000) {
    console.log('⚠️ Using cached editor content as fallback, length:', window.lastKnownEditorContent.length);
    return window.lastKnownEditorContent;
  }
  
  // Last resort: use database content if available
  if (window.editorContentFromDatabase && window.editorContentFromDatabase.trim()) {
    console.log('⚠️ Using database content as final fallback, length:', window.editorContentFromDatabase.length);
    return window.editorContentFromDatabase;
  }
  
  console.log('❌ No editor content found anywhere - this should not happen!');
  return '';
};

const saveEssayDocument = async () => {
  const enteredContent = getEditorContent();
  const generatedContent = essayContent.value.map(section => 
    `<h3>${section.title}</h3>${section.content}`
  ).join('');

  const payload = {
    document_id: getIdFromPath(),
    user_id: getUserIdFromQueryParams(),
    title: getTopicFromQueryParams(),
    topic: getTopicFromQueryParams(),
    word_count: parseInt(customWordCount.value) || 0,
    citation_style: selectedFormat.value || '',
    references: JSON.stringify(references.value),
    generated_essay: generatedContent,
    entered_essay: enteredContent
  };

  const response = await fetch('https://jfv6blghbfv5lr3wt6sho4kewe0mrifm.lambda-url.us-east-1.on.aws/api/save-essay', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    const errorText = await response.text();
    console.error('Essay save failed:', response.status, errorText);
    throw new Error(`HTTP error! status: ${response.status} - ${errorText}`);
  }

  const result = await response.json();
  console.log('Essay saved successfully:', result);
  return result;
};

const savePaperDocument = async () => {
  const enteredContent = getEditorContent();
  const paperId = getIdFromPath();
  const userId = getUserIdFromQueryParams();
  
  console.log('📄 Saving paper document:', { paperId, userId });
  
  if (!paperId || !userId) {
    throw new Error(`Missing required parameters: paper_id=${paperId}, user_id=${userId}`);
  }
  
  // DEBUG: Log references before saving
  console.log('📚 DEBUG: references.value before saving:', references.value);
  console.log('📚 DEBUG: references.value.length:', references.value.length);
  
  const payload = {
    user_id: userId,
    topic: selectedReferences.value.length > 0 
      ? selectedReferences.value.map(refId => {
          const ref = references.value.find(r => r.reference_id === refId);
          return ref ? ref.TitleName : '';
        }).join(', ')
      : getTopicFromQueryParams(),
    paper_id: paperId,
    citation_style: paperTemplate.value.citationStyle || '',
    selected_references: references.value.map(ref => JSON.stringify(ref)), // Save complete reference set, not just selected ones
    dialect: paperTemplate.value.dialect || 'US',
    word_count: parseInt(customWordCount.value) || 1000,
    reading_level: paperTemplate.value.readingLevel || 'college',
    entered_content: enteredContent,
    gen_paper: outlineData.value || '',
    outline: JSON.stringify(paperData.value.outline || {}),
    references: JSON.stringify(references.value || [])
  };
  
  console.log('📤 Paper payload:', payload);
  console.log('📚 DEBUG: payload.references is Array?', Array.isArray(payload.references));
  console.log('📚 DEBUG: payload.references content:', JSON.stringify(payload.references));
  console.log('📚 DEBUG: payload.selected_references is Array?', Array.isArray(payload.selected_references));
  console.log('📚 DEBUG: payload.selected_references length:', payload.selected_references?.length);
  console.log('📚 DEBUG: payload.selected_references sample:', payload.selected_references?.[0]?.substring(0, 100));

  const response = await fetch('https://jfv6blghbfv5lr3wt6sho4kewe0mrifm.lambda-url.us-east-1.on.aws/create_paper_draft', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    const errorText = await response.text();
    console.error('Paper save failed:', response.status, errorText);
    throw new Error(`HTTP error! status: ${response.status} - ${errorText}`);
  }

  const result = await response.json();
  console.log('Paper saved successfully:', result);
  return result;
};

const saveEconomicsDocument = async () => {
  const enteredContent = getEditorContent();
  const ecoId = getIdFromPath();
  const userId = getUserIdFromQueryParams();
  
  console.log('🏛️ SAVING ECONOMICS DOCUMENT');
  console.log('📋 Eco ID:', ecoId);
  console.log('👤 User ID:', userId);
  console.log('🔒 SECURITY: Each eco_id + user_id combination should be unique');
  
  if (!userId) {
    throw new Error(`Missing required parameter: user_id=${userId}`);
  }
  
  // Updated payload structure to handle new Complete IA data
  const payload = {
    user_id: userId,
    progress_data: {
      // Article content for left sidebar display
      article: ibEconomics.value.article || '',
      economics_unit: ibEconomics.value.economicsUnit || '',
      citation_style: ibEconomics.value.citationStyle || 'apa',
      
      // Query parameters for Railway API reconstruction
      article_title: getQueryParam('article_title') || '',
      article_url: getQueryParam('article_url') || '',
      article_date: getQueryParam('article_date') || '',
      student_name: getQueryParam('student_name') || '',
      school_name: getQueryParam('school_name') || '',
      
      // Concept suggestions from Railway API
      concept_suggestions: ibEconomics.value.suggestions || [],
      selected_concepts: ibEconomics.value.selectedConcepts || [],
      
      // Generated outline content (legacy)
      generated_outline: ibEconomics.value.outline || '',
      
      // NEW: Complete IA data from Railway API
      complete_ia: economicsCompleteIA.value || null,
      complete_ia_sections: economicsIASections.value || [],
      
      // Main editor content (user's writing)
      entered_content: enteredContent
    }
  };
  
  // Only include eco_id if we have one (for updates), otherwise let API auto-generate
  if (ecoId) {
    payload.eco_id = ecoId;
  }
  
  console.log('📤 Economics save payload (with Complete IA):', {
    ...payload,
    progress_data: {
      ...payload.progress_data,
      complete_ia: payload.progress_data.complete_ia ? 'Complete IA data present' : 'No Complete IA',
      complete_ia_sections: `${payload.progress_data.complete_ia_sections.length} sections`
    }
  });

  const response = await fetch(`${backend_url}/eco-docs/save-progress`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    const errorText = await response.text();
    console.error('Economics save failed:', response.status, errorText);
    throw new Error(`HTTP error! status: ${response.status} - ${errorText}`);
  }

  const result = await response.json();
  console.log('Economics saved successfully:', result);
  
  // If this was a new document creation, update the URL with the eco_id
  if (result.success && result.eco_id && !ecoId) {
    const currentUrl = new URL(window.location);
    const newUrl = currentUrl.pathname.replace(/\/editor\/.*$/, `/editor/${result.eco_id}`) + currentUrl.search;
    window.history.replaceState({}, '', newUrl);
    console.log('✅ URL updated with new eco_id:', result.eco_id);
  }
  
  return result;
};

const saveTokJournalDocument = async () => {
  const enteredContent = getEditorContent();
  const generatedContent = essayContent.value.map(section => 
    `<h3>${section.title}</h3>${section.content}`
  ).join('');

  // Serialize full references like essay/paper
  let allRefsJson = '[]';
  try { allRefsJson = JSON.stringify(references.value || []); } catch {}

  const tokId = getIdFromPath();
  const userId = getUserIdFromQueryParams();

  const payload = {
    tok_id: tokId,
    user_id: userId,
    data: {
      title: getTopicFromQueryParams(),
      instructions: tokJournal?.value?.instructions || '',
      citation_style: tokJournal?.value?.citationStyle || '',
      word_count: parseInt(customWordCount.value) || 350,
      references: allRefsJson,
      // Right sidebar outline and generated text
      generated_outline: outlineData?.value || '',
      generated_journal: generatedContent,
      // Editor content
      entered_content: enteredContent
    }
  };

  const response = await fetch('https://jfv6blghbfv5lr3wt6sho4kewe0mrifm.lambda-url.us-east-1.on.aws/save-progress', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });

  if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
  const result = await response.json();
  console.log('TOK Journal saved successfully:', result);
  return result;
};

const saveTokExhibitionDocument = async () => {
  const enteredContent = getEditorContent();
  const generatedContent = essayContent.value.map(section => 
    `<h3>${section.title}</h3>${section.content}`
  ).join('');
  
  const tokId = getIdFromPath(); // Extract tok_id from URL path
  const userId = getUserIdFromQueryParams();
  
  const payload = {
    tok_id: tokId,
    user_id: userId,
    data: {
      // All TOK Exhibition data goes inside the data object
      title: getTopicFromQueryParams(),
      
      // Save TOK Exhibition specific data
      selected_prompt: tokExhibition.value.selectedPrompt || '',
      selected_prompt_number: tokExhibition.value.selectedPromptNumber || null,
      available_prompts: tokExhibition.value.availablePrompts || [],
      
      // Save selected objects
      selected_objects: tokExhibition.value.selectedObjects || [],
      suggested_objects: tokExhibition.value.suggestedObjects || [],
      
      // Save references
      exhibition_references: tokExhibition.value.exhibitionReferences || [],
      selected_exhibition_references: tokExhibition.value.selectedExhibitionReferences || [],
      citation_format: tokExhibition.value.citationFormat || 'APA7',
      
      // Save current step and state
      current_step: tokExhibition.value.currentStep || 1,
      is_generating_essay: tokExhibition.value.isGeneratingEssay || false,
      
      // Save generated and entered content
      generated_essay: generatedContent,
      entered_content: enteredContent
    }
  };

  const response = await fetch('https://jfv6blghbfv5lr3wt6sho4kewe0mrifm.lambda-url.us-east-1.on.aws/save-progress', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  const result = await response.json();
  console.log('TOK Exhibition saved successfully:', result);
  return result;
};

const loadTokExhibitionDocument = async () => {
  const tokId = getIdFromPath(); // Extract tok_id from URL path
  const userId = getUserIdFromQueryParams();
  
  if (!tokId || !userId) {
    console.log('No tok ID or user ID found, starting fresh');
    return;
  }

  try {
    const response = await fetch(`https://jfv6blghbfv5lr3wt6sho4kewe0mrifm.lambda-url.us-east-1.on.aws/tok-draft/${tokId}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      }
    });

    if (!response.ok) {
      if (response.status === 404) {
        console.log('No existing TOK Exhibition document found, starting fresh');
        return;
      }
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    console.log('TOK Exhibition loaded successfully:', data);

    // The data should be in the response, extract from data object if needed
    const tokData = data.data || data;

    // Restore TOK Exhibition state
    if (tokData.selected_prompt) tokExhibition.value.selectedPrompt = tokData.selected_prompt;
    if (tokData.selected_prompt_number) tokExhibition.value.selectedPromptNumber = tokData.selected_prompt_number;
    if (tokData.available_prompts) tokExhibition.value.availablePrompts = tokData.available_prompts;
    
    if (tokData.selected_objects) tokExhibition.value.selectedObjects = tokData.selected_objects;
    if (tokData.suggested_objects) tokExhibition.value.suggestedObjects = tokData.suggested_objects;
    
    if (tokData.exhibition_references) tokExhibition.value.exhibitionReferences = tokData.exhibition_references;
    if (tokData.selected_exhibition_references) tokExhibition.value.selectedExhibitionReferences = tokData.selected_exhibition_references;
    if (tokData.citation_format) tokExhibition.value.citationFormat = tokData.citation_format;
    
    if (tokData.current_step) tokExhibition.value.currentStep = tokData.current_step;
    
    // Restore generated content
    if (tokData.generated_essay) {
      // Parse the generated essay back into sections
      parseEssayContent(tokData.generated_essay);
    }
    
    // Restore entered content to editor
    if (tokData.entered_content) {
      window.editorContentFromDatabase = tokData.entered_content;
      console.log('📝 TOK Exhibition content set in cache, length:', tokData.entered_content.length);
      
      // Load content into editor with retry mechanism (same as essay/paper templates)
      const loadWithRetry = (attempt = 1, maxAttempts = 10) => {
        console.log(`🔄 Loading attempt ${attempt}/${maxAttempts}`);
        
        if (window.loadEditorContentFromDatabase && typeof window.loadEditorContentFromDatabase === 'function') {
          try {
            const success = window.loadEditorContentFromDatabase();
            if (success !== false) {
              console.log('✅ Content loaded successfully on attempt', attempt);
              return;
            }
          } catch (error) {
            console.warn(`⚠️ Error on attempt ${attempt}:`, error);
          }
        }
        
        // If not successful and we have more attempts, retry
        if (attempt < maxAttempts) {
          setTimeout(() => {
            loadWithRetry(attempt + 1, maxAttempts);
          }, 300 * attempt); // Increasing delay
        } else {
          console.error('❌ Failed to load content after maximum attempts');
          // Try manual loader as final fallback
          if (window.manualLoadContent) {
            console.log('🔄 Trying manual loader as final fallback...');
            window.manualLoadContent();
          }
        }
      };
      
      // Start loading after a delay
      setTimeout(() => {
        loadWithRetry();
      }, 500);
    }

    console.log('✅ TOK Exhibition document loaded and restored');
    
  } catch (error) {
    console.error('Error loading TOK Exhibition document:', error);
    // Don't throw error, just start fresh
  }
};

const callGPTZeroAPI = async (content) => {
  const formData = new FormData();
  formData.append('user_id','user1')
  formData.append('submission_type', 'text');
  formData.append('submitted_text', content);
  
  const response = await fetch('https://web-production-a65cb.up.railway.app/api/gptzero/submit', {
    method: 'POST',
    headers: { 'accept': 'application/json' },
    body: formData
  });
  
  if (!response.ok) throw new Error(`API error: ${response.status}`);
  return await response.json();
};

const formatGPTZeroResult = (result) => {
  const doc = result.documents[0];
  const percentage = (doc.completely_generated_prob * 100).toFixed(1);
  const confidence = doc.confidence_category;
  
  let message = `
    <div class="result-item">
      <strong>AI Detection Result:</strong> ${doc.result_message}
    </div>
    <div class="result-item">
      <strong>AI Probability:</strong> ${percentage}%
    </div>
    <div class="result-item">
      <strong>Confidence:</strong> ${confidence}
    </div>
    <div class="result-item">
      <strong>Predicted Class:</strong> ${doc.predicted_class}
    </div>
  `;
  
  // Add sentence-level analysis if available
  // if (doc.sentences?.length > 0) {
  //   message += `<div class="sentence-analysis"><h4>Sentence Analysis:</h4>`;
  //   doc.sentences.forEach(sentence => {
  //     const aiProb = (sentence.generated_prob * 100).toFixed(1);
  //     message += `
  //       <div class="sentence-item">
  //         <p>${sentence.sentence}</p>
  //         <small>AI Probability: ${aiProb}%</small>
  //       </div>
  //     `;
  //   });
  //   message += `</div>`;
  // }
  
  return message;
};

const checkPlagiarism = async () => {
  try {
    isCheckingPlagiarism.value = true;
    plagiarismResult.value = null;
    plagiarismError.value = null;
    
    const content = getEditorContent();
    if (!content || content.trim().length < 50) {
      throw new Error('Content is too short to check for plagiarism');
    }
    
    const result = await callGPTZeroAPI(content);
    plagiarismResult.value = formatGPTZeroResult(result);
  } catch (error) {
    plagiarismError.value = error.message || 'Failed to check plagiarism';
    console.error('Plagiarism check error:', error);
  } finally {
    isCheckingPlagiarism.value = false;
  }
};

// Save confirmation dialog state
const showSaveDialog = ref(false);
let pendingUnloadEvent = null;

// Dialog handlers
const handleDialogSave = async () => {
  console.log('💾 User chose to SAVE - saving content...');
  try {
    // Use the existing working save functions
    if (selectedMode.value === 'essay') {
      await saveEssayDocument();
      console.log('✅ Essay content saved via existing function');
    } else if (selectedMode.value === 'paper-template') {
      await savePaperDocument();
      console.log('✅ Paper content saved via existing function');
    } else if (['microeconomics', 'macroeconomics', 'globaleconomics'].includes(selectedMode.value)) {
      await saveEconomicsDocument();
      console.log('✅ Economics content saved via existing function');
    } else if (selectedMode.value === 'tok-exhibition') {
      await saveTokExhibitionDocument();
      console.log('✅ TOK Exhibition content saved via existing function');
    } else if (selectedMode.value.includes('tok')) {
      // For other TOK modes, use the save function from bubble component
      if (typeof window.saveTokProgress === 'function') {
        await window.saveTokProgress();
        console.log('✅ TOK content saved via bubble component function');
      } else {
        console.warn('saveTokProgress function not available in fallback');
      }
    }
    
    // Close dialog and allow page to unload
    showSaveDialog.value = false;
    console.log('✅ Content saved successfully!');
    
    // Remove listeners and execute the original action after save
    window.removeEventListener('beforeunload', handleUnloadAttempt);
    window.removeEventListener('pagehide', handleUnloadAttempt);
    
    setTimeout(() => {
      if (pendingUnloadEvent) {
        if (pendingUnloadEvent.type === 'beforeunload' || pendingUnloadEvent.type === 'pagehide' || 
            (pendingUnloadEvent.type === 'keyboard' && (pendingUnloadEvent.key === 'F5' || pendingUnloadEvent.key === 'r'))) {
          window.location.reload();
        } else if (pendingUnloadEvent.type === 'keyboard' && pendingUnloadEvent.key === 'w') {
          window.close();
        }
      }
      pendingUnloadEvent = null;
    }, 100);
    
  } catch (error) {
    console.error('❌ Error saving document:', error);
    // Still close dialog
    showSaveDialog.value = false;
  }
};

const handleDialogDontSave = () => {
  console.log('⏭️ User chose DON\'T SAVE - content will not be saved, references are already working fine');
  
  // Don't call any API - references are already persisting as you mentioned
  // Close dialog and proceed with the original action
  showSaveDialog.value = false;
  
  // Remove listeners and execute the original action without saving
  window.removeEventListener('beforeunload', handleUnloadAttempt);
  window.removeEventListener('pagehide', handleUnloadAttempt);
  
  setTimeout(() => {
    if (pendingUnloadEvent) {
      if (pendingUnloadEvent.type === 'beforeunload' || pendingUnloadEvent.type === 'pagehide' || 
          (pendingUnloadEvent.type === 'keyboard' && (pendingUnloadEvent.key === 'F5' || pendingUnloadEvent.key === 'r'))) {
        window.location.reload();
      } else if (pendingUnloadEvent.type === 'keyboard' && pendingUnloadEvent.key === 'w') {
        window.close();
      }
    }
    pendingUnloadEvent = null;
  }, 100);
};

const handleDialogCancel = () => {
  console.log('❌ User chose CANCEL - staying on editor, no API calls, exactly where they stopped');
  
  // Just close dialog and stay on page - no API calls, user returns to editor
  showSaveDialog.value = false;
  pendingUnloadEvent = null;
  
  // User is directed back to where they stopped writing - no changes needed, they're already there
};

// Function to proceed with the original unload action
const proceedWithUnload = () => {
  if (pendingUnloadEvent) {
    console.log('🚀 Proceeding with unload action:', pendingUnloadEvent.type);
    
    // Remove our event listeners to avoid recursive calls
    window.removeEventListener('beforeunload', handlePageUnload);
    window.removeEventListener('pagehide', handlePageUnload);
    
    // Small delay to ensure dialog closes properly, then proceed
    setTimeout(() => {
      if (pendingUnloadEvent.type === 'beforeunload') {
        // Check if this was a refresh (Ctrl+R) or tab close
        // For both cases, we can safely reload
        window.location.reload();
      } else if (pendingUnloadEvent.type === 'pagehide') {
        // For mobile/tablet page hide
        window.close();
      }
    }, 100);
    
    pendingUnloadEvent = null;
  }
};

// Create named event handler function
const handleUnloadAttempt = (event) => {
  console.log('🚨 BEFOREUNLOAD EVENT TRIGGERED!');
  console.log('📊 Current mode:', selectedMode.value);
  console.log('📊 Event type:', event.type);
  
  if (selectedMode.value === 'essay' || selectedMode.value === 'paper-template' || 
      ['microeconomics', 'macroeconomics', 'globaleconomics'].includes(selectedMode.value) ||
      selectedMode.value.includes('tok')) {
      
      const content = getEditorContent();
      console.log('📊 Content length:', content?.length || 0);
      console.log('📊 Content exists:', !!content && content.trim().length > 0);
      
      if (content && content.trim().length > 0) {
        console.log('🚨 CONTENT EXISTS - SHOWING SAVE DIALOG');
        
        // BULLETPROOF: Always save before navigation for main website integration
        try {
          saveDocument();
          console.log('✅ Content auto-saved before navigation');
        } catch (error) {
          console.error('❌ Failed to save before navigation:', error);
        }
        
        // Set custom message in browser dialog and show it
        const message = 'You have unsaved changes. Choose an option:';
        event.returnValue = message;
        
        // When browser dialog appears, immediately show our custom dialog on top
        setTimeout(() => {
          console.log('🚨 Setting showSaveDialog.value = true');
          showSaveDialog.value = true;
          pendingUnloadEvent = event;
          console.log('🚨 Custom Save/Don\'t Save/Cancel dialog shown over browser dialog');
          console.log('🚨 showSaveDialog.value is now:', showSaveDialog.value);
        }, 10);
        
        return message;
      } else {
        console.log('⏭️ No content to save, allowing navigation');
      }
    } else {
      console.log('⏭️ Mode not supported for save dialog:', selectedMode.value);
    }
};

// Debounce mechanism to prevent infinite loops
let lastFetchTime = 0;
let lastSaveTime = 0;
const FETCH_DEBOUNCE_MS = 2000; // 2 seconds - back to original
const SAVE_DEBOUNCE_MS = 1000; // 1 second - back to original

// Use browser's dialog as trigger to show our custom dialog with save options
const setupAutoSaveEventListeners = () => {
  console.log('🔧 SETTING UP AUTO-SAVE EVENT LISTENERS');
  console.log('🔧 Current mode:', selectedMode.value);
  
  // Add the named event listener
  console.log('🔧 Adding beforeunload event listener');
  window.addEventListener('beforeunload', handleUnloadAttempt);

  // Handle tab switching (Alt+Tab) via visibilitychange event
  document.addEventListener('visibilitychange', () => {
    console.log('🔄 Visibility changed:', document.visibilityState, 'Mode:', selectedMode.value);
    
    if (document.visibilityState === 'hidden') {
      // Tab is being switched away from - save document
      if (selectedMode.value === 'essay' || selectedMode.value === 'paper-template' || 
          ['microeconomics', 'macroeconomics', 'globaleconomics'].includes(selectedMode.value) ||
          selectedMode.value.includes('tok')) {
        console.log('💾 Tab switching away - saving document...');
        
        // Debounce save operations
        const now = Date.now();
        if (now - lastSaveTime < SAVE_DEBOUNCE_MS) {
          console.log('🚫 Save debounced - too soon since last save');
          return;
        }
        lastSaveTime = now;
        
        // For economics, use direct save function
        if (['microeconomics', 'macroeconomics', 'globaleconomics'].includes(selectedMode.value)) {
          saveEconomicsDocument().catch(error => {
            console.error(' Failed to save economics on tab switch:', error);
          });
        } else if (selectedMode.value === 'tok-exhibition') {
          // For TOK Exhibition, use the specific save function
          saveTokExhibitionDocument().catch(error => {
            console.error(' Failed to save TOK Exhibition on tab switch:', error);
          });
        } else if (selectedMode.value === 'tok-essay') {
          // For TOK Essay, use the specific save function
          saveTokEssayDocument().catch(error => {
            console.error(' Failed to save TOK Essay on tab switch:', error);
          });
        } else if (selectedMode.value === 'tok') {
          // For TOK Journal, use the specific save function
          saveTokJournalDocument().catch(error => {
            console.error(' Failed to save TOK Journal on tab switch:', error);
          });
        } else if (selectedMode.value.includes('tok')) {
          // For other TOK modes, use the save function from bubble component
          if (typeof window.saveTokProgress === 'function') {
            window.saveTokProgress().catch(error => {
              console.error(' Failed to save TOK progress on tab switch:', error);
            });
          } else {
            console.warn(' saveTokProgress function not available');
          }
        } else {
          const content = getEditorContent();
          if (content && content.trim().length > 0) {
            saveDocument().catch(error => {
              console.error(' Failed to save on tab switch:', error);
            });
          }
        }
      }
    } else if (document.visibilityState === 'visible') {
      // Tab is being switched back to - load latest document
      if (selectedMode.value === 'essay' || selectedMode.value === 'paper-template' || 
          ['microeconomics', 'macroeconomics', 'globaleconomics'].includes(selectedMode.value) ||
          selectedMode.value === 'tok-exhibition') {
        console.log('🔄 Tab switching back - loading latest document...');
        
        // Debounce fetch operations
        const now = Date.now();
        if (now - lastFetchTime < FETCH_DEBOUNCE_MS) {
          console.log('🚫 Fetch debounced - too soon since last fetch');
          return;
        }
        lastFetchTime = now;
        
        setTimeout(() => {
          if (selectedMode.value === 'tok-exhibition') {
            loadTokExhibitionDocument().catch(error => {
              console.error('❌ Failed to load TOK Exhibition on tab switch back:', error);
            });
          } else {
            fetchSavedData().catch(error => {
              console.error('❌ Failed to load on tab switch back:', error);
            });
          }
        }, 200); // Longer delay for economics to ensure proper loading
      }
    }
  });

  // Handle window blur/focus events as additional tab switch detection
  window.addEventListener('blur', () => {
    console.log('🔄 Window blur detected, Mode:', selectedMode.value);
    
    // Window lost focus - save document
    if (selectedMode.value === 'essay' || selectedMode.value === 'paper-template' || 
        ['microeconomics', 'macroeconomics', 'globaleconomics'].includes(selectedMode.value) ||
        selectedMode.value.includes('tok')) {
      
      console.log('💾 Window blur - saving document...');
      
      // Debounce save operations
      const now = Date.now();
      if (now - lastSaveTime < SAVE_DEBOUNCE_MS) {
        console.log('🚫 Save debounced - too soon since last save');
        return;
      }
      lastSaveTime = now;
      
      // For economics, use direct save function
      if (['microeconomics', 'macroeconomics', 'globaleconomics'].includes(selectedMode.value)) {
        saveEconomicsDocument().catch(error => {
          console.error('❌ Failed to save economics on blur:', error);
        });
      } else if (selectedMode.value === 'tok-exhibition') {
        // For TOK Exhibition, use the specific save function
        saveTokExhibitionDocument().catch(error => {
          console.error('❌ Failed to save TOK Exhibition on blur:', error);
        });
      } else if (selectedMode.value === 'tok-essay') {
        // For TOK Essay, use the specific save function
        saveTokEssayDocument().catch(error => {
          console.error('❌ Failed to save TOK Essay on blur:', error);
        });
      } else if (selectedMode.value === 'tok') {
        // For TOK Journal, use the specific save function
        saveTokJournalDocument().catch(error => {
          console.error('❌ Failed to save TOK Journal on blur:', error);
        });
      } else if (selectedMode.value.includes('tok')) {
        // For other TOK modes, use the save function from bubble component
        if (typeof window.saveTokProgress === 'function') {
          window.saveTokProgress().catch(error => {
            console.error('❌ Failed to save TOK progress on blur:', error);
          });
        } else {
          console.warn(' saveTokProgress function not available on blur');
        }
      } else {
        const content = getEditorContent();
        if (content && content.trim().length > 0) {
          saveDocument().catch(error => {
            console.error('❌ Failed to save on blur:', error);
          });
        }
      }
    }
  });

  window.addEventListener('focus', () => {
    console.log('🔄 Window focus detected, Mode:', selectedMode.value);
    
    // Window gained focus - load latest document
    if (selectedMode.value === 'essay' || selectedMode.value === 'paper-template' || 
        ['microeconomics', 'macroeconomics', 'globaleconomics'].includes(selectedMode.value) ||
        selectedMode.value === 'tok-exhibition') {
      console.log('🔄 Window focus detected - loading latest document...');
      
      // Debounce fetch operations
      const now = Date.now();
      if (now - lastFetchTime < FETCH_DEBOUNCE_MS) {
        console.log('🚫 Fetch debounced - too soon since last fetch');
        return;
      }
      lastFetchTime = now;
      
      setTimeout(() => {
        if (selectedMode.value === 'tok-exhibition') {
          loadTokExhibitionDocument().catch(error => {
            console.error('❌ Failed to load TOK Exhibition on window focus:', error);
          });
        } else {
          fetchSavedData().catch(error => {
            console.error('❌ Failed to load on window focus:', error);
          });
        }
      }, 200); // Small delay to ensure window is fully focused
    }
  });
  
  // Also handle keyboard shortcuts
  document.addEventListener('keydown', (event) => {
    if ((event.ctrlKey && event.key === 'r') || event.key === 'F5' || (event.ctrlKey && event.key === 'w')) {
      if (selectedMode.value === 'essay' || selectedMode.value === 'paper-template' || 
          ['microeconomics', 'macroeconomics', 'globaleconomics'].includes(selectedMode.value) ||
          selectedMode.value.includes('tok')) {
        const content = getEditorContent();
        if (content && content.trim().length > 0 && !showSaveDialog.value) {
          event.preventDefault();
          showSaveDialog.value = true;
          pendingUnloadEvent = { type: 'keyboard', key: event.key, ctrlKey: event.ctrlKey };
        }
      }
    }
  });
  
  console.log('✅ Setup complete - custom dialog will overlay browser dialog');
};

// Helper functions to get save payloads
const getEssaySavePayload = () => {
  const enteredContent = getEditorContent();
  const generatedContent = essayContent.value.map(section => 
    `<h3>${section.title}</h3>${section.content}`
  ).join('');

  return {
    document_id: getIdFromPath(),
    user_id: getUserIdFromQueryParams(),
    title: getTopicFromQueryParams(),
    topic: getTopicFromQueryParams(),
    word_count: parseInt(customWordCount.value) || 0,
    citation_style: selectedFormat.value || '',
    references: references.value.map(ref => 
      `${ref.AuthorName}. (${ref.Year}). ${ref.TitleName}. ${ref.Publisher || 'Publisher not specified'}.`
    ).join('\n'), // Save complete reference set, not just selected ones
    generated_essay: generatedContent,
    entered_essay: enteredContent
  };
};

const getPaperSavePayload = () => {
  const enteredContent = getEditorContent();
  
  return {
    user_id: getUserIdFromQueryParams(),
    topic: selectedReferences.value.length > 0 
      ? selectedReferences.value.map(refId => {
          const ref = references.value.find(r => r.reference_id === refId);
          return ref ? ref.TitleName : '';
        }).join(', ')
      : getTopicFromQueryParams(),
    paper_id: getIdFromPath(),
    citation_style: paperTemplate.value.citationStyle || '',
    references: references.value,
    dialect: paperTemplate.value.dialect || 'US',
    word_count: parseInt(customWordCount.value) || 1000,
    reading_level: paperTemplate.value.readingLevel || 'college',
    entered_content: enteredContent,
    gen_paper: outlineData.value || ''
  };
};



const getTokJournalSavePayload = () => {
  const enteredContent = getEditorContent();
  const generatedContent = essayContent.value.map(section => 
    `<h3>${section.title}</h3>${section.content}`
  ).join('');
  
  return {
    document_id: getIdFromPath(),
    user_id: getUserIdFromQueryParams(),
    title: getTopicFromQueryParams(),
    instructions: tokJournal.value.instructions || '',
    citation_style: tokJournal.value.citationStyle || '',
    num_words: parseInt(customWordCount.value) || 350,
    references: references.value.map(ref => 
      `${ref.AuthorName}. (${ref.Year}). ${ref.TitleName}. ${ref.Publisher || 'Publisher not specified'}.`
    ).join('\n'), // Save complete reference set, not just selected ones
    generated_journal: generatedContent,
    entered_content: enteredContent
  };
};


// Cleanup function removed - no more auto-save intervals to clean up

// Fetch saved data functions
const backend_url = 'https://jfv6blghbfv5lr3wt6sho4kewe0mrifm.lambda-url.us-east-1.on.aws';

// Bulletproof flags to prevent any duplicate API calls
let isFetching = false;
let lastGeneratedTopicKey = null; // Track the last topic + user + paper combination we generated references for
let currentLoadedTopic = null; // Track the currently loaded topic to detect changes

// CLIENT-SIDE TOPIC-SPECIFIC REFERENCE CACHE
const topicReferencesCache = new Map(); // Store references per topic locally

// SESSION-BASED DUPLICATE CALL PREVENTION
const sessionGeneratedTopics = new Set(); // Track which topics we've generated this session

// Helper function to get year from different reference formats
const getRefYear = (ref) => {
  console.log('🔍 getRefYear called with:', ref);
  
  // Regular references have Year field
  if (ref.Year) {
    console.log('✅ Found Year field:', ref.Year);
    return ref.Year;
  }
  
  // TOK Exhibition references have year in citation field
  if (ref.citation) {
    console.log('🔍 Checking citation for year:', ref.citation);
    // Try to extract year from citation (look for 4-digit year)
    const yearMatch = ref.citation.match(/\b(19|20)\d{2}\b/);
    if (yearMatch) {
      console.log('✅ Extracted year from citation:', yearMatch[0]);
      return yearMatch[0];
    }
  }
  
  console.log('❌ No year found, returning No year');
  return 'No year';
};

// Helper function to get topic from query params
const getTopicFromQueryParams = () => {
  const urlParams = new URLSearchParams(window.location.search);
  let topic = urlParams.get('topic');
  
  // If no topic found, try parsing from URL in case of malformed URL
  if (!topic) {
    const urlString = window.location.href;
    const topicMatch = urlString.match(/[?&]topic=([^&]+)/);
    if (topicMatch) {
      topic = decodeURIComponent(topicMatch[1]);
    }
  }
  
  const finalTopic = topic || 'artificial intelligence';
  console.log('Getting topic from query params:', finalTopic);
  console.log('Full URL for topic extraction:', window.location.href);
  
  return finalTopic;
};

// Helper function to create document key including topic
const getDocumentKey = () => {
  const sessionId = getIdFromPath();
  const userId = getUserIdFromQueryParams();
  const topic = getTopicFromQueryParams();
  return `${userId}_${sessionId}_${topic}`;
};

// CLIENT-SIDE TOPIC-SPECIFIC REFERENCE MANAGEMENT
const getTopicCacheKey = () => {
  return `${getUserIdFromQueryParams()}_${getIdFromPath()}_${getTopicFromQueryParams()}`;
};

const saveReferencesToTopicCache = (references) => {
  const cacheKey = getTopicCacheKey();
  topicReferencesCache.set(cacheKey, references);
  console.log('💾 Saved', references.length, 'references to topic cache for:', cacheKey);
};

const loadReferencesFromTopicCache = () => {
  const cacheKey = getTopicCacheKey();
  const cachedRefs = topicReferencesCache.get(cacheKey);
  if (cachedRefs) {
    console.log('📂 Loaded', cachedRefs.length, 'references from topic cache for:', cacheKey);
    return cachedRefs;
  }
  console.log('📂 No cached references found for:', cacheKey);
  return null;
};

const fetchSavedData = async () => {
  // AGGRESSIVE CALL PREVENTION
  if (isFetching) {
    console.log('⏳ Fetch already in progress, skipping duplicate call');
    return;
  }
  
  // Additional debounce check
  const now = Date.now();
  if (now - lastFetchTime < FETCH_DEBOUNCE_MS) {
    console.log('🚫 Fetch debounced - too soon since last fetch (', now - lastFetchTime, 'ms ago)');
    return;
  }
  
  lastFetchTime = now;
  isFetching = true;
  try {
  const urlParams = new URLSearchParams(window.location.search);
  // Get session ID from URL path if not in query params
  const sessionId = urlParams.get('sessionId') || urlParams.get('document_id') || urlParams.get('paper_id') || getIdFromPath();
  const user_id = urlParams.get('user_id') || '';
  
  console.log('=== fetchSavedData called ===');
  console.log('Current URL:', window.location.href);
  console.log('URL params:', { sessionId, user_id, mode: selectedMode.value });
  console.log('All URL params:', Array.from(urlParams.entries()));
  console.log('Session ID from path:', getIdFromPath());
  
  if (!sessionId || !user_id) {
    console.log('❌ No session ID or user ID found, skipping fetch');
    console.log('Available URL params:', Array.from(urlParams.entries()));
    console.log('Session ID from path:', getIdFromPath());
    return;
  }

  console.log(`✅ Fetching saved data for mode: ${selectedMode.value}, session: ${sessionId}, user: ${user_id}`);

    if (selectedMode.value === 'essay') {
      await fetchEssayData(sessionId, user_id);
    } else if (selectedMode.value === 'paper-template') {
      await fetchPaperData(sessionId, user_id);
    } else if (['microeconomics', 'macroeconomics', 'globaleconomics'].includes(selectedMode.value)) {
      await fetchEconomicsData(sessionId, user_id);
    } else if (['tok-essay', 'tok', 'tok-exhibition'].includes(selectedMode.value)) {
      await fetchTokData(sessionId, user_id);
    }
    
    console.log('✅ Data fetch completed successfully');
    
  } catch (error) {
    console.error('❌ Error fetching saved data:', error);
  } finally {
    isFetching = false;
  }
};

// Helper function to toggle reference selection (UI only - doesn't affect database)
function toggleGeneralReferenceSelection(reference) {
  const index = selectedReferences.value.indexOf(reference.reference_id);
  
  if (index > -1) {
    // Remove from selection
    selectedReferences.value.splice(index, 1);
    console.log('✅ Reference deselected (UI only):', reference.TitleName);
  } else {
    // Add to selection
    selectedReferences.value.push(reference.reference_id);
    console.log('✅ Reference selected (UI only):', reference.TitleName);
  }
  
  // Complete reference list remains unchanged - only selection state changes
}

// Helper functions to process loaded data
const processEssayData = (data) => {
  console.log('Processing essay data:', data);
  
  // Handle entered essay content (main editor content)
  if (data.entered_essay) {
    window.editorContentFromDatabase = data.entered_essay;
    console.log('Essay entered content set in cache, length:', data.entered_essay.length);
    
    // Load content into editor with retry mechanism
    const loadWithRetry = (attempt = 1, maxAttempts = 10) => {
      console.log(`🔄 Loading attempt ${attempt}/${maxAttempts}`);
      
      if (window.loadEditorContentFromDatabase && typeof window.loadEditorContentFromDatabase === 'function') {
        try {
          const success = window.loadEditorContentFromDatabase();
          if (success !== false) {
            console.log('✅ Content loaded successfully on attempt', attempt);
            return;
          }
        } catch (error) {
          console.warn(`⚠️ Error on attempt ${attempt}:`, error);
        }
      }
      
      // If not successful and we have more attempts, retry
      if (attempt < maxAttempts) {
        setTimeout(() => {
          loadWithRetry(attempt + 1, maxAttempts);
        }, 300 * attempt); // Increasing delay
      } else {
        console.error('❌ Failed to load content after maximum attempts');
        // Try manual loader as final fallback
        if (window.manualLoadContent) {
          console.log('🔄 Trying manual loader as final fallback...');
          window.manualLoadContent();
        }
      }
    };
    
    // Start loading after a delay
    setTimeout(() => {
      loadWithRetry();
    }, 500);
  }
  
  // NUCLEAR TOPIC ISOLATION - Handle references with strict topic validation
  const topicForValidation = getTopicFromQueryParams();
  const dataTopic = data.topic || data.title;
  
  console.log('🎯 NUCLEAR TOPIC VALIDATION - Current:', topicForValidation, 'Data:', dataTopic);
  
  if (!dataTopic || dataTopic !== topicForValidation) {
    console.log('💥 NUCLEAR ISOLATION: Topic mismatch or missing - CLEARING ALL DATA');
    console.log('💥 Expected:', topicForValidation, 'Got:', dataTopic);
    
    // NUCLEAR CLEAR - wipe everything
    references.value = [];
    selectedReferences.value = [];
    essayData.value.references = [];
    essayData.value.generatedEssay = '';
    essayData.value.enteredEssay = '';
    
    console.log('💥 NUCLEAR: All essay data wiped for topic isolation');
  } else if (data.references) {
    try {
      console.log('📚 Raw references data from DB in processEssayData:', data.references);
      const parsedReferences = JSON.parse(data.references);
      console.log('📚 Parsed references in processEssayData:', parsedReferences.length, 'references');
      references.value = parsedReferences;
      selectedReferences.value = []; // Start with NO references selected - user must select them
      console.log('✅ 🔴 ESSAY REFERENCES LOADED - references.value.length is now:', references.value.length);
      console.log('✅ This should prevent API call on initialization!');
      console.log('✅ References loaded from essay database via processEssayData:', references.value.length, 'references');
    } catch (e) {
      console.error('Error parsing references in processEssayData:', e);
      references.value = [];
    }
  } else {
    console.log('❌ No references found in essay database via processEssayData');
    references.value = [];
  }
  
  // Set form data
  selectedFormat.value = data.citation_style || '';
  customWordCount.value = data.word_count || 0;
  
  // Handle generated essay content (for sidebar/display)
  if (data.generated_essay) {
    try {
      const contentLength = data.generated_essay.length;
      console.log(`Processing generated essay: ${Math.round(contentLength/1000)}k characters`);
      
      if (contentLength > 30000) {
        // For large content, set simple placeholder
        essayContent.value = [{
          title: 'Generated Essay',
          content: `Essay content (${Math.round(contentLength/1000)}k chars) generated`,
          expanded: false
        }];
      } else {
        // Normal parsing for smaller content
        parseEssayContent(data.generated_essay);
      }
      
      essayData.value.generatedEssay = data.generated_essay;
      console.log('✅ Generated essay saved to essayData.value.generatedEssay');
    } catch (error) {
      console.error('Error processing generated essay content:', error);
    }
  }
  
  // Handle references - EMERGENCY FIX
  if (data.references) {
    try {
      console.log('📚 RAW essay reference data:', data.references);
      
      const refs = data.references;
      let parsedReferences = [];
      
      if (typeof refs === 'string') {
        if (refs !== 'string' && refs.length > 0) {
          parsedReferences = JSON.parse(refs);
        }
      } else if (Array.isArray(refs)) {
        parsedReferences = refs;
      }
      
      console.log('📚 PARSED essay references:', parsedReferences);
      
      if (Array.isArray(parsedReferences) && parsedReferences.length > 0) {
        console.log('✅ SETTING essay references and selections');
        essayData.value.references = parsedReferences;
        references.value = parsedReferences; // Show them immediately
        selectedReferences.value = parsedReferences.map(ref => ref.reference_id || ref.id || Math.random().toString());
        
        console.log('📋 Essay Selected IDs:', selectedReferences.value);
        console.log('📋 Essay References set:', references.value.length);
      } else {
        console.log('❌ No valid essay references found');
        essayData.value.references = [];
        references.value = [];
        selectedReferences.value = [];
      }
    } catch (e) {
      console.error('❌ Error parsing essay references:', e);
      essayData.value.references = [];
      references.value = [];
      selectedReferences.value = [];
    }
  } else {
    console.log('❌ No essay reference data in response');
  }
  
  // Handle other form data
  if (data.citation_style) {
    selectedFormat.value = data.citation_style;
  }
  
  if (data.title) {
    essayData.value.title = data.title;
  }
  
  if (data.word_count) {
    customWordCount.value = data.word_count;
  }
  
  // References are now handled in processEssayData function - removed duplicate handling
};

const processPaperData = (data) => {
  console.log('📄 Processing paper data:', data);
  console.log('📄 Data keys:', Object.keys(data));
  console.log('📄 Has entered_content:', !!data.entered_content);
  console.log('📄 Has gen_paper:', !!data.gen_paper);
  
  // Handle entered content (main editor content) - check both paper and essay field names
  const content = data.entered_content || data.entered_essay;
  if (content) {
    window.editorContentFromDatabase = content;
    console.log('📄 Paper content set in cache, length:', content.length);
    console.log('📄 Content source:', data.entered_content ? 'entered_content' : 'entered_essay');
    
    // Load content into editor with retry mechanism
    const loadWithRetry = (attempt = 1, maxAttempts = 10) => {
      console.log(`🔄 Loading attempt ${attempt}/${maxAttempts}`);
      
      if (window.loadEditorContentFromDatabase && typeof window.loadEditorContentFromDatabase === 'function') {
        try {
          const success = window.loadEditorContentFromDatabase();
          if (success !== false) {
            console.log('✅ Content loaded successfully on attempt', attempt);
            return;
          }
        } catch (error) {
          console.warn(`⚠️ Error on attempt ${attempt}:`, error);
        }
      }
      
      // If not successful and we have more attempts, retry
      if (attempt < maxAttempts) {
        setTimeout(() => {
          loadWithRetry(attempt + 1, maxAttempts);
        }, 300 * attempt); // Increasing delay
      } else {
        console.error('❌ Failed to load content after maximum attempts');
        // Try manual loader as final fallback
        if (window.manualLoadContent) {
          console.log('🔄 Trying manual loader as final fallback...');
          window.manualLoadContent();
        }
      }
    };
    
    // Start loading after a delay
    setTimeout(() => {
      loadWithRetry();
    }, 500);
  }
  
  // Handle generated paper content - check both paper and essay field names
  const generatedContent = data.gen_paper || data.generated_essay;
  if (generatedContent) {
    outlineData.value = generatedContent;
    paperData.value.generatedPaper = generatedContent;
    console.log('📄 Generated content set, length:', generatedContent.length);
    console.log('📄 Generated content source:', data.gen_paper ? 'gen_paper' : 'generated_essay');
  }
  
  // Handle references - EMERGENCY FIX
  if (data.references) {
    try {
      console.log('📚 RAW reference data:', data.references);
      
      let parsedReferences = [];
      
      if (typeof data.references === 'string') {
        if (data.references !== 'string' && data.references.length > 0) {
          parsedReferences = JSON.parse(data.references);
        }
      } else if (Array.isArray(data.references)) {
        parsedReferences = data.references;
      }
      
      console.log('📚 PARSED references:', parsedReferences);
      
      // Restore references to screen
      references.value = parsedReferences;
      console.log('✅ References restored to screen:', references.value.length);
      
      if (Array.isArray(parsedReferences) && parsedReferences.length > 0) {
        console.log('✅ SETTING references and selections');
        paperData.value.references = parsedReferences;
        references.value = parsedReferences; // Show them immediately
        selectedReferences.value = parsedReferences.map(ref => ref.reference_id || ref.id || Math.random().toString());
        
        console.log('📋 Selected IDs:', selectedReferences.value);
        console.log('📋 References set:', references.value.length);
      } else {
        console.log('❌ No valid references found');
        paperData.value.references = [];
        references.value = [];
        selectedReferences.value = [];
      }
    } catch (e) {
      console.error('❌ Error parsing references:', e);
      paperData.value.references = [];
      references.value = [];
      selectedReferences.value = [];
    }
  } else {
    console.log('❌ No reference data in response');
  }
  
  // Handle outline
  if (data.outline) {
    try {
      paperData.value.outline = typeof data.outline === 'string' 
        ? JSON.parse(data.outline) 
        : data.outline;
    } catch (e) {
      console.error('Error parsing outline:', e);
      paperData.value.outline = {};
    }
  }
  
  // Handle other form data
  if (data.citation_style) {
    paperData.value.citationStyle = data.citation_style;
    paperTemplate.value.citationStyle = data.citation_style;
  }
  
  if (data.dialect) {
    paperTemplate.value.dialect = data.dialect;
  }
  
  if (data.reading_level) {
    paperTemplate.value.readingLevel = data.reading_level;
  }
  
  if (data.word_count) {
    customWordCount.value = data.word_count;
  }
  
  if (data.topic) {
    paperData.value.topic = data.topic;
  }
  
  // Handle selected_references - CRITICAL for preventing API calls
  console.log('📚 PAPER LOADING DEBUG: data.selected_references:', data.selected_references);
  console.log('📚 PAPER LOADING DEBUG: data.selected_references.length:', data.selected_references?.length);
  if (data.selected_references && data.selected_references.length > 0) {
    const parsedReferences = data.selected_references.map((refString) => {
      try {
        // Try to parse as JSON first (new format)
        return JSON.parse(refString);
      } catch (e) {
        // Fallback to old string parsing format for backward compatibility
        console.log('⚠️ Failed to parse reference as JSON, falling back to string parsing');
        return null;
      }
    }).filter(ref => ref !== null);

    console.log('📚 PARSED paper references:', parsedReferences.length);
    
    // NUCLEAR TOPIC ISOLATION for paper data
    const paperTopicForValidation = getTopicFromQueryParams();
    const dataTopic = data.topic;
    
    console.log('🎯 NUCLEAR PAPER TOPIC VALIDATION - Current:', paperTopicForValidation, 'Data:', dataTopic);
    
    if (!dataTopic || dataTopic !== paperTopicForValidation) {
      console.log('💥 NUCLEAR PAPER ISOLATION: Topic mismatch or missing - CLEARING ALL DATA');
      console.log('💥 Expected:', paperTopicForValidation, 'Got:', dataTopic);
      
      // NUCLEAR CLEAR - wipe everything
      references.value = [];
      selectedReferences.value = [];
      paperData.value.references = [];
      paperData.value.genPaper = '';
      paperData.value.enteredContent = '';
      outlineData.value = '';
      
      console.log('💥 NUCLEAR: All paper data wiped for topic isolation');
    } else {
      references.value = parsedReferences;
      selectedReferences.value = []; // Start with NO references selected - user must select them
      console.log('✅ 🔴 PAPER REFERENCES LOADED - references.value.length is now:', references.value.length);
      console.log('✅ This should prevent API call on initialization!');
    }
  } else {
    console.log('❌ No paper references found in database - API WILL BE CALLED');
    references.value = [];
    selectedReferences.value = [];
  }
};

// REMOVED: No longer loading references from API
// Just show saved references directly without any API calls

const processTokData = (data) => {
  console.log('Processing TOK data:', data);
  
  if (data.entered_essay) {
    window.editorContentFromDatabase = data.entered_essay;
    console.log('TOK content set in cache, length:', data.entered_essay.length);
  }
  
  if (data.title) {
    tokJournal.value.title = data.title;
  }
  
  if (data.citation_style) {
    tokJournal.value.citationStyle = data.citation_style;
  }
};

const fetchEssayData = async (sessionId, user_id) => {
  try {
    // loading.value is already true from onMounted, keep it visible
    console.log('Fetching essay data...');
    console.log('Session ID:', sessionId);
    console.log('User ID:', user_id);

    const url = new URL(`${backend_url}/api/retrieve-specific-essay`);
    url.searchParams.append('document_id', sessionId);
    url.searchParams.append('user_id', user_id);
    url.searchParams.append('topic', getTopicFromQueryParams());

    console.log('Fetching from URL:', url.toString());

    const essayResponse = await fetch(url.toString(), {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': '' // Add your API key here if needed
      }
    });

    console.log('Response status:', essayResponse.status);
    console.log('Response ok:', essayResponse.ok);

    if (!essayResponse.ok) {
      const errorText = await essayResponse.text();
      console.error('Error response body:', errorText);
      throw new Error(`HTTP error! status: ${essayResponse.status}, body: ${errorText}`);
    }

    const responseData = await essayResponse.json();
    console.log('Raw response data:', responseData);
    const data = responseData?.document;

    if (data) {
      console.log('Essay data received:', data);
      console.log('Data type:', typeof data);
      console.log('Data keys:', Object.keys(data));
      console.log('entered_essay exists:', !!data.entered_essay);
      console.log('generated_essay exists:', !!data.generated_essay);
      
      if (data.entered_essay) {
        console.log('entered_essay length:', data.entered_essay.length);
        console.log('entered_essay preview:', data.entered_essay.substring(0, 200) + '...');
      }
      
      if (data.generated_essay) {
        console.log('generated_essay length:', data.generated_essay.length);
        console.log('generated_essay preview:', data.generated_essay.substring(0, 200) + '...');
      }
      
      // Only set essay content if it was actually generated by user (like paper mode)
      // Don't auto-display essay for new documents - let user generate it first
      if (data.generated_essay && data.generated_essay.trim() && data.essay_generated !== false) {
        try {
          const contentLength = data.generated_essay.length;
          console.log(`Loading essay content: ${Math.round(contentLength/1000)}k characters`);
          
          if (contentLength > 30000) {
            // For large content, load safely without parsing
            console.log('Using safe loading for large content');
            
            // Set a simple placeholder in the sidebar
            essayContent.value = [{
              title: 'Large Essay Loaded',
              content: `Essay content (${Math.round(contentLength/1000)}k chars) loaded in editor`,
              expanded: false
            }];
            
            // Load content into editor
            setTimeout(() => {
              console.log('🔄 Attempting to load content into editor...');
              const success = window.manualLoadContent();
              if (success) {
                console.log('✅ Content loaded successfully!');
              } else {
                console.log('❌ Failed to load content, will retry...');
                // Retry after another delay
                setTimeout(() => {
                  window.manualLoadContent();
                }, 2000);
              }
            }, 1000);
            
          } else {
            // Normal parsing for smaller content
            parseEssayContent(data.generated_essay);
          }
        } catch (error) {
          console.error('Error processing essay content:', error);
          // Fallback - set minimal content
          essayContent.value = [{
            title: 'Essay Loaded',
            content: 'Content loaded in editor',
            expanded: false
          }];
        }
      } else {
        // No generated essay content to display for new documents
        essayContent.value = [];
        console.log('ℹ️ No essay content loaded - user needs to generate one first');
        console.log('Debug - generated_essay length:', data.generated_essay ? data.generated_essay.length : 'undefined');
        console.log('Debug - generated_essay preview:', data.generated_essay ? data.generated_essay.substring(0, 100) : 'undefined');
      }

      // Set references
      if (data.references) {
        try {
          console.log('📚 Raw references data from DB:', data.references);
          const parsedReferences = JSON.parse(data.references);
          console.log('📚 Parsed references:', parsedReferences.length, 'references');
          references.value = parsedReferences;
          selectedReferences.value = []; // Start with NO references selected - user must select them
          console.log('✅ References loaded from essay database - all available but NONE selected initially:', references.value.length, 'references');
          console.log('✅ References loaded from essay database:', references.value.length, 'references');
        } catch (e) {
          console.error('Error parsing references:', e);
          references.value = [];
        }
      } else {
        console.log('❌ No references found in essay database');
        references.value = [];
      }

      // Set other form data
      selectedFormat.value = data.citation_style || '';
      customWordCount.value = data.word_count || 0;
      
      // Set entered content in editor if available - use database content directly
      if (data.entered_essay) {
        // Store content in memory for editor initialization
        window.editorContentFromDatabase = data.entered_essay;
        console.log('✅ Database content loaded for essay, length:', data.entered_essay.length);
        
        // Load content into editor with improved retry mechanism
        const loadWithRetry = (attempt = 1, maxAttempts = 10) => {
          console.log(`🔄 Loading attempt ${attempt}/${maxAttempts}`);
          
          if (window.loadEditorContentFromDatabase && typeof window.loadEditorContentFromDatabase === 'function') {
            try {
              const success = window.loadEditorContentFromDatabase();
              if (success !== false) {
                console.log('✅ Content loaded successfully on attempt', attempt);
                return;
              }
            } catch (error) {
              console.warn(`⚠️ Error on attempt ${attempt}:`, error);
            }
          }
          
          // If not successful and we have more attempts, retry
          if (attempt < maxAttempts) {
            setTimeout(() => {
              loadWithRetry(attempt + 1, maxAttempts);
            }, 300 * attempt); // Increasing delay
          } else {
            console.error('❌ Failed to load content after maximum attempts');
            // Try manual loader as final fallback
            if (window.manualLoadContent) {
              console.log('🔄 Trying manual loader as final fallback...');
              window.manualLoadContent();
            }
          }
        };
        
        // Start loading after a delay
        setTimeout(() => {
          loadWithRetry();
        }, 500);
      } else {
        console.log('❌ No entered essay content found in database');
        console.log('Available data keys:', Object.keys(data));
      }
    }

    console.log('Essay data fetched successfully:', data);
  } catch (error) {
    console.error('Error fetching essay data:', error);
  } finally {
    loading.value = false;
  }
};



const fetchPaperData = async (sessionId, user_id) => {
  try {
    // loading.value is already true from onMounted, keep it visible
    console.log('Fetching paper data...');
    console.log('Session ID:', sessionId);
    console.log('User ID:', user_id);

    const url = new URL(`${backend_url}/api/retrieve-specific-paper-draft`);
    url.searchParams.append('paper_id', sessionId);
    url.searchParams.append('user_id', user_id);
    url.searchParams.append('topic', getTopicFromQueryParams());

    console.log('Fetching from URL:', url.toString());

    const pdfResponse = await fetch(url.toString(), {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': '' // Add your API key here if needed
      }
    });

    console.log('Response status:', pdfResponse.status);
    console.log('Response ok:', pdfResponse.ok);

    if (!pdfResponse.ok) {
      const errorText = await pdfResponse.text();
      console.error('Error response body:', errorText);
      throw new Error(`HTTP error! status: ${pdfResponse.status}, body: ${errorText}`);
    }

    const data = await pdfResponse.json();
    console.log('Raw paper response data:', data);

    if (data) {
      console.log('Paper data received:', data);
      console.log('Data type:', typeof data);
      console.log('Data keys:', Object.keys(data));
      console.log('entered_content exists:', !!data.entered_content);
      console.log('gen_paper exists:', !!data.gen_paper);
      
      if (data.entered_content) {
        console.log('entered_content length:', data.entered_content.length);
        console.log('entered_content preview:', data.entered_content.substring(0, 200) + '...');
      }
      
      if (data.gen_paper) {
        console.log('gen_paper length:', data.gen_paper.length);
        console.log('gen_paper preview:', data.gen_paper.substring(0, 200) + '...');
      }
      
      // Load generated outline if it exists - always persist existing outlines
      if (data.gen_paper && data.gen_paper.trim()) {
        outlineData.value = data.gen_paper;
        console.log('✅ Generated outline loaded from database and will persist');
      } else {
        outlineData.value = '';
        console.log('ℹ️ No outline found in database - user needs to generate one first');
      }
      
      // Set entered content in editor - use database content directly
      if (data.entered_content) {
        // Store content in memory for editor initialization
        window.editorContentFromDatabase = data.entered_content;
        console.log('✅ Database content loaded for paper, length:', data.entered_content.length);
        
        // Load content into editor with improved retry mechanism
        const loadWithRetry = (attempt = 1, maxAttempts = 10) => {
          console.log(`🔄 Loading attempt ${attempt}/${maxAttempts}`);
          
          if (window.loadEditorContentFromDatabase && typeof window.loadEditorContentFromDatabase === 'function') {
            try {
              const success = window.loadEditorContentFromDatabase();
              if (success !== false) {
                console.log('✅ Content loaded successfully on attempt', attempt);
                return;
              }
            } catch (error) {
              console.warn(`⚠️ Error on attempt ${attempt}:`, error);
            }
          }
          
          // If not successful and we have more attempts, retry
          if (attempt < maxAttempts) {
            setTimeout(() => {
              loadWithRetry(attempt + 1, maxAttempts);
            }, 300 * attempt); // Increasing delay
          } else {
            console.error('❌ Failed to load content after maximum attempts');
            // Try manual loader as final fallback
            if (window.manualLoadContent) {
              console.log('🔄 Trying manual loader as final fallback...');
              window.manualLoadContent();
            }
          }
        };
        
        // Start loading after a delay
        setTimeout(() => {
          loadWithRetry();
        }, 500);
      } else {
        console.log('❌ No entered paper content found in database');
        console.log('Available data keys:', Object.keys(data));
      }
      

      // Set form data
      paperTemplate.value.citationStyle = data.citation_style || '';
      paperTemplate.value.dialect = data.dialect || 'US';
      paperTemplate.value.readingLevel = data.reading_level || 'college';
      customWordCount.value = data.word_count || 1000;

      // Parse selected_references back to complete reference set
      console.log('📚 LOADING DEBUG: data.selected_references:', data.selected_references);
      console.log('📚 LOADING DEBUG: data.selected_references.length:', data.selected_references?.length);
      if (data.selected_references && data.selected_references.length > 0) {
        const parsedReferences = data.selected_references.map((refString) => {
          try {
            // Try to parse as JSON first (new format)
            return JSON.parse(refString);
          } catch (e) {
            // Fallback to old string parsing format for backward compatibility
            const parts = refString.split('. "');
            if (parts.length >= 2) {
              const authors = parts[0]?.trim() || '';
              const rest = parts[1];
              const titleAndRest = rest?.split('". ') || ['', ''];
              const title = titleAndRest[0]?.trim() || '';
              const publisherYear = titleAndRest[1] || '';
              const publisherYearParts = publisherYear.split(', ');
              const publisher = publisherYearParts[0]?.trim() || '';
              const year = publisherYearParts[1]?.trim() || '';

              return {
                reference_id: `ref-${Math.random().toString(36).substr(2, 9)}`,
                AuthorName: authors,
                TitleName: title,
                Publisher: publisher,
                Year: year,
                Abstract: '', // Not available in the string format
              };
            }
            return null;
          }
        }).filter(ref => ref !== null);

        references.value = parsedReferences;
        selectedReferences.value = []; // Start with NO references selected - user must select them
      } else {
        references.value = [];
        selectedReferences.value = [];
      }
    }

    console.log('Paper data fetched successfully:', data);
  } catch (error) {
    console.error('Error fetching paper data:', error);
  } finally {
    loading.value = false;
  }
};

const fetchEconomicsData = async (sessionId, user_id) => {
  try {
    loading.value = true;
    console.log('🔍 FETCHING ECONOMICS DATA');
    console.log('📋 Eco ID (sessionId):', sessionId);
    console.log('👤 User ID:', user_id);
    console.log('🌐 Mode:', selectedMode.value);

    const url = `${backend_url}/eco-docs/${sessionId}`;
    
    console.log('🔗 Full fetch URL:', url);
    console.log('📊 Expected: Economics document data with history and latest_content');

    const ecoResponse = await fetch(url, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json'
      }
    });

    console.log('Response status:', ecoResponse.status);
    console.log('Response ok:', ecoResponse.ok);

    if (!ecoResponse.ok) {
      if (ecoResponse.status === 404) {
        console.log('ℹ️ No existing economics document found - this is normal for new documents');
        
        // For 404 (new documents), generate concept suggestions if we have an article
        if (['microeconomics', 'macroeconomics', 'globaleconomics'].includes(selectedMode.value)) {
          const queryArticle = getArticleFromQueryParams();
          if (queryArticle && queryArticle.trim()) {
            ibEconomics.value.article = queryArticle;
            console.log('🔄 New document (404): Auto-generating concept suggestions...');
            setTimeout(() => {
              getEconomicsSuggestions();
            }, 500); // Small delay to ensure UI is ready
          }
        }
        return; // Don't treat 404 as an error for new documents
      }
      const errorText = await ecoResponse.text();
      console.error('Error response body:', errorText);
      throw new Error(`HTTP error! status: ${ecoResponse.status}, body: ${errorText}`);
    }

    const responseData = await ecoResponse.json();
    // Handle both direct response and nested doc structure
    const data = responseData?.doc || responseData;
    
    console.log('📥 RAW RESPONSE DATA:', responseData);
    console.log('📄 EXTRACTED DOC DATA:', data);
    console.log('🔍 SECURITY CHECK - Response user_id:', data?.user_id);
    console.log('🔍 SECURITY CHECK - Requested user_id:', user_id);
    console.log('🔍 SECURITY CHECK - Match?', data?.user_id === user_id);

    if (data) {
      // SECURITY CHECK: Ensure the returned data belongs to the requesting user
      if (data.user_id && data.user_id !== user_id) {
        console.error('🚨 SECURITY VIOLATION: Document user_id mismatch!');
        console.error('🚨 Document belongs to user:', data.user_id);
        console.error('🚨 Current user:', user_id);
        console.error('🚨 This should not happen - backend security issue!');
        console.log('🚫 Not generating concept suggestions due to security violation');
        return; // Don't process data that doesn't belong to this user
      }
      
      console.log('✅ Security check passed - user_id matches');
      processEconomicsData(data);
    } else {
      console.log('ℹ️ No economics document data found - this is normal for new documents');
      
      // Only generate concept suggestions for truly new documents (not security violations)
      // This should only run when data is null/undefined (true 404), not when security check failed
      if (['microeconomics', 'macroeconomics', 'globaleconomics'].includes(selectedMode.value)) {
        const queryArticle = getArticleFromQueryParams();
        if (queryArticle && queryArticle.trim()) {
          ibEconomics.value.article = queryArticle;
          console.log('🔄 New document: Auto-generating concept suggestions...');
          setTimeout(() => {
            getEconomicsSuggestions();
          }, 500); // Small delay to ensure UI is ready
        }
      }
    }

  } catch (error) {
    console.error('Error fetching economics data:', error);
    console.log('🚫 Not generating concept suggestions due to fetch error');
  } finally {
    loading.value = false;
    
    // FINAL FALLBACK: Ensure we ALWAYS have concept suggestions for economics modes
    // This runs after all database/error handling is complete
    setTimeout(() => {
      if (['microeconomics', 'macroeconomics', 'globaleconomics'].includes(selectedMode.value)) {
        const hasExistingSuggestions = ibEconomics.value.suggestions && ibEconomics.value.suggestions.length > 0;
        const hasArticle = ibEconomics.value.article && ibEconomics.value.article.trim();
        
        if (!hasExistingSuggestions && hasArticle) {
          console.log('🔄 FINAL FALLBACK: No concept suggestions found anywhere - generating now...');
          getEconomicsSuggestions();
        } else if (hasExistingSuggestions) {
          console.log('✅ FINAL CHECK: Concept suggestions already loaded:', ibEconomics.value.suggestions.length, 'concepts');
        } else {
          console.log('⚠️ FINAL CHECK: No article available for concept generation');
        }
      }
    }, 1000); // Wait for all other processes to complete
  }
};

const processEconomicsData = (data) => {
  console.log('Processing economics data:', data);
  
  // REVERT TO ORIGINAL WORKING STRUCTURE
  
  // Handle main editor content - DON'T use article field for editor content
  // The article field is for left sidebar display, not main editor content
  console.log('Processing economics data - article field is for left sidebar only');
  
  // Handle article content for left sidebar
  if (data.article) {
    ibEconomics.value.article = data.article;
    console.log('✅ Article loaded from database:', data.article.substring(0, 100) + '...');
  }
  
  // Handle concept suggestions from progress_data or latest_content
  if (data.progress_data?.concept_suggestions) {
    ibEconomics.value.suggestions = data.progress_data.concept_suggestions;
    ibEconomics.value.conceptSuggestions = data.progress_data.concept_suggestions;
    console.log('✅ Concept suggestions loaded from progress_data:', data.progress_data.concept_suggestions);
  } else if (data.latest_content?.analysis?.economic_issues) {
    const suggestions = data.latest_content.analysis.economic_issues;
    ibEconomics.value.suggestions = suggestions;
    ibEconomics.value.conceptSuggestions = suggestions;
    console.log('✅ Concept suggestions loaded from latest_content.analysis:', suggestions);
  }
  
  // Handle generated outline from progress_data or latest_content
  if (data.progress_data?.generated_outline) {
    ibEconomics.value.outline = data.progress_data.generated_outline;
    console.log('✅ Generated outline loaded from progress_data');
  } else if (data.latest_content?.generate_outline?.outline) {
    ibEconomics.value.outline = data.latest_content.generate_outline.outline;
    console.log('✅ Generated outline loaded from latest_content');
  }
    
  // Handle main editor content for economics - load saved editor content if exists
  let editorContent = '';
  if (data.progress_data?.editor_content) {
    editorContent = data.progress_data.editor_content;
    console.log('✅ Editor content loaded from progress_data');
  } else if (data.latest_content?.progress?.editor_content) {
    editorContent = data.latest_content.progress.editor_content;
    console.log('✅ Editor content loaded from latest_content.progress');
  } else if (data.latest_content?.generate_outline?.outline) {
    // If no specific editor content, use the outline as starting content
    const outline = data.latest_content.generate_outline.outline;
    editorContent = `
      <h2>Introduction</h2>
      <p>${outline.introduction || ''}</p>
      
      <h2>Key Points</h2>
      ${outline.key_points?.map(point => `<p>• ${point}</p>`).join('') || ''}
      
      <h2>Conclusion</h2>
      <p>${outline.conclusion || ''}</p>
    `;
    console.log('✅ Using outline as editor content');
  }
  
  if (editorContent) {
    window.editorContentFromDatabase = editorContent;
    console.log('Economics editor content set in cache, length:', editorContent.length);
    
    // Load content into editor with retry mechanism
    const loadWithRetry = (attempt = 1, maxAttempts = 10) => {
      console.log(`🔄 Loading attempt ${attempt}/${maxAttempts}`);
      
      if (window.loadEditorContentFromDatabase && typeof window.loadEditorContentFromDatabase === 'function') {
        try {
          const success = window.loadEditorContentFromDatabase();
          if (success !== false) {
            console.log('✅ Content loaded successfully on attempt', attempt);
            return;
          }
        } catch (error) {
          console.warn(`⚠️ Error on attempt ${attempt}:`, error);
        }
      }
      
      // If not successful and we have more attempts, retry
      if (attempt < maxAttempts) {
        setTimeout(() => {
          loadWithRetry(attempt + 1, maxAttempts);
        }, 300 * attempt); // Increasing delay
      } else {
        console.error('❌ Failed to load content after maximum attempts');
      }
    };
    
    // Start loading after a delay
    setTimeout(() => {
      loadWithRetry();
    }, 500);
  } else {
    console.log('ℹ️ No saved editor content found for economics template');
  }
  
  // Handle progress data from latest_content
  if (data.latest_content && data.latest_content.progress) {
    const progressData = data.latest_content.progress;
    
    // NEW: Handle Complete IA data from Railway API
    if (progressData.complete_ia) {
      economicsCompleteIA.value = progressData.complete_ia;
      console.log('✅ Complete IA loaded from database');
      
      // Rebuild collapsible sections from saved Complete IA
      economicsIASections.value = buildEconomicsIASections(progressData.complete_ia);
      console.log('✅ Complete IA sections rebuilt:', economicsIASections.value.length, 'sections');
    }
    
    // Handle Railway API query parameters for reconstruction
    if (progressData.article_title) {
      ibEconomics.value.articleTitle = progressData.article_title;
      console.log('✅ Article title from progress_data:', progressData.article_title);
    }
    
    if (progressData.article_url) {
      ibEconomics.value.articleUrl = progressData.article_url;
      console.log('✅ Article URL from progress_data:', progressData.article_url);
    }
    
    if (progressData.article_date) {
      ibEconomics.value.articleDate = progressData.article_date;
      console.log('✅ Article date from progress_data:', progressData.article_date);
    }
    
    if (progressData.student_name) {
      ibEconomics.value.studentName = progressData.student_name;
      console.log('✅ Student name from progress_data:', progressData.student_name);
    }
    
    if (progressData.school_name) {
      ibEconomics.value.schoolName = progressData.school_name;
      console.log('✅ School name from progress_data:', progressData.school_name);
    }

    // Handle left sidebar concept suggestions - load from database if they exist
    if (progressData.concept_suggestions && Array.isArray(progressData.concept_suggestions) && progressData.concept_suggestions.length > 0) {
      ibEconomics.value.conceptSuggestions = progressData.concept_suggestions;
      ibEconomics.value.suggestions = progressData.concept_suggestions;
      console.log('✅ Concept suggestions loaded from database:', progressData.concept_suggestions.length, 'concepts');
    }
  }

  // Check for existing concept suggestions in history data structure
  let hasExistingSuggestions = false;
  if (data.history && Array.isArray(data.history)) {
    // Look through history for saved concept suggestions
    for (const historyItem of data.history) {
      if (historyItem.request_payload && 
          historyItem.request_payload.progress_data && 
          historyItem.request_payload.progress_data.concept_suggestions &&
          Array.isArray(historyItem.request_payload.progress_data.concept_suggestions) &&
          historyItem.request_payload.progress_data.concept_suggestions.length > 0) {
        
        // Load the existing suggestions
        ibEconomics.value.conceptSuggestions = historyItem.request_payload.progress_data.concept_suggestions;
        ibEconomics.value.suggestions = historyItem.request_payload.progress_data.concept_suggestions;
        hasExistingSuggestions = true;
        console.log('✅ Concept suggestions loaded from history:', historyItem.request_payload.progress_data.concept_suggestions.length, 'concepts');
        break; // Use the first found suggestions
      }
    }
  }

  // Only generate new suggestions if none exist and we have an article
  if (!hasExistingSuggestions && 
      (!ibEconomics.value.suggestions || ibEconomics.value.suggestions.length === 0) &&
      ibEconomics.value.article && ibEconomics.value.article.trim() && 
      ['microeconomics', 'macroeconomics', 'globaleconomics'].includes(selectedMode.value)) {
    console.log('ℹ️ No concept suggestions found - generating now...');
    console.log('🔄 Auto-generating concept suggestions for economics template...');
    setTimeout(() => {
      getEconomicsSuggestions();
    }, 500); // Small delay to ensure UI is ready
  }
    
  // Handle right sidebar generated outline from progress data
  if (data.latest_content && data.latest_content.progress && data.latest_content.progress.generated_outline) {
    ibEconomics.value.outline = data.latest_content.progress.generated_outline;
    console.log('✅ Generated outline loaded from database');
  }
  
  // Handle article text in left sidebar - only use database article if it's meaningful content
  if (data.article && data.article.trim() && !data.article.includes('<p style="line-height: 1.5"></p>')) {
    ibEconomics.value.article = data.article;
    console.log('✅ Article text loaded from database in left sidebar');
  } else {
    // If database article is empty/default, use the article from query params
    const queryArticle = getArticleFromQueryParams();
    if (queryArticle && queryArticle.trim()) {
      ibEconomics.value.article = queryArticle;
      console.log('✅ Article text loaded from query params in left sidebar');
    }
  }

  console.log('Economics data processed successfully');
};

const fetchTokJournalData = async (sessionId, user_id) => {
  try {
    // loading.value is already true from onMounted, keep it visible
    console.log('Fetching TOK journal data...');

    const url = new URL(`${backend_url}/api/retrieve-specific-tok-journal`);
    url.searchParams.append('document_id', sessionId);
    url.searchParams.append('user_id', user_id);

    const journalResponse = await fetch(url.toString(), {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': '' // Add your API key here if needed
      }
    });

    if (!journalResponse.ok) {
      throw new Error(`HTTP error! status: ${journalResponse.status}`);
    }

    const responseData = await journalResponse.json();
    const data = responseData?.document;

    if (data) {
      console.log('TOK Journal data received:', data);
      
      // Set generated journal content
      if (data.generated_journal) {
        parseEssayContent(data.generated_journal);
      }

      // Set references if available
      if (data.references) {
        try {
          const parsedReferences = JSON.parse(data.references);
          references.value = parsedReferences;
          selectedReferences.value = []; // Start with NO references selected - user must select them
        } catch (e) {
          console.error('Error parsing references:', e);
        }
      }

      // Set form data
      tokJournal.value.title = data.title || '';
      tokJournal.value.instructions = data.instructions || '';
      tokJournal.value.citationStyle = data.citation_style || '';
      customWordCount.value = data.num_words || 350;
      
      // Set entered content in editor - use database content directly
      if (data.entered_content) {
        // Store content in memory for editor initialization
        window.editorContentFromDatabase = data.entered_content;
        console.log('✅ Database content loaded for TOK journal, length:', data.entered_content.length);
        
        // Load content into editor with improved retry mechanism
        const loadWithRetry = (attempt = 1, maxAttempts = 10) => {
          console.log(`🔄 Loading attempt ${attempt}/${maxAttempts}`);
          
          if (window.loadEditorContentFromDatabase && typeof window.loadEditorContentFromDatabase === 'function') {
            try {
              const success = window.loadEditorContentFromDatabase();
              if (success !== false) {
                console.log('✅ Content loaded successfully on attempt', attempt);
                return;
              }
            } catch (error) {
              console.warn(`⚠️ Error on attempt ${attempt}:`, error);
            }
          }
          
          // If not successful and we have more attempts, retry
          if (attempt < maxAttempts) {
            setTimeout(() => {
              loadWithRetry(attempt + 1, maxAttempts);
            }, 300 * attempt); // Increasing delay
          } else {
            console.error('❌ Failed to load content after maximum attempts');
            // Try manual loader as final fallback
            if (window.manualLoadContent) {
              console.log('🔄 Trying manual loader as final fallback...');
              window.manualLoadContent();
            }
          }
        };
        
        // Start loading after a delay
        setTimeout(() => {
          loadWithRetry();
        }, 500);
      }
      
    }

    console.log('TOK Journal data fetched successfully:', data);
  } catch (error) {
    console.error('Error fetching TOK journal data:', error);
  } finally {
    loading.value = false;
  }
};

// Comprehensive TOK fetch function that handles all TOK template types
const fetchTokData = async (sessionId, user_id) => {
  console.log('🚀 fetchTokData called for TOK templates')
  console.log('- Session ID:', sessionId)
  console.log('- User ID:', user_id) 
  console.log('- Mode:', selectedMode.value)
  
  if (!sessionId || !user_id) {
    console.warn('❌ Missing required parameters for TOK fetch')
    return
  }

  try {
    // Handle TOK Exhibition specifically
    if (selectedMode.value === 'tok-exhibition') {
      console.log('📡 Fetching TOK Exhibition data from correct API endpoint')
      
      const response = await fetch(`https://jfv6blghbfv5lr3wt6sho4kewe0mrifm.lambda-url.us-east-1.on.aws/tok-draft/${sessionId}`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        }
      });

      if (response.ok) {
        const data = await response.json();
        console.log('✅ TOK Exhibition data loaded successfully');

        // Extract payload robustly across possible shapes
        // Supported shapes: { data: {...} } | { payload: {...} } | flat
        const root = data || {};
        const tokData = root.data || root.payload?.data || root.payload || root.document?.data || root;

        // Restore TOK Exhibition state
        if (tokData.selected_prompt) tokExhibition.value.selectedPrompt = tokData.selected_prompt;
        if (tokData.selected_prompt_number) tokExhibition.value.selectedPromptNumber = tokData.selected_prompt_number;
        // Map prompts from multiple possible keys
        const dbPrompts = tokData.available_prompts || tokData.prompts || tokData.prompt_list || tokData.availablePrompts;
        if (Array.isArray(dbPrompts) && dbPrompts.length > 0) {
          tokExhibition.value.availablePrompts = dbPrompts;
          window.tokExhibitionPromptsLoadedFromDB = true;
          console.log('✅ Prompts loaded from database, count:', dbPrompts.length);
        }
        
        if (tokData.selected_objects) tokExhibition.value.selectedObjects = tokData.selected_objects;
        if (tokData.suggested_objects) tokExhibition.value.suggestedObjects = tokData.suggested_objects;
        
        if (tokData.exhibition_references) tokExhibition.value.exhibitionReferences = tokData.exhibition_references;
        if (tokData.selected_exhibition_references) tokExhibition.value.selectedExhibitionReferences = tokData.selected_exhibition_references;
        if (tokData.citation_format) tokExhibition.value.citationFormat = tokData.citation_format;
        
        if (tokData.current_step) tokExhibition.value.currentStep = tokData.current_step;
        
        // Restore generated content
        if (tokData.generated_essay) {
          parseEssayContent(tokData.generated_essay);
        }
        
        // Restore entered content to editor (support multiple keys)
        const entered = tokData.entered_content || tokData.entered_essay || tokData.content || tokData.mainContent;
        if (entered) {
          window.editorContentFromDatabase = entered;
          console.log('📝 TOK Exhibition content set in cache, length:', entered.length);
          
          // Load content into editor with retry mechanism (same as essay/paper templates)
          const loadWithRetry = (attempt = 1, maxAttempts = 10) => {
            console.log(`🔄 Loading attempt ${attempt}/${maxAttempts}`);
            
            if (window.loadEditorContentFromDatabase && typeof window.loadEditorContentFromDatabase === 'function') {
              try {
                const success = window.loadEditorContentFromDatabase();
                if (success !== false) {
                  console.log('✅ Content loaded successfully on attempt', attempt);
                  return;
                }
              } catch (error) {
                console.warn(`⚠️ Error on attempt ${attempt}:`, error);
              }
            }
            
            // If not successful and we have more attempts, retry
            if (attempt < maxAttempts) {
              setTimeout(() => {
                loadWithRetry(attempt + 1, maxAttempts);
              }, 300 * attempt); // Increasing delay
            } else {
              console.error('❌ Failed to load content after maximum attempts');
              // Try manual loader as final fallback
              if (window.manualLoadContent) {
                console.log('🔄 Trying manual loader as final fallback...');
                window.manualLoadContent();
              }
            }
          };
          
          // Start loading after a delay
          setTimeout(() => {
            loadWithRetry();
          }, 500);
        }

        // Check if we need to fetch prompts
        setTimeout(() => {
          const hasPrompts = (tokExhibition.value.availablePrompts && tokExhibition.value.availablePrompts.length > 0) || window.tokExhibitionPromptsLoadedFromDB;
          if (!hasPrompts) {
            console.log('📝 No prompts found in saved data, fetching from API');
            fetchTokExhibitionPrompts();
          } else {
            console.log('✅ Prompts loaded from database, skipping API call. Count:', tokExhibition.value.availablePrompts.length);
          }
        }, 100);

        console.log('✅ TOK Exhibition document loaded and restored');
        return data;
      } else if (response.status === 404) {
        console.log('ℹ️ No existing TOK Exhibition document found, starting fresh');
        // Fetch prompts for new document
        setTimeout(() => {
          console.log('📝 New document - fetching prompts from API');
          fetchTokExhibitionPrompts();
        }, 100);
      } else {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
    } else if (selectedMode.value === 'tok-essay') {
      // Handle TOK Essay using unified endpoint and essay-like mapping
      console.log('📡 Fetching TOK Essay data from correct API endpoint')
      const response = await fetch(`https://jfv6blghbfv5lr3wt6sho4kewe0mrifm.lambda-url.us-east-1.on.aws/tok-draft/${sessionId}`, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' }
      });
      if (response.ok) {
        const data = await response.json();
        console.log('✅ TOK Essay data loaded successfully');
        const root = data || {};
        const tokData = root.data || root.payload?.data || root.payload || root.document?.data || root;

        // Form fields
        if (tokData.title) tokEssay.value.title = tokData.title;
        if (tokData.aok1) tokEssay.value.aok1 = tokData.aok1;
        if (tokData.aok2) tokEssay.value.aok2 = tokData.aok2;
        if (tokData.citation_style) tokEssay.value.citationStyle = tokData.citation_style;
        if (tokData.word_count) tokEssay.value.wordCount = tokData.word_count;

        // References - populate full list if provided
        if (tokData.references) {
          try {
            const parsed = Array.isArray(tokData.references) ? tokData.references : JSON.parse(tokData.references);
            references.value = parsed;
          } catch(e) { console.warn('Failed to parse tok-essay references list:', e); }
        }

        // Selected references - try to map to IDs
        if (tokData.selected_references && Array.isArray(tokData.selected_references)) {
          const selectedIds = [];
          tokData.selected_references.forEach((item) => {
            try {
              const obj = typeof item === 'string' ? JSON.parse(item) : item;
              const id = obj.reference_id || obj.id || obj._id || obj.TitleName;
              if (id) selectedIds.push(id);
            } catch(err) {
              // If not JSON, push raw string id
              selectedIds.push(item);
            }
          });
          selectedReferences.value = selectedIds;
        }

        // Generated outline and essay
        if (tokData.generated_outline) {
          outlineData.value = tokData.generated_outline;
        }
        if (tokData.generated_essay) {
          parseEssayContent(tokData.generated_essay);
        }

        // Editor content
        const entered = tokData.entered_content || tokData.entered_essay || tokData.content || tokData.mainContent;
        if (entered) {
          window.editorContentFromDatabase = entered;
          const loadWithRetry = (attempt = 1, max = 10) => {
            if (window.loadEditorContentFromDatabase) {
              try {
                const ok = window.loadEditorContentFromDatabase();
                if (ok !== false) return;
              } catch {}
            }
            if (attempt < max) setTimeout(() => loadWithRetry(attempt + 1, max), 300 * attempt);
          };
          setTimeout(() => loadWithRetry(), 500);
        }

        console.log('✅ TOK Essay document loaded and restored');
        return data;
      } else if (response.status === 404) {
        console.log('ℹ️ No existing TOK Essay document found, starting fresh');
      } else {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
    } else if (selectedMode.value === 'tok') {
      // Handle TOK Journal using unified endpoint and essay-like mapping
      console.log('📡 Fetching TOK Journal data from correct API endpoint')
      const response = await fetch(`https://jfv6blghbfv5lr3wt6sho4kewe0mrifm.lambda-url.us-east-1.on.aws/tok-draft/${sessionId}`, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' }
      });
      if (response.ok) {
        const data = await response.json();
        console.log('✅ TOK Journal data loaded successfully');
        const root = data || {};
        const tokData = root.data || root.payload?.data || root.payload || root.document?.data || root;

        // Left sidebar fields
        if (tokData.title) tokJournal.value.title = tokData.title;
        if (tokData.instructions) tokJournal.value.instructions = tokData.instructions;
        if (tokData.citation_style) tokJournal.value.citationStyle = tokData.citation_style;
        if (tokData.word_count) customWordCount.value = tokData.word_count;

        // References full list
        if (tokData.references) {
          try {
            const parsed = Array.isArray(tokData.references) ? tokData.references : JSON.parse(tokData.references);
            references.value = parsed;
          } catch(e) { console.warn('Failed to parse tok-journal references list:', e); }
        }

        // Generated outline and journal
        if (tokData.generated_outline) {
          outlineData.value = tokData.generated_outline;
        }
        if (tokData.generated_journal) {
          parseEssayContent(tokData.generated_journal);
        }

        // Editor content
        const entered = tokData.entered_content || tokData.entered_essay || tokData.content || tokData.mainContent;
        if (entered) {
          window.editorContentFromDatabase = entered;
          const loadWithRetry = (attempt = 1, max = 10) => {
            if (window.loadEditorContentFromDatabase) {
              try {
                const ok = window.loadEditorContentFromDatabase();
                if (ok !== false) return;
              } catch {}
            }
            if (attempt < max) setTimeout(() => loadWithRetry(attempt + 1, max), 300 * attempt);
          };
          setTimeout(() => loadWithRetry(), 500);
        }

        console.log('✅ TOK Journal document loaded and restored');
        return data;
      } else if (response.status === 404) {
        console.log('ℹ️ No existing TOK Journal document found, starting fresh');
      } else {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
    } else {
      // Handle other TOK modes with existing logic
      if (typeof window.retrieveTokProgress === 'function') {
        console.log('📡 Using retrieveTokProgress from bubble component')
        const result = await window.retrieveTokProgress()
        if (result) {
          console.log('✅ TOK data retrieved successfully:', result)
          return result
        } else {
          console.log('ℹ️ No existing TOK data found to retrieve')
        }
      } else {
        console.warn('⚠️ retrieveTokProgress function not available from bubble component')
      }
    }
    
  } catch (error) {
    console.error('❌ Error fetching TOK data:', error)
    
    // Don't throw the error - just log it and continue
    // This allows the app to function even if no saved data exists
    console.log('ℹ️ Continuing without fetched TOK data (new document)')
  } finally {
    loading.value = false
    console.log('✅ TOK data fetch process completed')
  }
}

// Perform initial mode setup before fetching data
async function initializeMode() {
  try {
    // Initialize economics data from query parameters if in economics mode
    if (['microeconomics', 'macroeconomics', 'globaleconomics'].includes(selectedMode.value)) {
      const economicsUnitMap = {
        'microeconomics': 'microeconomics',
        'macroeconomics': 'macroeconomics',
        'globaleconomics': 'global_economy'
      };
      ibEconomics.value.economicsUnit = economicsUnitMap[selectedMode.value];
      ibEconomics.value.article = getArticleFromQueryParams();
      if (ibEconomics.value.article && ibEconomics.value.article.trim()) {
        console.log('Economics article preset from URL');
      }
    }

    // Initialize document service with the detected mode
    const serviceMode = selectedMode.value === 'paper-template' ? 'paper' : selectedMode.value;
    documentService.setMode(serviceMode);
    documentService.init();

    // Set default right tab and TOK Exhibition handling
    if (selectedMode.value === 'tok-exhibition') {
      activeRightTab.value = 'essay';
      console.log('TOK Exhibition: initialized. Data will be loaded via fetchSavedData -> fetchTokData');
      // Important: Do NOT fetch prompts here. They will be restored from DB in fetchTokData,
      // and only fetched if not present.
    } else if (['microeconomics', 'macroeconomics', 'globaleconomics'].includes(selectedMode.value)) {
      activeRightTab.value = 'toc';
    }
  } catch (e) {
    console.error('initializeMode failed:', e);
  }
}

// Initialize component and fetch data
onMounted(async () => {
  try {
    // FIRST: Initialize mode and setup
    await initializeMode();
    
    // THEN: Fetch saved data for all supported modes
    await fetchSavedData();
    
    // Note: Concept suggestions generation moved to processEconomicsData 
    // to ensure database has been checked first
    
    // Set up auto-save event listeners
    setupAutoSaveEventListeners();
  } catch (error) {
    console.error('Error during component initialization:', error);
  }
});

// Cleanup when component unmounts
onBeforeUnmount(() => {
  console.log('Component unmounting - no auto-save intervals to clean up');
});

// Economics IA API Functions
const API_BASE_URL = 'https://jfv6blghbfv5lr3wt6sho4kewe0mrifm.lambda-url.us-east-1.on.aws'

// Get Concept Suggestions
async function suggestConcepts() {
  if (!economics.value.article || !economics.value.unit) {
    alert('Please provide both article text and select an economics unit.')
    return
  }
  
  economics.value.loading = true
  economics.value.error = null
  
  try {
    const payload = {
      article: economics.value.article,
      economics_unit: economics.value.unit
    }
    
    const response = await fetch(`${API_BASE_URL}/suggest-concepts`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload)
    })
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    
    const data = await response.json()
    
    if (data.success && data.suggested_concepts) {
      economics.value.suggestedConcepts = data.suggested_concepts
      economics.value.currentStep = 2
      // Switch to outline tab in right sidebar
      activeRightTab.value = 'outline'
    } else {
      throw new Error(data.message || 'Failed to get concept suggestions')
    }
    
  } catch (error) {
    console.error('Error getting concept suggestions:', error)
    economics.value.error = error.message
    alert('Failed to get concept suggestions. Please try again.')
  } finally {
    economics.value.loading = false
  }
}

// Generate Economics Outline
// async function generateEconomicsOutline() {
//   if (!economics.value.selectedConcept) {
//     alert('Please select a concept first.')
//     return
//   }
  
//   economics.value.loading = true
//   economics.value.error = null
  
//   try {
//     const endpoint = `${API_BASE_URL}/${economics.value.unit}/generate-outline`
    
//     const payload = {
//       article: economics.value.article,
//       economics_unit: economics.value.unit,
//       key_concept: economics.value.selectedConcept,
//       citation_style: economics.value.citationStyle
//     }
    
//     const response = await fetch(endpoint, {
//       method: 'POST',
//       headers: {
//         'Content-Type': 'application/json',
//       },
//       body: JSON.stringify(payload)
//     })
    
//     if (!response.ok) {
//       throw new Error(`HTTP error! status: ${response.status}`)
//     }
    
//     const data = await response.json()
    
//     if (data.success && data.outline) {
//       economics.value.outline = data.outline
//       economics.value.currentStep = 3
//     } else {
//       throw new Error(data.message || 'Failed to generate outline')
//     }
    
//   } catch (error) {
//     console.error('Error generating outline:', error)
//     economics.value.error = error.message
//     alert('Failed to generate outline. Please try again.')
//   } finally {
//     economics.value.loading = false
//   }
// }

// Generate Full Commentary
async function generateCommentary() {
  if (!economics.value.outline) {
    alert('Please generate an outline first.')
    return
  }
  
  economics.value.loading = true
  economics.value.error = null
  
  try {
    const endpoint = `${API_BASE_URL}/${economics.value.unit}/generate-commentary`
    
    const payload = {
      article: economics.value.article,
      outline: economics.value.outline,
      economics_unit: economics.value.unit,
      key_concept: economics.value.selectedConcept,
      citation_style: economics.value.citationStyle
    }
    
    const response = await fetch(endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload)
    })
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    
    const data = await response.json()
    
    if (data.success && data.commentary) {
      economics.value.commentary = data.commentary
      
      // Insert the commentary text into the editor
      if (data.commentary.commentary_text && window.getEditorHTMLContent) {
        try {
          // Get current editor content
          const currentContent = window.getEditorHTMLContent()
          
          // Add the new commentary
          const newContent = currentContent + '<div class="economics-commentary">' + 
                           data.commentary.commentary_text + '</div>'
          
          // Set the new content in the editor
          if (window.loadEditorContentFromDatabase) {
            window.editorContentFromDatabase = newContent
            window.loadEditorContentFromDatabase()
          }
          
          // Switch to diagrams tab if available
          if (data.commentary.diagrams && data.commentary.diagrams.length > 0) {
            activeRightTab.value = 'diagrams'
          }
          
        } catch (editorError) {
          console.error('Error updating editor content:', editorError)
        }
      }
      
    } else {
      throw new Error(data.message || 'Failed to generate commentary')
    }
    
  } catch (error) {
    console.error('Error generating commentary:', error)
    economics.value.error = error.message
    alert('Failed to generate commentary. Please try again.')
  } finally {
    economics.value.loading = false
  }
}

// Reset Economics Workflow
function resetEconomicsWorkflow() {
  economics.value.currentStep = 1
  economics.value.suggestedConcepts = []
  economics.value.selectedConcept = ''
  economics.value.outline = null
  economics.value.commentary = null
  economics.value.error = null
  activeRightTab.value = 'outline'
}

// Note: Diagram rendering is now handled inline in the template for better Vue compatibility

// Global functions for enhanced save capabilities using new document service
window.saveReferences = async (references) => {
  try {
    console.log('💾 Saving references using document service...');
    await documentService.saveReferences(references);
    console.log('✅ References saved successfully');
    return true;
  } catch (error) {
    console.error('❌ Failed to save references:', error);
    return false;
  }
};

window.saveGeneratedContent = async (generatedContent) => {
  try {
    console.log('💾 Saving generated content using document service...');
    await documentService.saveGeneratedContent(generatedContent);
    console.log('✅ Generated content saved successfully');
    return true;
  } catch (error) {
    console.error('❌ Failed to save generated content:', error);
    return false;
  }
};

window.saveOutline = async (outline) => {
  try {
    console.log('💾 Saving outline using document service...');
    await documentService.saveOutline(outline);
    console.log('✅ Outline saved successfully');
    return true;
  } catch (error) {
    console.error('❌ Failed to save outline:', error);
    return false;
  }
};

window.saveAllDocumentData = async (allData) => {
  try {
    console.log('💾 Saving all document data using document service...');
    await documentService.saveAll(allData);
    console.log('✅ All document data saved successfully');
    return true;
  } catch (error) {
    console.error('❌ Failed to save all document data:', error);
    return false;
  }
};

window.loadDocumentData = async () => {
  try {
    console.log('📥 Loading document data using document service...');
    const data = await documentService.loadDocument();
    console.log('✅ Document data loaded successfully:', data);
    return data;
  } catch (error) {
    console.error('❌ Failed to load document data:', error);
    return null;
  }
};

// Function to switch document service mode
window.setDocumentServiceMode = (mode) => {
  try {
    console.log(`🔄 Switching document service mode to: ${mode}`);
    documentService.setMode(mode);
    console.log('✅ Document service mode switched successfully');
    return true;
  } catch (error) {
    console.error('❌ Failed to switch document service mode:', error);
    return false;
  }
};

// Enhanced debug function for testing new services
window.testNewDocumentService = async () => {
  console.log('🧪 Testing new document service functionality...');
  
  try {
    // Test mode detection and switching
    console.log('Current service mode:', documentService.currentMode);
    
    // Test saving content
    const testContent = '<p>Test content for document service</p>';
    await documentService.saveContent(testContent);
    console.log('✅ Save content test passed');
    
    // Test saving references
    const testRefs = ['Test Reference 1', 'Test Reference 2'];
    await documentService.saveReferences(testRefs);
    console.log('✅ Save references test passed');
    
    // Test loading document
    const loadedData = await documentService.loadDocument();
    console.log('✅ Load document test completed:', loadedData);
    
    console.log('✅ All document service tests completed');
    return true;
    
  } catch (error) {
    console.error('❌ Document service test failed:', error);
    return false;
  }
};

// Add to available debug functions
console.log('\n📋 Enhanced debug functions available:');
console.log('- window.saveReferences(references)');
console.log('- window.saveGeneratedContent(content)');
console.log('- window.saveOutline(outline)');
console.log('- window.saveAllDocumentData(data)');
console.log('- window.loadDocumentData()');
console.log('- window.setDocumentServiceMode(mode)');
console.log('- window.testNewDocumentService()');
console.log('- window.generateReturnUrl() // For main website integration');
console.log('- window.getDocumentInfo() // Get current document info');

// MAIN WEBSITE INTEGRATION FUNCTIONS
// Function to generate return URL for main website integration
window.generateReturnUrl = () => {
  const params = window.originalUrlParams || {};
  const baseUrl = window.location.origin + window.location.pathname;
  const urlParams = new URLSearchParams();
  
  if (params.selectmodule) urlParams.set('selectmodule', params.selectmodule);
  if (params.user_id) urlParams.set('user_id', params.user_id);
  if (params.document_id) {
    if (params.selectmodule === 'paper') {
      urlParams.set('paper_id', params.document_id);
    } else {
      urlParams.set('document_id', params.document_id);
    }
  }
  if (params.topic) urlParams.set('topic', params.topic);
  
  const returnUrl = `${baseUrl}?${urlParams.toString()}`;
  console.log('🔗 Generated return URL:', returnUrl);
  return returnUrl;
};

// Function to get current document info
window.getDocumentInfo = () => {
  const info = {
    mode: selectedMode.value,
    documentId: getIdFromPath(),
    userId: getUserIdFromQueryParams(),
    hasContent: !!(getEditorContent() && getEditorContent().trim()),
    contentLength: getEditorContent()?.length || 0,
    hasOutline: !!(outlineData.value && outlineData.value.trim()),
    referenceCount: references.value?.length || 0,
    lastSaved: new Date().toISOString()
  };
  console.log('📊 Document info:', info);
  return info;
};

</script>



<style scoped>

html, body, #app {

  width: 100vw;

  height: 100vh;

  min-width: 100vw;

  min-height: 100vh;

  margin: 0;

  padding: 0;

  overflow: hidden;

  background: none;

  box-sizing: border-box;

}

.editor-fullscreen {

  width: 100vw;

  height: 100vh;

  min-height: 100vh;

  min-width: 100vw;

  overflow: hidden;

  background: linear-gradient(120deg, #f8fafc 0%, #e0e7ef 100%);

  display: flex;

  flex-direction: column;

  box-sizing: border-box;

}

.editor-content-area {

  flex: 1;

  display: flex;

  height: 100vh;

  width: 100vw;

  align-items: stretch;

  justify-content: stretch;

  box-sizing: border-box;

  position: relative;

}

.sidebar {

  width: 320px;

  min-width: 260px;

  max-width: 340px;

  padding: 0 0 0 0;

  display: flex;

  flex-direction: column;

  gap: 14px;

  background: rgba(255,255,255,0.85);

  box-shadow: 0 4px 32px 0 rgba(0,0,0,0.06);

  z-index: 2;

  border-radius: 0;

  margin: 0;

  align-items: stretch;

  justify-content: flex-start;

  backdrop-filter: blur(8px);

  height: 100vh;

  box-sizing: border-box;

  transition: transform 0.3s ease-in-out;

}

.scrollable-sidebar {

  overflow-y: auto;

  scrollbar-width: thin;

  scrollbar-color: #b6c6e3 #f1f5f9;

}

.scrollable-sidebar::-webkit-scrollbar {

  width: 8px;

  background: #f1f5f9;

  border-radius: 8px;

}

.scrollable-sidebar::-webkit-scrollbar-thumb {

  background: #b6c6e3;

  border-radius: 8px;

}

.sidebar.left {

  border-right: 1.5px solid #e5e7eb;

  margin-left: 0;

}

.sidebar.left.left-hidden {

  transform: translateX(-100%);

}

.sidebar.right {

  border-left: 1.5px solid #e5e7eb;

  margin-right: 0;

}

.sidebar.right.toc-hidden {

  transform: translateX(100%);

}

.card {

  background: rgba(255,255,255,0.95);

  border-radius: 14px;

  box-shadow: 0 2px 12px 0 rgba(0,0,0,0.04);

  padding: 20px 18px;

  margin-bottom: 0;

  display: flex;

  flex-direction: column;

  gap: 12px;

  border: none;

  box-sizing: border-box;

}

.citation-card {

  margin-bottom: 0;

}

.section-title {

  font-weight: 700;

  font-size: 1.15em;

  margin-bottom: 8px;

  display: flex;

  align-items: center;

  gap: 8px;

  letter-spacing: 0.01em;

}

.references-header {

  justify-content: space-between;

  display: flex;

  align-items: center;

  width: 100%;

}

.selected-count {

  font-size: 0.95em;

  color: #888;

  font-weight: 500;

}

.icon {

  font-size: 1.3em;

  filter: drop-shadow(0 2px 4px #e0e7ef);

}

.references-card {

  flex: 0 0 auto;

  max-height: 480px;

  min-height: 220px;

  overflow: hidden;

  display: flex;

  flex-direction: column;

  background: rgba(245,248,255,0.95);

  border: 1px solid #e5e7eb;

  box-sizing: border-box;

}

.references-list {

  flex: 1 1 auto;

  overflow-y: auto;

  max-height: 400px;

  min-height: 120px;

  padding: 0;

  margin: 0;

  list-style: none;

  scrollbar-width: thin;

  scrollbar-color: #b6c6e3 #f1f5f9;

  box-sizing: border-box;

}

.references-list::-webkit-scrollbar {

  width: 7px;

  background: #f1f5f9;

  border-radius: 8px;

}

.references-list::-webkit-scrollbar-thumb {

  background: #b6c6e3;

  border-radius: 8px;

}

.reference-item {

  margin-bottom: 14px;

  padding-bottom: 10px;

  border-bottom: 1px solid #e3e8f0;

  transition: background 0.2s;

  cursor: pointer;

  display: flex;

  align-items: flex-start;

  background: #fff;

  border-radius: 10px;

  box-shadow: 0 1px 4px 0 rgba(0,0,0,0.03);

  padding: 10px 8px;

  margin-top: 8px;

  box-sizing: border-box;

}

.reference-item:hover {

  background: #f0f6ff;

}

.ref-checkbox-label {

  display: flex;

  align-items: flex-start;

  gap: 10px;

  width: 100%;

  font-size: 0.97em;

  box-sizing: border-box;

}

.ref-checkbox {

  margin-top: 3px;

  accent-color: #2563eb;

  width: 18px;

  height: 18px;

  border-radius: 4px;

  border: 1.5px solid #2563eb;

  cursor: pointer;

  flex-shrink: 0;

}

.ref-card {

  display: flex;

  flex-direction: column;

  gap: 2px;

  font-size: 0.97em;

  width: 100%;

  box-sizing: border-box;

}

.ref-title-row {

  font-size: 1em;

  font-weight: 600;

  color: #222;

  margin-bottom: 2px;

}

.ref-title {

  color: #222;

  font-size: 1em;

  font-weight: 600;

}

.ref-authors {

  font-size: 0.93em;

  color: #444;

  margin-bottom: 1px;

}

.ref-year {

  font-size: 0.93em;

  color: #888;

  margin-bottom: 2px;

}

.ref-abstract {

  font-size: 0.93em;

  color: #2563eb;

  text-decoration: underline;

  margin-top: 2px;

  cursor: pointer;

  width: fit-content;

}

.word-count-card {

  margin-top: 0;

  background: linear-gradient(120deg, #e0e7ef 0%, #f8fafc 100%);

  border: 1.5px solid #e5e7eb;

  text-align: center;

  box-shadow: 0 2px 8px 0 rgba(0,0,0,0.03);

  border-radius: 14px;

  display: flex;

  flex-direction: column;

  align-items: center;

  gap: 10px;

  box-sizing: border-box;

}

.custom-word-count-input {

  width: 100%;

  display: flex;

  flex-direction: column;

  align-items: center;

  margin-top: 8px;

  box-sizing: border-box;

}

.custom-word-count-input input {

  width: 90%;

  padding: 8px 12px;

  border-radius: 10px;

  border: 1.5px solid #cbd5e1;

  font-size: 1.08em;

  text-align: center;

  outline: none;

  transition: border 0.2s;

  background: #fff;

  box-shadow: 0 1px 4px 0 rgba(0,0,0,0.03);

  box-sizing: border-box;

}

.custom-word-count-input input:focus {

  border: 1.5px solid #2563eb;

}

/* .main-editor {

  flex: 1;

  padding: 0;

  margin: 0;

  display: flex;

  justify-content: center;

  align-items: flex-start;

  background: #fff;

  min-width: 0;

  overflow: auto;

  border-radius: 0;

  box-shadow: 0 2px 24px 0 rgba(0,0,0,0.06);

  height: 100vh;

  box-sizing: border-box;

} */
 .main-editor {
  flex: 1;                /* fill the remaining space next to sidebars */
  min-height: 0;          /* allow overflow:auto to work properly */
  overflow: auto;         /* enables scrolling inside the editor area */
  padding: 0;
  margin: 0;
  display: flex;
  justify-content: center;
  align-items: flex-start;
  background: #fff;
  box-shadow: 0 2px 24px rgba(0,0,0,0.06);
  box-sizing: border-box;
  /* REMOVE height: 100vh; */
}


 .toc-sidebar {
   padding: 0;
   gap: 0;
   background: #fff;
   box-shadow: none;
   border-left: 1.5px solid #e5e7eb;
   display: flex;
   flex-direction: column;
   align-items: stretch;
   justify-content: flex-start;
   overflow-y: auto;
 }

/* Custom scrollbar for right sidebar */
.toc-sidebar::-webkit-scrollbar {
  width: 8px;
  background: #f1f5f9;
  border-radius: 8px;
}
.toc-sidebar::-webkit-scrollbar-thumb {
  background: #b6c6e3;
  border-radius: 8px;
}

.toc-tab-header {
  display: flex;
  align-items: center;
  height: 48px;
  border-bottom: 1.5px solid #e5e7eb;
  background: #fff;
  padding: 0 16px 0 0;
  font-size: 1.08em;
  position: relative;
}

.toc-tab {
  padding: 0 18px;
  height: 100%;
  display: flex;
  align-items: center;
  color: #64748b; /* Default inactive color */
  background: #fff;
  border-radius: 8px 8px 0 0;
  font-weight: 500;
  margin-right: 8px;
  cursor: pointer; /* Add pointer cursor */
  transition: all 0.2s ease;
  border-bottom: 2.5px solid transparent; /* Inactive state has no border */
}

.toc-tab.active {
  color: #2563eb; /* Active text color */
  font-weight: 600;
  border-bottom: 2.5px solid #2563eb; /* Blue underline for active tab */
}

.toc-tab:hover {
  background: #f8fafc; /* Light hover effect */
}

.toc-tab-close {
  margin-left: auto;
  color: #64748b;
  font-size: 1.2em;
  cursor: pointer;
  padding: 2px 8px;
  border-radius: 6px;
  transition: background 0.2s;
  user-select: none;
}

.toc-tab-close:hover {
  background: #f1f5f9;
}

.toc-card-outer {

  flex: 1 1 auto;

  display: flex;

  flex-direction: column;

  align-items: stretch;

  justify-content: flex-start;

  padding: 0;

  background: #fff;

  height: 100%;

  box-sizing: border-box;

}

.toc-card-inner {

  background: #fff;

  border-radius: 0;

  box-shadow: none;

  border: none;

  padding: 18px 16px;

  min-height: 100%;

  flex: 1;

  display: flex;

  flex-direction: column;

  align-items: stretch;

  gap: 10px;

  box-sizing: border-box;

}

.toc-title {

  font-size: 1.08em;

  font-weight: 600;

  color: #222;

  margin-bottom: 8px;

}

.toc-content {
  flex: 1;
  color: #64748b;
  font-size: 1em;
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: #b6c6e3 #f1f5f9;
}

.toc-content::-webkit-scrollbar {
  width: 8px;
  background: #f1f5f9;
  border-radius: 8px;
}
.toc-content::-webkit-scrollbar-thumb {
  background: #b6c6e3;
  border-radius: 8px;
}

.minimal-sidebar {

  background: #fff !important;

  color: #111 !important;

  box-shadow: none !important;

  border-right: 1px solid #eee !important;

}

.minimal-sidebar .card {

  background: #fff !important;

  color: #111 !important;

  box-shadow: none !important;

  border: none !important;

}

.minimal-sidebar .section-title,

.minimal-sidebar .references-header,

.minimal-sidebar .selected-count {

  color: #111 !important;

  font-weight: 600;

  font-size: 1em;

}

.minimal-sidebar .ref-title,

.minimal-sidebar .ref-authors,

.minimal-sidebar .ref-year,

.minimal-sidebar .ref-abstract {

  color: #111 !important;

}

.minimal-sidebar .ref-abstract {

  text-decoration: underline;

}

.minimal-sidebar .ref-checkbox {

  accent-color: #111 !important;

}

.minimal-sidebar .custom-word-count-input input {

  background: #fff !important;

  color: #111 !important;

  border: 1px solid #bbb !important;

}

.generate-essay-btn {

  width: 90%;

  margin: 24px auto 12px auto;

  display: block;

  background: #2563eb;

  color: #fff;

  border: none;

  border-radius: 8px;

  padding: 12px 0;

  font-size: 1.08em;

  font-weight: 600;

  cursor: pointer;

  transition: background 0.2s;

}

.generate-essay-btn:hover:not(:disabled) {

  background: #174bbd;

}

.generate-essay-btn:disabled {

  background: #94a3b8;

  cursor: not-allowed;

}

.dropdown {

  width: 100%;

  padding: 8px 12px;

  border-radius: 8px;

  border: 1.5px solid #cbd5e1;

  font-size: 1em;

  background: #fff;

  cursor: pointer;

  outline: none;

  transition: border 0.2s;

}

.dropdown:focus {

  border: 1.5px solid #2563eb;

}

.loading {

  text-align: center;

  padding: 20px;

  color: #64748b;

  font-style: italic;

}

/* Enhanced Loading Styles */
.references-loading-container {
  padding: 20px;
  text-align: center;
}

.loading-spinner-container {
  margin-bottom: 24px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.loading-spinner {
  width: 40px;
  height: 40px;
  border: 3px solid #f3f3f3;
  border-top: 3px solid #007bff;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.loading-text {
  color: #64748b;
  font-size: 14px;
  font-weight: 500;
}

/* Skeleton Loader Styles */
.skeleton-loader-container {
  margin-top: 20px;
}

.skeleton-reference-card {
  background: #f8f9fa;
  border: 1px solid #e9ecef;
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 12px;
  animation: pulse 1.5s ease-in-out infinite;
}

.skeleton-title {
  height: 16px;
  background: linear-gradient(90deg, #e9ecef 25%, #f8f9fa 50%, #e9ecef 75%);
  background-size: 200% 100%;
  border-radius: 4px;
  margin-bottom: 8px;
  animation: shimmer 1.5s ease-in-out infinite;
}

.skeleton-authors {
  height: 12px;
  width: 70%;
  background: linear-gradient(90deg, #e9ecef 25%, #f8f9fa 50%, #e9ecef 75%);
  background-size: 200% 100%;
  border-radius: 4px;
  margin-bottom: 4px;
  animation: shimmer 1.5s ease-in-out infinite;
  animation-delay: 0.1s;
}

.skeleton-year {
  height: 12px;
  width: 30%;
  background: linear-gradient(90deg, #e9ecef 25%, #f8f9fa 50%, #e9ecef 75%);
  background-size: 200% 100%;
  border-radius: 4px;
  margin-bottom: 8px;
  animation: shimmer 1.5s ease-in-out infinite;
  animation-delay: 0.2s;
}

.skeleton-abstract {
  height: 12px;
  width: 85%;
  background: linear-gradient(90deg, #e9ecef 25%, #f8f9fa 50%, #e9ecef 75%);
  background-size: 200% 100%;
  border-radius: 4px;
  animation: shimmer 1.5s ease-in-out infinite;
  animation-delay: 0.3s;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.8; }
}

@keyframes shimmer {
  0% { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}

.toc-placeholder {

  color: #94a3b8;

  font-style: italic;

  text-align: center;

  padding: 20px;

  font-size: 0.9em;

}

.toc-sections {

  display: flex;

  flex-direction: column;

  gap: 8px;

}

.toc-section {
  /* Remove box styling so content stretches full width */
  background: none;
  border: none;
  box-shadow: none;
  margin: 0;
  padding: 0;
}

.toc-section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: #f8fafc;
  cursor: pointer;
  transition: background 0.2s;
  border-bottom: 1px solid #e5e7eb;
  font-weight: 600;
  border-radius: 0;
}

.toc-section-header:hover {

  background: #f1f5f9;

}

.toc-section-title {
  font-weight: 600;
  color: #374151;
  font-size: 0.95em;
  flex: 1;
  text-align: left;
}

.toc-section-arrow {
  font-size: 1.2em;
  color: #6b7280;
  transition: transform 0.2s;
  font-weight: bold;
  margin-left: 8px;
}

.toc-section-arrow.expanded {
  transform: rotate(90deg);
}

.toc-section-copy {
  margin-left: 10px;
  color: #2563eb;
  font-size: 1.1em;
  cursor: pointer;
  background: none;
  border: none;
  padding: 2px 6px;
  border-radius: 4px;
  transition: background 0.2s;
  display: flex;
  align-items: center;
  /* Move copy button to right of header, not inside content */
  position: relative;
  z-index: 2;
}
.toc-section-copy:hover {
  background: #e5e7eb;
}

.toc-section-content {
  padding: 0 0 16px 0;
  background: none;
  border: none;
  font-size: 0.97em;
  line-height: 1.6;
  color: #222;
  margin: 0;
  width: 100%;
  max-width: 100%;
  overflow-x: auto;
  word-break: break-word;
  white-space: pre-line;
}

.toc-section-content p {

  margin: 0 0 12px 0;

}

.toc-section-content p:last-child {

  margin-bottom: 0;

}

.minimal-sidebar,

.sidebar.right {

  font-family: 'Segoe UI', 'Arial', 'Helvetica Neue', Helvetica, sans-serif !important;

  font-size: 0.93em !important;

}

.left-sidebar-toggle-btn {

  position: fixed;

  left: 10px;

  top: 50%;

  transform: translateY(-50%);

  background: #2563eb;

  color: white;

  border: none;

  border-radius: 0 8px 8px 0;

  padding: 12px 8px;

  cursor: pointer;

  font-size: 1.2em;

  z-index: 1000;

  box-shadow: 0 2px 8px 0 rgba(0,0,0,0.15);

  transition: background 0.2s;

  user-select: none;

}

.left-sidebar-toggle-btn:hover {

  background: #174bbd;

}

.abstract-dialog-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 10000;
}

.abstract-dialog {
  background: white;
  border-radius: 12px;
  padding: 20px;
  max-width: 400px;
  width: 90%;
  max-height: 70vh;
  overflow-y: auto;
  box-shadow: 0 10px 25px rgba(0, 0, 0, 0.2);
}

.abstract-dialog-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid #e5e7eb;
}

.abstract-dialog-title {
  margin: 0;
  font-size: 1em;
  font-weight: 600;
  color: #111;
  font-family: 'Segoe UI', 'Arial', 'Helvetica Neue', Helvetica, sans-serif;
}

.abstract-dialog-close {
  background: none;
  border: none;
  font-size: 1.2em;
  cursor: pointer;
  color: #666;
  padding: 4px;
  border-radius: 4px;
  transition: background 0.2s;
}

.abstract-dialog-close:hover {
  background: #f3f4f6;
}

.abstract-dialog-content {
  color: #333;
  font-family: 'Segoe UI', 'Arial', 'Helvetica Neue', Helvetica, sans-serif;
  font-size: 0.9em;
  line-height: 1.5;
}

.abstract-text p {
  margin: 0;
  line-height: 1.5;
  color: #444;
  font-size: 0.9em;
}

.sidebar-toggle-btn {

  position: fixed;

  right: 10px;

  top: 50%;

  transform: translateY(-50%);

  background: #2563eb;

  color: white;

  border: none;

  border-radius: 8px 0 0 8px;

  padding: 12px 8px;

  cursor: pointer;

  font-size: 1.2em;

  z-index: 1000;

  box-shadow: 0 2px 8px 0 rgba(0,0,0,0.15);

  transition: background 0.2s;

  user-select: none;

}

.sidebar-toggle-btn:hover {

  background: #174bbd;

}

.copy-toast {
  position: fixed;
  bottom: 32px;
  left: 50%;
  transform: translateX(-50%);
  background: #2563eb;
  color: #fff;
  padding: 10px 24px;
  border-radius: 8px;
  font-size: 1em;
  font-weight: 500;
  z-index: 9999;
  box-shadow: 0 2px 8px 0 rgba(0,0,0,0.12);
  pointer-events: none;
  opacity: 0.95;
  animation: fadeInOut 1.5s;
}

@keyframes fadeInOut {
  0% { opacity: 0; }
  10% { opacity: 0.95; }
  90% { opacity: 0.95; }
  100% { opacity: 0; }
}

/* Paper Template Styles */
.sidebar-header {
  background: linear-gradient(120deg, #f0f9ff 0%, #e0f2fe 100%);
  border: 1.5px solid #0284c7;
  box-shadow: 0 2px 8px 0 rgba(2, 132, 199, 0.1);
  border-radius: 14px;
  margin-bottom: 14px;
  margin-left: 0;
  margin-right: 0;
  margin-top: 0;
}

.instruction-type-selector {
  display: flex;
  gap: 24px;
  margin-bottom: 12px;
}

.radio-option {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  font-size: 0.95em;
  color: #374151;
}

.radio-input {
  width: 16px;
  height: 16px;
  accent-color: #2563eb;
  cursor: pointer;
}

.radio-label {
  font-weight: 500;
  cursor: pointer;
}

.instruction-input {
  margin-top: 8px;
}



.pdf-preview {
  margin-top: 6px;
  padding: 6px 8px;
  background: #f0f9ff;
  border: 1px solid #0284c7;
  border-radius: 4px;
  font-size: 0.85em;
}

/* TOK Essay Styles */
.form-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 12px;
}

.field-label {
  font-size: 0.95em;
  font-weight: 500;
  color: #374151;
  margin-bottom: 4px;
}

.form-field input {
  padding: 8px 12px;
  border: 1.5px solid #cbd5e1;
  border-radius: 8px;
  font-size: 1em;
  background: #fff;
  outline: none;
  transition: border 0.2s;
}

.form-field input:focus {
  border: 1.5px solid #2563eb;
}

.form-field input::placeholder {
  color: #9ca3af;
}

/* Plagiarism Checker Styles */
.plag-checker-btn {
  padding: 10px 16px;
  background-color: #2563eb;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.95em;
  font-weight: 500;
  width: 100%;
  margin-bottom: 16px;
  transition: background-color 0.2s;
}

.plag-checker-btn:hover:not(:disabled) {
  background-color: #1d4ed8;
}

.plag-checker-btn:disabled {
  background-color: #94a3b8;
  cursor: not-allowed;
}

.plagiarism-result, .plagiarism-error {
  padding: 12px;
  border-radius: 6px;
  font-size: 0.9em;
  line-height: 1.5;
}

.plagiarism-result {
  background-color: #f0fdf4;
  border-left: 4px solid #16a34a;
  color: #166534;
}

.plagiarism-result h4 {
  margin: 0 0 8px 0;
  font-size: 1em;
  font-weight: 600;
}

.plagiarism-error {
  background-color: #fef2f2;
  border-left: 4px solid #dc2626;
  color: #991b1b;
}

.result-item {
  margin-bottom: 10px;
  padding-bottom: 10px;
  border-bottom: 1px solid #e5e7eb;
}

.result-item:last-child {
  border-bottom: none;
  margin-bottom: 0;
}

/* TOK Exhibition Styles */
.exhibition-step {
  margin-bottom: 20px;
}

.step-title {
  font-size: 1.1em;
  font-weight: 600;
  color: #2563eb;
  margin-bottom: 15px;
  padding-bottom: 8px;
  border-bottom: 2px solid #e5e7eb;
}

.selected-prompt {
  background: #f0f9ff;
  border: 1px solid #0284c7;
  border-radius: 8px;
  padding: 12px;
  margin-top: 10px;
}

.selected-prompt p {
  margin: 5px 0 0 0;
  color: #374151;
  font-size: 0.95em;
  line-height: 1.4;
}

.selected-prompt-display {
  background: #f8fafc;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 15px;
  font-size: 0.9em;
  color: #374151;
}

.objects-grid {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.object-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fff;
  border: 2px solid #e5e7eb;
  border-radius: 8px;
  padding: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.object-item:hover {
  border-color: #2563eb;
  background: #f8fafc;
}

.object-item.selected {
  border-color: #2563eb;
  background: #eff6ff;
}

.object-content {
  flex: 1;
}

.object-content h5 {
  margin: 0 0 5px 0;
  font-size: 1em;
  font-weight: 600;
  color: #1f2937;
}

.object-content p {
  margin: 0;
  font-size: 0.9em;
  color: #6b7280;
  line-height: 1.4;
}

.object-selection {
  margin-left: 10px;
}

.selection-info {
  font-size: 0.9em;
  color: #6b7280;
  margin: 10px 0;
  text-align: center;
  font-weight: 500;
}

.selected-summary {
  background: #f8fafc;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 15px;
}

.selected-summary ul {
  margin: 5px 0 0 20px;
  color: #374151;
}

.exhibition-ref {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px;
  margin-bottom: 8px;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
}

.exhibition-ref:hover {
  border-color: #2563eb;
  background: #f8fafc;
}

.exhibition-ref.selected {
  border-color: #2563eb;
  background: #eff6ff;
}

.ref-content {
  flex: 1;
}

.ref-content h6 {
  margin: 0 0 5px 0;
  font-size: 0.95em;
  font-weight: 600;
  color: #1f2937;
}

.step-navigation {
  display: flex;
  gap: 10px;
  margin-top: 20px;
  justify-content: space-between;
}

.success-message {
  background: #f0fdf4;
  border: 1px solid #16a34a;
  border-radius: 8px;
  padding: 15px;
  color: #166534;
  text-align: center;
  margin-bottom: 15px;
}

/* Process Steps */
.process-steps {
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.process-step {
  display: flex;
  align-items: flex-start;
  padding: 15px;
  border-radius: 8px;
  border: 2px solid #e5e7eb;
  background: #f8fafc;
  transition: all 0.2s;
}

.process-step.active {
  border-color: #2563eb;
  background: #eff6ff;
}

.process-step.completed {
  border-color: #16a34a;
  background: #f0fdf4;
}

.step-number {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border-radius: 50%;
  background: #e5e7eb;
  color: #6b7280;
  font-weight: 600;
  margin-right: 12px;
  flex-shrink: 0;
}

.process-step.active .step-number {
  background: #2563eb;
  color: white;
}

.process-step.completed .step-number {
  background: #16a34a;
  color: white;
}

.step-content h4 {
  margin: 0 0 5px 0;
  font-size: 1em;
  font-weight: 600;
  color: #1f2937;
}

.step-detail {
  margin: 0;
  font-size: 0.9em;
  color: #6b7280;
  line-height: 1.4;
}

.selected-objects-list ul {
  margin: 8px 0 0 16px;
  font-size: 0.85em;
}

.selected-objects-list li {
  margin-bottom: 3px;
  color: #374151;
}

/* Search functionality styles for blank template */
.search-section {
  margin-bottom: 12px;
  padding: 12px 0;
  border-bottom: 1px solid #e2e8f0;
}

.search-input-container {
  display: flex;
  gap: 10px;
  align-items: center;
}

.search-input {
  flex: 1;
  padding: 9px 12px;
  border: 1px solid #cbd5e1;
  border-radius: 4px;
  font-size: 13px;
  background: white;
  transition: all 0.2s ease;
  font-family: inherit;
}

.search-input:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.1);
}

.search-btn {
  padding: 9px 14px;
  background: #2563eb;
  color: white;
  border: none;
  border-radius: 4px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s ease;
  white-space: nowrap;
  min-width: 70px;
  height: 37px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.search-btn:hover:not(:disabled) {
  background: #1d4ed8;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.12);
}

.search-btn:active:not(:disabled) {
  transform: translateY(0.5px);
}

.search-btn:disabled {
  background: #94a3b8;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

/* TOK Essay Outline Loading Styles */
.tok-outline-loading-container {
  padding: 20px;
  text-align: center;
}

.skeleton-tok-outline-container {
  margin-top: 20px;
  text-align: left;
}

.skeleton-tok-section {
  margin-bottom: 16px;
  padding: 12px;
  background: #f8fafc;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  animation: pulse 1.5s ease-in-out infinite;
}

.skeleton-section-title {
  height: 18px;
  width: 70%;
  background: linear-gradient(90deg, #e5e7eb 25%, #f8fafc 50%, #e5e7eb 75%);
  background-size: 200% 100%;
  border-radius: 4px;
  margin-bottom: 10px;
  animation: shimmer 1.5s ease-in-out infinite;
}

.skeleton-section-content {
  height: 14px;
  width: 100%;
  background: linear-gradient(90deg, #e5e7eb 25%, #f8fafc 50%, #e5e7eb 75%);
  background-size: 200% 100%;
  border-radius: 4px;
  margin-bottom: 6px;
  animation: shimmer 1.5s ease-in-out infinite;
  animation-delay: 0.1s;
}

.skeleton-section-content.short {
  width: 80%;
  animation-delay: 0.2s;
}

/* IB Economics Template Styles */
.concept-suggestions {
  max-height: 400px;
  overflow-y: auto;
}

.concept-item {
  padding: 12px;
  margin-bottom: 8px;
  border: 2px solid #e5e7eb;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
  background: #f9fafb;
}

.concept-item:hover {
  border-color: #3b82f6;
  background: #eff6ff;
}

.concept-item.selected {
  border-color: #3b82f6;
  background: #dbeafe;
}

.concept-item.disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.concept-item.disabled:hover {
  border-color: #e5e7eb;
  background: #f9fafb;
}

.concept-name {
  font-weight: 600;
  color: #1f2937;
  margin-bottom: 4px;
  text-transform: capitalize;
}

.concept-score {
  font-size: 0.875rem;
  color: #059669;
  font-weight: 500;
  margin-bottom: 6px;
}

.concept-explanation {
  font-size: 0.875rem;
  color: #6b7280;
  line-height: 1.4;
}

.economics-outline {
  padding: 16px 0;
}

.outline-section {
  margin-bottom: 24px;
  padding: 16px;
  background: #f8fafc;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
}

.outline-section-title {
  font-size: 1rem;
  font-weight: 600;
  color: #1f2937;
  margin: 0 0 12px 0;
  border-bottom: 2px solid #3b82f6;
  padding-bottom: 4px;
}

.outline-section p {
  margin: 0;
  color: #374151;
  line-height: 1.5;
}

.terminology-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.terminology-list li {
  background: #dbeafe;
  color: #1e40af;
  padding: 4px 12px;
  border-radius: 16px;
  font-size: 0.875rem;
  font-weight: 500;
}

.diagram-item {
  margin-bottom: 16px;
  padding: 12px;
  background: #ffffff;
  border: 1px solid #d1d5db;
  border-radius: 6px;
}

.diagram-item h4 {
  margin: 0 0 8px 0;
  color: #1f2937;
  font-size: 0.875rem;
  font-weight: 600;
}

.diagram-item p {
  margin: 0;
  color: #6b7280;
  font-size: 0.875rem;
  line-height: 1.4;
}

.empty-state {
  padding: 32px 16px;
  text-align: center;
}

.empty-message {
  color: #6b7280;
}

.empty-message p {
  margin: 0 0 8px 0;
  line-height: 1.5;
}

.empty-hint {
  font-size: 0.875rem;
  color: #9ca3af;
}

.selected-count {
  font-size: 0.875rem;
  color: #059669;
  font-weight: 500;
}

.loading-state {
  padding: 20px;
  text-align: center;
}

.empty-concepts {
  padding: 16px;
  text-align: center;
  color: #6b7280;
  font-style: italic;
}

/* Economics outline specific styles */
.word-count {
  display: block;
  margin-top: 8px;
  color: #6b7280;
  font-size: 0.8rem;
  font-style: italic;
}

.analysis-item, .stakeholder-item, .evaluation-item {
  margin-bottom: 16px;
  padding: 12px;
  background-color: #f9fafb;
  border-radius: 6px;
}

.analysis-item h4, .stakeholder-item h4, .evaluation-item h4 {
  margin: 0 0 8px 0;
  font-size: 0.9rem;
  font-weight: 600;
  color: #374151;
}

.analysis-item p, .stakeholder-item p, .evaluation-item p {
  margin: 0;
  font-size: 0.85rem;
  line-height: 1.5;
  color: #4b5563;
}

.analysis-content p, .evaluation-content p {
  margin: 0;
  font-size: 0.9rem;
  line-height: 1.6;
  color: #374151;
}

/* Copy entire content button styles */
.toc-header-with-copy {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.toc-header-with-copy .toc-title {
  margin-bottom: 0;
}

.copy-all-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  background: #2563eb;
  color: white;
  border: none;
  border-radius: 6px;
  padding: 6px 12px;
  font-size: 0.85em;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  box-shadow: 0 1px 3px rgba(37, 99, 235, 0.3);
}

.copy-all-btn:hover {
  background: #1d4ed8;
  transform: translateY(-1px);
  box-shadow: 0 2px 6px rgba(37, 99, 235, 0.4);
}

.copy-all-btn:active {
  transform: translateY(0);
  box-shadow: 0 1px 3px rgba(37, 99, 235, 0.3);
}

.copy-all-btn svg {
  flex-shrink: 0;
}

</style>