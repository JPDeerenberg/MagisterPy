import asyncio
import os
import hashlib
import httpx
import time
from datetime import date, timedelta

try:
    from MagisterPy import MagisterClient, MagisterAuth
except ImportError:
    print("❌ CRITICAL: MagisterPy not found. Did you run 'pip install .' inside the folder?")
    exit(1)

try:
    from main import SCHOOL as M_SCHOOL, USERNAME as M_USER, PASSWORD as M_PASS
except ImportError:
    M_SCHOOL, M_USER, M_PASS = "", "", ""

SCHOOL = os.getenv("SCHOOL", M_SCHOOL)
USERNAME = os.getenv("USERNAME", M_USER)
PASSWORD = os.getenv("PASSWORD", M_PASS)
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK", "YOUR_WEBHOOK_URL_HERE")

TOKEN_FILE = os.getenv("TOKEN_FILE", "access_token.txt")
CHECK_INTERVAL = 60

if os.path.dirname(TOKEN_FILE):
    os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)

state = {
    "seen_grade_ids": set(),
    "seen_message_ids": set(),
    "schedule_hashes": {},
    "initialized": False
}

async def send_discord_notification(text: str):
    """Sends a standardized alert to Discord."""
    if "YOUR_WEBHOOK" in DISCORD_WEBHOOK or not DISCORD_WEBHOOK:
        print(f"⚠️ [Discord Mock] {text}")
        return

    async with httpx.AsyncClient() as client:
        try:
            payload = {
                "username": "Magister Bot",
                "avatar_url": "https://i.imgur.com/bM8k8s6.png",
                "content": text
            }
            await client.post(DISCORD_WEBHOOK, json=payload)
        except Exception as e:
            print(f"❌ Failed to notify Discord: {e}")

async def refresh_session():
    """Uses Playwright to login and get a new token."""
    print(f"🔄 Refreshing token for {USERNAME}...")
    
    if not PASSWORD:
        print("💀 CRITICAL: No password provided. Cannot auto-refresh.")
        return None

    try:
        auth = MagisterAuth(SCHOOL, USERNAME, PASSWORD)
        token = await auth.get_token()
        
        with open(TOKEN_FILE, "w") as f:
            f.write(token)
            
        print("✅ Token refreshed and saved.")
        return token
    except Exception as e:
        print(f"💀 Login Failed: {e}")
        await send_discord_notification(f"⚠️ **Bot Error**: Failed to refresh Magister token. Fix me.")
        return None

def compute_appointment_hash(appt):
    """Generates a unique signature for a lesson to detect changes."""

    raw_data = f"{appt.id}|{appt.start}|{appt.end}|{appt.location}|{appt.description}|{appt.info_type}"
    return hashlib.md5(raw_data.encode()).hexdigest()

async def check_updates():
    """Main logic loop."""
    
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r") as f:
            token = f.read().strip()
    else:
        print("📂 No token file found. Initiating first login...")
        token = await refresh_session()

    if not token:
        return 

    try:
        async with MagisterClient(SCHOOL, token) as m:
            
            grades = await m.get_grades(limit=10)
            
            new_grades = [g for g in grades if g.id not in state["seen_grade_ids"]]
            
            if new_grades and state["initialized"]:
                for g in new_grades:
                    print(f"🔔 New Grade: {g.subject.description}")
                    await send_discord_notification(f"📊 **New Grade** posted for **{g.subject.description}**.")
            
            state["seen_grade_ids"].update(g.id for g in grades)


            folders = await m.get_folders()
            inbox = next((f for f in folders if "Postvak IN" in f.name), None)
            
            if inbox:
                msgs = await m.get_messages(inbox.id, limit=5)
                new_msgs = [msg for msg in msgs if msg.id not in state["seen_message_ids"]]
                
                if new_msgs and state["initialized"]:
                    for msg in new_msgs:
                        print(f"🔔 New Email from {msg.sender_name}")
                        await send_discord_notification(f"📧 **New Message** from **{msg.sender_name}**.")
                
                state["seen_message_ids"].update(msg.id for msg in msgs)


            today = date.today()
            tomorrow = today + timedelta(days=1)
            appointments = await m.get_schedule(today, tomorrow)
            
            current_hashes = {}
            for appt in appointments:
                h = compute_appointment_hash(appt)
                current_hashes[appt.id] = h
                
                if state["initialized"] and appt.id in state["schedule_hashes"]:
                    if state["schedule_hashes"][appt.id] != h:
                        print(f"🔔 Schedule Update: {appt.description}")
                        await send_discord_notification(f"📅 **Schedule Update**: Changes detected for **{appt.description}** ({appt.start.strftime('%H:%M')}).")
            
            state["schedule_hashes"] = current_hashes

            if not state["initialized"]:
                print(f"✅ Baseline established. Monitoring {len(state['seen_grade_ids'])} grades, {len(state['seen_message_ids'])} msgs.")
                await send_discord_notification("🚀 **Magister Bot Online**. Monitoring started.")
                state["initialized"] = True

    except Exception as e:
        error_str = str(e)
        if "401" in error_str or "403" in error_str:
            print("🔒 Token expired. Refreshing...")
            await refresh_session()
        else:
            print(f"⚠️ Check failed: {e}")

async def run_server():
    print("🚀 Magister Surveillance Server Started.")
    
    if not USERNAME or not PASSWORD:
        print("❌ CONFIG ERROR: SCHOOL, USERNAME, and PASSWORD are required.")
        print("   Set them in main.py OR as Environment Variables.")
        return

    while True:
        await check_updates()
        await asyncio.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        print("\n👋 Server stopped.")