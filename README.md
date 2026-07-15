# 🎓 DeKUT CS & IT Smart FAQ Assistant

> **A WhatsApp-based FAQ bot for the School of Computer Science & IT at Dedan Kimathi University of Technology (DeKUT).**
> Students send text or voice messages to a WhatsApp number and receive instant, accurate replies from the Dean / Chair of Department (COD) — powered by an NLTK Context-Free Grammar parser with optional OpenAI refinement.

---

## 📋 Table of Contents

1. [How It Works](#how-it-works)
2. [Project Structure](#project-structure)
3. [Prerequisites](#prerequisites)
4. [Step-by-Step Setup](#step-by-step-setup)
   - [Step 1 — Clone the project](#step-1--clone-the-project)
   - [Step 2 — Create a virtual environment](#step-2--create-a-virtual-environment)
   - [Step 3 — Install dependencies](#step-3--install-dependencies)
   - [Step 4 — Configure environment variables](#step-4--configure-environment-variables)
   - [Step 5 — Run database migrations](#step-5--run-database-migrations)
   - [Step 6 — Validate the parser (offline test)](#step-6--validate-the-parser-offline-test)
   - [Step 7 — Set up ngrok](#step-7--set-up-ngrok)
   - [Step 8 — Launch the WhatsApp bot](#step-8--launch-the-whatsapp-bot)
   - [Step 9 — Register the Twilio webhook](#step-9--register-the-twilio-webhook)
   - [Step 10 — Test on WhatsApp](#step-10--test-on-whatsapp)
5. [API Endpoints](#api-endpoints)
6. [Intent Categories](#intent-categories)
7. [Validation Results](#validation-results)
8. [Production Deployment](#production-deployment)

---

## How It Works

```
Student (WhatsApp)
        │
        │  sends text or voice note
        ▼
   Twilio WhatsApp API
        │
        │  HTTP POST (webhook)
        ▼
   Django Server  (/webhook/whatsapp/)
        │
        ├─► Voice note? → OpenAI Whisper STT → text
        │
        ▼
   NLTK CFG ChartParser  (22 grammar rules)
        │
        ├─► Parse success (confidence 1.0) → canned Dean/COD response
        └─► Parse fail   → keyword-vote fallback (confidence 0.0–0.99)
        │
        ▼  (optional, if OPENAI_API_KEY is set)
   GPT-4o Refinement  → polished, personalised reply
        │
        ▼
   TwiML Response  → WhatsApp reply delivered to student
```

---

## 📁 Project Structure

```
FAQ/
├── assistant/
│   ├── dataset.py          # 40 student queries × 8 intent categories
│   ├── grammar_rules.py    # NLTK CFG (22 core rules, 110+ productions)
│   ├── parser.py           # ChartParser + keyword-vote fallback + response engine
│   ├── ai_services.py      # OpenAI Whisper STT, GPT-4o refinement, TTS
│   ├── views.py            # Twilio WhatsApp webhook + /api/query/ endpoint
│   ├── models.py           # ConversationLog Django model
│   ├── urls.py             # App-level URL routing
│   └── migrations/         # Auto-generated Django migrations
├── faq_assistant/
│   ├── settings.py         # Django settings (reads from .env)
│   ├── urls.py             # Root URL config
│   └── wsgi.py             # WSGI entry point (Gunicorn)
├── start_whatsapp_bot.py   # One-command launcher (Django + ngrok + Twilio)
├── setup_ngrok.sh          # Downloads ngrok binary
├── validate.py             # Offline CLI validator — runs all 40 test queries
├── manage.py               # Django management script
├── requirements.txt        # Python dependencies
├── .env.example            # Environment variable template
└── db.sqlite3              # SQLite database (auto-created on first migrate)
```

---

## ⚙️ Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.10+ | `python3 --version` |
| pip | latest | `pip --version` |
| Twilio account | — | Free at [twilio.com](https://www.twilio.com) |
| ngrok account | — | Free at [ngrok.com](https://ngrok.com) |
| OpenAI API key | — | **Optional** — enables voice + GPT-4o |

---

## 🚀 Step-by-Step Setup

### Step 1 — Clone the project

```bash
git clone https://github.com/nexuskem/Smart_Grammar_FAQ_Assistant_DeKUT.git
cd Smart_Grammar_FAQ_Assistant_DeKUT
```

---

### Step 2 — Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate        # Linux / macOS
# .venv\Scripts\activate         # Windows
```

You should see `(.venv)` at the start of your terminal prompt.

---

### Step 3 — Install dependencies

```bash
pip install -r requirements.txt
```

Expected output ends with:
```
Successfully installed django-4.2.x nltk-3.x twilio-9.x openai-2.x ...
```

---

### Step 4 — Configure environment variables

```bash
cp .env.example .env
```

Open `.env` in a text editor and fill in these values:

```ini
# ── Django ────────────────────────────────────────────────────────────────────
DJANGO_SECRET_KEY=<generate with: python3 -c "import secrets; print(secrets.token_urlsafe(50))">
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,.ngrok-free.app,.ngrok-free.dev,.ngrok.io

# ── Twilio ────────────────────────────────────────────────────────────────────
# Get these from: https://console.twilio.com  (main dashboard)
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx   # starts with AC
TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx      # 32-character hex string
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886            # your Twilio sandbox number

# ── OpenAI (optional) ─────────────────────────────────────────────────────────
# Leave blank to run in offline / CFG-only mode (text messages only)
# Set to enable: voice note transcription (Whisper) + GPT-4o response refinement
OPENAI_API_KEY=sk-...
```

> ⚠️ **Never commit `.env` to git.** It is listed in `.gitignore`.

**Where to find your Twilio credentials:**

1. Log in at [console.twilio.com](https://console.twilio.com)
2. The **Account SID** and **Auth Token** are on the main dashboard
3. Click the 👁 eye icon to reveal the Auth Token
4. The Auth Token is exactly **32 hexadecimal characters**

---

### Step 5 — Run database migrations

```bash
python3 manage.py makemigrations assistant
python3 manage.py migrate
```

Expected output:
```
Operations to perform:
  Apply all migrations: admin, assistant, auth, contenttypes, sessions
Running migrations:
  Applying assistant.0001_initial... OK
  ...
```

---

### Step 6 — Validate the parser (offline test)

Run this **before** setting up WhatsApp to confirm the CFG parser works correctly:

```bash
python3 validate.py --batch
```

Expected output:
```
════════════════════════════════════════════════════════════════════════
  BATCH RESULT:  40/40 correct  (100.0%)

  registration              ████████████████████  5/5  (100%)
  missing_marks             ████████████████████  6/6  (100%)
  graduation                ████████████████████  5/5  (100%)
  supplementary_exam        ████████████████████  5/5  (100%)
  recommendation_letter     ████████████████████  5/5  (100%)
  project_approval          ████████████████████  5/5  (100%)
  course_exemption          ████████████████████  5/5  (100%)
  general_inquiry           ████████████████████  4/4  (100%)
════════════════════════════════════════════════════════════════════════
```

You can also test a single query interactively:

```bash
python3 validate.py
# ❯ Your query: I need a recommendation letter for my internship at Safaricom
```

Or test one query directly:

```bash
python3 validate.py --query "How do I apply for a credit transfer?"
```

---

### Step 7 — Set up ngrok

ngrok creates a secure public HTTPS tunnel to your local Django server so Twilio can reach it.

**7a. Install ngrok**

```bash
bash setup_ngrok.sh
```

Or install manually from [ngrok.com/download](https://ngrok.com/download).

**7b. Get your free authtoken**

1. Sign up at [ngrok.com](https://ngrok.com) (free)
2. Go to [dashboard.ngrok.com/tunnels/authtokens](https://dashboard.ngrok.com/tunnels/authtokens)
3. Copy your authtoken

**7c. Save the authtoken**

```bash
ngrok config add-authtoken <YOUR_TOKEN_HERE>
```

---

### Step 8 — Launch the WhatsApp bot

This single command starts everything — Django server, ngrok tunnel, and Twilio webhook registration:

```bash
source .venv/bin/activate
python3 start_whatsapp_bot.py
```

You will see output like:

```
══════════════════════════════════════════════════════════════════════
   🎓 DeKUT CS & IT Smart FAQ Assistant — WhatsApp Bot Launcher
══════════════════════════════════════════════════════════════════════

① Validating configuration …
  ✓ DJANGO_SECRET_KEY is set.
  ✓ TWILIO_ACCOUNT_SID: AC1fc41551…
  ✓ TWILIO_AUTH_TOKEN is set.
  ✓ TWILIO_WHATSAPP_NUMBER: whatsapp:+254740873466
  ⚠  OPENAI_API_KEY not set → offline/CFG-only mode (text only).

② Opening ngrok tunnel …
  ✓ Tunnel is live → https://abc123.ngrok-free.app

③ Starting Django server on port 8000 …
  ✓ Django is running (PID 12345) → http://127.0.0.1:8000/

④ Registering Twilio webhook …
  ✓ Webhook set on phone number +254740873466

──────────────────────────────────────────────────────────────────────
  🎓 DeKUT FAQ WhatsApp Bot is LIVE
──────────────────────────────────────────────────────────────────────
  Public URL    https://abc123.ngrok-free.app
  Webhook       https://abc123.ngrok-free.app/webhook/whatsapp/
  Health        https://abc123.ngrok-free.app/health/
──────────────────────────────────────────────────────────────────────
```

> Press **CTRL-C** to stop the bot cleanly.

---

### Step 9 — Register the Twilio webhook

> **If Step 8 auto-registered the webhook (✓ shown), skip this step.**

If you see a warning about webhook registration (e.g. using the Twilio Sandbox), set it manually:

1. Go to **[Twilio Console → Messaging → Try it out → Send a WhatsApp message](https://console.twilio.com)**
2. Under **"Sandbox Configuration"**, find the field **"When a message comes in"**
3. Paste your webhook URL (shown in the Step 8 output):
   ```
   https://abc123.ngrok-free.app/webhook/whatsapp/
   ```
4. Set Method to **HTTP POST**
5. Click **Save**

**Also join the sandbox (one-time per student):**

Send this message from your WhatsApp to the Twilio sandbox number:
```
join <your-sandbox-keyword>
```
(The keyword is shown in the Twilio Console sandbox page.)

---

### Step 10 — Test on WhatsApp

Send any of these messages to your Twilio WhatsApp number:

| Type | Example message |
|---|---|
| Registration | `I want to register for units but the portal shows an error` |
| Missing marks | `My CAT marks for SCS 2301 are missing from the portal` |
| Supplementary | `I failed SCS 3304 with 35%. Am I eligible for a supplementary exam?` |
| Graduation | `What are the minimum requirements to graduate?` |
| Recommendation | `I need a reference letter for my internship at Safaricom` |
| Project approval | `How do I get my final year project topic approved?` |
| Credit transfer | `Can I transfer units from my diploma programme?` |
| General | `What are the office hours for the COD?` |

You should receive an instant reply within 2–3 seconds.

---

## 🌐 API Endpoints

Once the bot is running, these endpoints are available:

### Health check
```bash
curl https://your-ngrok-url.ngrok-free.app/health/
```
```json
{
  "status": "ok",
  "service": "DeKUT CS & IT FAQ Assistant",
  "ai_mode": "offline (CFG only)",
  "twilio_configured": true
}
```

### Direct text query (no WhatsApp needed — good for testing)
```bash
curl -X POST https://your-ngrok-url.ngrok-free.app/api/query/ \
  -H "Content-Type: application/json" \
  -d '{"query": "I failed SCS 3304 with 35%. Am I eligible for a supplementary exam?", "sender": "test-user"}'
```
```json
{
  "query": "I failed SCS 3304 with 35%...",
  "matched_rule": "S -> IntentNP",
  "category": "supplementary_exam",
  "confidence": 1.0,
  "ai_refined": false,
  "response": "Dear Student,\n\nSupplementary examinations are available..."
}
```

### WhatsApp webhook (called automatically by Twilio)
```
POST /webhook/whatsapp/
```

---

## 🧠 Intent Categories

| Intent | Example Query |
|---|---|
| `registration` | "I want to register for units but the portal shows an error" |
| `missing_marks` | "My CAT marks for SCS 2301 are not on the portal" |
| `graduation` | "What are the minimum graduation requirements?" |
| `supplementary_exam` | "I failed with 35%. Can I sit a supplementary exam?" |
| `recommendation_letter` | "I need a reference letter for my internship" |
| `project_approval` | "How do I get my FYP topic approved?" |
| `course_exemption` | "Can my diploma units be transferred?" |
| `general_inquiry` | "What are the office hours for the COD?" |

---

## ✅ Validation Results

| Metric | Value |
|---|---|
| Total queries tested | 40 / 40 |
| Correctly classified | **40 / 40 (100%)** |
| CFG parse hits | **40 / 40 (100%)** |
| Keyword-vote fallback used | 0 |
| Average parse time | < 1 ms |

---

## 🔧 Production Deployment (Gunicorn)

For a stable production server replace `manage.py runserver` with Gunicorn:

```bash
# Set production mode in .env
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=yourdomain.com

# Run with Gunicorn
gunicorn faq_assistant.wsgi:application --bind 0.0.0.0:8000 --workers 3
```

For a permanent public URL (no ngrok), deploy to:
- **Railway** — `railway up`
- **Render** — connect GitHub repo, set env vars in dashboard
- **Heroku** — `heroku create && git push heroku main`

Set `DJANGO_ALLOWED_HOSTS` to your deployment domain in the platform's environment variable settings.

---

## 📦 Dependencies

| Package | Purpose |
|---|---|
| `django>=4.2` | Web framework + webhook server |
| `twilio>=8.5` | WhatsApp webhook + TwiML responses |
| `openai>=1.30` | Whisper STT, GPT-4o refinement, TTS *(optional)* |
| `nltk>=3.8` | CFG ChartParser |
| `pydub>=0.25` | Audio format conversion (OGG → WAV) |
| `SpeechRecognition>=3.10` | Offline STT fallback |
| `python-dotenv>=1.0` | `.env` file loading |
| `requests>=2.31` | Media download from Twilio |
| `gunicorn>=21.2` | Production WSGI server |

---

## 👨‍💻 Authors

**School of Computer Science & IT — Dedan Kimathi University of Technology (DeKUT)**
Theory of Computation — FAQ Assistant Project

---

## 📄 Licence

For academic use only. © DeKUT School of Computer Science & IT.
