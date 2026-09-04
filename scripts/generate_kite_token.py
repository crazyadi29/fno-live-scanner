"""
ZERODHA KITE CONNECT Token Generator
------------------------------------
Run this script every morning.
Requires:
  pip install requests
"""
import sys
import webbrowser
from urllib.parse import urlparse, parse_qs
import hashlib
import requests

def generate_kite_token():
    print("=" * 60)
    print("      ZERODHA KITE CONNECT DAILY TOKEN GENERATOR")
    print("=" * 60)

    api_key = input("Enter Kite API Key: ").strip()
    api_secret = input("Enter Kite API Secret: ").strip()

    # Step 1: Open Login URL
    login_url = f"https://kite.zerodha.com/connect/login?v=3&api_key={api_key}"
    print("\nOpening Zerodha Kite Login in your browser...")
    webbrowser.open(login_url)

    print("\nAfter logging in with Zerodha credentials & TOTP, you will be redirected to your redirect URL.")
    redirect_url_or_token = input("\nPaste the redirected URL (or request_token): ").strip()

    if "request_token=" in redirect_url_or_token:
        parsed = urlparse(redirect_url_or_token)
        request_token = parse_qs(parsed.query).get("request_token", [""])[0]
    else:
        request_token = redirect_url_or_token

    if not request_token:
        print("Error: Could not find request_token!")
        sys.exit(1)

    # Step 2: Calculate SHA-256 Checksum = sha256(api_key + request_token + api_secret)
    checksum = hashlib.sha256(f"{api_key}{request_token}{api_secret}".encode('utf-8')).hexdigest()

    # Step 3: Post to session/token
    token_url = "https://api.kite.trade/session/token"
    payload = {
        "api_key": api_key,
        "request_token": request_token,
        "checksum": checksum
    }

    resp = requests.post(token_url, data=payload)
    if resp.status_code == 200:
        data = resp.json()
        access_token = data.get("data", {}).get("access_token")
        print("\n" + "=" * 60)
        print("✅ SUCCESS! YOUR KITE DAILY ACCESS TOKEN:")
        print("=" * 60)
        print(f"\n{access_token}\n")
        print("=" * 60)
        print("Copy and paste this token into your scanner dashboard under 'Connect Broker & Settings'.")
    else:
        print(f"❌ Failed to generate Kite token: {resp.text}")

if __name__ == "__main__":
    generate_kite_token()
