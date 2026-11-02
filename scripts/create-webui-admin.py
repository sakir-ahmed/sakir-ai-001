#!/usr/bin/env python3
"""Owner-run private onboarding; credentials never enter command arguments or logs."""
import getpass
import json
import urllib.error
import urllib.request


def main():
    print("Create your Open WebUI account privately on this server.")
    print("Only use this before the UI is published; first account becomes administrator.")
    email = input("Your login email: ").strip()
    password = getpass.getpass("New password (hidden): ")
    confirmation = getpass.getpass("Repeat password (hidden): ")
    if len(password) < 12 or password != confirmation:
        raise SystemExit("Use matching passwords of at least 12 characters; nothing submitted.")
    body = json.dumps({"email": email, "password": password,
                       "name": "Sakir", "profile_image_url": "/user.png"}).encode()
    request = urllib.request.Request("http://127.0.0.1:8082/api/v1/auths/signup",
                                     data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.load(response)
    except urllib.error.HTTPError as error:
        raise SystemExit(f"Account creation declined (HTTP {error.code}); no credentials printed.") from None
    user = result.get("user", result)
    role = user.get("role")
    if role != "admin":
        raise SystemExit("Administrator role not verified. Keep UI private and inspect existing accounts.")
    print("Administrator created. Keep password private. Disable further signups before publishing.")


if __name__ == "__main__":
    main()
