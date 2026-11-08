import json
import os
from datetime import datetime, timezone

import gspread
from google.oauth2.service_account import Credentials

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

SPREADSHEET_ID = os.environ["SPREADSHEET_ID"]
SHEET_NAME = os.environ.get("SHEET_NAME", "Sheet1")

HEADERS = [
    "Processed At",
    "Store Name",
    "Receipt Date",
    "Item Name",
    "Quantity",
    "Unit Price",
    "Item Total",
    "Receipt Total",
    "Tax",
]


def _get_worksheet() -> gspread.Worksheet:
    raw = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
    info = json.loads(raw)
    creds = Credentials.from_service_account_info(info, scopes=_SCOPES)
    gc = gspread.authorize(creds)
    return gc.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)


def _ensure_headers(ws: gspread.Worksheet) -> None:
    """Add header row only if the sheet is completely empty."""
    all_values = ws.get_all_values()
    if not all_values:
        ws.append_row(HEADERS, value_input_option="USER_ENTERED")


def append_receipt(receipt: dict) -> int:
    ws = _get_worksheet()
    _ensure_headers(ws)

    store = receipt.get("store_name") or ""
    date = receipt.get("receipt_date") or ""
    items = receipt.get("items") or []
    receipt_total = receipt.get("total") or ""
    tax = receipt.get("tax") or ""
    processed_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    rows = []
    for item in items:
        rows.append([
            processed_at,
            store,
            date,
            item.get("name", ""),
            item.get("quantity", 1),
            item.get("unit_price", ""),
            item.get("total", ""),
            receipt_total,
            tax,
        ])

    if rows:
        ws.append_rows(rows, value_input_option="USER_ENTERED")

    return len(rows)
