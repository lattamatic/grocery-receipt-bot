import base64
import json
import os

import httpx

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-1.5-flash:generateContent?key=" + GEMINI_API_KEY
    if GEMINI_API_KEY
    else ""
)

_PROMPT = """You are a receipt OCR assistant. Carefully read this grocery receipt image.

Return ONLY a single valid JSON object — no markdown, no extra text — in this exact structure:
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
- Do not include any text outside the JSON object."""


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
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 2048},
    }


def _extract_json(raw: str) -> dict:
    text = raw.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        parts = text.split("```")
        # parts[1] is the content inside the fences
        text = parts[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


async def parse_receipt(image_bytes: bytes) -> dict:
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    )
    payload = _build_payload(image_bytes)

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()

    data = response.json()
    raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
    return _extract_json(raw_text)
