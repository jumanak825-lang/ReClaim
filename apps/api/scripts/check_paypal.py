"""Check PayPal Sandbox configuration without printing any secret.

Usage (from apps/api, with PAYPAL_* exported):  .venv/Scripts/python scripts/check_paypal.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core import config  # noqa: E402
from app.integrations import paypal  # noqa: E402

s = config.settings
print(f"PAYPAL_BASE_URL     {s.paypal_base_url} ({'sandbox' if s.paypal_is_sandbox else 'NOT SANDBOX'})")
print(f"payment mode        {s.paypal_mode}")
print(f"PAYPAL_CLIENT_ID    {'set' if s.paypal_client_id else 'missing'}")
print(f"PAYPAL_CLIENT_SECRET {'set' if s.paypal_client_secret else 'missing'}")
print(f"PAYPAL_WEBHOOK_ID   {'set' if s.paypal_webhook_id else 'missing (webhooks will be rejected with 503)'}")
if not (s.paypal_client_id and s.paypal_client_secret):
    sys.exit("Set PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET first.")
try:
    paypal.access_token()
except paypal.PayPalError as exc:
    sys.exit(f"OAuth FAILED: {exc}")
print("OAuth OK: credentials accepted by PayPal.")
