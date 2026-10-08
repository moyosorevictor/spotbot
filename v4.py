"""
SubsGigs spot watcher v4. Reads your Telegram token and chat ID from
config.json (see README).

    python3 bot_fast.py --login   # log in once (same saved login as before)
    python3 bot_fast.py           # start watching

How it spots an open campaign: it reads each campaign card's
"N spots currently available" text. If N is more than 0, it clicks the
labelled button inside that card (it prefers words like save / claim / join,
so the exact label doesn't have to be "Save a spot").
If it can't find a button it still alerts you at once so you can go manually,
and sends the card's code so the bot can be fixed afterwards.
"""
import json
import os
import random
import re
import sys
import time
from pathlib import Path

import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

URL = "https://subsgigs-alpha.vercel.app/campaigns"
MIN_WAIT, MAX_WAIT = 5, 10
STOP_AFTER_CLAIM = True
RESTART_AFTER_ERRORS = 3

HERE = Path(__file__).parent
PROFILE_DIR = str(HERE / "chrome-profile")
SHOT = str(HERE / "claimed.png")
DEBUG_SHOT = str(HERE / "debug.png")

def load_telegram_settings():
    """Read the Telegram token and chat ID from environment variables or config.json."""
    token = os.environ.get("TG_TOKEN")
    chat_id = os.environ.get("TG_CHAT_ID")
    cfg = HERE / "config.json"
    if cfg.exists():
        data = json.loads(cfg.read_text())
        token = token or data.get("TG_TOKEN")
        chat_id = chat_id or data.get("TG_CHAT_ID")
    if not token or not chat_id:
        sys.exit("Missing Telegram settings. Copy config.example.json to config.json and fill it in.")
    return token, str(chat_id)


TG_TOKEN, TG_CHAT_ID = load_telegram_settings()

LOWER = "abcdefghijklmnopqrstuvwxyz"
UPPER = LOWER.upper()
SPOTS_RE = re.compile(r"(\d+)\s+spots?\s+currently\s+available", re.I)
ACTION_RE = re.compile(r"save|claim|join|enter|reserve|spot|apply|participate", re.I)
LOGGED_IN_WORDS = ("log out", "my profile", "creator dashboard", "live campaigns")
OLD_BUTTON_XPATH = (
    "//*[self::button or self::a]"
    f"[contains(translate(normalize-space(.), '{UPPER}', '{LOWER}'), 'save a spot')]"
)


def tg(text, photo=None, tries=4):
    base = f"https://api.telegram.org/bot{TG_TOKEN}"
    for attempt in range(tries):
        try:
            if photo:
                with open(photo, "rb") as f:
                    r = requests.post(f"{base}/sendPhoto",
                                      data={"chat_id": TG_CHAT_ID, "caption": text[:1000]},
                                      files={"photo": f}, timeout=25)
            else:
                r = requests.post(f"{base}/sendMessage",
                                  data={"chat_id": TG_CHAT_ID, "text": text[:4000]}, timeout=25)
            if r.ok:
                return True
            print("Telegram said:", r.status_code)
        except Exception as e:
            print(f"Telegram try {attempt + 1}/{tries} failed:", str(e)[:100])
        time.sleep(5)
    return False


def make_driver():
    opts = Options()
    opts.add_argument(f"--user-data-dir={PROFILE_DIR}")
    opts.add_argument("--window-size=1200,900")
    driver = webdriver.Chrome(options=opts)
    driver.set_page_load_timeout(30)
    driver.set_script_timeout(30)
    try:
        driver.command_executor.set_timeout(40)
    except Exception:
        pass
    return driver


def safe_quit(driver):
    try:
        driver.quit()
    except Exception:
        pass


def page_text(driver):
    try:
        return driver.find_element(By.TAG_NAME, "body").text.lower()
    except Exception:
        return ""


def wait_for_logged_in(driver, seconds=40):
    end = time.time() + seconds
    while time.time() < end:
        if any(w in page_text(driver) for w in LOGGED_IN_WORDS):
            return True
        time.sleep(0.5)
    return False


def wait_for_cards(driver, seconds=10):
    """Give the campaign cards a moment to appear after the dashboard shows."""
    end = time.time() + seconds
    while time.time() < end:
        t = page_text(driver)
        if "currently available" in t or "no live campaigns" in t:
            return
        time.sleep(0.5)


def open_cards(driver):
    """Campaign elements whose 'N spots currently available' has N > 0."""
    found = []
    xp = f"//*[text()[contains(translate(., '{UPPER}', '{LOWER}'), 'currently available')]]"
    for el in driver.find_elements(By.XPATH, xp):
        try:
            m = SPOTS_RE.search(el.text or "")
            if m and int(m.group(1)) > 0:
                found.append((el, int(m.group(1))))
        except Exception:
            pass
    return found


def card_of(el):
    try:
        return el.find_element(By.XPATH, "./ancestor::*[contains(., 'per accepted entry')][1]")
    except Exception:
        return el.find_element(By.XPATH, "./../../..")


def pick_button(card):
    best = (None, "")
    for b in card.find_elements(By.XPATH, ".//button | .//a"):
        try:
            if not (b.is_displayed() and b.is_enabled()):
                continue
            label = (b.text or "").strip()
            if not label or "reference" in label.lower():
                continue
            if ACTION_RE.search(label):
                return b, label
            if best[0] is None:
                best = (b, label)
        except Exception:
            pass
    return best


def old_style_button(driver):
    for el in driver.find_elements(By.XPATH, OLD_BUTTON_XPATH):
        try:
            if el.is_displayed() and el.is_enabled():
                return el, "Save a spot"
        except Exception:
            pass
    return None, ""


def click(driver, btn):
    try:
        btn.click()
    except Exception:
        driver.execute_script("arguments[0].click();", btn)


def watch():
    tg("Spot watcher v4 started.")
    driver = None
    errors = 0
    alerted_login = False
    alerted_trouble = False
    last_open_alert = 0

    while True:
        try:
            if driver is None:
                driver = make_driver()

            driver.get(URL)
            if not wait_for_logged_in(driver):
                if not alerted_login:
                    driver.save_screenshot(DEBUG_SHOT)
                    seen = page_text(driver)[:300].replace("\n", " | ")
                    tg(f"Not seeing the dashboard.\nPage: {driver.current_url}\nText: {seen}", DEBUG_SHOT)
                    alerted_login = True
            else:
                alerted_login = False
                wait_for_cards(driver)

                btn, label, n, card_html = None, "", 0, ""
                cards = open_cards(driver)
                if cards:
                    el, n = cards[0]
                    card = card_of(el)
                    btn, label = pick_button(card)
                    try:
                        card_html = card.get_attribute("outerHTML") or ""
                    except Exception:
                        pass
                if btn is None:
                    btn, label = old_style_button(driver)

                if btn is not None:
                    click(driver, btn)
                    time.sleep(2.5)
                    driver.save_screenshot(SHOT)
                    sent = False
                    for _ in range(5):
                        if tg(f"Clicked '{label}'. Check the screenshot and finish the task!", SHOT):
                            sent = True
                            break
                    print("Clicked. Telegram sent:", sent)
                    if STOP_AFTER_CLAIM:
                        break
                elif cards and time.time() - last_open_alert > 60:
                    driver.save_screenshot(DEBUG_SHOT)
                    tg("SPOTS AVAILABLE but I couldn't find the button. Open the site NOW!", DEBUG_SHOT)
                    tg("Card code (send this to Claude):\n" + re.sub(r"\s+", " ", card_html)[:2500])
                    last_open_alert = time.time()

            if alerted_trouble:
                tg("Connection is back. Watching normally again.")
                alerted_trouble = False
            errors = 0

        except Exception as e:
            errors += 1
            print(f"Error {errors}:", str(e)[:150])
            if errors >= RESTART_AFTER_ERRORS:
                print("Reopening Chrome...")
                safe_quit(driver)
                driver = None
                time.sleep(10)
            if errors == 5 and not alerted_trouble:
                tg("Bot is having trouble (probably internet). It keeps retrying by itself.", tries=2)
                alerted_trouble = True

        time.sleep(random.uniform(MIN_WAIT, MAX_WAIT))

    safe_quit(driver)


def login():
    driver = make_driver()
    try:
        driver.get(URL)
        input("Log in in the Chrome window, then come back here and press Enter... ")
        print("Login saved.")
    finally:
        safe_quit(driver)


if __name__ == "__main__":
    if "--login" in sys.argv:
        login()
    else:
        watch()

