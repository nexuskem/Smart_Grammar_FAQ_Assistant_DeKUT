#!/usr/bin/env python3
"""
start_whatsapp_bot.py
──────────────────────────────────────────────────────────────────────────────
DeKUT CS & IT Smart FAQ Assistant — One-Command WhatsApp Bot Launcher

WHAT THIS SCRIPT DOES
─────────────────────
1. Validates your .env configuration.
2. Starts the Django development server (port 8000) in the background.
3. Opens an ngrok HTTPS tunnel to port 8000.
4. Automatically registers the tunnel URL as the Twilio webhook
   using the Twilio REST API (no manual console steps needed).
5. Prints a live status dashboard and keeps everything running.
6. On CTRL-C: gracefully shuts down Django and the tunnel.

REQUIREMENTS
────────────
  pip install pyngrok        ← ngrok Python wrapper
  ngrok authtoken <token>    ← one-time setup (free at ngrok.com)

USAGE
─────
  python3 start_whatsapp_bot.py
  python3 start_whatsapp_bot.py --port 8080   # use a different port
  python3 start_whatsapp_bot.py --no-twilio   # skip webhook registration

──────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

# ── Colour helpers ─────────────────────────────────────────────────────────────

RESET  = "\033[0m"
BOLD   = "\033[1m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
BLUE   = "\033[94m"

def ok(msg):  print(f"  {GREEN}✓{RESET} {msg}")
def warn(msg): print(f"  {YELLOW}⚠{RESET}  {msg}")
def err(msg): print(f"  {RED}✗{RESET} {msg}")
def info(msg): print(f"  {CYAN}→{RESET} {msg}")
def banner(msg): print(f"\n{BOLD}{BLUE}{msg}{RESET}\n")


# ── Locate project root ────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent


# ── Step 0: Load .env ─────────────────────────────────────────────────────────

def load_env():
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        err(f".env file not found at {env_path}")
        err("Run:  cp .env.example .env   then fill in your credentials.")
        sys.exit(1)

    # Use python-dotenv if available, else parse manually
    try:
        from dotenv import load_dotenv, set_key
        load_dotenv(env_path, override=True)
        return env_path  # return path so we can use set_key later
    except ImportError:
        # Manual minimal parser
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    os.environ.setdefault(key.strip(), value.strip())
        return env_path


# ── Step 1: Validate credentials ──────────────────────────────────────────────

def validate_env(skip_twilio: bool = False):
    banner("① Validating configuration …")

    issues = []

    secret = os.getenv("DJANGO_SECRET_KEY", "")
    if not secret or "insecure" in secret.lower():
        issues.append("DJANGO_SECRET_KEY is not set or uses the insecure default.")
    else:
        ok("DJANGO_SECRET_KEY is set.")

    if not skip_twilio:
        account_sid = os.getenv("TWILIO_ACCOUNT_SID", "")
        auth_token  = os.getenv("TWILIO_AUTH_TOKEN", "")
        wa_number   = os.getenv("TWILIO_WHATSAPP_NUMBER", "")

        if not account_sid.startswith("AC"):
            issues.append("TWILIO_ACCOUNT_SID is missing or invalid (must start with 'AC').")
        else:
            ok(f"TWILIO_ACCOUNT_SID: {account_sid[:10]}…")

        if len(auth_token) < 10:
            issues.append("TWILIO_AUTH_TOKEN looks too short — double check your .env.")
        else:
            ok("TWILIO_AUTH_TOKEN is set.")

        if not wa_number.startswith("whatsapp:+"):
            issues.append("TWILIO_WHATSAPP_NUMBER must be in format  whatsapp:+<number>")
        else:
            ok(f"TWILIO_WHATSAPP_NUMBER: {wa_number}")

    openai_key = os.getenv("OPENAI_API_KEY", "")
    if openai_key:
        ok("OPENAI_API_KEY is set → voice + GPT-4o refinement enabled.")
    else:
        warn("OPENAI_API_KEY not set → running in offline/CFG-only mode (text only).")

    if issues:
        print()
        err("Configuration errors found:")
        for issue in issues:
            print(f"     • {issue}")
        print()
        err("Fix the above in your .env file then re-run this script.")
        sys.exit(1)

    print()
    ok("All required credentials are present.")


# ── Step 2: Start Django dev server ───────────────────────────────────────────

def start_django(port: int, extra_env: dict | None = None) -> subprocess.Popen:
    banner(f"② Starting Django server on port {port} …")

    python = sys.executable
    manage = PROJECT_ROOT / "manage.py"

    # Merge current environment with any overrides (e.g. updated ALLOWED_HOSTS)
    env = {**os.environ}
    if extra_env:
        env.update(extra_env)

    proc = subprocess.Popen(
        [python, str(manage), "runserver", f"0.0.0.0:{port}", "--noreload"],
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
    )

    # Give it 3 seconds to start
    time.sleep(3)
    if proc.poll() is not None:
        out, _ = proc.communicate()
        err("Django failed to start:")
        print(out)
        sys.exit(1)

    ok(f"Django is running  (PID {proc.pid})  →  http://127.0.0.1:{port}/")
    return proc


# ── Step 3: Open ngrok tunnel ─────────────────────────────────────────────────

def start_tunnel(port: int) -> str:
    banner("③ Opening ngrok tunnel …")

    try:
        from pyngrok import ngrok, conf  # type: ignore
    except ImportError:
        err("pyngrok is not installed.")
        print()
        print("  Install it with:")
        print(f"    pip install pyngrok")
        print()
        print("  Then get a free authtoken at  https://ngrok.com  and run:")
        print("    ngrok authtoken <your-token>")
        print()
        sys.exit(1)

    # Open an HTTPS tunnel
    try:
        tunnel = ngrok.connect(port, "http")
    except Exception as exc:
        err(f"ngrok tunnel failed: {exc}")
        print()
        print("  Make sure you have configured an authtoken:")
        print("    ngrok authtoken <your-token>")
        sys.exit(1)

    public_url = tunnel.public_url
    # ngrok always gives http:// — force https
    if public_url.startswith("http://"):
        public_url = "https://" + public_url[7:]

    ok(f"Tunnel is live  →  {public_url}")
    return public_url


# ── Step 4: Register webhook with Twilio ──────────────────────────────────────

def register_twilio_webhook(public_url: str):
    banner("④ Registering Twilio webhook …")

    webhook_url = public_url.rstrip("/") + "/webhook/whatsapp/"
    account_sid = os.getenv("TWILIO_ACCOUNT_SID", "")
    auth_token  = os.getenv("TWILIO_AUTH_TOKEN", "")
    wa_number   = os.getenv("TWILIO_WHATSAPP_NUMBER", "")

    # Extract the raw number (strip "whatsapp:" prefix)
    raw_number = wa_number.replace("whatsapp:", "").strip()

    try:
        from twilio.rest import Client  # type: ignore
    except ImportError:
        warn("twilio package not installed — skipping automatic webhook registration.")
        warn(f"Set it manually in the Twilio Console:")
        warn(f"  URL: {webhook_url}")
        return

    try:
        client = Client(account_sid, auth_token)

        # Find the incoming phone number resource
        numbers = client.incoming_phone_numbers.list(phone_number=raw_number)
        if numbers:
            resource = numbers[0]
            resource.update(
                sms_url=webhook_url,
                sms_method="POST",
            )
            ok(f"Webhook set on phone number {raw_number}")
        else:
            # Try messaging services / sandbox approach
            warn(f"Phone number {raw_number} not found in your account.")
            warn("If you are using the Twilio Sandbox, set the webhook manually:")
            print()
            print(f"    {BOLD}{webhook_url}{RESET}")
            print()
            print("  Twilio Console → Messaging → Try it out → Send a WhatsApp message")
            print("  → 'When a message comes in' field → paste the URL above → Save.")
            return

        ok(f"Webhook URL: {webhook_url}")

    except Exception as exc:
        warn(f"Could not auto-register webhook: {exc}")
        warn(f"Set it manually in the Twilio Console:")
        print(f"\n    {BOLD}{webhook_url}{RESET}\n")


# ── Step 5: Update .env with public URL ───────────────────────────────────────

def update_env_url(env_path: Path, public_url: str):
    """Patch PUBLIC_BASE_URL in .env in-place (unquoted, so Django parses it cleanly)."""
    try:
        from dotenv import set_key  # type: ignore
        # quote_mode='never' prevents python-dotenv from wrapping values in quotes
        set_key(str(env_path), "PUBLIC_BASE_URL", public_url, quote_mode="never")
        ok(f"PUBLIC_BASE_URL updated in .env → {public_url}")
    except Exception as exc:
        warn(f"Could not update .env automatically: {exc}")
        warn(f"Add this to your .env manually:  PUBLIC_BASE_URL={public_url}")


# ── Step 6: Dashboard ─────────────────────────────────────────────────────────

def print_dashboard(public_url: str, port: int):
    webhook = public_url.rstrip("/") + "/webhook/whatsapp/"
    health  = public_url.rstrip("/") + "/health/"
    query   = public_url.rstrip("/") + "/api/query/"

    print()
    print("─" * 70)
    print(f"{BOLD}{GREEN}  🎓 DeKUT FAQ WhatsApp Bot is LIVE{RESET}")
    print("─" * 70)
    print(f"  {BOLD}Public URL  {RESET}  {public_url}")
    print(f"  {BOLD}Webhook     {RESET}  {webhook}")
    print(f"  {BOLD}Health      {RESET}  {health}")
    print(f"  {BOLD}API Query   {RESET}  {query}")
    print("─" * 70)
    print()
    print(f"  {YELLOW}WhatsApp Test:{RESET}")
    print(f"    Send a message to  {os.getenv('TWILIO_WHATSAPP_NUMBER', '<your-number>')}")
    print(f"    from your personal WhatsApp account.")
    print()
    print(f"  {YELLOW}Quick API test:{RESET}")
    print(f"    curl -X POST {query} \\")
    print(f"      -H 'Content-Type: application/json' \\")
    print(f'      -d \'{{"query": "I failed SCS 3304. Am I eligible for supplementary?", "sender": "test"}}\'')
    print()

    offline = not os.getenv("OPENAI_API_KEY", "").strip()
    if offline:
        print(f"  {YELLOW}Mode: OFFLINE (CFG only){RESET} — voice notes disabled.")
        print(f"  Add OPENAI_API_KEY to .env to enable Whisper STT + GPT-4o refinement.")
    else:
        print(f"  {GREEN}Mode: ONLINE{RESET} — Whisper STT + GPT-4o refinement enabled.")

    print()
    print(f"  Press  {BOLD}CTRL-C{RESET}  to stop the bot.")
    print("─" * 70)
    print()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="DeKUT FAQ WhatsApp Bot Launcher",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--port",       type=int, default=8000, help="Local port for Django (default: 8000)")
    parser.add_argument("--no-twilio",  action="store_true",   help="Skip Twilio webhook registration")
    parser.add_argument("--no-tunnel",  action="store_true",   help="Skip ngrok tunnel (use existing PUBLIC_BASE_URL)")
    args = parser.parse_args()

    print()
    print(f"{BOLD}{BLUE}{'═' * 70}{RESET}")
    print(f"{BOLD}{BLUE}   🎓 DeKUT CS & IT Smart FAQ Assistant — WhatsApp Bot Launcher{RESET}")
    print(f"{BOLD}{BLUE}{'═' * 70}{RESET}")

    # --- Load environment ---
    env_path = load_env()

    # --- Validate ---
    validate_env(skip_twilio=args.no_twilio)

    public_url = ""
    extra_env  = {}

    # --- Tunnel FIRST (so we know the hostname before Django starts) ---
    if args.no_tunnel:
        public_url = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
        if not public_url:
            err("--no-tunnel specified but PUBLIC_BASE_URL is not set in .env.")
            sys.exit(1)
        info(f"Using existing public URL: {public_url}")
    else:
        public_url = start_tunnel(args.port)
        update_env_url(env_path, public_url)

        # Pass updated ALLOWED_HOSTS directly to Django subprocess env
        from urllib.parse import urlparse
        host = urlparse(public_url).hostname or ""
        current = os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
        if host and host not in current:
            extra_env["DJANGO_ALLOWED_HOSTS"] = current.rstrip(",") + "," + host
        extra_env["PUBLIC_BASE_URL"] = public_url

    # --- Start Django (after tunnel, so ALLOWED_HOSTS includes the ngrok host) ---
    django_proc = start_django(args.port, extra_env=extra_env)

    # --- Register Twilio webhook ---
    if not args.no_twilio:
        register_twilio_webhook(public_url)

    # --- Dashboard ---
    print_dashboard(public_url, args.port)

    # --- Keep alive ---
    def shutdown(sig, frame):
        print(f"\n  {YELLOW}Shutting down …{RESET}")
        django_proc.terminate()
        try:
            from pyngrok import ngrok  # type: ignore
            ngrok.kill()
        except Exception:
            pass
        print(f"  {GREEN}Bot stopped cleanly.{RESET}\n")
        sys.exit(0)

    signal.signal(signal.SIGINT,  shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # Forward Django output to terminal while waiting
    try:
        for line in django_proc.stdout:  # type: ignore
            sys.stdout.write(line)
    except Exception:
        pass

    django_proc.wait()


if __name__ == "__main__":
    main()
