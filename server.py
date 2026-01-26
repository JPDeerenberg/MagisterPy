import asyncio
import os
import hashlib
import httpx
import random
import time
from datetime import date, timedelta, datetime

# Load the .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("📂 Loaded configuration from .env")
except ImportError:
    print("⚠️ python-dotenv not installed. Relying on system environment variables.")

try:
    from MagisterPy import MagisterClient, MagisterAuth
except ImportError:
    print("❌ CRITICAL: MagisterPy not found. Run 'pip install .' first.")
    exit(1)

# CONFIGURATION
SCHOOL = os.getenv("SCHOOL")
USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
TOKEN_FILE = os.getenv("TOKEN_FILE", "access_token.txt")

if not SCHOOL or not USERNAME or not PASSWORD:
    print("❌ CONFIG ERROR: Missing credentials in .env file.")
    exit(1)

if os.path.dirname(TOKEN_FILE):
    os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)

# STEALTH SETTINGS
BASE_INTERVAL = 60          
JITTER_RANGE = (-10, 40)    
SLEEP_START_HOUR = 1        
SLEEP_END_HOUR = 6          

# STATE
state = {
    "seen_grade_ids": set(),
    "seen_message_ids": set(),
    "schedule_hashes": {},
    "initialized": False
}

async def send_discord_notification(text: str):
    if "YOUR_WEBHOOK" in str(DISCORD_WEBHOOK) or not DISCORD_WEBHOOK:
        print(f"⚠️ [Mock Discord] {text}")
        return

    async with httpx.AsyncClient() as client:
        try:
            payload = {
                "username": "Magister Ninja",
                "content": text
            }
            await client.post(DISCORD_WEBHOOK, json=payload)
        except Exception as e:
            print(f"❌ Failed to notify Discord: {e}")

async def refresh_session():
    print(f"🔄 Refreshing token for {USERNAME}...")
    try:
        auth = MagisterAuth(SCHOOL, USERNAME, PASSWORD)
        token = await auth.get_token()
        with open(TOKEN_FILE, "w") as f:
            f.write(token)
        print("✅ Token refreshed.")
        return token
    except Exception as e:
        print(f"💀 Login Failed: {e}")
        await send_discord_notification(f"⚠️ **Bot Error**: Token refresh failed.")
        return None

def compute_appointment_hash(appt):
    # Using getattr for info_type to be safe if model isn't updated
    info = getattr(appt, "info_type", 0) 
    raw = f"{appt.id}|{appt.start}|{appt.end}|{appt.location}|{appt.description}|{info}"
    return hashlib.md5(raw.encode()).hexdigest()

def is_sleeping_hours():
    now = datetime.now().hour
    if SLEEP_START_HOUR <= now < SLEEP_END_HOUR:
        return True
    return False

async def check_updates():
    if not os.path.exists(TOKEN_FILE):
        token = await refresh_session()
    else:
        with open(TOKEN_FILE, "r") as f:
            token = f.read().strip()

    if not token: return

    try:
        async with MagisterClient(SCHOOL, token) as m:
            
            # 1. Grades
            grades = await m.get_grades(limit=10)
            new_grades = [g for g in grades if g.id not in state["seen_grade_ids"]]
            
            if new_grades and state["initialized"]:
                for g in new_grades:
                    print(f"🔔 New Grade: {g.subject.description}")
                    await send_discord_notification(f"📊 **New Grade**: {g.subject.description}")
            state["seen_grade_ids"].update(g.id for g in grades)

            # 2. Messages
            folders = await m.get_folders()
            inbox = next((f for f in folders if "Postvak IN" in f.name), None)
            if inbox:
                msgs = await m.get_messages(inbox.id, limit=5)
                new_msgs = [msg for msg in msgs if msg.id not in state["seen_message_ids"]]
                if new_msgs and state["initialized"]:
                    for msg in new_msgs:
                        print(f"🔔 New Mail: {msg.sender_name}")
                        await send_discord_notification(f"📧 **Mail**: From {msg.sender_name}")
                state["seen_message_ids"].update(msg.id for msg in msgs)

            # 3. Schedule
            today = date.today()
            appts = await m.get_schedule(today, today + timedelta(days=1))
            current_hashes = {}
            for appt in appts:
                h = compute_appointment_hash(appt)
                current_hashes[appt.id] = h
                if state["initialized"] and appt.id in state["schedule_hashes"]:
                    if state["schedule_hashes"][appt.id] != h:
                        print(f"🔔 Schedule Update: {appt.description}")
                        await send_discord_notification(f"📅 **Update**: {appt.description}")
            state["schedule_hashes"] = current_hashes

            if not state["initialized"]:
                print(f"✅ Monitoring initialized.")
                state["initialized"] = True

    except Exception as e:
        if "401" in str(e) or "403" in str(e):
            print("🔒 Token expired.")
            await refresh_session()
        else:
            print(f"⚠️ Error: {e}")

async def run_server():
    print("🚀 Magister Ninja Server Started.")
    
    while True:
        if is_sleeping_hours():
            print("💤 Zzz... (Sleeping mode active)")
            await asyncio.sleep(1800) 
            continue

        await check_updates()
        
        jitter = random.uniform(*JITTER_RANGE)
        sleep_time = BASE_INTERVAL + jitter
        print(f"⏳ Waiting {sleep_time:.1f}s...")
        await asyncio.sleep(sleep_time)

if __name__ == "__main__":
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        print("\n👋 Exiting.")