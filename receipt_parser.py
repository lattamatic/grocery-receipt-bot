import asyncio
import base64
import json
import logging
import os

import httpx

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
# Tried in order; the next model is used when one is overloaded or too slow.
GEMINI_MODELS = [
    m.strip()
    for m in os.environ.get("GEMINI_MODELS", "gemini-3.5-flash-lite,gemini-3.5-flash").split(",")
    if m.strip()
]
_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"

logger = logging.getLogger(__name__)

_PROMPT = """You are a receipt OCR assistant. Carefully read this grocery receipt image.

Return a single JSON object in this exact structure:
{
  "store_name": "string or null",
  "receipt_date": "YYYY-MM-DD or null",
  "currency": "ISO 4217 code such as EUR, or null",
  "items": [
    {
      "name": "item description",
      "category": "Groceries | Personal care | Household | Other",
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
- Include discount or price-reduction lines as their own items with negative amounts.
- Keep item names as printed on the receipt; do not translate them.
- "category" must be exactly one of: Groceries, Personal care, Household, Other.
- If a value is not visible or unclear, use null.
- Quantities default to 1 if not shown.
- All monetary values must be numbers (not strings).
- If the image is not a receipt, return an empty "items" list."""


def _build_payload(image_bytes: bytes, mime_type: str) -> dict:
    b64 = base64.b64encode(image_bytes).decode()
    return {
        "contents": [
            {
                "parts": [
                    {"text": _PROMPT},
                    {"inline_data": {"mime_type": mime_type, "data": b64}},
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


async def parse_receipt(image_bytes: bytes, mime_type: str = "image/jpeg") -> dict:
    payload = _build_payload(image_bytes, mime_type)
    last_error: Exception | None = None

    # Key goes in a header so it never appears in logged request URLs.
    async with httpx.AsyncClient(timeout=45, headers={"x-goog-api-key": GEMINI_API_KEY}) as client:
        for round_number in range(2):
            for model in GEMINI_MODELS:
                try:
                    response = await client.post(
                        f"{_BASE_URL}/{model}:generateContent", json=payload
                    )
                    response.raise_for_status()
                    parts = response.json()["candidates"][0]["content"]["parts"]
                    text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
                    receipt = _extract_json(text)
                    logger.info("Receipt parsed with %s", model)
                    return receipt
                except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
                    logger.warning("%s failed: %r", model, exc)
                    last_error = exc
            await asyncio.sleep(3)

    raise last_error
