import requests
from urllib.parse import urlparse, parse_qs
from bs4 import BeautifulSoup
from .jsparser import JsParser

class LoginRequestsSender():
    def extract_redirect_url_from_html(self, html_content: str) -> str:
        soup = BeautifulSoup(html_content, 'html.parser')
        # Find script defer="defer"
        script_tag = soup.find('script', {'defer': 'defer'})
        if script_tag and 'src' in script_tag.attrs:
            return script_tag['src']
        
        # Fallback: Find any main script
        for s in soup.find_all('script'):
            if s.get('src') and ('main' in s['src'] or 'account' in s['src']):
                return s['src']
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
            "x-xsrf-token": session.cookies.get("XSRF-TOKEN")
        }
        return session.post(url, json=payload, headers=headers)

    def get_app_auth_token(self, session, api_url):
        # This is where we get the actual Bearer token
        # We need to construct the authorize URL carefully
        subdomain = urlparse(api_url).netloc.split('.')[0]
        params = {
            "client_id": f"M6-{subdomain}.magister.net",
            "redirect_uri": f"https://{subdomain}.magister.net/oidc/redirect_callback.html",
            "response_type": "id_token token",
            "scope": "openid profile grades.read grades.manage calendar.user", # Shortened for brevity
            "state": "123", "nonce": "456"
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
        
    def get_api_url(self, session, token):
        # We need this to get the subdomain
        # Standard Magister trick: check host-meta
        return "https://magister.net" # Placeholder, usually dynamically fetched