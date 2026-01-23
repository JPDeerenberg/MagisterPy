import asyncio
import requests
import re
import json
from urllib.parse import urlparse, parse_qs
from bs4 import BeautifulSoup


class JsParser:
    def get_authcode_from_js(self, js_content: str):
        try:
            authcode_identifier = "].map((function(t))"
            end_column = js_content.find(authcode_identifier)
            
            if end_column == -1:
                authcode_identifier = "].map(function(t)"
                end_column = js_content.find(authcode_identifier)

            if end_column == -1:
                raise ValueError("Marker not found in JS.")

            buffer_size = 500
            snippet = js_content[max(0, end_column - buffer_size):end_column + len(authcode_identifier)]
            
            arrays = []
            arrays = []
            for match in re.finditer(r'\[(.*?)\]', snippet):
                try:
                    clean = match.group(0).replace("'", '"')
                    arr = json.loads(clean)
                    if isinstance(arr, list):
                        arrays.append(arr)
                except: 
                    pass

            if len(arrays) < 2:
                raise ValueError("Could not find obfuscated arrays.")

            indices = arrays[-1]
            chars = arrays[-2]
            
            indices = [int(x) for x in indices]
            
            authcode = "".join(str(chars[i]) for i in indices)
            return authcode

        except Exception as e:
            raise ValueError(f"Parser crashed: {e}")


class LoginRequestsSender:
    def extract_redirect_url_from_html(self, html_content: str) -> str:
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            script_tag = soup.find('script', {'defer': 'defer'})
            if script_tag and 'src' in script_tag.attrs:
                return script_tag['src']
            
            for s in soup.find_all('script'):
                if s.get('src') and ('main' in s['src'] or 'account' in s['src']):
                    return s['src']
        except:
            pass
        return None

    def extract_dynamic_authcode(self, js_content):
        return JsParser().get_authcode_from_js(js_content)

    def search_for_tenant_id(self, session, school_name, session_id):
        url = "https://accounts.magister.net/challenges/tenant/search"
        resp = session.get(url, params={"sessionId": session_id, "key": school_name})
        return resp.json()[0]["id"]

    def set_school(self, session, school_name, payload):
        tenant_id = self.search_for_tenant_id(session, school_name, payload["sessionId"])
        payload["tenant"] = tenant_id
        return self._post(session, payload, "https://accounts.magister.net/challenges/tenant")

    def set_username(self, session, username, payload):
        payload["username"] = username
        return self._post(session, payload, "https://accounts.magister.net/challenges/username")

    def set_password(self, session, password, payload):
        payload["password"] = password
        payload["userWantsToPairSoftToken"] = False
        return self._post(session, payload, "https://accounts.magister.net/challenges/password")

    def _post(self, session, payload, url):
        headers = {
            "content-type": "application/json",
            "x-xsrf-token": session.cookies.get("XSRF-TOKEN", "")
        }
        resp = session.post(url, json=payload, headers=headers)
        if not resp.ok:
            raise ValueError(f"Challenge failed ({url}): {resp.text}")
        return resp

    def get_app_auth_token(self, session, api_url):
        # This is where we get the actual Bearer token
        # We need to construct the authorize URL carefully
        subdomain = urlparse(api_url).netloc.split('.')[0]
        params = {
            "client_id": f"M6-{subdomain}.magister.net",
            "redirect_uri": f"https://{subdomain}.magister.net/oidc/redirect_callback.html",
            "response_type": "id_token token",
            "scope": "openid profile grades.read grades.manage calendar.user",
            "state": "123", 
            "nonce": "456"
        }
        url = "https://accounts.magister.net/connect/authorize"
        resp = session.get(url, params=params, allow_redirects=False)
        
        if "Location" in resp.headers:
            loc = resp.headers["Location"]
            if "access_token=" in loc:
                start = loc.find("access_token=") + 13
                end = loc.find("&", start)
                token = loc[start:end] if end != -1 else loc[start:]
                return f"Bearer {token}"
        return None


class MagisterAuth:
    def __init__(self, school_url: str, username: str, password: str):
        self.school_url = school_url  # Full URL like "https://hlml.magister.net"
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.request_sender = LoginRequestsSender()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        })

    async def get_token(self) -> str:
        return await asyncio.to_thread(self._sync_login_flow)

    def _sync_login_flow(self) -> str:
        print("⚡ Initializing Session...")
        
        resp = self.session.get("https://accounts.magister.net/", allow_redirects=True)
        
        qs = parse_qs(urlparse(resp.url).query)
        session_id = qs.get('sessionId', [None])[0]
        return_url = qs.get('returnUrl', [None])[0]
        
        if not session_id:
            print(f"DEBUG: Landed on {resp.url}")
            raise ValueError("❌ Failed to scrape Session ID")
        
        js_url = self.request_sender.extract_redirect_url_from_html(resp.text)
        if not js_url.startswith("http"):
            js_url = "https://accounts.magister.net" + js_url
            
        print(f"   Downloading JS: {js_url}")
        js_resp = self.session.get(js_url)
        auth_code = self.request_sender.extract_dynamic_authcode(js_resp.text)
        
        payload = {
            "authCode": auth_code,
            "sessionId": session_id,
            "returnUrl": return_url
        }
        
        print("   Solving Challenges...")
        school_name = urlparse(self.school_url).netloc.split('.')[0]
        self.request_sender.set_school(self.session, school_name, payload)
        self.request_sender.set_username(self.session, self.username, payload)
        self.request_sender.set_password(self.session, self.password, payload)
        
        print("   Authorizing...")
        token = self.request_sender.get_app_auth_token(self.session, self.school_url)
        
        if not token:
            raise ValueError("Login successful, but token not found.")
        
        print("✅ Access Granted.")
        return token