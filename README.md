# LinkedIn Outreach Agent 🤖
### Automated SDE Job Outreach for Freshers

---

## What This Does
1. Connects to your LinkedIn using an automatic Chrome profile (No need to enter email/password, it stays logged in!)
2. Searches for Recruiters, HRs, and Engineers at target companies
3. Sends personalized connection requests (AI writes the note)
4. Tracks everyone you've reached out to in a CSV

---

## Setup (Windows Friendly)

### Step 1 — Clone the project and open a terminal
Ensure you have Python installed (preferably Python 3.10+). Open Command Prompt or PowerShell in the project folder:
```cmd
cd path\to\linkedin_agent
```

### Step 2 — Create and activate a Virtual Environment
```cmd
python -m venv venv
venv\Scripts\activate
```

### Step 3 — Install dependencies
```cmd
pip install -r requirements.txt
playwright install chromium
```

### Step 4 — Fill in your details
Open `config.py` and update your API key and details. **Note: You DO NOT need to fill in `LINKEDIN_EMAIL` or `LINKEDIN_PASSWORD` anymore, as the agent uses a persistent Chrome session.**

```python
YOUR_NAME         = "Your Name"              # Your real name
YOUR_ROLE         = "Software Developer (Fresher)"
RESUME_LINK       = "https://drive.google.com/your-resume"
# GROK_API_KEY      = "your-api-key-here"      # Replace with your actual key NO NEED OF GROK API FOR NOW -> Future usecase
```

---

## Running the Agent

### Target one or more companies:
```cmd
python main.py Google
python main.py Google Microsoft Infosys TCS
```

### Or interactive mode:
```cmd
python main.py
```

*Note: The first time you run this, a browser window might open. Log into LinkedIn manually just once. After that, Playwright will remember your session automatically!*

---

## Checking Your Progress
```cmd
python utils/tracker.py
```
Output:
```
📊 OUTREACH TRACKER SUMMARY
Total connections sent : 45
📤 Sent     : 30
✅ Accepted  : 12
💬 Replied   : 3

By Company:
🏢 Google         15 sent | 5 accepted | 1 replied
🏢 Microsoft      15 sent | 4 accepted | 2 replied
🏢 Infosys        15 sent | 3 accepted | 0 replied
```

---

## Daily Limits (Stay Safe ✅)
| Action | Safe Limit |
|--------|-----------|
| Connection requests/day | 20-25 |
| Companies per session | 2-3 |
| Break between sessions | 12+ hours |

---

## Project Structure
```
linkedin_agent/
├── main.py                    ← Run this
├── config.py                  ← Your settings (No LinkedIn password required)
├── requirements.txt
├── agents/
│   ├── linkedin_connector.py  ← Playwright scraper + auto sender
│   └── message_generator.py   ← AI message writer
├── utils/
│   └── tracker.py             ← View your outreach stats
└── data/
    └── outreach_tracker.csv   ← Auto-generated log
```

---

## Next Steps After Setup
1. Run for 3-4 companies
2. Check tracker daily
3. Prepare for interviews! 🎯
