"""
Agent 2 — LinkedIn Scraper + Auto Connector
Logs in, searches company people, sends connection requests
"""

import asyncio
import random
import csv
import os
import sys
from datetime import datetime
from urllib.parse import urlparse
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import (
    LINKEDIN_EMAIL, LINKEDIN_PASSWORD,
    CONNECTIONS_PER_COMPANY, TARGET_TITLES,
    MIN_DELAY, MAX_DELAY, TRACKER_FILE
)
from agents.message_generator import generate_connection_note


# ── Helpers ──────────────────────────────────────────────────

async def human_delay(min_s=None, max_s=None):
    """Random delay to mimic human behaviour."""
    lo = min_s or MIN_DELAY
    hi = max_s or MAX_DELAY
    await asyncio.sleep(random.uniform(lo, hi))


def rank_person(title: str) -> int:
    """Return priority score — lower is higher priority."""
    title_lower = title.lower()
    for i, keyword in enumerate(TARGET_TITLES):
        if keyword in title_lower:
            return i
    return len(TARGET_TITLES)  # lowest priority


def save_to_tracker(row: dict):
    """Append a row to the CSV tracker."""
    os.makedirs(os.path.dirname(TRACKER_FILE), exist_ok=True)
    file_exists = os.path.exists(TRACKER_FILE)
    with open(TRACKER_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "date", "company", "name", "title", "profile_url", "status", "note_sent"
        ])
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


# ── Login ─────────────────────────────────────────────────────

async def login(page):
    print("🔐 Logging into LinkedIn...")
    await page.goto("https://www.linkedin.com/login")
    await human_delay(2, 3)

    try:
        # Wait for either #username or #session_key or any email input
        username_el = await page.wait_for_selector("#username, #session_key, input[type='email']", timeout=5000)
        await username_el.fill(LINKEDIN_EMAIL)
        await human_delay(0.5, 1.5)
        
        password_el = await page.wait_for_selector("#password, #session_password, input[type='password']", timeout=5000)
        await password_el.fill(LINKEDIN_PASSWORD)
        await human_delay(0.5, 1.5)
        
        submit_btn = await page.wait_for_selector("button[type='submit'], .login__form_action_container button, button[aria-label='Sign in']", timeout=5000)
        await submit_btn.click()
        await human_delay(4, 6)
    except Exception as e:
        print(f"  ⚠️  Auto-login skipped or fields not found (you can log in manually).")

    # Now wait for the user to solve captcha or login manually
    print("  ⏳ Waiting up to 60 seconds for you to log in manually or solve CAPTCHA...")
    for _ in range(30):
        if "feed" in page.url or "mynetwork" in page.url or "linkedin.com/in/" in page.url:
            print("✅ Logged in successfully!")
            return True
        import asyncio
        await asyncio.sleep(2)

    print("❌ Login failed (timed out after 60s) — please try again.")
    return False


# ── Connect directly on the company People tab ────────────────

async def connect_on_people_page(page, company_url: str, company: str) -> int:
    """
    Navigate to the company People tab, find all Connect buttons there,
    click them one by one, handle the modal, and return the total sent.
    Never navigates away from the page — much more reliable.
    """
    print(f"\n🔍 Opening People tab for: {company}")

    people_tab_url = company_url.rstrip("/") + "/people/"
    await page.goto(people_tab_url)
    await human_delay(4, 6)

    # The People tab shows stats first (Where they live, Where they studied, etc.)
    # We need to scroll past all of that to reach the actual employee cards
    print("  📜 Scrolling to find employee cards...")
    for _ in range(4):
        await page.evaluate("window.scrollBy(0, 800)")
        await human_delay(1, 2)
        
        # Click "Show more results" if it appears during scrolling
        try:
            show_more = await page.query_selector("button:has-text('Show more results')")
            if show_more and await show_more.is_visible():
                await show_more.click()
                print("  🔄 Clicked 'Show more results'")
                await human_delay(2, 3)
        except Exception:
            pass

    # Wait for Connect buttons to appear after scrolling
    button_selector = (
        "button[data-action='connect-btn'], "
        "button[aria-label*='Invite'][aria-label*='connect'], "
        "button:text-is('Connect')"
    )
    try:
        await page.wait_for_selector(button_selector, timeout=8000)
    except PlaywrightTimeout:
        # Fallback: try the LinkedIn people search with currentCompany filter
        print("  ⚠️  No Connect buttons on People tab. Trying search fallback...")
        parsed = urlparse(company_url)
        path_parts = [p for p in parsed.path.split('/') if p and p != 'company']
        company_slug = path_parts[0] if path_parts else company.replace(' ', '%20')

        # Get the company's numeric ID from the page if possible
        search_url = (
            f"https://www.linkedin.com/search/results/people/"
            f"?keywords={company.replace(' ', '%20')}"
            f"&origin=FACETED_SEARCH"
            f"&sid=s7k"
        )
        await page.goto(search_url)
        await human_delay(3, 5)
        
        # Scroll on search page too
        for _ in range(3):
            await page.evaluate("window.scrollBy(0, 800)")
            await human_delay(1, 2)

        try:
            await page.wait_for_selector(button_selector, timeout=8000)
        except PlaywrightTimeout:
            print("  ⚠️  No Connect buttons found in search either. Saving screenshot...")
            await page.screenshot(path="debug_people_tab.png")
            return 0

    total_sent = 0
    processed_names = set()
    
    # Load historically contacted people to avoid repeating across runs
    try:
        if os.path.exists(TRACKER_FILE):
            with open(TRACKER_FILE, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if 'name' in row:
                        processed_names.add(row['name'])
    except Exception:
        pass

    show_more_attempts = 0

    # Keep looping while there are still Connect buttons and we haven't hit the limit
    while total_sent < CONNECTIONS_PER_COMPANY:
        # Re-query every iteration since DOM can change after a modal closes
        all_buttons = await page.query_selector_all("button")
        connect_buttons = []
        for btn in all_buttons:
            try:
                txt = (await btn.inner_text()).strip()
                aria = await btn.get_attribute("aria-label") or ""
                data_act = await btn.get_attribute("data-action") or ""
                
                # It's a connect button if it matches any of our patterns
                if txt == "Connect" or ("Invite" in aria and "connect" in aria) or data_act == "connect-btn":
                    # Extra safety: ensure it's not disabled
                    is_disabled = await btn.get_attribute("disabled") is not None
                    if not is_disabled:
                        connect_buttons.append(btn)
            except Exception:
                continue

        if not connect_buttons:
            print("  ℹ️  No more Connect buttons on this page.")
            break

        btn_to_click = None
        current_name = "Unknown"
        current_title = "Unknown"
        current_profile = ""
        
        print(f"  🔍 [DEBUG] Scanning {len(connect_buttons)} potential Connect buttons...")

        # Find the first connect button for a person we haven't processed yet
        for btn in connect_buttons:
            try:
                # CRITICAL FIX: Only look for strictly individual li cards, NEVER generic lockup wrappers
                card = await btn.evaluate_handle(
                    "el => el.closest('li.org-people-profile-card') "
                    "|| el.closest('li.reusable-search__result-container') "
                    "|| el.closest('li.search-result') "
                    "|| el.parentElement"
                )
                name_el = await card.query_selector(
                    ".org-people-profile-card__profile-title, "
                    ".entity-result__title-text, "
                    ".artdeco-entity-lockup__title, "
                    "span[aria-hidden='true']"
                )
                title_el = await card.query_selector(
                    ".artdeco-entity-lockup__subtitle, "
                    ".org-people-profile-card__profile-position, "
                    ".entity-result__primary-subtitle"
                )
                profile_el = await card.query_selector("a[href*='/in/']")

                n = (await name_el.inner_text()).strip() if name_el else ""
                t = (await title_el.inner_text()).strip() if title_el else "Unknown"
                p = await profile_el.get_attribute("href") if profile_el else ""
                
                # Fallback: extract name from the button's aria-label if standard extraction failed
                if not n or n == "Unknown":
                    aria_lbl = await btn.get_attribute("aria-label") or ""
                    if "Invite" in aria_lbl and "to connect" in aria_lbl:
                        n = aria_lbl.replace("Invite", "").replace("to connect", "").strip()
                    else:
                        n = "Unknown_Person_" + str(random.randint(1000, 9999))
                
                print(f"      - Found card for: {n} (in processed? {n in processed_names})")
                
                # If we haven't processed this person yet, pick them!
                if n not in processed_names:
                    btn_to_click = btn
                    current_name = n
                    current_title = t
                    current_profile = p
                    break
            except Exception:
                continue
                
        if not btn_to_click:
            print("  ℹ️  All visible Connect buttons have already been processed.")
            
            if show_more_attempts >= 3:
                print("  ⚠️  Reached limit (3) for 'Show more results'. Moving to next company.")
                break
                
            # Try to scroll a bit more to reveal new people
            await page.evaluate("window.scrollBy(0, 1000)")
            await human_delay(2, 3)
            
            # Check for show more results
            try:
                show_more = await page.query_selector("button:has-text('Show more results')")
                if show_more and await show_more.is_visible():
                    await show_more.click()
                    print("  🔄 Clicked 'Show more results'")
                    show_more_attempts += 1
                    await human_delay(3, 4)
                    
            except Exception:
                pass
                
            # Whether we clicked show more or just scrolled, continue the loop
            # to query all_buttons again and see if new cards appeared
            continue

        print(f"\n  👤 {current_name} — {current_title}")

        # Click the Connect button
        await btn_to_click.click()
        await human_delay(1.5, 2.5)

        # ── Handle the modal ──────────────────────────────────────
        # User requested to ALWAYS send without a note!

        modal = await page.query_selector("[role='dialog']")
        if not modal:
            print("     ⚠️  No modal appeared after clicking Connect")
            processed_names.add(current_name)
            continue

        # Look for the send button directly
        send_btn = await page.query_selector(
            "button[aria-label='Send without a note'], "
            "button:has-text('Send without a note'), "
            "button[aria-label='Send invitation'], "
            "button:has-text('Send')"
        )
        
        if send_btn:
            await send_btn.click()
            await human_delay(2, 3)
            print(f"     ✅ Request sent (without note)!")
            save_to_tracker({
                "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "company": company,
                "name": current_name,
                "title": current_title,
                "profile_url": current_profile,
                "status": "Sent",
                "note_sent": "",
            })
            total_sent += 1
            processed_names.add(current_name)
            
            # ──────────────────────────────────────────────────────────
            # USER IDEA: REFRESH PAGE AFTER EVERY SUCCESSFUL REQUEST
            # ──────────────────────────────────────────────────────────
            print("  🔄 Refreshing page as requested by user to reset DOM state...")
            await page.reload()
            await human_delay(4, 6)
            
            # Scroll a bit after refresh to load cards again
            for _ in range(3):
                await page.evaluate("window.scrollBy(0, 800)")
                await human_delay(1, 2)
            # ──────────────────────────────────────────────────────────

        else:
            # Close modal if we couldn't send
            close_btn = await page.query_selector("button[aria-label='Dismiss'], button[data-test-modal-close-btn]")
            if close_btn:
                await close_btn.click()
            print("     ❌ Could not find Send button")

        await human_delay(MIN_DELAY, MAX_DELAY)

    return total_sent


# ── Main Orchestrator ─────────────────────────────────────────


async def run_outreach(company_urls: list[str]):
    """Main function — runs the full outreach pipeline."""

    user_data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "playwright_profile")

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=False,   # Keep visible so you can intervene if needed
            slow_mo=50,       # Slows actions slightly — more human-like
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )

        # A persistent context always comes with at least one page
        page = context.pages[0] if context.pages else await context.new_page()

        # Step 1: Login
        logged_in = await login(page)
        if not logged_in:
            print("\n❌ Cannot proceed without login. Exiting.")
            await browser.close()
            return

        total_sent = 0

        for company_url in company_urls:
            print(f"\n{'='*50}")
            print(f"🏢 Company URL: {company_url}")
            print(f"{'='*50}")

            # Extract company name by visiting the page
            print(f"  🌐 Visiting company page to extract name...")
            await page.goto(company_url)
            await human_delay(3, 5)
            
            try:
                # Usually company names are in an h1 on their page
                h1_el = await page.query_selector("h1")
                if h1_el:
                    company = (await h1_el.inner_text()).strip()
                else:
                    # Fallback to URL path parsing
                    parsed = urlparse(company_url)
                    path_parts = [p for p in parsed.path.split('/') if p]
                    company = path_parts[-1].replace('-', ' ').title()
            except Exception as e:
                print(f"  ⚠️ Error extracting company name: {e}")
                parsed = urlparse(company_url)
                path_parts = [p for p in parsed.path.split('/') if p]
                company = path_parts[-1].replace('-', ' ').title()
                
            print(f"  📌 Extracted Company Name: {company}")

            # Step 2: Connect directly on the People tab (no individual profile visits)
            sent_for_company = await connect_on_people_page(page, company_url, company)
            total_sent += sent_for_company

            print(f"\n  📊 Sent {sent_for_company} requests for {company}")

            # Longer pause between companies
            if len(company_urls) > 1:
                wait = random.uniform(30, 60)
                print(f"\n  ⏳ Waiting {wait:.0f}s before next company...")
                await asyncio.sleep(wait)


        print(f"\n{'='*50}")
        print(f"✅ DONE! Total requests sent: {total_sent}")
        print(f"📁 Tracker saved to: {TRACKER_FILE}")

        await context.close()


# ── Entry point ───────────────────────────────────────────────

if __name__ == "__main__":
    # Test with one company URL
    company_urls = ["https://www.linkedin.com/company/google/"]
    asyncio.run(run_outreach(company_urls))
