import asyncio
import os
import json
import datetime
from pathlib import Path


try:
    from MagisterPy import MagisterClient, MagisterAuth
except ImportError:
    print("❌ CRITICAL: MagisterPy not found. Make sure you are in the right folder.")
    exit(1)


try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

SCHOOL = os.getenv('SCHOOL')
USERNAME = os.getenv('USERNAME')
PASSWORD = os.getenv('PASSWORD')
TOKEN_FILE = "access_token.txt"
DUMP_DIR = "magister_dump"


class MagisterJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime.date, datetime.datetime)):
            return obj.isoformat()
        if hasattr(obj, "__dict__"):
            return obj.__dict__
        return super().default(obj)

def save_json(filename, data):
    Path(DUMP_DIR).mkdir(parents=True, exist_ok=True)
    filepath = Path(DUMP_DIR) / filename
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, cls=MagisterJSONEncoder, indent=4, ensure_ascii=False)
        print(f"✅ Saved {filename}")
    except Exception as e:
        print(f"❌ Failed to save {filename}: {e}")

async def get_fresh_token():
    print("🔄 Refreshing your dusty token...")
    auth = MagisterAuth(SCHOOL, USERNAME, PASSWORD)
    try:
        token = await auth.get_token()
        with open(TOKEN_FILE, 'w') as f:
            f.write(token)
        return token
    except Exception as e:
        print(f"💀 Login failed hard: {e}")
        exit(1)

async def main():
    if not all([SCHOOL, USERNAME, PASSWORD]):
        print("❌ Bro, check your .env file. You're missing credentials.")
        return

    
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'r') as f:
            token = f.read().strip()
    else:
        token = await get_fresh_token()

    print(f"--- 🗑️ Dumping Magister Data for {USERNAME} ---")

    
    for attempt in range(2):
        try:
            async with MagisterClient(SCHOOL, token) as client:
                
                
                print("📥 Fetching Profile...")
                
                resp = await client.client.get("/api/account")
                
                if resp.status_code == 401:
                    raise Exception("401 Unauthorized") 
                
                resp.raise_for_status()
                profile = resp.json()
                save_json("profile.json", profile)

                
                print("📥 Fetching Grades...")
                grades = await client.get_grades(limit=50)
                save_json("grades.json", grades)

                
                print("📥 Fetching Schedule...")
                today = datetime.date.today()
                
                schedule = await client.get_schedule(start=today, end=today + datetime.timedelta(days=7))
                save_json("schedule.json", schedule)

                
                print("📥 Fetching Messages...")
                folders = await client.get_folders()
                
                
                inbox = next((f for f in folders if "Postvak IN" in f.name), None)
                
                if inbox:
                    
                    messages = await client.get_messages(folder_id=inbox.id, limit=20)
                    save_json("messages.json", messages)
                else:
                    print("⚠️ Couldn't find an Inbox. Weird.")

                print("\n✨ Dump complete. Go check the 'magister_dump' folder.")
                break 

        except Exception as e:
            if "401" in str(e) and attempt == 0:
                print("🔒 Token is expired (bummer). Logging in again...")
                token = await get_fresh_token()
                
            else:
                print(f"💥 CRITICAL ERROR: {e}")
                break

if __name__ == "__main__":
    asyncio.run(main())