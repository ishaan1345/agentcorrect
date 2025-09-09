/**
 * AgentCorrect Content Script
 * Captures edits to AI drafts and applies learned corrections
 */

(function() {
  'use strict';

  // Track text fields being monitored
  const monitoredFields = new Map();
  
  // Store corrections temporarily
  let pendingCorrections = [];
  
  // Debounce timer
  let debounceTimer = null;

  /**
   * Initialize on page load
   */
  function init() {
    console.log('AgentCorrect: Initializing...');
    
    // Find and monitor text fields
    findTextFields();
    
    // Re-scan periodically for dynamic content
    setInterval(findTextFields, 2000);
    
    // Listen for messages from background
    chrome.runtime.onMessage.addListener(handleMessage);
  }

  /**
   * Find text fields that might contain AI drafts
   */
  function findTextFields() {
    // Zendesk
    const zendeskFields = document.querySelectorAll(
      '.comment_input_wrapper textarea, ' +
      '.zd-comment-box textarea, ' +
      '[data-test-id="composer-text-area"]'
    );
    
    // Intercom
    const intercomFields = document.querySelectorAll(
      '.composer__textarea, ' +
      '.intercom-composer-textarea, ' +
      '[contenteditable="true"]'
    );
    
    // Generic support fields
    const genericFields = document.querySelectorAll(
      'textarea[name*="comment"], ' +
      'textarea[name*="message"], ' +
      'textarea[name*="reply"], ' +
      'div[contenteditable="true"][role="textbox"]'
    );
    
    const allFields = [...zendeskFields, ...intercomFields, ...genericFields];
    
    allFields.forEach(field => {
      if (!monitoredFields.has(field)) {
        monitorField(field);
      }
    });
  }

  /**
   * Monitor a text field for changes
   */
  function monitorField(field) {
    let originalValue = '';
    let aiGenerated = false;
    
    monitoredFields.set(field, { originalValue, aiGenerated });
    
    // Detect when AI populates field
    const observer = new MutationObserver((mutations) => {
      mutations.forEach(mutation => {
        if (mutation.type === 'childList' || mutation.type === 'characterData') {
          const newValue = getFieldValue(field);
          const data = monitoredFields.get(field);
          
          // Heuristic: Sudden large text = probably AI
          if (newValue.length > 50 && newValue.length > data.originalValue.length * 2) {
            data.aiGenerated = true;
            data.originalValue = newValue;
            monitoredFields.set(field, data);
            
            // Apply automatic corrections
            applyCorrections(field);
          }
        }
      });
    });
    
    observer.observe(field, {
      childList: true,
      characterData: true,
      subtree: true
    });
    
    // Track manual edits
    field.addEventListener('input', () => handleEdit(field));
    field.addEventListener('blur', () => captureCorrection(field));
  }

  /**
   * Get value from field (handles both textarea and contenteditable)
   */
  function getFieldValue(field) {
    if (field.tagName === 'TEXTAREA' || field.tagName === 'INPUT') {
      return field.value;
    } else {
      return field.innerText || field.textContent || '';
    }
  }

  /**
   * Set value in field
   */
  function setFieldValue(field, value) {
    if (field.tagName === 'TEXTAREA' || field.tagName === 'INPUT') {
      field.value = value;
      field.dispatchEvent(new Event('input', { bubbles: true }));
    } else {
      field.innerText = value;
      field.dispatchEvent(new Event('input', { bubbles: true }));
    }
  }

  /**
   * Handle manual edits
   */
  function handleEdit(field) {
    const data = monitoredFields.get(field);
    if (data && data.aiGenerated) {
      // User is editing AI draft
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => {
        data.editedValue = getFieldValue(field);
        monitoredFields.set(field, data);
      }, 500);
    }
  }

  /**
   * Capture correction when field loses focus
   */
  function captureCorrection(field) {
    const data = monitoredFields.get(field);
    
    if (data && data.aiGenerated && data.originalValue && data.editedValue) {
      if (data.originalValue !== data.editedValue) {
        // Send correction to background
        chrome.runtime.sendMessage({
          type: 'correction',
          original: data.originalValue,
          corrected: data.editedValue,
          url: window.location.href
        });
        
        // Reset
        data.aiGenerated = false;
        data.originalValue = '';
        data.editedValue = '';
        monitoredFields.set(field, data);
      }
    }
  }

  /**
   * Apply learned corrections to field
   */
  async function applyCorrections(field) {
    const originalText = getFieldValue(field);
    
    // Get corrections from background
    const response = await chrome.runtime.sendMessage({
      type: 'applyCorrections',
      text: originalText
    });
    
    if (response && response.corrected && response.corrected !== originalText) {
      setFieldValue(field, response.corrected);
      
      // Show notification
      showNotification(field, response.corrections);
      
      // Update stored value
      const data = monitoredFields.get(field);
      data.originalValue = response.corrected;
      monitoredFields.set(field, data);
    }
  }

  /**
   * Show notification about applied corrections
   */
  function showNotification(field, corrections) {
    // Remove existing notification
    const existing = document.querySelector('.agentcorrect-notification');
    if (existing) existing.remove();
    
    // Create notification
    const notification = document.createElement('div');
    notification.className = 'agentcorrect-notification';
    notification.innerHTML = `
      <div style="
        position: fixed;
        bottom: 20px;
        right: 20px;
        background: #4CAF50;
        color: white;
        padding: 12px 20px;
        border-radius: 4px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.2);
        z-index: 10000;
        font-family: system-ui, -apple-system, sans-serif;
        font-size: 14px;
        max-width: 300px;
      ">
        <strong>AgentCorrect Applied ${corrections.length} Fix${corrections.length > 1 ? 'es' : ''}:</strong>
        <ul style="margin: 5px 0 0 0; padding-left: 20px;">
          ${corrections.map(c => `<li>${c}</li>`).join('')}
        </ul>
      </div>
    `;
    
    document.body.appendChild(notification);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
      notification.remove();
    }, 5000);
  }

  /**
   * Handle messages from background
   */
  function handleMessage(request, sender, sendResponse) {
    if (request.type === 'ping') {
      sendResponse({ status: 'active' });
    }
  }

  // Initialize when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();