# ============================================================
#  LinkedIn Outreach Agent — Config
#  Fill in your details here before running
# ============================================================

YOUR_NAME        = "Yash Jain"
YOUR_ROLE        = "Software Developer (Fresher)"
RESUME_LINK      = "https://drive.google.com/file/d/1BhFMHRvmFJrP-0UsRELO1QVq3v_7CWXl/view?usp=sharing"   # Google Drive / PDF link
LINKEDIN_EMAIL   = "[EMAIL_ADDRESS]"
LINKEDIN_PASSWORD = "[PASSWORD]"
GROK_API_KEY     = ""

# How many people to connect per company (LinkedIn daily limit is ~20-25 safe)
CONNECTIONS_PER_COMPANY = 15

# Who to prioritize (in order)
TARGET_TITLES = [
    "recruiter",
    "talent acquisition",
    "hr",
    "hiring manager",
    "engineering manager",
    "tech lead",
    "software engineer",
    "sde",
]

# Delay between actions (seconds) — mimics human behavior
MIN_DELAY = 3
MAX_DELAY = 7

# Output file for tracking
TRACKER_FILE = "data/outreach_tracker.csv"
