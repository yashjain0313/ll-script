"""
Agent 2 -- LinkedIn Messenger (1st Degree Connections)
Logs in, navigates to company People tab filtered to 1st-degree connections,
and sends a personalized DM to each person.
"""

import asyncio
import random
import csv
import os
import sys
from datetime import datetime
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import (
    MIN_DELAY, MAX_DELAY
)
from data.dm_database import (
    get_all_messaged_names_global, record_message, is_already_messaged
)

DM_TRACKER_FILE = "data/dm_tracker.csv"

# -- Helpers --

async def human_delay(min_s=None, max_s=None):
    lo = min_s or MIN_DELAY
    hi = max_s or MAX_DELAY
    await asyncio.sleep(random.uniform(lo, hi))


def save_dm_to_tracker(data: dict):
    file_exists = os.path.isfile(DM_TRACKER_FILE)
    os.makedirs(os.path.dirname(DM_TRACKER_FILE), exist_ok=True)
    with open(DM_TRACKER_FILE, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "company", "name", "title", "profile_url", "status", "message_sent"])
        if not file_exists:
            writer.writeheader()
        writer.writerow(data)


# -- Find chat box with multiple selectors --

async def find_chat_box(page):
    selectors = [
        "div.msg-form__contenteditable",
        "div[role='textbox'][data-artdeco-is-focused]",
        "div[role='textbox']",
        ".msg-form__contenteditable",
        "[contenteditable='true']",
        "div[aria-label='Write a message\u2026']",
        "div[aria-label='Write a message']",
    ]
    for sel in selectors:
        try:
            el = await page.wait_for_selector(sel, timeout=2000, state="visible")
            if el:
                print(f"     [OK] Chat box found via: {sel}")
                return el
        except Exception:
            continue
    return None


# -- Find send button with multiple selectors --

async def find_send_button(page):
    selectors = [
        "button.msg-form__send-button",
        "button[data-control-name='send-action']",
        "button[aria-label='Send']",
        "button.artdeco-button--primary[type='submit']",
        ".msg-form__send-btn",
        "button.send-button",
        "button:has-text('Send')",
    ]
    for sel in selectors:
        try:
            el = await page.query_selector(sel)
            if el and await el.is_visible() and await el.is_enabled():
                print(f"     [OK] Send button found via: {sel}")
                return el
        except Exception:
            continue
    return None


# -- Core Messaging Logic --

async def message_1st_degree_connections(page, company_name, dm_text, max_messages=20):
    if company_name.startswith("https://www.linkedin.com/company/"):
        search_url = company_name.rstrip("/") + "/people/?facetNetwork=F"
        print(f"\n[*] Navigating to Company People Tab: {search_url}")
    elif company_name.startswith("http"):
        search_url = company_name
        print(f"\n[*] Using provided custom search URL")
    else:
        print(f"\n[*] Searching for 1st-degree connections at: {company_name}")
        search_url = (
            f"https://www.linkedin.com/search/results/people/"
            f"?keywords={company_name.replace(' ', '%20')}"
            f"&network=%5B%22F%22%5D"
            f"&origin=FACETED_SEARCH"
        )

    await page.goto(search_url)
    await human_delay(4, 6)

    total_sent = 0
    processed_names = set()

    # Load from SQLite DB (persistent across sessions)
    try:
        processed_names = get_all_messaged_names_global()
        print(f"  [i] Loaded {len(processed_names)} previously messaged people from DB.")
    except Exception as e:
        print(f"  [!] Could not load DB: {e}")

    # Also load from CSV as fallback
    try:
        if os.path.exists(DM_TRACKER_FILE):
            with open(DM_TRACKER_FILE, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if 'name' in row:
                        processed_names.add(row['name'])
    except Exception:
        pass

    consecutive_failures = 0
    all_processed_page_attempts = 0  # Track how many times we see all-processed pages

    while total_sent < max_messages:
        print("  [>] Scrolling to find connection cards...")
        for _ in range(3):
            await page.evaluate("window.scrollBy(0, 800)")
            await human_delay(1, 2)
            try:
                show_more = await page.query_selector("button:has-text('Show more results')")
                if show_more and await show_more.is_visible():
                    await show_more.click()
                    print("  [>] Clicked 'Show more results'")
                    await human_delay(2, 3)
            except Exception:
                pass

        button_selector = "button:has-text('Message'), a:has-text('Message')"
        try:
            await page.wait_for_selector(button_selector, timeout=8000)
        except PlaywrightTimeout:
            print("  [!] No Message buttons found on page.")
            return total_sent

        all_buttons = await page.query_selector_all("button, a")
        message_buttons = []
        for btn in all_buttons:
            try:
                txt = (await btn.inner_text()).strip()
                aria = await btn.get_attribute("aria-label") or ""
                if txt == "Message" or ("Message" in aria and "Connect" not in aria):
                    is_disabled = await btn.get_attribute("disabled") is not None
                    if not is_disabled:
                        message_buttons.append(btn)
            except Exception:
                continue

        if not message_buttons:
            print("  [i] No more Message buttons on this page.")
            break

        btn_to_click = None
        current_name = "Unknown"
        current_title = "Unknown"
        current_profile = ""

        for btn in message_buttons:
            try:
                card = await btn.evaluate_handle(
                    "el => el.closest('li.org-people-profile-card') "
                    "|| el.closest('li.reusable-search__result-container') "
                    "|| el.closest('li.search-result') "
                    "|| el.parentElement"
                )

                n = await card.evaluate("""(card) => {
                    let t = card.querySelector('.org-people-profile-card__profile-title');
                    if (t && t.innerText.trim()) return t.innerText.trim();
                    let ns = card.querySelector('span[dir="ltr"] > span[aria-hidden="true"]');
                    if (ns && ns.innerText.trim()) return ns.innerText.trim();
                    let a = card.querySelector('.entity-result__title-text a');
                    if (a) return a.innerText.split('\\n')[0].trim();
                    return '';
                }""")

                title_el = await card.query_selector(
                    ".org-people-profile-card__profile-position, "
                    ".entity-result__primary-subtitle"
                )
                t = (await title_el.inner_text()).strip() if title_el else "Unknown"

                profile_el = await card.query_selector("a[href*='/in/']")
                p = await profile_el.get_attribute("href") if profile_el else ""

                if not n:
                    aria_lbl = await btn.get_attribute("aria-label") or ""
                    if "Message" in aria_lbl:
                        n = aria_lbl.replace("Message to", "").replace("Message", "").strip()
                if not n:
                    n = "Unknown_Person_" + str(random.randint(1000, 9999))

                print(f"      - Found: {n} (already processed: {n in processed_names})")

                if n not in processed_names:
                    btn_to_click = btn
                    current_name = n
                    current_title = t
                    current_profile = p
                    break

            except Exception:
                continue

        if not btn_to_click:
            all_processed_page_attempts += 1
            print(f"  [i] All visible people have been messaged. (attempt {all_processed_page_attempts}/3)")
            
            if all_processed_page_attempts >= 3:
                print("  [DONE] Checked multiple pages, no new people found. Stopping.")
                break
            
            try:
                next_btn = await page.query_selector("button[aria-label='Next']")
                if next_btn and await next_btn.is_visible() and await next_btn.is_enabled():
                    await next_btn.click()
                    print("  [>] Moving to next page...")
                    await human_delay(3, 5)
                    continue

                await page.evaluate("window.scrollBy(0, 1000)")
                await human_delay(2, 3)
                show_more = await page.query_selector("button:has-text('Show more results')")
                if show_more and await show_more.is_visible():
                    await show_more.click()
                    print("  [>] Clicked 'Show more results'")
                    await human_delay(3, 5)
                    continue
                else:
                    break
            except Exception:
                break

        print(f"\n  [>] Messaging: {current_name} -- {current_title}")

        # -- NUCLEAR: Remove ALL existing chat overlay bubbles from the DOM --
        await page.evaluate("""() => {
            document.querySelectorAll('.msg-overlay-list-bubble').forEach(el => el.remove());
            document.querySelectorAll('.msg-overlay-bubble-header').forEach(el => {
                let parent = el.closest('.msg-overlay-list-bubble');
                if (parent) parent.remove();
            });
        }""")
        await human_delay(1, 1.5)

        # Click Message button via JS (bypasses all overlay interception)
        try:
            await btn_to_click.evaluate("node => node.click()")
        except Exception as e:
            print(f"     [!] Could not click Message button: {e}")
            processed_names.add(current_name)
            consecutive_failures += 1
            if consecutive_failures >= 3:
                print("  [!] Too many consecutive failures. Stopping.")
                break
            continue

        await human_delay(3, 4)

        # Prepare the personalized message
        first_name = current_name.split()[0] if current_name and "Unknown" not in current_name else ""
        final_message = dm_text.replace("{name}", first_name)

        # -- TYPE AND SEND entirely via JavaScript --
        # Uses execCommand('insertText') which properly triggers LinkedIn's React/Ember
        # framework, enabling the Send button (unlike innerHTML which leaves it grayed out)
        print("     [>] Typing and sending message via JS...")
        message_sent = await page.evaluate("""(messageText) => {
            return new Promise((resolve) => {
                // Find the most recently added chat box (the last one in DOM order)
                let chatBoxes = document.querySelectorAll(
                    'div.msg-form__contenteditable, div[role="textbox"]'
                );
                let chatBox = chatBoxes[chatBoxes.length - 1];
                if (!chatBox) {
                    console.log('No chat box found');
                    resolve(false);
                    return;
                }

                // Focus and clear the chat box
                chatBox.focus();
                chatBox.innerHTML = '';
                
                // Use execCommand('insertText') -- this is the KEY fix!
                // Unlike innerHTML, this triggers React/Ember's input handling
                // which enables the Send button properly
                document.execCommand('insertText', false, messageText);

                // Wait for LinkedIn to process and enable the Send button
                setTimeout(() => {
                    let sendBtn = document.querySelector('button.msg-form__send-button')
                        || document.querySelector("button[aria-label='Send']")
                        || document.querySelector('button.artdeco-button--primary[type="submit"]');
                    
                    // Broader selector fallback
                    if (!sendBtn) {
                        let allBtns = document.querySelectorAll('button');
                        for (let b of allBtns) {
                            if (b.innerText.trim() === 'Send' && b.offsetParent !== null) {
                                sendBtn = b;
                                break;
                            }
                        }
                    }
                    
                    if (sendBtn && !sendBtn.disabled) {
                        sendBtn.click();
                        resolve(true);
                    } else if (sendBtn) {
                        // Button found but disabled -- force remove disabled and click
                        sendBtn.removeAttribute('disabled');
                        sendBtn.click();
                        resolve(true);
                    } else {
                        resolve(false);
                    }
                }, 2000);
            });
        }""", final_message)

        await human_delay(1, 2)

        if message_sent:
            print(f"     [OK] Message sent to {current_name}!")
            # Save to CSV tracker
            save_dm_to_tracker({
                "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "company": company_name,
                "name": current_name,
                "title": current_title,
                "profile_url": current_profile,
                "status": "Messaged",
                "message_sent": final_message,
            })
            # Save to SQLite DB (persistent)
            try:
                record_message(
                    company_url=company_name,
                    company_name=company_name,
                    person_name=current_name,
                    person_title=current_title,
                    profile_url=current_profile,
                    message_sent=final_message
                )
            except Exception as db_err:
                print(f"     [!] DB save error: {db_err}")
            total_sent += 1
            processed_names.add(current_name)
            consecutive_failures = 0
            all_processed_page_attempts = 0  # Reset since we found someone new
        else:
            print(f"     [!] Could not send message to {current_name}. Skipping.")
            processed_names.add(current_name)
            consecutive_failures += 1

        await human_delay(1.5, 2.5)

        # Nuclear cleanup again before refresh
        await page.evaluate("""() => {
            document.querySelectorAll('.msg-overlay-list-bubble').forEach(el => el.remove());
        }""")

        await human_delay(0.5, 1)
        print("  [>] Refreshing page to reset DOM state...")
        await page.reload()
        await human_delay(4, 6)

    print(f"\n  [DONE] Finished! Sent {total_sent} messages.")
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

        print("\n[*] Checking LinkedIn login status...")
        await page.goto("https://www.linkedin.com/feed/")
        await human_delay(3, 5)

        if "feed" not in page.url and "checkpoint" not in page.url:
            print("  [!] You are not logged in! Please log in manually.")
            await page.wait_for_url("**/feed/**", timeout=60000)
            print("[OK] Logged in successfully!")

        print(f"\n==================================================")
        print(f"[*] Starting DM Campaign for: {company_name}")
        print(f"==================================================")

        sent = await message_1st_degree_connections(page, company_name, dm_text)

        print(f"\n==================================================")
        print(f"[DONE] Total DMs sent: {sent}")
        print(f"[*] Tracker saved to: {DM_TRACKER_FILE}")

        await browser.close()
