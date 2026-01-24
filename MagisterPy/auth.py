import asyncio
import time
from urllib.parse import urlparse, parse_qs
from playwright.sync_api import sync_playwright

class MagisterAuth:
    def __init__(self, school_url: str, username: str, password: str):
        self.school_url = school_url
        self.username = username
        self.password = password

    async def get_token(self) -> str:
        """
        Async wrapper for the synchronous browser flow. 
        Keeps main.py happy while we do the heavy lifting in a thread.
        """
        return await asyncio.to_thread(self._browser_login_flow)

    def _browser_login_flow(self) -> str:
        print("⚡ Launching Headless Browser (The modern way)...")
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()

            try:
                print(f"   Navigating to {self.school_url}...")
                page.goto(self.school_url)

                print("   Entering Username...")
                page.wait_for_selector('input[id*="username"], input[name*="username"]', state="visible")
                page.fill('input[id*="username"], input[name*="username"]', self.username)
                
                if page.is_visible('button[id*="submit"], button[type="submit"]'):
                    page.click('button[id*="submit"], button[type="submit"]')
                else:
                    page.keyboard.press("Enter")

                print("   Entering Password...")
                page.wait_for_selector('input[id*="password"], input[name*="password"]', state="visible")
                page.fill('input[id*="password"], input[name*="password"]', self.password)
                
                if page.is_visible('button[id*="submit"], button[type="submit"]'):
                    page.click('button[id*="submit"], button[type="submit"]')
                else:
                    page.keyboard.press("Enter")

                print("   Waiting for dashboard...")
                page.wait_for_url("**/vandaag**", timeout=30000)

                print("   Authorizing API Scopes...")
                
                subdomain = urlparse(self.school_url).netloc.split('.')[0]
                
                oauth_url = (
                    "https://accounts.magister.net/connect/authorize"
                    f"?client_id=M6-{subdomain}.magister.net"
                    f"&redirect_uri=https://{subdomain}.magister.net/oidc/redirect_callback.html"
                    "&response_type=id_token%20token"
                    "&scope=openid%20profile%20grades.read%20grades.manage%20calendar.user"
                    "&state=123&nonce=456"
                )

                page.goto(oauth_url)
                
                page.wait_for_url("**/oidc/redirect_callback.html*", timeout=10000)
                
                current_url = page.url
                if "access_token=" in current_url:
                    start = current_url.find("access_token=") + 13
                    end = current_url.find("&", start)
                    if end == -1:
                        token = current_url[start:]
                    else:
                        token = current_url[start:end]
                    
                    print("✅ Access Granted. Token captured.")
                    return token
                else:
                    raise ValueError("Redirected, but no access_token found in URL.")

            except Exception as e:
                print(f"❌ Browser Login Failed: {e}")
                try:
                    page.screenshot(path="login_failure.png")
                    print("   📸 Screenshot saved to login_failure.png")
                except:
                    pass
                raise e
            finally:
                browser.close()