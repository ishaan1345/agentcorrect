# AgentCorrect - Stop Fixing The Same AI Mistakes

## What It Does

AgentCorrect is a Chrome extension that learns the corrections support agents make to AI-generated drafts and applies them automatically next time.

**The Problem:** Support agents waste hours daily fixing the same AI mistakes:
- "I understand your frustration" → Changed to "I can help" (50x per day)
- "Unfortunately" → Removed (30x per day)
- Missing order numbers → Added manually (100x per day)

**The Solution:** After an agent makes the same correction 3 times, AgentCorrect creates a rule and fixes it automatically next time.

## Installation

1. Clone this repository
2. Open Chrome and go to `chrome://extensions/`
3. Enable "Developer mode" (top right)
4. Click "Load unpacked"
5. Select the `agentcorrect_extension` folder

## How It Works

1. **Monitors** text fields in Zendesk, Intercom, and other support tools
2. **Detects** when AI populates a draft response
3. **Captures** what the agent changes before sending
4. **Learns** patterns after 3+ identical corrections
5. **Applies** fixes automatically to future AI drafts

## Features

- ✅ Works on Zendesk, Intercom, Salesforce, Freshdesk, HelpScout
- ✅ Learns company-specific corrections
- ✅ Shows applied fixes in real-time
- ✅ Tracks time and money saved
- ✅ Simple popup showing stats and top rules

## How It Actually Works (Technical)

```javascript
// 1. AI writes draft
"I understand your frustration with the delay"

// 2. Agent edits it
"I can help expedite your order"

// 3. After 3 similar edits, rule created
Rule: "I understand your frustration" → "I can help"

// 4. Next time AI writes it, auto-fixed
AI: "I understand your frustration with billing"
AgentCorrect: "I can help with billing" // Fixed automatically!
```

## Privacy

- All data stored locally in your browser
- No data sent to external servers
- Company-specific corrections stay private
- Can clear all data anytime

## ROI

For a 100-agent support team:
- Each agent saves 2-3 minutes per ticket
- 100 tickets/day = 200-300 minutes saved
- $25/hour × 5 hours = $125/day/agent
- **Annual savings: $3.1 million**

## Common Rules It Learns

1. **Phrase replacements**
   - "I understand your frustration" → "I can help"
   - "Unfortunately" → [removed]
   - "As per our policy" → [removed]

2. **Adding specifics**
   - "your order" → "order #12345"
   - "the refund" → "the $127.50 refund"

3. **Tone adjustments**
   - "We regret to inform you" → [removed]
   - "Please bear with us" → [removed]

## Support

This is a simple tool that does one thing well: prevents agents from making the same edits repeatedly.

No AI. No complex ML. Just pattern matching for repetitive fixes.

## License

MIT