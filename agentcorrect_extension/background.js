/**
 * AgentCorrect Background Script
 * Manages correction rules and applies them
 */

// Storage for corrections and rules
let corrections = [];
let rules = {};
let stats = {
  correctionsCapture: 0,
  rulesCreated: 0,
  fixesApplied: 0,
  timeSavedMinutes: 0
};

// Common phrases that always need fixing
const COMMON_FIXES = {
  "I understand your frustration": "I can help",
  "Unfortunately,": "",
  "Unfortunately": "",
  "I apologize for the inconvenience": "",
  "As per our policy": "",
  "Please bear with us": "",
  "We regret to inform you": "",
  "Thank you for your patience": "",
  "I'm sorry to hear that": "I can help with that",
  "at this time": "",
  "in order to": "to",
  "due to the fact that": "because"
};

// Initialize
chrome.runtime.onInstalled.addListener(() => {
  loadData();
  console.log('AgentCorrect: Installed and ready');
});

/**
 * Load saved data
 */
async function loadData() {
  const data = await chrome.storage.local.get(['corrections', 'rules', 'stats']);
  
  corrections = data.corrections || [];
  rules = data.rules || {};
  stats = data.stats || {
    correctionsCapture: 0,
    rulesCreated: 0,
    fixesApplied: 0,
    timeSavedMinutes: 0
  };
  
  // Initialize common fixes as rules
  for (const [original, replacement] of Object.entries(COMMON_FIXES)) {
    if (!rules[original]) {
      rules[original] = {
        replacement: replacement,
        count: 0,
        created: new Date().toISOString()
      };
    }
  }
  
  saveData();
}

/**
 * Save data
 */
async function saveData() {
  await chrome.storage.local.set({
    corrections: corrections.slice(-1000), // Keep last 1000
    rules: rules,
    stats: stats
  });
}

/**
 * Handle messages from content script
 */
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.type === 'correction') {
    handleCorrection(request.original, request.corrected);
    sendResponse({ success: true });
  } else if (request.type === 'applyCorrections') {
    const result = applyCorrections(request.text);
    sendResponse(result);
  } else if (request.type === 'getStats') {
    sendResponse(getStats());
  } else if (request.type === 'getRules') {
    sendResponse(getRules());
  } else if (request.type === 'clearData') {
    clearData();
    sendResponse({ success: true });
  }
  
  return true; // Keep message channel open
});

/**
 * Handle a new correction
 */
function handleCorrection(original, corrected) {
  // Skip minor edits
  if (Math.abs(original.length - corrected.length) < 3 && similarity(original, corrected) > 0.95) {
    return;
  }
  
  // Store correction
  corrections.push({
    original: original,
    corrected: corrected,
    timestamp: new Date().toISOString()
  });
  
  stats.correctionsCapture++;
  
  // Find patterns
  findPatterns(original, corrected);
  
  saveData();
}

/**
 * Find patterns in corrections
 */
function findPatterns(original, corrected) {
  // Check for exact replacements (short texts)
  if (original.length < 200) {
    const key = original.trim();
    if (!rules[key]) {
      rules[key] = {
        replacement: corrected,
        count: 1,
        created: new Date().toISOString()
      };
    } else if (rules[key].replacement === corrected) {
      rules[key].count++;
      
      // Create permanent rule after 3 occurrences
      if (rules[key].count === 3) {
        stats.rulesCreated++;
        console.log(`AgentCorrect: New rule created - "${key.substring(0, 50)}..." → "${corrected.substring(0, 50)}..."`);
      }
    }
  }
  
  // Check for phrase replacements
  for (const [badPhrase, goodPhrase] of Object.entries(COMMON_FIXES)) {
    if (original.includes(badPhrase) && !corrected.includes(badPhrase)) {
      if (!rules[badPhrase]) {
        rules[badPhrase] = {
          replacement: goodPhrase,
          count: 1,
          created: new Date().toISOString()
        };
      } else {
        rules[badPhrase].count++;
      }
    }
  }
  
  // Find removed sentences
  const originalSentences = original.split(/[.!?]+/);
  const correctedSentences = corrected.split(/[.!?]+/);
  
  for (const sentence of originalSentences) {
    const trimmed = sentence.trim();
    if (trimmed.length > 10 && !corrected.includes(trimmed)) {
      const removalKey = `REMOVE:${trimmed}`;
      if (!rules[removalKey]) {
        rules[removalKey] = {
          replacement: '',
          count: 1,
          created: new Date().toISOString()
        };
      } else {
        rules[removalKey].count++;
      }
    }
  }
}

/**
 * Apply corrections to text
 */
function applyCorrections(text) {
  let corrected = text;
  const appliedCorrections = [];
  
  // Try exact match first
  if (rules[text] && rules[text].count >= 3) {
    stats.fixesApplied++;
    stats.timeSavedMinutes += 2;
    saveData();
    
    return {
      corrected: rules[text].replacement,
      corrections: [`Complete text replacement (seen ${rules[text].count} times)`]
    };
  }
  
  // Apply phrase rules
  for (const [pattern, rule] of Object.entries(rules)) {
    if (rule.count >= 3) {
      if (pattern.startsWith('REMOVE:')) {
        // Removal rule
        const toRemove = pattern.substring(7);
        if (corrected.includes(toRemove)) {
          corrected = corrected.replace(toRemove, '');
          appliedCorrections.push(`Removed "${toRemove.substring(0, 30)}..."`);
          stats.fixesApplied++;
        }
      } else if (corrected.includes(pattern)) {
        // Replacement rule
        const regex = new RegExp(escapeRegex(pattern), 'g');
        corrected = corrected.replace(regex, rule.replacement);
        
        if (rule.replacement) {
          appliedCorrections.push(`"${pattern}" → "${rule.replacement}"`);
        } else {
          appliedCorrections.push(`Removed "${pattern}"`);
        }
        stats.fixesApplied++;
      }
    }
  }
  
  // Clean up double spaces
  corrected = corrected.replace(/\s+/g, ' ').trim();
  
  if (appliedCorrections.length > 0) {
    stats.timeSavedMinutes += appliedCorrections.length * 0.5;
    saveData();
  }
  
  return {
    corrected: corrected,
    corrections: appliedCorrections
  };
}

/**
 * Get statistics
 */
function getStats() {
  const activeRules = Object.entries(rules).filter(([_, rule]) => rule.count >= 3).length;
  
  return {
    correctionsCapture: stats.correctionsCapture,
    rulesCreated: activeRules,
    fixesApplied: stats.fixesApplied,
    timeSavedMinutes: Math.round(stats.timeSavedMinutes),
    timeSavedHours: (stats.timeSavedMinutes / 60).toFixed(1),
    costSaved: Math.round(stats.timeSavedMinutes * 0.42) // $25/hour
  };
}

/**
 * Get active rules
 */
function getRules() {
  return Object.entries(rules)
    .filter(([_, rule]) => rule.count >= 3)
    .map(([pattern, rule]) => ({
      pattern: pattern.substring(0, 50),
      replacement: rule.replacement ? rule.replacement.substring(0, 50) : '[removed]',
      count: rule.count,
      created: rule.created
    }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 20); // Top 20 rules
}

/**
 * Clear all data
 */
function clearData() {
  corrections = [];
  rules = {};
  stats = {
    correctionsCapture: 0,
    rulesCreated: 0,
    fixesApplied: 0,
    timeSavedMinutes: 0
  };
  
  // Re-add common fixes
  for (const [original, replacement] of Object.entries(COMMON_FIXES)) {
    rules[original] = {
      replacement: replacement,
      count: 0,
      created: new Date().toISOString()
    };
  }
  
  saveData();
}

/**
 * Calculate similarity between two strings
 */
function similarity(s1, s2) {
  const longer = s1.length > s2.length ? s1 : s2;
  const shorter = s1.length > s2.length ? s2 : s1;
  
  if (longer.length === 0) return 1.0;
  
  const editDistance = levenshteinDistance(longer, shorter);
  return (longer.length - editDistance) / longer.length;
}

/**
 * Calculate Levenshtein distance
 */
function levenshteinDistance(s1, s2) {
  const costs = [];
  
  for (let i = 0; i <= s1.length; i++) {
    let lastValue = i;
    for (let j = 0; j <= s2.length; j++) {
      if (i === 0) {
        costs[j] = j;
      } else if (j > 0) {
        let newValue = costs[j - 1];
        if (s1.charAt(i - 1) !== s2.charAt(j - 1)) {
          newValue = Math.min(Math.min(newValue, lastValue), costs[j]) + 1;
        }
        costs[j - 1] = lastValue;
        lastValue = newValue;
      }
    }
    if (i > 0) costs[s2.length] = lastValue;
  }
  
  return costs[s2.length];
}

/**
 * Escape regex special characters
 */
function escapeRegex(str) {
  return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}