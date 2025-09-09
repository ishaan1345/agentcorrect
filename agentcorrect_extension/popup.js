/**
 * AgentCorrect Popup Script
 */

document.addEventListener('DOMContentLoaded', () => {
  loadStats();
  loadRules();
  
  // Refresh button
  document.getElementById('refresh').addEventListener('click', () => {
    loadStats();
    loadRules();
  });
  
  // Clear data button
  document.getElementById('clear').addEventListener('click', () => {
    if (confirm('Clear all learned corrections and rules?')) {
      chrome.runtime.sendMessage({ type: 'clearData' }, () => {
        loadStats();
        loadRules();
      });
    }
  });
});

/**
 * Load statistics
 */
function loadStats() {
  chrome.runtime.sendMessage({ type: 'getStats' }, (stats) => {
    if (stats) {
      document.getElementById('corrections').textContent = stats.correctionsCapture;
      document.getElementById('rules').textContent = stats.rulesCreated;
      document.getElementById('fixes').textContent = stats.fixesApplied;
      
      // Format time saved
      if (stats.timeSavedMinutes < 60) {
        document.getElementById('time').textContent = `${stats.timeSavedMinutes} min`;
      } else {
        document.getElementById('time').textContent = `${stats.timeSavedHours} hours`;
      }
      
      document.getElementById('money').textContent = `$${stats.costSaved}`;
    }
  });
}

/**
 * Load rules
 */
function loadRules() {
  chrome.runtime.sendMessage({ type: 'getRules' }, (rules) => {
    const ruleList = document.getElementById('ruleList');
    
    if (rules && rules.length > 0) {
      ruleList.innerHTML = rules.map(rule => {
        const pattern = escapeHtml(rule.pattern);
        const replacement = rule.replacement ? escapeHtml(rule.replacement) : '[removed]';
        
        return `
          <div class="rule-item">
            "${pattern}..." → "${replacement}..."
            <span class="rule-count">${rule.count}x</span>
          </div>
        `;
      }).join('');
    } else {
      ruleList.innerHTML = '<div class="empty-state">No rules yet. Start editing AI drafts!</div>';
    }
  });
}

/**
 * Escape HTML
 */
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}