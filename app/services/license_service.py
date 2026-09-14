"""
Core license business logic, shared by:
  - app/routes/dashboard.py  (user-facing license views)
  - app/routes/admin.py      (admin license management)
  - app/api/license.py       (the EA-facing validation API)

Keeping this in one place means the validation rules the API enforces
are exactly the rules a human sees on their dashboard — no drift.
"""

import hashlib
import hmac
from datetime import datetime

from flask import current_app

from app.extensions import db
from app.models.license import License, LicenseBinding, ValidationLog


def issue_license(user, product, access_method="purchase", order=None, max_activations=1, expires_at=None):
    """Create and persist a new license for a user/product pair."""
    lic = License(
        user_id=user.id,
        product_id=product.id,
        license_key=License.generate_key(),
        status="active",
        access_method=access_method,
        max_activations=max_activations,
        order_id=order.id if order else None,
        expires_at=expires_at,
    )
    db.session.add(lic)
    return lic


def revoke_license(license_obj, note=None):
    license_obj.status = "revoked"
    license_obj.revoked_at = datetime.utcnow()
    if note:
        license_obj.notes = (license_obj.notes or "") + f"\n[revoked] {note}"


def set_license_status(license_obj, status, note=None):
    assert status in ("active", "suspended", "revoked")
    license_obj.status = status
    if status == "revoked":
        license_obj.revoked_at = datetime.utcnow()
    if note:
        license_obj.notes = (license_obj.notes or "") + f"\n[{status}] {note}"


def sign_response(license_key: str, account: str, valid: bool, server_time: str, nonce: str = "") -> str:
    """
    HMAC-sign the fields that matter in a validation response so the EA
    can confirm the reply genuinely came from this server (and wasn't
    forged by, say, a spoofed DNS entry or edited hosts file).
    The EA must reconstruct this exact pipe-joined string to verify.
    """
    secret = current_app.config["LICENSE_HMAC_SECRET"].encode("utf-8")
    payload = f"{license_key}|{account}|{valid}|{server_time}|{nonce}".encode("utf-8")
    return hmac.new(secret, payload, hashlib.sha256).hexdigest()


def log_validation(license_key, account, result, ea_version=None, ip_address=None):
    entry = ValidationLog(
        license_key=license_key,
        account_identifier=account,
        result=result,
        ea_version=ea_version,
        ip_address=ip_address,
    )
    db.session.add(entry)
    db.session.commit()
    return entry


def check_rate_limit(license_key: str) -> bool:
    """Return True if this key is within the allowed validation rate."""
    from datetime import timedelta
    limit = current_app.config["LICENSE_API_RATE_LIMIT_PER_HOUR"]
    since = datetime.utcnow() - timedelta(hours=1)
    count = ValidationLog.query.filter(
        ValidationLog.license_key == license_key,
        ValidationLog.created_at >= since,
    ).count()
    return count < limit


def validate_license(license_key: str, account: str, product_code: str = None):
    """
    Core validation logic. Returns (result_code, license_obj_or_None).

    result_code is one of:
      invalid_key, revoked, suspended, expired, wrong_product,
      not_bound, activation_limit_reached, valid
    """
    if not license_key or not account:
        return "invalid_key", None

    license_key = license_key.strip().upper()
    account = account.strip()

    lic = License.query.filter_by(license_key=license_key).first()
    if not lic:
        return "invalid_key", None

    if lic.status == "revoked":
        return "revoked", lic
    if lic.status == "suspended":
        return "suspended", lic

    if lic.is_expired:
        return "expired", lic

    if product_code:
        requested = product_code.strip().upper()
        if lic.product.code.upper() != requested:
            # Deliberately reported as invalid_key, not "wrong_product",
            # so a caller can't use this endpoint to enumerate which
            # product a given key belongs to.
            return "invalid_key", lic

    binding = LicenseBinding.query.filter_by(
        license_id=lic.id, account_identifier=account, is_active=True
    ).first()

    if not binding:
        # No existing binding for this account. Auto-bind if there is
        # room under the activation limit; otherwise reject.
        if lic.max_activations is not None and lic.active_binding_count >= lic.max_activations:
            return "activation_limit_reached", lic

        binding = LicenseBinding(license_id=lic.id, account_identifier=account, is_active=True)
        db.session.add(binding)
        db.session.commit()

    return "valid", lic
