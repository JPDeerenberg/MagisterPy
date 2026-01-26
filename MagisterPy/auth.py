import asyncio
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

class MagisterAuth:
    def __init__(self, school_url: str, username: str, password: str):
        self.school_url = school_url
        self.username = username
        self.password = password

    async def get_token(self) -> str:
        return await asyncio.to_thread(self._browser_login_flow)

    def _browser_login_flow(self) -> str:
        print("⚡ Launching Browser (Stealth Mode)...")
        
        with sync_playwright() as p:
            # 1. Launch with minimal arguments to avoid flagging
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled", # Hides "Chrome is being controlled by software"
                    "--disable-gpu"
                ]
            )
            
            # 2. Create a context that looks like a real laptop
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1366, "height": 768},
                locale="nl-NL",
                timezone_id="Europe/Amsterdam"
            )

            # 3. CRITICAL: Inject script to delete the 'webdriver' property
            # This is the specific flag Magister checks to see if you are a bot.
            context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)

            page = context.new_page()

            try:
                print(f"   Navigating to {self.school_url}...")
                # We wait for 'networkidle' to ensure the heavy Login JS actually loads
                page.goto(self.school_url, wait_until="networkidle", timeout=60000)

                # --- STEP 1: USERNAME ---
                print("   Looking for Username input...")
                
                # We search for ANY input field first, because the ID might have changed.
                # This is more robust than looking for specific names.
                try:
                    # Wait up to 30s for the form to render
                    page.wait_for_selector('input', state="visible", timeout=30000)
                except:
                    # If it fails, we try one desperate reload
                    print("   ⚠️ Input not found. Retrying with reload...")
                    page.reload(wait_until="networkidle")
                    page.wait_for_selector('input', state="visible", timeout=30000)

                # Now we figure out WHICH input it is
                if page.is_visible('input[name="loginfmt"]'):
                    print("   ✅ Identified Microsoft Login")
                    page.fill('input[name="loginfmt"]', self.username)
                elif page.is_visible('input[name="username"]'):
                    print("   ✅ Identified Magister Login")
                    page.fill('input[name="username"]', self.username)
                else:
                    # Fallback: Fill the first visible input field found
                    print("   ⚠️ Unknown Login Form. Trying first input...")
                    page.fill('input:visible', self.username)

                print("   Clicking Next...")
                page.keyboard.press("Enter")
                
                # --- STEP 2: PASSWORD ---
                print("   Waiting for Password...")
                page.wait_for_timeout(2000) # Wait for animation
                
                # Wait specifically for a password type input
                page.wait_for_selector('input[type="password"]', state="visible", timeout=30000)
                page.fill('input[type="password"]', self.password)
                
                print("   Logging in...")
                page.keyboard.press("Enter")

                # --- STEP 3: CLEANUP & TOKEN ---
                print("   Waiting for Dashboard...")
                # Check for "Stay Signed In" screen and skip it blindly
                try:
                    page.wait_for_selector('text=Aangemeld blijven', timeout=4000)
                    page.keyboard.press("Enter")
                except:
                    pass

                page.wait_for_url("**/vandaag", timeout=60000)

                print("   Starting OAuth Handshake...")
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
                page.wait_for_url("**/oidc/redirect_callback.html*", timeout=30000)
                
                current_url = page.url
                if "access_token=" in current_url:
                    start = current_url.find("access_token=") + 13
                    end = current_url.find("&", start)
                    token = current_url[start:] if end == -1 else current_url[start:end]
                    print("✅ Token Captured.")
                    return token
                else:
                    fragment = urlparse(current_url).fragment
                    if "access_token=" in fragment:
                        start = fragment.find("access_token=") + 13
                        end = fragment.find("&", start)
                        token = fragment[start:] if end == -1 else fragment[start:end]
                        print("✅ Token Captured (Hash).")
                        return token

                    raise ValueError("Token not found in URL")

            except Exception as e:
                print(f"❌ Login Failed: {e}")
                # Save screenshot if possible
                try: page.screenshot(path="login_failed.png")
                except: pass
                raise e
            finally:
                browser.close()