import asyncio
import os
from client import MagisterClient
from auth import MagisterAuth

SCHOOL = ""
USERNAME = ""
PASSWORD = ""
TOKEN_FILE = "access_token.txt"

async def main():
    print(f"--- Login to {SCHOOL} ---")
    
    token = None

    if os.path.exists(TOKEN_FILE):
        print(f"📂 Found {TOKEN_FILE}, attempting to reuse session...")
        with open(TOKEN_FILE, "r") as f:
            token = f.read().strip()
    
    elif PASSWORD:
        print("🔑 Using hardcoded password (I hope nobody is looking over your shoulder)...")
        try:
            auth = MagisterAuth(SCHOOL, USERNAME, PASSWORD)
            token = await auth.get_token()
            with open(TOKEN_FILE, "w") as f:
                f.write(token)
        except Exception as e:
            print(f"🛑 Login Failed: {e}")
            return
            
    else:
        pw_input = input("Enter Password: ") 
        try:
            auth = MagisterAuth(SCHOOL, USERNAME, pw_input)
            token = await auth.get_token()
            with open(TOKEN_FILE, "w") as f:
                f.write(token)
        except Exception as e:
            print(f"🛑 Login Failed: {e}")
            return

    if not token:
        print("💀 No token, no service.")
        return

    async with MagisterClient(SCHOOL, token) as m:
        print("\n🚀 Systems Initialized.")

        print("\n📈 Checking Grades...")
        try:
            grades = await m.get_grades(limit=5)
            for g in grades:
                print(f"   - {g.subject.description}: {g.value} ({'Pass' if g.is_pass else 'Fail'})")
        except Exception as e:
            print(f"   ! Could not fetch grades: {e}")

        print("\n📧 Checking Inbox...")
        try:
            folders = await m.get_folders()
            inbox = next((f for f in folders if "Postvak IN" in f.name), None)
            
            if inbox and inbox.unread_count > 0:
                print(f"🔥 You have {inbox.unread_count} unread emails!")
                messages = await m.get_messages(inbox.id, limit=5)
                for msg in messages:
                    print(f"   - [{msg.sent_at.strftime('%d/%m')}] {msg.sender_name}: {msg.subject}")
            else:
                print("   No new mail. Silence is golden.")
        except Exception as e:
            print(f"   ! Could not fetch mail: {e}")

        print("\n💀 Checking Assignments...")
        try:
            assignments = await m.get_assignments(open_only=True)
            if assignments:
                for a in assignments:
                    print(f"   - ⚠️ DUE {a.deadline.strftime('%d-%m %H:%M')}: {a.title}")
            else:
                print("   You are free. For now.")
        except Exception as e:
            print(f"   ! Could not fetch assignments: {e}")

if __name__ == "__main__":
    asyncio.run(main())