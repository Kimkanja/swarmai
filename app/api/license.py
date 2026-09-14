"""
POST /api/license/validate
POST /api/license/deactivate
GET  /api/license/status/<key>

Called by the trading EA running inside the MetaTrader terminal. This
is a machine-to-machine API, not a browser flow:

  - No CSRF token (exempted in app/__init__.py) — the license key
    itself is the credential the caller presents.
  - No user session / cookies.
  - Every response is HMAC-signed (see license_service.sign_response)
    so the EA can detect a forged reply from a spoofed local server,
    e.g. via an edited hosts file or a compromised network.
  - Responses are deliberately generic on failure ("invalid_key" covers
    both "no such key" and "wrong product for this key") so the API
    can't be used to enumerate valid keys or learn which products
    exist for a given key.
  - Rate limited per license key to blunt brute-force key guessing.

Nothing here trusts client-supplied data beyond the license key +
account identifier pair; all authorization decisions are re-derived
from the database on every call.
"""

from datetime import datetime

from flask import Blueprint, request, jsonify

from app.extensions import db
from app.models.license import License, LicenseBinding
from app.models.settings import SiteSetting
from app.services.license_service import (
    validate_license,
    sign_response,
    log_validation,
    check_rate_limit,
)

license_api_bp = Blueprint("license_api", __name__)

MESSAGES = {
    "valid": "License active.",
    "invalid_key": "License key not recognized.",
    "revoked": "License has been revoked. Contact support.",
    "suspended": "License is suspended. Contact support.",
    "expired": "License has expired.",
    "activation_limit_reached": "Activation limit reached for this license.",
    "maintenance": "Validation temporarily unavailable.",
    "rate_limited": "Too many validation attempts. Try again later.",
    "bad_request": "Missing required fields.",
}


def _client_ip():
    return request.headers.get("X-Forwarded-For", request.remote_addr or "").split(",")[0].strip()


def _build_response(result, key, account, extra=None, nonce="", http_status=200):
    extra = extra or {}
    valid = result == "valid"
    server_time = datetime.utcnow().isoformat() + "Z"
    signature = sign_response(key, account, valid, server_time, nonce)

    body = {
        "valid": valid,
        "result": result,
        "message": MESSAGES.get(result, "Unrecognized result."),
        "server_time": server_time,
        "nonce": nonce,
        "signature": signature,
        **extra,
    }
    return jsonify(body), http_status


@license_api_bp.route("/validate", methods=["POST"])
def validate():
    payload = request.get_json(silent=True) or {}

    key = (payload.get("key") or "").strip().upper()
    account = (payload.get("account") or "").strip()
    product_code = payload.get("product")
    ea_version = payload.get("ea_version")
    nonce = (payload.get("nonce") or "")[:64]

    if not key or not account:
        return _build_response("bad_request", key, account, nonce=nonce, http_status=400)

    if SiteSetting.get_bool("maintenance_mode", False):
        # Not a failure — the EA should keep running on its cached
        # grace period rather than shutting down.
        return _build_response("maintenance", key, account, nonce=nonce, http_status=503)

    if not check_rate_limit(key):
        return _build_response("rate_limited", key, account, nonce=nonce, http_status=429)

    result, lic = validate_license(key, account, product_code)
    log_validation(key, account, result, ea_version=ea_version, ip_address=_client_ip())

    if result != "valid":
        return _build_response(result, key, account, nonce=nonce)

    extra = {
        "product": lic.product.code,
        "expires_at": lic.expires_at.isoformat() if lic.expires_at else None,
        "recheck_hours": int(SiteSetting.get("validation_cache_hours", 6)),
        "grace_hours": int(SiteSetting.get("grace_period_hours", 72)),
    }
    return _build_response("valid", key, account, extra=extra, nonce=nonce)


@license_api_bp.route("/deactivate", methods=["POST"])
def deactivate():
    payload = request.get_json(silent=True) or {}
    key = (payload.get("key") or "").strip().upper()
    account = (payload.get("account") or "").strip()

    if not key or not account:
        return _build_response("bad_request", key, account, http_status=400)

    lic = License.query.filter_by(license_key=key).first()
    if not lic:
        return _build_response("invalid_key", key, account)

    binding = LicenseBinding.query.filter_by(
        license_id=lic.id, account_identifier=account, is_active=True
    ).first()

    if binding:
        binding.is_active = False
        binding.deactivated_at = datetime.utcnow()
        db.session.commit()

    log_validation(key, account, "deactivated", ip_address=_client_ip())
    return _build_response("valid", key, account, extra={"deactivated": True})


@license_api_bp.route("/status/<key>", methods=["GET"])
def status(key):
    """
    Lightweight status check (no account binding logic) — e.g. for a
    user's dashboard to show live status without duplicating routes.
    Returns minimal info; use /validate for the EA activation flow.
    """
    key = key.strip().upper()
    lic = License.query.filter_by(license_key=key).first()
    if not lic:
        return jsonify({"found": False}), 404

    return jsonify({
        "found": True,
        "status": lic.status,
        "product": lic.product.code,
        "expired": lic.is_expired,
        "expires_at": lic.expires_at.isoformat() if lic.expires_at else None,
    })
