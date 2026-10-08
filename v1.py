"""
SubsGigs spot watcher (Chrome version).

Usage (from the folder this file is in):
    python3 spot_bot_chrome.py --test    # sends a test Telegram message
    python3 spot_bot_chrome.py --login   # opens Chrome so you log in once
    python3 spot_bot_chrome.py           # starts watching
"""
import random
import sys
import time
from pathlib import Path

import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

# ---------- EDIT THESE ----------
TG_TOKEN = "PASTE_BOT_TOKEN_HERE"
TG_CHAT_ID = "PASTE_CHAT_ID_HERE"
URL = "https://subsgigs-alpha.vercel.app/campaigns"
MIN_WAIT, MAX_WAIT = 5, 10      # seconds between checks (random in this range)
HEADLESS = False                # False = you can see the Chrome window
STOP_AFTER_CLAIM = True         # stop after the first successful click
# --------------------------------

HERE = Path(__file__).parent
PROFILE_DIR = str(HERE / "chrome-profile")    # keeps your login between runs
SHOT = str(HERE / "claimed.png")

LOWER = "abcdefghijklmnopqrstuvwxyz"
UPPER = LOWER.upper()
BUTTON_XPATH = (
    "//*[self::button or self::a]"
    f"[contains(translate(normalize-space(.), '{UPPER}', '{LOWER}'), 'save a spot')]"
)


def tg(text, photo=None):
    base = f"https://api.telegram.org/bot{TG_TOKEN}"
    try:
        if photo:
            with open(photo, "rb") as f:
                requests.post(f"{base}/sendPhoto", data={"chat_id": TG_CHAT_ID, "caption": text},
                              files={"photo": f}, timeout=20)
        else:
            requests.post(f"{base}/sendMessage", data={"chat_id": TG_CHAT_ID, "text": text}, timeout=20)
    except Exception as e:
        print("Telegram error:", e)


def make_driver(headless):
    opts = Options()
    opts.add_argument(f"--user-data-dir={PROFILE_DIR}")
    opts.add_argument("--window-size=1200,900")
    if headless:
        opts.add_argument("--headless=new")
    return webdriver.Chrome(options=opts)


def page_text(driver):
    try:
        return driver.find_element(By.TAG_NAME, "body").text.lower()
    except Exception:
        return ""


def wait_for_logged_in(driver, seconds=10):
    """The dashboard shows a 'Log out' button when you're logged in."""
    end = time.time() + seconds
    while time.time() < end:
        if "log out" in page_text(driver):
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
    driver = make_driver(HEADLESS)
    try:
        tg("Spot watcher started.")
        errors = 0
        logged_out_alerted = False

        while True:
            try:
                driver.get(URL)
                if not wait_for_logged_in(driver):
                    if not logged_out_alerted:
                        tg("You look logged out. Run: python3 spot_bot_chrome.py --login")
                        logged_out_alerted = True
                else:
                    logged_out_alerted = False
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
                print("Error:", e)
                if errors == 5:
                    tg(f"Bot is hitting errors: {e}")

            time.sleep(random.uniform(MIN_WAIT, MAX_WAIT))
    finally:
        driver.quit()


def login():
    driver = make_driver(False)
    try:
        driver.get(URL)
        input("Log in in the Chrome window, then come back here and press Enter... ")
        print("Login saved.")
    finally:
        driver.quit()


if __name__ == "__main__":
    if "--test" in sys.argv:
        tg("Test message from your spot bot. Telegram works!")
        print("Sent (check Telegram).")
    elif "--login" in sys.argv:
        login()
    else:
        watch()