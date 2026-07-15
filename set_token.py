#!/usr/bin/env python3
"""
set_token.py — Quickly set your Twilio Auth Token in .env

Usage:
    python3 set_token.py <your-32-char-auth-token>

This is a convenience helper so you never have to open .env manually.
"""

import sys
from pathlib import Path

def main():
    if len(sys.argv) != 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        print("Usage:  python3 set_token.py <your-32-char-auth-token>")
        print()
        print("Get your token at: https://console.twilio.com")
        print("  Main Dashboard → Auth Token → click the 👁  eye icon to reveal it.")
        sys.exit(0 if "-h" in sys.argv else 1)

    token = sys.argv[1].strip()

    # Basic sanity checks
    if len(token) < 16:
        print(f"❌  Token is only {len(token)} characters — real Twilio Auth Tokens are 32 hex chars.")
        print("    Make sure you copied the full token from console.twilio.com.")
        sys.exit(1)

    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.exists():
        print(f"❌  .env file not found at {env_path}")
        sys.exit(1)

    # Read, replace, write
    content = env_path.read_text()
    lines = content.splitlines(keepends=True)
    updated = False

    with open(env_path, "w") as f:
        for line in lines:
            if line.startswith("TWILIO_AUTH_TOKEN="):
                f.write(f"TWILIO_AUTH_TOKEN={token}\n")
                updated = True
            else:
                f.write(line)

    if not updated:
        # Append if the key wasn't found
        with open(env_path, "a") as f:
            f.write(f"\nTWILIO_AUTH_TOKEN={token}\n")
        print(f"✅  TWILIO_AUTH_TOKEN added to .env")
    else:
        masked = token[:4] + "•" * (len(token) - 8) + token[-4:]
        print(f"✅  TWILIO_AUTH_TOKEN updated in .env  →  {masked}")

    print()
    print("Now launch the bot:")
    print("    python3 start_whatsapp_bot.py")


if __name__ == "__main__":
    main()
