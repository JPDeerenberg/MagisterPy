import asyncio
import os
import hashlib
import httpx
from datetime import date, timedelta

from client import MagisterClient
from auth import MagisterAuth
from main import SCHOOL, USERNAME, PASSWORD, TOKEN_FILE

DISCORD_WEBHOOK = ""
CHECK_INTERVAL = 60

state = {
    "seen_grade_ids": set(),
    "seen_message_ids": set(),
    "schedule_hashes": {},
    "initialized": False 
}

async def send_discord_notification(text: str):
    """Sends a message to Discord. No content, just the alert."""
    if "YOUR_ID" in DISCORD_WEBHOOK:
        print(f"⚠️ Discord Webhook not configured. Logged: {text}")
        return

    async with httpx.AsyncClient() as client:
        try:
            payload = {"content": text}
            await client.post(DISCORD_WEBHOOK, json=payload)
        except Exception as e:
            print(f"❌ Failed to send Discord notification: {e}")

async def refresh_session():
    """Runs the headless browser to get a fresh token."""
    print("🔄 Token expired. Refreshing session...")
    try:
        auth = MagisterAuth(SCHOOL, USERNAME, PASSWORD)
        token = await auth.get_token()
        
        with open(TOKEN_FILE, "w") as f:
            f.write(token)
        print("✅ Token refreshed successfully.")
        return token
    except Exception as e:
        print(f"💀 Critical Failure: Could not refresh token. {e}")
        return None

def compute_appointment_hash(appt):
    """Creates a unique signature for an appointment to detect changes."""
    data = f"{appt.id}-{appt.start}-{appt.end}-{appt.location}-{appt.description}-{appt.completed}"
    return hashlib.md5(data.encode()).hexdigest()

async def check_updates():
    if not os.path.exists(TOKEN_FILE):
        print("❌ No token file found. Running refresh...")
        token = await refresh_session()
    else:
        with open(TOKEN_FILE, "r") as f:
            token = f.read().strip()

    if not token:
        return

    try:
        async with MagisterClient(SCHOOL, token) as m:
            
            grades = await m.get_grades(limit=10) 
            current_grade_ids = {g.id for g in grades}
            
            new_grades = [g for g in grades if g.id not in state["seen_grade_ids"]]
            
            if new_grades and state["initialized"]:
                for g in new_grades:
                    print(f"🔔 New Grade detected for {g.subject.description}")
                    await send_discord_notification(f"📊 **New Grade** posted for **{g.subject.description}**.")
            
            state["seen_grade_ids"].update(current_grade_ids)


            folders = await m.get_folders()
            inbox = next((f for f in folders if "Postvak IN" in f.name), None)
            
            if inbox:
                messages = await m.get_messages(inbox.id, limit=10)
                current_msg_ids = {msg.id for msg in messages}
                
                new_msgs = [msg for msg in messages if msg.id not in state["seen_message_ids"]]
                
                if new_msgs and state["initialized"]:
                    for msg in new_msgs:
                        print(f"🔔 New Message from {msg.sender_name}")
                        await send_discord_notification(f"📧 **New Message** received from **{msg.sender_name}**.")
                
                state["seen_message_ids"].update(current_msg_ids)


            today = date.today()
            tomorrow = today + timedelta(days=1)
            appointments = await m.get_schedule(today, tomorrow)
            
            current_hashes = {}
            for appt in appointments:
                h = compute_appointment_hash(appt)
                current_hashes[appt.id] = h
                
                if state["initialized"] and appt.id in state["schedule_hashes"]:
                    if state["schedule_hashes"][appt.id] != h:
                        print(f"🔔 Schedule change detected: {appt.description}")
                        await send_discord_notification(f"📅 **Schedule Update**: '{appt.description}' has been modified.")
            
            state["schedule_hashes"] = current_hashes

            if not state["initialized"]:
                print(f"✅ Initialized. Monitoring {len(state['seen_grade_ids'])} grades, {len(state['seen_message_ids'])} msgs, {len(state['schedule_hashes'])} appts.")
                state["initialized"] = True

    except Exception as e:
        err_str = str(e)
        if "401" in err_str or "403" in err_str:
            print("🔒 Token seems invalid. Triggering refresh...")
            await refresh_session()
        else:
            print(f"⚠️ Error during check: {e}")

async def run_server():
    print("🚀 Magister Surveillance Server Started.")
    print("   Press Ctrl+C to stop (if you can find it).")
    
    while True:
        await check_updates()
        await asyncio.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        print("\n👋 Server stopped. Have a nice life.")