import hashlib
import getpass
import json
from urllib.parse import urlencode

import requests

AUTH_URL = "https://api-t1.fyers.in/api/v3/generate-authcode"
TOKEN_URL = "https://api-t1.fyers.in/api/v3/validate-authcode"


def main():
    app_id = input("Fyers App ID: ").strip()
    app_secret = getpass.getpass("Fyers App Secret: ").strip()
    redirect_uri = input("Redirect URI registered in Fyers: ").strip()
    state = "fno-pulse"

    login_url = f"{AUTH_URL}?{urlencode({
        'client_id': app_id,
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'state': state,
    })}"
    print("\nOpen this URL in your browser and authorize the app:\n")
    print(login_url)
    print("\nAfter redirect, paste only the auth_code value.")
    auth_code = input("Auth code: ").strip()

    app_id_hash = hashlib.sha256(f"{app_id}:{app_secret}".encode()).hexdigest()
    response = requests.post(
        TOKEN_URL,
        json={
            "grant_type": "authorization_code",
            "appIdHash": app_id_hash,
            "code": auth_code,
        },
        timeout=15,
    )
    response.raise_for_status()
    payload = response.json()

    if payload.get("s") != "ok" or not payload.get("access_token"):
        print(json.dumps(payload, indent=2))
        raise SystemExit("Fyers did not return an access token")

    print("\nAdd this variable in Railway:")
    print(f"FYERS_APP_ID={app_id}")
    print(f"FYERS_ACCESS_TOKEN={payload['access_token']}")
    print("ACTIVE_ADAPTER=fyers")


if __name__ == "__main__":
    main()
