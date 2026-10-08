# Campaign Spot Watcher

A small Python bot that watches a first-come-first-served campaign page, saves a spot for you the moment one opens, and sends the result to your phone through Telegram. It runs on a computer that stays on, and your phone just receives the alerts.

Built for the SubsGigs creator dashboard, but the idea (watch a page, click the button when a spot opens, notify) works for any similar page with a few selector tweaks.

> **Disclaimer:** This is a personal automation project. It is not affiliated with or endorsed by any platform. Automated claiming may be against a site's rules and could get your account limited or banned. Read the site's terms (or ask its admins) before using it. You use it at your own risk.

## What it does

- Reloads the campaigns page every 5-10 seconds (random, to stay gentle on the site)
- Detects an open campaign and clicks the **Save a spot** button
- Sends you a Telegram message with a screenshot
- Keeps working through internet drops (v3+)
- Tells you whether the spot actually looks saved (v5)

## Versions

| File | Version | What it adds |
|------|---------|--------------|
| `bot_auto.py` | v3 | Looks for a button labelled "Save a spot". Retries Telegram messages, reopens Chrome by itself after repeated errors, gives up on hung pages after 30s. |
| `bot_fast.py` | v4 | Detects open campaigns by reading each card's "N spots currently available" text, then clicks the labelled button inside that card, so the exact button label doesn't matter. If it can't find a button it still alerts you and sends the card's HTML so it can be fixed. |
| `bot_verify.py` | v5 | After clicking, reloads the page and checks the same campaign again, then sends a second message: **LOOKS SAVED**, **NOT SAVED (probably)** or **UNSURE**. Remembers clicked campaigns in `claimed_campaigns.txt` so a restart never clicks the same one twice. |

Use **v5 (`bot_verify.py`)** unless you have a reason not to. v5 is the newest and has had the least real-world testing.

## Requirements

- Python 3.9 or newer
- Google Chrome installed
- A Telegram account
- A computer that stays on and awake while the bot runs (a laptop with the lid open and plugged in works)

Developed and run on macOS. It should work on Windows and Linux too, but that's untested.

## Setup

### 1. Install

```bash
git clone <your-repo-url>
cd <your-repo-folder>
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Selenium downloads the matching Chrome driver automatically the first time it runs.

### 2. Create your Telegram bot

1. In Telegram, message **@BotFather** and send `/newbot`. Follow the prompts. It gives you a **token**.
2. Open your new bot and send it any message (like "hi"). Bots can't message you until you've messaged them first.
3. In a browser, open `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`. Find `"chat":{"id":` and copy the number. That's your **chat ID**.

### 3. Add your settings

```bash
cp config.example.json config.json
```

Then edit `config.json` and fill in your token and chat ID. This file is in `.gitignore`. **Never commit it.** Anyone with your token can control your bot. (You can also use the environment variables `TG_TOKEN` and `TG_CHAT_ID` instead.)

### 4. Log in once

```bash
python3 bot_verify.py --login
```

A Chrome window opens. Log in to the site, wait until you see your dashboard, then press Enter in the terminal. Your login is saved in a local `chrome-profile/` folder (also gitignored, since it holds your session).

### 5. Run it

```bash
python3 bot_verify.py
```

You should get "Spot watcher v5 started." in Telegram. Leave the terminal and the Chrome window it opened running (minimize them, don't close them). Keep the computer plugged in and awake. On macOS you can run `caffeinate -d` in a second terminal tab.

Press **Ctrl + C** to stop it.

## Telegram messages you'll see

| Message | Meaning |
|---------|---------|
| Spot watcher v5 started. | The bot is running. |
| Clicked '...'. Checking if it saved... | It clicked the button. Screenshot attached. |
| LOOKS SAVED / NOT SAVED / UNSURE | The v5 verdict. Always double-check on the site. |
| SPOTS AVAILABLE but I couldn't find the button | Go claim it by hand now. The card's HTML is sent so the selector can be fixed. |
| Not seeing the dashboard | Your login likely expired. Run `--login` again. |
| Bot is having trouble | Probably an internet drop. It keeps retrying by itself. |

## Settings

Near the top of each script:

- `MIN_WAIT, MAX_WAIT` - seconds between checks (default 5-10). Lower values react faster but put more load on the site and raise the chance of being rate-limited or flagged.
- `STOP_AFTER_CLAIM` - stop after the first click (default `True`) so it can't claim twice.
- `URL` - the campaigns page to watch.

## How detection works

v4 and v5 read each campaign card's text (for example "2 requirements · 10 spots currently available") and treat any card with more than 0 spots as open. They then click the first enabled button with a text label inside that card (preferring labels like save, claim or join) and ignore icon-only buttons and "Open reference" links.

If the site's layout changes, the likeliest things to update are the `SPOTS_RE` pattern, the `"per accepted entry"` text used to find a card, and `ACTION_RE`.

## Limitations

- It needs a real Chrome window, so it can't run on a phone. Use a computer or a cheap always-on cloud server, and let your phone receive the Telegram alerts.
- Chrome must stay open. Closing the bot's window will make it reopen one, but it can't run while the computer sleeps or the internet is down.
- The v5 verdict is a best guess based on what the page shows, not a confirmation from the site.
- It won't solve CAPTCHAs, and it isn't designed to.

## Security notes

- Keep `config.json` and `chrome-profile/` out of Git. The included `.gitignore` already does this.
- If you ever leak your bot token (a screenshot, a commit), revoke it with `/revoke` in @BotFather and use the new one.
