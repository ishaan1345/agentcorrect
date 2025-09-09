# AgentCorrect Chrome Extension

A browser extension that learns from support agents' repetitive corrections to AI-generated drafts and applies them automatically.

## The Problem
Support agents waste 2-3 hours daily fixing the same AI mistakes:
- "I understand your frustration" → "I can help" (50x/day)
- "Unfortunately" → Removed (30x/day)  
- Missing order numbers → Added manually (100x/day)

## The Solution
After an agent makes the same correction 3 times, AgentCorrect creates a rule and fixes it automatically next time.

## Installation

1. Clone this repository
2. Open Chrome → `chrome://extensions/`
3. Enable "Developer mode"
4. Click "Load unpacked"
5. Select the `agentcorrect_extension` folder

## How It Works

1. **Monitors** support platform text fields (Zendesk, Intercom, etc.)
2. **Captures** edits agents make to AI drafts
3. **Learns** patterns after 3+ identical corrections
4. **Applies** fixes automatically to future AI drafts

## ROI

- **Time saved:** 2-3 minutes per ticket
- **For 100 agents:** 5 hours/day saved
- **Annual savings:** $3.1 million

## Technical Details

- Pure JavaScript (no complex ML)
- Simple pattern matching for repetitive fixes
- All data stored locally in browser
- Works on any support platform

## License

MIT