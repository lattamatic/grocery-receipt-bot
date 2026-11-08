# Architecture

## Overview

grocery-receipt-bot is a stateless Telegram bot. Each incoming photo triggers a linear pipeline: download → AI parse → spreadsheet append → confirm. There is no database; Google Sheets is the only persistence layer.

---

## Component diagram

```
┌─────────────┐       photo        ┌───────────────────┐
│   Telegram  │ ────────────────▶  │     bot.py        │
│   (user)    │ ◀────────────────  │  (Application)    │
└─────────────┘   confirmation     └────────┬──────────┘
                                            │
                              ┌─────────────┴──────────────┐
                              │                            │
                     ┌────────▼────────┐       ┌──────────▼────────┐
                     │ receipt_parser  │       │  sheets_writer    │
                     │  (Gemini API)   │       │  (gspread)        │
                     └────────┬────────┘       └──────────┬────────┘
                              │                            │
                     ┌────────▼────────┐       ┌──────────▼────────┐
                     │ Gemini 1.5 Flash│       │  Google Sheets    │
                     │  (Google API)   │       │  (Spreadsheet)    │
                     └─────────────────┘       └───────────────────┘
```

---

## Data flow

1. **Telegram webhook/poll** — `python-telegram-bot` polls the Telegram API for new updates.
2. **Photo handler** (`bot.py:handle_photo`) — downloads the highest-resolution photo variant from Telegram's CDN as raw bytes.
3. **Receipt parser** (`receipt_parser.py:parse_receipt`) — base64-encodes the image, sends a multipart prompt to Gemini 1.5 Flash REST API, strips any markdown code fences from the response, and returns a plain Python dict.
4. **Sheets writer** (`sheets_writer.py:append_receipt`) — creates one spreadsheet row per line item. If the sheet is empty it inserts a header row first. Uses `append_rows` (never `update`) so existing data is never touched.
5. **Confirmation** — bot edits its "Analysing…" placeholder message with a Markdown summary of what was saved.

---

## Error handling

| Failure | Bot response |
|---|---|
| Gemini API error (5xx, timeout) | "couldn't analyse that receipt" message |
| Gemini returns no items | "couldn't find any line items" message |
| Sheets API error (auth, quota) | "parsed but couldn't save" message |
| No photo in message | "please send a photo" nudge |

Errors are logged at ERROR level with the full exception. The bot never crashes — all external calls are wrapped in try/except.

---

## Gemini prompt design

The prompt instructs the model to:
- Return **only** a JSON object (no prose, no markdown fences)
- Use `null` for unreadable fields rather than guessing
- Separate line items from totals/tax (which go in top-level fields)
- Default quantity to 1 when not shown

`temperature: 0.1` keeps responses deterministic and reduces hallucination.

The JSON is parsed with a defensive `_extract_json` helper that strips accidental markdown fences before `json.loads`.

---

## Google Sheets strategy

- Uses a **service account** (not OAuth) so the bot can run headlessly with no user interaction.
- The service account JSON is stored as a single environment variable (`GOOGLE_SERVICE_ACCOUNT_JSON`) — never as a file in the repo.
- `_ensure_headers` checks whether the sheet is empty and inserts column headers only once. If the sheet already has data, headers are skipped and rows append immediately below the last occupied row.
- All writes use `value_input_option="USER_ENTERED"` so Google Sheets auto-formats numbers and dates.

---

## Deployment

Runs as a single `worker` process on Railway (see `Procfile`). No web server is needed — Telegram polling is outbound HTTP, not inbound.

All secrets are injected as Railway environment variables. Nothing sensitive is in the codebase.

---

## Scaling considerations (future)

- **Webhook mode** — swap `run_polling()` for `run_webhook()` to reduce latency and avoid the 100-update polling limit. Requires a public HTTPS URL (Railway provides one).
- **Queue** — add a Redis queue if volume justifies it; currently each photo is processed synchronously in the handler coroutine.
- **Multiple sheets** — add a `SHEET_NAME` env var per user group, or route by Telegram chat ID to different tabs.
