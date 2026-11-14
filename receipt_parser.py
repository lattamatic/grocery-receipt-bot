import asyncio
import base64
import json
import os

import httpx

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")
GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent"
)

_PROMPT = """You are a receipt OCR assistant. Carefully read this grocery receipt image.

Return a single JSON object in this exact structure:
{
  "store_name": "string or null",
  "receipt_date": "YYYY-MM-DD or null",
  "items": [
    {
      "name": "item description",
      "quantity": 1,
      "unit_price": 0.00,
      "total": 0.00
    }
  ],
  "subtotal": 0.00,
  "tax": 0.00,
  "total": 0.00
}

Rules:
- Include every purchased line item (skip subtotal/tax/total rows — put those in the top-level fields).
- If a value is not visible or unclear, use null.
- Quantities default to 1 if not shown.
- All monetary values must be numbers (not strings).
- If the image is not a receipt, return an empty "items" list."""


def _build_payload(image_bytes: bytes) -> dict:
    b64 = base64.b64encode(image_bytes).decode()
    return {
        "contents": [
            {
                "parts": [
                    {"text": _PROMPT},
                    {"inline_data": {"mime_type": "image/jpeg", "data": b64}},
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 8192,
            "responseMimeType": "application/json",
        },
    }


def _extract_json(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


async def parse_receipt(image_bytes: bytes) -> dict:
    # Key goes in a header so it never appears in logged request URLs.
    payload = _build_payload(image_bytes)
    async with httpx.AsyncClient(timeout=90) as client:
        for attempt in range(3):
            try:
                response = await client.post(
                    GEMINI_URL,
                    headers={"x-goog-api-key": GEMINI_API_KEY},
                    json=payload,
                )
                # The free tier returns 429/503 under load; those are worth retrying.
                if response.status_code in (429, 500, 503) and attempt < 2:
                    await asyncio.sleep(3 * (attempt + 1))
                    continue
                response.raise_for_status()
                break
            except httpx.TimeoutException:
                if attempt == 2:
                    raise

    parts = response.json()["candidates"][0]["content"]["parts"]
    raw_text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
    return _extract_json(raw_text)
