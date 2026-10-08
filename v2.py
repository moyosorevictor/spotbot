"""
SubsGigs spot watcher v2 (Chrome). Reads your Telegram token and chat ID
from spot_bot_chrome.py in the same folder, so you don't paste them again.

    python3 bot.py --login   # log in once (same saved login as before)
    python3 bot.py           # start watching
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

HERE = Path(__file__).parent
PROFILE_DIR = str(HERE / "chrome-profile")
SHOT = str(HERE / "claimed.png")
DEBUG_SHOT = str(HERE / "debug.png")

# Pull Telegram settings from the old file so nothing needs re-pasting
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


def tg(text, photo=None):
    base = f"https://api.telegram.org/bot{TG_TOKEN}"
    try:
        if photo:
            with open(photo, "rb") as f:
                requests.post(f"{base}/sendPhoto", data={"chat_id": TG_CHAT_ID, "caption": text[:1000]},
                              files={"photo": f}, timeout=20)
        else:
            requests.post(f"{base}/sendMessage", data={"chat_id": TG_CHAT_ID, "text": text}, timeout=20)
    except Exception as e:
        print("Telegram error:", e)


def make_driver():
    opts = Options()
    opts.add_argument(f"--user-data-dir={PROFILE_DIR}")
    opts.add_argument("--window-size=1200,900")
    return webdriver.Chrome(options=opts)


def page_text(driver):
    try:
        return driver.find_element(By.TAG_NAME, "body").text.lower()
    except Exception:
        return ""


def wait_for_logged_in(driver, seconds=15):
    end = time.time() + seconds
    while time.time() < end:
        text = page_text(driver)
        if any(w in text for w in LOGGED_IN_WORDS):
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
    driver = make_driver()
    try:
        tg("Spot watcher v2 started.")
        errors = 0
        alerted = False
        while True:
            try:
                driver.get(URL)
                if not wait_for_logged_in(driver):
                    if not alerted:
                        driver.save_screenshot(DEBUG_SHOT)
                        seen = page_text(driver)[:300].replace("\n", " | ")
                        tg(f"Not seeing the dashboard.\nPage: {driver.current_url}\nText: {seen}", DEBUG_SHOT)
                        alerted = True
                else:
                    if alerted:
                        tg("Dashboard is back. Watching again.")
                    alerted = False
                    btn = find_button(driver)
                    if btn:
                        try:
                            btn.click()
                        except Exception:
                            driver.execute_script("arguments[0].click();", btn)
                        time.sleep(2.5)
                        driver.save_screenshot(SHOT)
                        tg("Clicked 'Save a spot'. Check the screenshot and finish the task!", SHOT)
                        print("Clicked. Done.")
                        if STOP_AFTER_CLAIM:
                            break
                errors = 0
            except Exception as e:
                errors += 1
                print("Error:", str(e)[:200])
                if errors == 5:
                    tg(f"Bot is hitting errors: {str(e)[:200]}")
            time.sleep(random.uniform(MIN_WAIT, MAX_WAIT))
    finally:
        driver.quit()


def login():
    driver = make_driver()
    try:
        driver.get(URL)
        input("Log in in the Chrome window, then come back here and press Enter... ")
        print("Login saved.")
    finally:
        driver.quit()


if __name__ == "__main__":
    if "--login" in sys.argv:
        login()
    else:
        watch()