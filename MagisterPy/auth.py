import asyncio
import os
from urllib.parse import urlparse
from playwright.async_api import async_playwright

class MagisterAuth:
    def __init__(self, school_url: str, username: str, password: str, state_file: str = None):
        self.school_url = school_url
        self.username = username
        self.password = password
        self.state_file = state_file

    async def get_token(self) -> str:
        print(f"[Auth] 🚀 Launching Headless Browser...")
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-blink-features=AutomationControlled", "--disable-gpu"]
            )

            context_options = {
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "viewport": {"width": 1366, "height": 768},
                "locale": "nl-NL",
                "timezone_id": "Europe/Amsterdam"
            }

            if self.state_file and os.path.exists(self.state_file):
                print(f"[Auth] 🍪 Found session file: {self.state_file}")
                context = await browser.new_context(storage_state=self.state_file, **context_options)
            else:
                print(f"[Auth] 🆕 No session file found. Starting fresh.")
                context = await browser.new_context(**context_options)

            
            await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
            page = await context.new_page()

            try:
                
                subdomain = urlparse(self.school_url).netloc.split('.')[0]
                oauth_url = (
                    "https://accounts.magister.net/connect/authorize"
                    f"?client_id=M6-{subdomain}.magister.net"
                    f"&redirect_uri=https://{subdomain}.magister.net/oidc/redirect_callback.html"
                    "&response_type=id_token%20token"
                    "&scope=openid%20profile%20grades.read%20grades.manage%20calendar.user"
                    "&state=123&nonce=456"
                )

                
                print("[Auth] ⚡ Attempting Fast Login (Cookie Re-use)...")
                try:
                    await page.goto(oauth_url, wait_until="domcontentloaded", timeout=15000)
                    if "access_token=" in page.url:
                        print("[Auth] ✅ Fast Login Successful! Skipping UI.")
                        return self._extract_token(page.url)
                except:
                    print("[Auth] ⚠️ Fast Login failed/timed out.")

                
                if "account/login" in page.url or "challenge" in page.url:
                    print("[Auth] 🛡️ Starting Full Login Flow...")
                    await self._perform_full_login(page)
                    
                    print("[Auth] 🔄 Retrying OAuth Handshake...")
                    await page.goto(oauth_url, wait_until="domcontentloaded")
                    await page.wait_for_url("**/oidc/redirect_callback.html*", timeout=30000)

                
                token = self._extract_token(page.url)
                print("[Auth] 🔑 Token Captured.")
                
                if self.state_file:
                    await context.storage_state(path=self.state_file)
                    print(f"[Auth] 💾 Session saved to {self.state_file}")

                return token

            except Exception as e:
                print(f"[Auth] ❌ Error: {e}")
                raise e
            finally:
                await browser.close()

    async def _perform_full_login(self, page):
        if "login" not in page.url:
            print(f"[Auth] 🌍 Opening {self.school_url}...")
            await page.goto(self.school_url, wait_until="networkidle")

        
        print("[Auth] 🔎 Looking for Username field...")
        try:
            await page.wait_for_selector('input', state="visible", timeout=15000)
        except:
            print("[Auth] ⚠️ Input not found. Reloading page...")
            await page.reload()
            await page.wait_for_selector('input', state="visible", timeout=15000)

        print(f"[Auth] 👤 Filling in Username: {self.username}")
        if await page.is_visible('input[name="loginfmt"]'):
            await page.fill('input[name="loginfmt"]', self.username)
        elif await page.is_visible('input[name="username"]'):
            await page.fill('input[name="username"]', self.username)
        else:
            await page.fill('input:visible', self.username)

        print("[Auth] 🖱️ Pressing Next...")
        await page.keyboard.press("Enter")
        
        
        print("[Auth] 🔐 Waiting for Password field...")
        await page.wait_for_selector('input[type="password"]', state="visible", timeout=30000)
        await page.wait_for_timeout(1000)
        
        print("[Auth] ✍️ Filling in Password...")
        await page.fill('input[type="password"]', self.password)
        
        print("[Auth] 🚀 Logging in...")
        await page.keyboard.press("Enter")

        
        try:
            if await page.wait_for_selector('text=Aangemeld blijven', timeout=5000):
                print("[Auth] ⏩ Skipping 'Stay Signed In'...")
                await page.keyboard.press("Enter")
        except:
            pass
        
        print("[Auth] ⏳ Waiting for Dashboard...")
        await page.wait_for_url("**/vandaag", timeout=60000)
        print("[Auth] 🎉 Login Successful!")

    def _extract_token(self, url: str) -> str:
        if "access_token=" in url:
            start = url.find("access_token=") + 13
            end = url.find("&", start)
            return url[start:] if end == -1 else url[start:end]
        
        fragment = urlparse(url).fragment
        if "access_token=" in fragment:
            start = fragment.find("access_token=") + 13
            end = fragment.find("&", start)
            return fragment[start:] if end == -1 else fragment[start:end]
        
        raise ValueError("No access_token found in URL")