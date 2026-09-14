"""
Payment abstraction layer — currently UNUSED by the live purchase flow.

Per your instruction, Swarm AI does not use automated payment right now:
buyers see the fixed price on the product page and message the admin on
Telegram to pay and receive their license (see app/routes/products.py
buy() and Product.telegram_link()).

This file is kept only as a ready-made hook for later: if you ever want
to add automated checkout (Stripe, Paystack, Flutterwave, a crypto
gateway, etc.), wire it in here so routes/templates never need to touch
a provider SDK directly.
"""

from dataclasses import dataclass


@dataclass
class CheckoutResult:
    redirect_url: str | None
    manual: bool  # True if no automated checkout is configured yet


def start_checkout(user, product) -> CheckoutResult:
    """
    Kick off a purchase. Returns where to send the user next.

    TODO: once a payment provider is selected, replace this with a real
    checkout session creation call and return provider's redirect URL.
    """
    if product.purchase_url:
        return CheckoutResult(redirect_url=product.purchase_url, manual=False)

    # No automated checkout configured — send the user to support/contact.
    return CheckoutResult(redirect_url=None, manual=True)


def handle_webhook(payload, signature_header):
    """
    Placeholder for provider webhook handling (payment confirmation ->
    order.status = 'paid' -> issue_license()). Implement once a provider
    is connected; verify the signature_header against the provider's
    documented scheme before trusting `payload`.
    """
    raise NotImplementedError("No payment provider is connected yet.")
