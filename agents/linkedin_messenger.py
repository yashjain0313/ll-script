"""
Agent 2 — LinkedIn Messenger (1st Degree Connections)
Logs in, searches for 1st-degree connections at a company, and sends a personalized DM.
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
    MIN_DELAY, MAX_DELAY
)

DM_TRACKER_FILE = "data/dm_tracker.csv"

# ── Helpers ──────────────────────────────────────────────────

async def human_delay(min_s=None, max_s=None):
    """Random delay to mimic human behaviour."""
    lo = min_s or MIN_DELAY
    hi = max_s or MAX_DELAY
    await asyncio.sleep(random.uniform(lo, hi))


def save_dm_to_tracker(data: dict):
    """Save outreach attempt to CSV."""
    file_exists = os.path.isfile(DM_TRACKER_FILE)
    os.makedirs(os.path.dirname(DM_TRACKER_FILE), exist_ok=True)
    with open(DM_TRACKER_FILE, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "company", "name", "title", "profile_url", "status", "message_sent"])
        if not file_exists:
            writer.writeheader()
        writer.writerow(data)


# ── Core Messaging Logic ──────────────────────────────────────

async def message_1st_degree_connections(page, company_name, dm_text, max_messages=20):
    print(f"\n🔍 Searching for 1st-degree connections at: {company_name}")

    # Search URL for 1st degree connections matching the keyword (company name)
    search_url = (
        f"https://www.linkedin.com/search/results/people/"
        f"?keywords={company_name.replace(' ', '%20')}"
        f"&network=%5B%22F%22%5D"  # "F" stands for First-degree
        f"&origin=FACETED_SEARCH"
    )
    
    await page.goto(search_url)
    await human_delay(4, 6)
    
    total_sent = 0
    processed_names = set()
    
    # Load historically messaged people to avoid double-texting across runs
    try:
        if os.path.exists(DM_TRACKER_FILE):
            with open(DM_TRACKER_FILE, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if 'name' in row:
                        processed_names.add(row['name'])
    except Exception:
        pass

    show_more_attempts = 0

    while total_sent < max_messages:
        print("  📜 Scrolling to find connection cards...")
        for _ in range(3):
            await page.evaluate("window.scrollBy(0, 800)")
            await human_delay(1, 2)
            
            try:
                # On search pages, pagination is usually at the bottom (Next button) 
                # or infinite scroll.
                next_btn = await page.query_selector("button[aria-label='Next']")
                if next_btn and await next_btn.is_visible():
                    # We will handle next page click later if needed
                    pass
            except Exception:
                pass

        # Wait for Message buttons to appear
        # We specifically look for buttons that say "Message"
        button_selector = "button:has-text('Message'), a:has-text('Message')"
        
        try:
            await page.wait_for_selector(button_selector, timeout=8000)
        except PlaywrightTimeout:
            print(f"  ⚠️  No 1st-degree connections with 'Message' buttons found for {company_name}.")
            return total_sent

        # Re-query every iteration since DOM can change after chat closes
        all_buttons = await page.query_selector_all("button, a")
        message_buttons = []
        for btn in all_buttons:
            try:
                txt = (await btn.inner_text()).strip()
                aria = await btn.get_attribute("aria-label") or ""
                
                # Check if it's a message button
                if txt == "Message" or ("Message" in aria and "Connect" not in aria):
                    is_disabled = await btn.get_attribute("disabled") is not None
                    if not is_disabled:
                        message_buttons.append(btn)
            except Exception:
                continue

        if not message_buttons:
            print("  ℹ️  No more Message buttons on this page.")
            break

        btn_to_click = None
        current_name = "Unknown"
        current_title = "Unknown"
        current_profile = ""

        # Find the first message button for a person we haven't processed yet
        for btn in message_buttons:
            try:
                # Find the parent card
                card = await btn.evaluate_handle(
                    "el => el.closest('li.reusable-search__result-container') "
                    "|| el.closest('li.search-result') "
                    "|| el.parentElement"
                )
                name_el = await card.query_selector(
                    ".entity-result__title-text, "
                    "span[aria-hidden='true']"
                )
                title_el = await card.query_selector(
                    ".entity-result__primary-subtitle"
                )
                profile_el = await card.query_selector("a[href*='/in/']")

                n = (await name_el.inner_text()).strip() if name_el else ""
                t = (await title_el.inner_text()).strip() if title_el else "Unknown"
                p = await profile_el.get_attribute("href") if profile_el else ""
                
                # Fallback: extract name from the button's aria-label
                if not n or n == "Unknown":
                    aria_lbl = await btn.get_attribute("aria-label") or ""
                    if "Message" in aria_lbl:
                        n = aria_lbl.replace("Message", "").strip()
                    else:
                        n = "Unknown_Person_" + str(random.randint(1000, 9999))
                
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
            print("  ℹ️  All visible 1st-degree connections have already been messaged.")
            
            # Check for next page
            try:
                next_btn = await page.query_selector("button[aria-label='Next']")
                if next_btn and await next_btn.is_visible() and await next_btn.is_enabled():
                    await next_btn.click()
                    print("  🔄 Moving to next page of results...")
                    await human_delay(3, 5)
                    continue
                else:
                    break # No more pages
            except Exception:
                break

        print(f"\n  👤 Messaging: {current_name} — {current_title}")

        # Click the Message button
        await btn_to_click.click()
        await human_delay(2, 3)

        # ── Handle the chat overlay ──────────────────────────────────────
        
        # Wait for the chat box to appear
        chat_box = await page.query_selector("div.msg-form__contenteditable, div[role='textbox']")
        if not chat_box:
            print("     ⚠️  Chat box did not open. Saving screenshot...")
            await page.screenshot(path="debug_chat_box.png")
            processed_names.add(current_name)
            
            # Ensure we close any broken overlay
            close_btn = await page.query_selector("button[data-control-name='overlay.close_conversation_window']")
            if close_btn:
                await close_btn.click()
                await human_delay(1, 2)
            continue
            
        # Type the personalized message
        print("     📝 Typing message...")
        await chat_box.click()
        await human_delay(0.5, 1)
        
        # We replace placeholders if necessary (e.g. {name})
        final_message = dm_text.replace("{name}", current_name.split()[0] if current_name else "")
        
        # Type the message quickly
        await chat_box.fill(final_message)
        await human_delay(1, 2)
        
        # Click Send
        send_btn = await page.query_selector("button.msg-form__send-button")
        if send_btn and await send_btn.is_enabled():
            await send_btn.click()
            print(f"     ✅ Message sent successfully!")
            save_dm_to_tracker({
                "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "company": company_name,
                "name": current_name,
                "title": current_title,
                "profile_url": current_profile,
                "status": "Messaged",
                "message_sent": final_message,
            })
            total_sent += 1
            processed_names.add(current_name)
        else:
            print("     ❌ Send button not found or disabled.")
            processed_names.add(current_name)
            
        await human_delay(1.5, 2.5)
        
        # Close the chat overlay to keep the screen clean
        close_btn = await page.query_selector("button.msg-overlay-bubble-header__control--close-btn, button[data-control-name='overlay.close_conversation_window']")
        if close_btn:
            await close_btn.click()
            await human_delay(1, 2)

        # ──────────────────────────────────────────────────────────
        # REFRESH PAGE AFTER EVERY SUCCESSFUL REQUEST
        # ──────────────────────────────────────────────────────────
        print("  🔄 Refreshing page to reset DOM state...")
        await page.reload()
        await human_delay(4, 6)

    return total_sent


async def run_dm_campaign(company_name: str, dm_text: str):
    """Entry point for the Streamlit app to run the DM campaign."""
    async with async_playwright() as p:
        user_data_dir = os.path.join(os.getcwd(), "playwright_profile")
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=False,
            args=["--start-maximized", "--disable-blink-features=AutomationControlled"],
            viewport={"width": 1280, "height": 800}
        )

        page = browser.pages[0] if browser.pages else await browser.new_page()

        print("\n🔐 Checking LinkedIn login status...")
        await page.goto("https://www.linkedin.com/feed/")
        await human_delay(3, 5)

        if "feed" not in page.url and "checkpoint" not in page.url:
            print("  ⚠️  You are not logged in! Please log in manually.")
            await page.wait_for_url("**/feed/**", timeout=60000)
            print("✅ Logged in successfully!")

        print(f"\n==================================================")
        print(f"🚀 Starting DM Campaign for: {company_name}")
        print(f"==================================================")

        sent = await message_1st_degree_connections(page, company_name, dm_text)
        
        print(f"\n==================================================")
        print(f"✅ DONE! Total DMs sent: {sent}")
        print(f"📁 Tracker saved to: {DM_TRACKER_FILE}")
        
        await browser.close()
