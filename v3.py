"""
SubsGigs spot watcher v3 (self-recovering). Reads your Telegram token and chat ID
from spot_bot_chrome.py in the same folder.

    python3 bot_auto.py --login   # log in once (same saved login as before)
    python3 bot_auto.py           # start watching

Improvements over bot.py:
  * Telegram messages are retried several times if the internet hiccups
  * if Chrome gets stuck or errors repeat, Chrome is closed and reopened automatically
  * pages that hang are given up on after 30 seconds instead of 2 minutes
"""
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
RESTART_AFTER_ERRORS = 3        # reopen Chrome after this many errors in a row

HERE = Path(__file__).parent
PROFILE_DIR = str(HERE / "chrome-profile")
SHOT = str(HERE / "claimed.png")
DEBUG_SHOT = str(HERE / "debug.png")

_old = (HERE / "spot_bot_chrome.py").read_text()
TG_TOKEN = re.search(r'TG_TOKEN\s*=\s*"([^"]*)"', _old).group(1)
TG_CHAT_ID = re.search(r'TG_CHAT_ID\s*=\s*"([^"]*)"', _old).group(1)

LOWER = "abcdefghijklmnopqrstuvwxyz"
UPPER = LOWER.upper()
BUTTON_XPATH = (
    "//*[self::button or self::a]"
    f"[contains(translate(normalize-space(.), '{UPPER}', '{LOWER}'), 'save a spot')]"
)
LOGGED_IN_WORDS = ("log out", "my profile", "creator dashboard", "live campaigns")


def tg(text, photo=None, tries=4):
    """Send a Telegram message, retrying if the connection hiccups. Returns True if sent."""
    base = f"https://api.telegram.org/bot{TG_TOKEN}"
    for attempt in range(tries):
        try:
            if photo:
                with open(photo, "rb") as f:
                    r = requests.post(f"{base}/sendPhoto", data={"chat_id": TG_CHAT_ID, "caption": text[:1000]},
                                      files={"photo": f}, timeout=25)
            else:
                r = requests.post(f"{base}/sendMessage", data={"chat_id": TG_CHAT_ID, "text": text}, timeout=25)
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


def wait_for_logged_in(driver, seconds=15):
    end = time.time() + seconds
    while time.time() < end:
        if any(w in page_text(driver) for w in LOGGED_IN_WORDS):
            return True
        time.sleep(0.5)
    return False


def find_button(driver):
    for el in driver.find_elements(By.XPATH, BUTTON_XPATH):
        try:
            if el.is_displayed() and el.is_enabled():
                return el
        except Exception:
            pass
    return None


def watch():
    tg("Spot watcher v3 started.")
    driver = None
    errors = 0
    alerted_login = False
    alerted_trouble = False

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
                btn = find_button(driver)
                if btn:
                    try:
                        btn.click()
                    except Exception:
                        driver.execute_script("arguments[0].click();", btn)
                    time.sleep(2.5)
                    driver.save_screenshot(SHOT)
                    # keep trying to deliver this alert for a few minutes
                    sent = False
                    for _ in range(5):
                        if tg("Clicked 'Save a spot'. Check the screenshot and finish the task!", SHOT):
                            sent = True
                            break
                    print("Clicked. Telegram sent:" , sent)
                    if STOP_AFTER_CLAIM:
                        break

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

