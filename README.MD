# ![MagisterPy](magisterpy.png)

# MagisterPy 🕵️‍♂️

**The unofficial, stealthy, and slightly aggressive Magister wrapper.**

Let's be real: checking Magister manually is for people who don't know how to code. This bot automates the anxiety of waiting for grades by checking them for you, 24/7, and screaming at you via Discord when something happens.

## ✨ Features that keep you un-banned

- **Stealth Mode:** Uses a heavily modified headless Chromium browser to bypass Magister's "Are you a robot?" checks. We lie to the server and tell it we are a human on a Windows laptop.
- **Discord Notifications:** Get instant alerts for:
  - 📊 **New Grades:** Find out you failed math before your teacher even closes the tab.
  - 📅 **Schedule Changes:** Detects **New**, **Cancelled**, and **Moved** lessons automatically.
  - 📧 **New Emails:** Because who actually checks their school email?
- **Session Persistence:** Saves your login cookies (`browser_state.json`) so it doesn't have to log in every time.
- **Sleep Schedule:** The bot pauses between **01:00 and 06:00** (configurable) so you don't get flagged for suspicious activity.
- **Jitter:** Randomized check intervals so the traffic looks organic, not robotic.

---

## 🐳 The "I Have a Server" Method (Recommended)

If you are running this on a proper server (Ubuntu/Debian) with Docker, you are winning.

### 1. Clone & Configure

Clone the repo and open `docker-compose.yml`. You need to set your secrets here.

```yaml
version: "3.8"
services:
  magister-bot:
    container_name: magister_surveillance
    build: .
    restart: unless-stopped
    environment:
      - SCHOOL=https://YOUR_SCHOOL.magister.net
      - USERNAME=your_magister_username
      - PASSWORD=your_super_secret_password
      - DISCORD_WEBHOOK=[https://discord.com/api/webhooks/YOUR_WEBHOOK_URL](https://discord.com/api/webhooks/YOUR_WEBHOOK_URL)
      - TOKEN_FILE=/app/data/access_token.txt
      # Configurable Sleep & Check Times
      - SLEEP_START=23 # 11 PM
      - SLEEP_END=6 # 6 AM
      - CHECK_INTERVAL=120 # Check every 120 seconds (2 mins)
    volumes:
      - ./magister_data:/app/data
```

### 2. Launch

Run the following command. Note the space between `docker` and `compose`.

```bash
docker compose up --build -d

```

### 3. Verify & Watch Logs

Check the logs to see the bot in action. You will see it navigating the Microsoft login flow in real-time.

```bash
docker logs -f magister_surveillance

```

---

## 💻 The "I Run This on My Laptop" Method

If you want to run this locally like a savage:

### 1. Install Dependencies

You need Python 3.9+. Install the package and the browser binaries.

```bash
# Install the library and dependencies
pip install .

# Install the browser binary (Chromium) because we need it to login
playwright install chromium

```

### 2. Create the `.env` file

Create a file named `.env` in the root folder (next to `server.py`). **Do not commit this to GitHub.**

```ini
SCHOOL=https://YOUR_SCHOOL.magister.net
USERNAME=your_username
PASSWORD=your_password
DISCORD_WEBHOOK=https://discord.com/api/webhooks/YOUR_WEBHOOK
TOKEN_FILE=access_token.txt
SLEEP_START=1
SLEEP_END=6
CHECK_INTERVAL=300

```

### 3. Run the Server

```bash
python3 server.py

```

---

## 📜 Log Guide

When you look at the logs (`docker logs -f magister_surveillance`), here is what you are seeing:

- **[Auth] 🚀 Launching Headless Browser...**
  The bot is starting up the invisible browser.
- **[Auth] 🌍 Opening https://...**
  It is navigating to your school's login page.
- **[Auth] 👤 Filling in Username / ✍️ Filling in Password**
  It is typing your credentials just like a human would.
- **[Auth] 💾 Session saved**
  It successfully logged in and saved the cookies. The next time it runs, it will skip the login screen entirely!
- **[14:05:00] 💤 Sleeping...**
  It's past your bedtime (defined in `SLEEP_START`). The bot is hibernating.

---

## ⚠️ Disclaimer & Legal Stuff

**This tool is not endorsed by, affiliated with, or liked by Magister.**

Using automated scripts to access Magister may violate their Terms of Service. I am not responsible if your account gets banned, suspended, or if your school IT admin gives you a dirty look in the hallway.

**Use responsibly.**

- The bot sleeps at night for a reason.
- The check interval has "jitter" (random delay) for a reason.
- Don't remove these safety features unless you want an IP ban.
