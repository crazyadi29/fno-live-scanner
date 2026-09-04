"""
FYERS API v3 Token Generator
----------------------------
Run this script once every morning (or set it to run automatically).
Requires:
  pip install requests
"""
import sys
import webbrowser
from urllib.parse import urlparse, parse_qs
import requests
import hashlib

def generate_fyers_token():
    print("=" * 60)
    print("          FYERS API v3 DAILY TOKEN GENERATOR")
    print("=" * 60)
    
    app_id = input("Enter Fyers App ID (e.g. XC12345-100): ").strip()
    secret_key = input("Enter Fyers Secret Key: ").strip()
    redirect_uri = input("Enter Redirect URI configured in Fyers portal (default: https://trade.fyers.in/api-login/redirect-uri/index.html): ").strip()
    if not redirect_uri:
        redirect_uri = "https://trade.fyers.in/api-login/redirect-uri/index.html"

    # Step 1: Open Login URL in Browser
    auth_url = f"https://api-t1.fyers.in/api/v3/generate-authcode?client_id={app_id}&redirect_uri={redirect_uri}&response_type=code&state=fno_pulse"
    print("\nOpening Fyers Login page in your browser...")
    webbrowser.open(auth_url)

    print("\nAfter logging in with your PIN/OTP, your browser will redirect to a URL.")
    auth_code_or_url = input("\nPaste the redirected URL (or the auth_code value): ").strip()

    # Extract auth_code if full URL was pasted
    if "auth_code=" in auth_code_or_url:
        parsed = urlparse(auth_code_or_url)
        auth_code = parse_qs(parsed.query).get("auth_code", [""])[0]
    else:
        auth_code = auth_code_or_url

    if not auth_code:
        print("Error: Could not extract auth_code!")
        sys.exit(1)

    # Step 2: Generate SHA-256 AppIdHash
    app_id_hash = hashlib.sha256(f"{app_id}:{secret_key}".encode('utf-8')).hexdigest()

    # Step 3: Exchange auth_code for Access Token
    token_url = "https://api-t1.fyers.in/api/v3/validate-authcode"
    payload = {
        "grant_type": "authorization_code",
        "appIdHash": app_id_hash,
        "code": auth_code
    }

    resp = requests.post(token_url, json=payload)
    if resp.status_code == 200:
        data = resp.json()
        access_token = data.get("access_token")
        print("\n" + "=" * 60)
        print("✅ SUCCESS! YOUR FYERS DAILY ACCESS TOKEN:")
        print("=" * 60)
        print(f"\n{access_token}\n")
        print("=" * 60)
        print("Copy and paste this token into your scanner dashboard under 'Connect Broker & Settings'.")
    else:
        print(f"❌ Failed to generate token: {resp.text}")

if __name__ == "__main__":
    generate_fyers_token()
