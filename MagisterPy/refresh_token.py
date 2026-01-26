import asyncio
from auth import MagisterAuth
from main import SCHOOL, USERNAME, PASSWORD, TOKEN_FILE

async def refresh_my_token():
    print(f"😒 Waking up the headless browser to fetch a token for {USERNAME}...")

    if not PASSWORD:
        print("🛑 You didn't set a password in main.py. This script is now useless.")
        return

    auth = MagisterAuth(SCHOOL, USERNAME, PASSWORD)
    
    try:
        token = await auth.get_token()
        
        with open(TOKEN_FILE, "w") as f:
            f.write(token)
            
        print(f"🎉 New token acquired and dumped into '{TOKEN_FILE}'.")
        
    except Exception as e:
        print(f"💀 Failed to refresh token. Error: {e}")

if __name__ == "__main__":
    asyncio.run(refresh_my_token())