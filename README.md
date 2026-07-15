# 🎓 DeKUT CS & IT Smart FAQ Assistant

> **A smart voice- and text-based FAQ assistant for the School of Computer Science & IT at Dedan Kimathi University of Technology (DeKUT).**  
> Processes student queries directed to the Chair of Department (COD) and the Dean, using a Context-Free Grammar (CFG) parser, keyword-vote fallback, and optional OpenAI AI refinement. Deployed on WhatsApp via Twilio.

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
│   └── wsgi.py             # WSGI entry point (Gunicorn / uWSGI)
├── validate.py             # Standalone CLI validation tool (Phase 5)
├── manage.py               # Django management script
├── requirements.txt        # Python dependencies
├── .env.example            # Environment variable template
└── db.sqlite3              # SQLite database (auto-created on first migrate)
```

---

## ⚙️ Prerequisites

| Requirement | Version |
|---|---|
| Python | 3.10+ |
| Django | 4.2+ |
| NLTK | 3.8+ |
| Twilio account | WhatsApp sandbox enabled |
| OpenAI API key | Optional — enables STT, TTS, and GPT-4o refinement |

---

## 🚀 Quick Start

### 1. Clone / navigate to the project

```bash
cd "FAQ"
```

### 2. Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate       # Linux / macOS
# .venv\Scripts\activate        # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

> **No internet access?** Django (4.2), NLTK (3.9), and python-dotenv are usually available system-wide on Ubuntu/Debian. The core parser and validator work with just `nltk`.

### 4. Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and fill in your values:

```ini
# Django
DJANGO_SECRET_KEY=<generate with: python3 -c "import secrets; print(secrets.token_urlsafe(50))">
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1

# OpenAI (leave blank to run in offline / CFG-only mode)
OPENAI_API_KEY=sk-...

# Twilio WhatsApp sandbox
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx   # must start with AC
TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_WHATSAPP_NUMBER=whatsapp:+254740873466

# Optional: public URL for serving TTS audio files back to WhatsApp
PUBLIC_BASE_URL=https://your-ngrok-url.ngrok.io
```

> ⚠️ **Never commit `.env` to version control.** It is already listed in `.gitignore`.

### 5. Run database migrations

```bash
python3 manage.py makemigrations assistant
python3 manage.py migrate
```

### 6. Start the development server

```bash
python3 manage.py runserver
```

The server starts at **http://127.0.0.1:8000/**

---

## ✅ Validate the Parser (Offline — no API key needed)

### Run the full 40-query batch test

```bash
python3 validate.py --batch
```

Expected output: **40/40 correct (100%)** via CFG parse.

### Interactive mode (type any student query)

```bash
python3 validate.py
```

```
  ❯ Your query: I need a recommendation letter for my internship at Safaricom
```

### Test a single query

```bash
python3 validate.py --query "How do I apply for a credit transfer from another university?"
```

### Test an audio file (requires OPENAI_API_KEY)

```bash
python3 validate.py --audio /path/to/voice_note.ogg
```

### Generate an HTML report

```bash
python3 validate.py --batch --report
# Opens: validation_report.html
```

### Enable GPT-4o response refinement

```bash
python3 validate.py --batch --ai
```

---

## 🌐 API Endpoints

Once the Django server is running:

### Health check

```bash
curl http://127.0.0.1:8000/health/
```

```json
{
  "status": "ok",
  "service": "DeKUT CS & IT FAQ Assistant",
  "ai_mode": "offline (CFG only)",
  "twilio_configured": true
}
```

### Direct text query (no WhatsApp needed)

```bash
curl -X POST http://127.0.0.1:8000/api/query/ \
  -H "Content-Type: application/json" \
  -d '{"query": "I failed SCS 3304 with 35%. Am I eligible for a supplementary exam?", "sender": "test-user"}'
```

```json
{
  "query": "...",
  "matched_rule": "S -> IntentNP",
  "category": "supplementary_exam",
  "confidence": 1.0,
  "tokens_used": ["supp_topic"],
  "ai_refined": false,
  "response": "Dear Student,\n\nSupplementary examinations are available..."
}
```

### WhatsApp webhook (Twilio POST)

```
POST /webhook/whatsapp/
```

This is called automatically by Twilio. See the WhatsApp setup section below.

---

## 📱 WhatsApp Deployment (Twilio)

### Step 1 — Install Twilio

```bash
pip install twilio
```

### Step 2 — Expose your server to the internet

```bash
# Install ngrok from https://ngrok.com, then:
ngrok http 8000
```

Copy the generated HTTPS URL, e.g. `https://abc123.ngrok.io`

### Step 3 — Set your webhook URL in Twilio

1. Go to [Twilio Console → Messaging → Try it out → Send a WhatsApp message](https://console.twilio.com/us1/develop/sms/try-it-out/whatsapp-learn)
2. Set the **"When a message comes in"** webhook to:
   ```
   https://abc123.ngrok.io/webhook/whatsapp/
   ```
3. Method: `HTTP POST`

### Step 4 — Test

Send any message from WhatsApp to your Twilio sandbox number. You should receive an instant reply from the Dean/COD.

---

## 🧠 How the Parser Works

```
Student query (text or voice note)
        │
        ▼
┌─────────────────────────┐
│  Lexical Normaliser      │  Lowercases → expands multi-word phrases →
│  (parser.py)             │  extracts [modal?, verb, topic] token sequence
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│  NLTK ChartParser        │  Parses token sequence against 22-rule CFG
│  (grammar_rules.py)      │  Confidence = 1.0 on success
└────────────┬────────────┘
             │ No parse tree?
             ▼
┌─────────────────────────┐
│  Keyword-Vote Fallback   │  Counts intent keywords in raw query
│  (parser.py)             │  Confidence = 0.0–0.99
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│  Response Engine         │  Maps intent → canned Dean/COD response
│  (parser.py)             │
└────────────┬────────────┘
             │ (if OPENAI_API_KEY is set)
             ▼
┌─────────────────────────┐
│  GPT-4o Refinement       │  Personalises and polishes the response
│  (ai_services.py)        │
└─────────────────────────┘
```

### Intent Categories

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

## 🧪 Validation Results

| Metric | Value |
|---|---|
| Total queries tested | 40 / 40 |
| Correctly classified | **40 / 40 (100%)** |
| CFG parse hits | **40 / 40 (100%)** |
| Keyword-vote fallback | 0 used |

---

## 🔧 Production Deployment (Gunicorn)

```bash
pip install gunicorn
gunicorn faq_assistant.wsgi:application --bind 0.0.0.0:8000 --workers 3
```

Set `DJANGO_DEBUG=False` and `DJANGO_ALLOWED_HOSTS=yourdomain.com` in `.env` for production.

---

## 📦 Dependencies

```
django>=4.2          # Web framework
twilio>=8.5          # WhatsApp webhook + TwiML
openai>=1.30         # Whisper STT, GPT-4o, TTS (optional)
nltk>=3.8            # CFG ChartParser
pydub>=0.25          # Audio format conversion
python-dotenv>=1.0   # .env file loading
requests>=2.31       # Media download from Twilio
gunicorn>=21.2       # Production WSGI server
```

---

## 👨‍💻 Authors

**School of Computer Science & IT — Dedan Kimathi University of Technology (DeKUT)**  
Theory of Computation — FAQ Assistant Project

---

## 📄 Licence

For academic use only. © DeKUT School of Computer Science & IT.
# Smart_Grammar_FAQ_Assistant_DeKUT
