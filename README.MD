# ![Image](magisterpy.png)

# MagisterPy

**The unofficial, stealthy, and slightly aggressive Magister wrapper.**

Let's be real: checking Magister manually is for people who don't know how to code. This bot automates the anxiety of waiting for grades by checking them for you, 24/7, and screaming at you via Discord when something happens.

## ✨ Features that keep you un-banned

- **Stealth Mode:** Uses a heavily modified headless Chromium browser to bypass Magister's "Are you a robot?" checks. We lie to the server and tell it we are a human on a Windows laptop.
- **Discord Notifications:** Get instant alerts for:
  - 📊 **New Grades**
  - 📅 **Schedule Changes**
  - 📧 **New Emails**
- **Dockerized:** Runs in a container so you can host it on a server and touch grass.
- **Sleep Schedule:** The bot pauses between **01:00 and 06:00** so you don't get flagged for suspicious activity (and so you can sleep).
- **Jitter:** Randomized check intervals so the traffic looks organic, not robotic.

---

## 🐳 Docker Method (Recommended)

If you are running this on a proper server with Docker, you can use this method.

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
    volumes:
      - ./magister_data:/app/data
```

### 2. Launch

Run the following command. Note the space between `docker` and `compose`.

```bash
docker compose up --build -d

```

### 3. Verify

Check if the bot is actually working or if it crashed immediately:

```bash
docker logs -f magister_surveillance

```

---

## 💻 The System Library Method

If you want to run this locally:

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
DISCORD_WEBHOOK=[https://discord.com/api/webhooks/YOUR_WEBHOOK](https://discord.com/api/webhooks/YOUR_WEBHOOK)
TOKEN_FILE=access_token.txt

```

### 3. Run the Server

```bash
python3 server.py

```

---

## ⚠️ Disclaimer & Legal Stuff

**This tool is not endorsed by, affiliated with, or liked by Magister.**

Using automated scripts to access Magister may violate their Terms of Service. I am not responsible if your account gets banned, suspended, or if your school IT admin gives you a dirty look in the hallway.

**Use responsibly.**

- The bot sleeps at night for a reason.
- The check interval has "jitter" (random delay) for a reason.
- Don't remove these safety features unless you want an IP ban.

## 🐛 Troubleshooting

**"It says `MagisterPy not found`"**
You didn't install the package. Run `pip install .` in the root folder.

**"It gets stuck on `Navigating to...`"**
Magister is blocking you. The `auth.py` script tries to hide the `navigator.webdriver` flag, but sometimes their security gets tighter. Try running it again later.

**"My password is in the logs!"**
Stop sharing your screen.
