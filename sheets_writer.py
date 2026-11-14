import json
import os
from datetime import datetime, timezone

import gspread
from google.oauth2.service_account import Credentials

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

SPREADSHEET_ID = os.environ["SPREADSHEET_ID"]
SHEET_NAME = os.environ.get("SHEET_NAME", "Sheet1")
DEFAULT_CURRENCY = os.environ.get("DEFAULT_CURRENCY", "EUR")

HEADERS = [
    "Receipt ID",
    "Purchase Date",
    "Store",
    "Item",
    "Category",
    "Quantity",
    "Unit Price",
    "Total Price",
    "Currency",
    "Receipt Total",
    "Logged At",
]


def _get_worksheet() -> gspread.Worksheet:
    info = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
    creds = Credentials.from_service_account_info(info, scopes=_SCOPES)
    return gspread.authorize(creds).open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)


def _cell(value):
    return "" if value is None else value


def build_rows(receipt: dict, receipt_id: str) -> list[list]:
    now = datetime.now(timezone.utc)
    logged_at = now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"
    currency = receipt.get("currency") or DEFAULT_CURRENCY

    return [
        [
            receipt_id,
            _cell(receipt.get("receipt_date")),
            _cell(receipt.get("store_name")),
            _cell(item.get("name")),
            item.get("category") or "Other",
            item.get("quantity") or 1,
            _cell(item.get("unit_price")),
            _cell(item.get("total")),
            currency,
            _cell(receipt.get("total")),
            logged_at,
        ]
        for item in receipt.get("items") or []
    ]


def append_receipt(receipt: dict, receipt_id: str) -> int:
    rows = build_rows(receipt, receipt_id)
    if not rows:
        return 0

    ws = _get_worksheet()
    if not ws.acell("A1").value:
        ws.append_row(HEADERS, value_input_option="USER_ENTERED", table_range="A1")
    # Append-only: rows go below the last occupied row, anchored at column A.
    ws.append_rows(rows, value_input_option="USER_ENTERED", table_range="A1")
    return len(rows)
