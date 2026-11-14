# grocery-receipt-bot

A Telegram bot that reads grocery receipt photos and logs every line item to Google Sheets — automatically, using AI vision.

Send a receipt photo → the bot extracts store name, date, items, prices → appends rows to your spreadsheet → confirms with a summary.

---

## How it works

```
You (Telegram)
    │
    │  photo of receipt
    ▼
Telegram Bot (Python)
    │
    │  image bytes
    ▼
Google Gemini Flash  ←── free vision AI
    │
    │  structured JSON
    ▼
Google Sheets  ←── appends one row per line item
    │
    ▼
Confirmation message back to you
```

---

## Columns written to the spreadsheet

| Column | Description |
|---|---|
| Receipt ID | `<Telegram chat ID>-<message ID>`, shared by all rows of one receipt |
| Purchase Date | Date on the receipt (YYYY-MM-DD) |
| Store | Store name from the receipt |
| Item | Product description as printed |
| Category | Groceries, Personal care, Household or Other |
| Quantity | Number of units |
| Unit Price | Price per unit |
| Total Price | Line total (discount lines are negative) |
| Currency | ISO code read from the receipt, falling back to `DEFAULT_CURRENCY` |
| Receipt Total | Full receipt total |
| Logged At | UTC timestamp when the bot saved the row |

The bot only **appends** rows — it never deletes or overwrites existing data.

---

## Stack

| Layer | Technology | Cost |
|---|---|---|
| Trigger | Telegram Bot API | Free |
| AI Vision | Google Gemini Flash | Free tier |
| Storage | Google Sheets | Free |
| Hosting | Railway | Your existing plan |

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/lattamatic/grocery-receipt-bot.git
cd grocery-receipt-bot
```

### 2. Install dependencies (local dev)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Create `.env`

```bash
cp .env.example .env
```

Fill in the values — see [Environment variables](#environment-variables) below.

### 4. Run locally

```bash
python bot.py
```

---

## Environment variables

| Variable | Where to get it |
|---|---|
| `TELEGRAM_TOKEN` | [@BotFather](https://t.me/BotFather) on Telegram |
| `GEMINI_API_KEY` | [Google AI Studio](https://aistudio.google.com) → Get API key |
| `SPREADSHEET_ID` | The long ID in your Google Sheet URL |
| `SHEET_NAME` | Tab name in the spreadsheet (default: `Sheet1`) |
| `DEFAULT_CURRENCY` | Optional. Currency used when the receipt does not show one (default: `EUR`) |
| `GEMINI_MODELS` | Optional. Comma-separated Gemini model IDs tried in order (default: `gemini-3.5-flash-lite,gemini-3.5-flash`) |
| `ALLOWED_CHAT_IDS` | Optional. Comma-separated Telegram chat IDs allowed to use the bot; empty means anyone. `/start` shows your chat ID |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Full JSON from your Google Cloud service account key (see below) |

### Google Service Account setup

1. [Google Cloud Console](https://console.cloud.google.com) → create project `receipt-bot`
2. Enable **Google Sheets API**
3. IAM & Admin → Service Accounts → Create (`receipt-bot`)
4. Keys tab → Add Key → JSON → download
5. Share your Google Sheet with the service account email (Editor access)
6. Copy the entire JSON content into `GOOGLE_SERVICE_ACCOUNT_JSON`

---

## Deploy to Railway

1. Push this repo to GitHub
2. Railway → New Project → Deploy from GitHub repo
3. Add all environment variables in Railway's Variables tab
4. Set the start command to `python bot.py` or Railway will use the `Procfile` automatically

---

## Project structure

```
grocery-receipt-bot/
├── bot.py               # Telegram bot — handlers and entry point
├── receipt_parser.py    # Gemini vision API call and JSON extraction
├── sheets_writer.py     # Google Sheets append logic
├── requirements.txt
├── Procfile             # Railway process definition
├── .env.example         # Template for environment variables
├── .gitignore
└── docs/
    └── ARCHITECTURE.md  # Detailed technical design
```
