"""
LinkedIn Outreach Agent — Main Entry Point
==========================================
Usage:
    python main.py                          # Interactive mode
    python main.py https://www.linkedin.com/company/google/ # Pass URLs directly
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

from agents.linkedin_connector import run_outreach
from utils.tracker import print_summary


BANNER = """
╔══════════════════════════════════════════════════╗
║        LinkedIn Outreach Agent  🤖               ║
║        Built for: SDE Fresher Job Hunt           ║
╚══════════════════════════════════════════════════╝
"""

SAFETY_WARNING = """
⚠️  SAFETY TIPS (to avoid LinkedIn ban):
   • Don't send more than 20-25 requests/day total
   • Keep MIN_DELAY ≥ 3 seconds in config.py
   • Don't run more than 2-3 companies per session
   • If LinkedIn shows CAPTCHA, solve it manually
   • Take a break of 1-2 days between heavy sessions
"""


def get_companies_interactive() -> list[str]:
    print("\n📋 Enter company LinkedIn URLs (one per line).")
    print("   Example: https://www.linkedin.com/company/google/")
    print("   Type 'done' when finished:\n")
    company_urls = []
    while True:
        url = input("  Company URL: ").strip()
        if url.lower() in ("done", ""):
            break
        if url:
            company_urls.append(url)
    return company_urls


def main():
    print(BANNER)
    print(SAFETY_WARNING)

    # Get companies from CLI args or interactive input
    if len(sys.argv) > 1:
        company_urls = sys.argv[1:]
        print(f"🏢 Company URLs to target:\n   " + "\n   ".join(company_urls) + "\n")
    else:
        company_urls = get_companies_interactive()

    if not company_urls:
        print("❌ No URLs provided. Exiting.")
        return

    # Confirm before running
    print(f"\n🚀 Ready to send up to {len(company_urls) * 15} connection requests")
    print(f"   Target URLs: {len(company_urls)}")
    confirm = input("\n   Proceed? (y/n): ").strip().lower()

    if confirm != "y":
        print("🛑 Cancelled.")
        return

    # Run the agent
    asyncio.run(run_outreach(company_urls))

    # Show summary after
    print("\n")
    print_summary()


if __name__ == "__main__":
    main()
