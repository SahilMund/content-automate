"""
One-time script to get your LinkedIn access token.

Steps:
  1. Create a LinkedIn app at https://www.linkedin.com/developers/apps
  2. Add these products: "Share on LinkedIn" + "Sign In with LinkedIn using OpenID Connect"
  3. Set Redirect URL to: http://localhost:8080/callback
  4. Copy Client ID and Client Secret into .env
  5. Run:  python auth_linkedin.py
  6. A browser opens — log in and approve access
  7. Token is printed and saved to .env automatically
"""
import os
import secrets
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

import requests
from dotenv import load_dotenv, set_key

load_dotenv()

CLIENT_ID     = os.getenv("LINKEDIN_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("LINKEDIN_CLIENT_SECRET", "")
REDIRECT_URI  = "http://localhost:8080/callback"
SCOPES        = "openid profile w_member_social"
ENV_FILE      = os.path.join(os.path.dirname(__file__), ".env")

if not CLIENT_ID or not CLIENT_SECRET:
    print("ERROR: Set LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET in .env first.")
    sys.exit(1)

# ── Step 1: capture auth code via local server ────────────────

_auth_code: list[str] = []
_state = secrets.token_urlsafe(16)


class _CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        params = parse_qs(urlparse(self.path).query)
        returned_state = params.get("state", [None])[0]
        if returned_state != _state:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"<h1>Error: state mismatch. Try running the script again.</h1>")
            return
        if "code" in params:
            _auth_code.append(params["code"][0])
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"<h1>Auth complete! Return to your terminal.</h1>")
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"<h1>Error: no code in callback.</h1>")

    def log_message(self, *_):
        pass


server = HTTPServer(("localhost", 8080), _CallbackHandler)
t = threading.Thread(target=server.handle_request)
t.daemon = True
t.start()

# ── Step 2: open browser to LinkedIn auth page ────────────────

auth_url = "https://www.linkedin.com/oauth/v2/authorization?" + urlencode({
    "response_type": "code",
    "client_id":     CLIENT_ID,
    "redirect_uri":  REDIRECT_URI,
    "scope":         SCOPES,
    "state":         _state,
})

print(f"\nOpening browser for LinkedIn login…\nIf it doesn't open, visit:\n{auth_url}\n")
webbrowser.open(auth_url)

t.join(timeout=120)
server.server_close()

if not _auth_code:
    print("Timed out waiting for callback. Try again.")
    sys.exit(1)

# ── Step 3: exchange code for access token ────────────────────

resp = requests.post(
    "https://www.linkedin.com/oauth/v2/accessToken",
    data={
        "grant_type":    "authorization_code",
        "code":          _auth_code[0],
        "redirect_uri":  REDIRECT_URI,
        "client_id":     CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    },
    headers={"Content-Type": "application/x-www-form-urlencoded"},
)
if not resp.ok:
    print(f"\nToken exchange failed ({resp.status_code}):")
    print(resp.text)
    sys.exit(1)
token_data = resp.json()
access_token = token_data["access_token"]
expires_in   = token_data.get("expires_in", "unknown")

# ── Step 4: fetch user sub (needed for author URN) ────────────

me = requests.get(
    "https://api.linkedin.com/v2/userinfo",
    headers={"Authorization": f"Bearer {access_token}"},
)
me.raise_for_status()
sub = me.json()["sub"]

# ── Step 5: save to .env ──────────────────────────────────────

set_key(ENV_FILE, "LINKEDIN_ACCESS_TOKEN", access_token)
set_key(ENV_FILE, "LINKEDIN_USER_SUB", sub)

print("\n✅ LinkedIn auth complete!")
print(f"   User sub   : {sub}")
print(f"   Token saved to .env  (expires in {expires_in}s ≈ 60 days)")
print("\nYou're all set — run the bot normally now.")
