import hashlib
import hmac
import json
import requests

from django.conf import settings


def flutterwave_headers():
    return {
        'Authorization': f'Bearer {settings.FLUTTERWAVE_SECRET_KEY}',
        'Content-Type': 'application/json',
    }


def flutterwave_base_url():
    return 'https://api.flutterwave.com'  # works for both test/live endpoints per Flutterwave docs


def flutterwave_pay_endpoint():
    # Charge/Payment initialization endpoint
    return f'{flutterwave_base_url()}/v3/payments'


def create_payment(reference: str, tx_ref: str, amount: str, customer: dict, redirect_url: str):
    payload = {
        'tx_ref': reference,
        'amount': amount,
        'currency': 'RWF',
        'redirect_url': redirect_url,
        'payment_options': 'card,ussd',
        'customer': customer,
        'customizations': {
            'title': 'Hardcore Fashion Store',
            'description': 'Payment for your order',
        },
    }

    resp = requests.post(
        flutterwave_pay_endpoint(),
        headers=flutterwave_headers(),
        data=json.dumps(payload),
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def verify_webhook_signature(raw_body: bytes, received_signature: str) -> bool:
    secret = settings.FLUTTERWAVE_SECRET_KEY.encode('utf-8')
    # Flutterwave webhook signature formats vary by product; many use X-Signature.
    # We'll fall back to comparing against HMAC-SHA256 over raw body.
    computed = hmac.new(secret, raw_body, hashlib.sha256).hexdigest()
    if not received_signature:
        return False
    return hmac.compare_digest(computed, received_signature)

