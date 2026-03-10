# ─────────────────────────────────────────────────────────────
# MBRL Scan-to-Print — Configuration
# Copy this file to config.py and fill in your values.
# config.py is gitignored and will never be pushed to GitHub.
# ─────────────────────────────────────────────────────────────

# ── SONA API ──────────────────────────────────────────────────
# Your SONA domain prefix (the part before .sona-systems.com)
SONA_DOMAIN = "marshall-mor"

# Your SONA API key — must be for an admin account.
# To generate: SONA → Users → Add/Edit/Search → find your admin user
#              → click "Set API Key" → click "Set API Key" to generate.
# Note: username/password auth was deprecated December 2024.
SONA_API_TOKEN = "YOUR_SONA_API_KEY_HERE"

# ── Email notifications ───────────────────────────────────────
# Sent at checkout to notify lab manager + RA that credit is due.

# Gmail recommended. Use an App Password, not your regular password.
# To create one: myaccount.google.com → Security → 2-Step Verification → App passwords
EMAIL_SMTP_HOST = "smtp.gmail.com"
EMAIL_SMTP_PORT = 587
EMAIL_ADDRESS   = "your.email@gmail.com"
EMAIL_PASSWORD  = "YOUR_APP_PASSWORD_HERE"   # 16-char Gmail app password

# For USC Outlook/Exchange use these instead:
# EMAIL_SMTP_HOST = "smtp.office365.com"
# EMAIL_SMTP_PORT = 587
# EMAIL_ADDRESS   = "yournetid@usc.edu"
# EMAIL_PASSWORD  = "YOUR_PASSWORD"

# Recipients — both lab manager and RA get notified
EMAIL_LAB_MANAGER = "huhb@marshall.usc.edu"
EMAIL_RA          = ""    # Leave blank — RA enters their email in the app each session

# ── CSV log ───────────────────────────────────────────────────
# Where to save the checkout log. Defaults to the same folder as server.py.
# e.g. "/Users/brianhuh/Documents/MBRL/checkout_log.csv"
CSV_LOG_PATH = "checkout_log.csv"
