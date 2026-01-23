import requests
from urllib.parse import urlparse, parse_qs
from .request_manager import LoginRequestsSender
from .magister_errors import *

class MagisterSession():
    def __init__(self):
        self.session = requests.Session()
        self.request_sender = LoginRequestsSender()
        self.app_auth_token = None

    def login(self, school, username, password):
        print("⚡ (Old Engine) Initializing Session...")
        
        # 1. Init
        resp = self.session.get("https://accounts.magister.net/", allow_redirects=True)
        
        # 2. Extract Params
        qs = parse_qs(urlparse(resp.url).query)
        session_id = qs.get('sessionId', [None])[0]
        return_url = qs.get('returnUrl', [None])[0]
        
        # 3. Get JS & AuthCode
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
        
        # 4. Challenges
        print("   Solving Challenges...")
        self.request_sender.set_school(self.session, school, payload)
        self.request_sender.set_username(self.session, username, payload)
        self.request_sender.set_password(self.session, password, payload)
        
        # 5. Get Token
        print("   Authorizing...")
        # Note: We need the school URL to generate the correct client_id
        # We assume school name matches subdomain for now, or we fetch it
        # Just passing a generic URL to trigger the logic
        token = self.request_sender.get_app_auth_token(self.session, f"https://{school}.magister.net")
        
        self.app_auth_token = token
        return token