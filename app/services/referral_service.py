from app.extensions import db
from app.models.referral import ReferralVerification


def attach_referrer(new_user, referral_code):
    """
    Link new_user to the user owning referral_code, if valid.
    Prevents a user from referring themselves.
    """
    if not referral_code:
        return None

    from app.models.user import User
    referrer = User.query.filter_by(referral_code=referral_code.strip().upper()).first()

    if not referrer or referrer.id == new_user.id:
        return None

    new_user.referred_by_id = referrer.id
    return referrer


def submit_referral_verification(user, product, reference):
    """User submits proof of completing the affiliate route for a product."""
    existing = ReferralVerification.query.filter_by(user_id=user.id, product_id=product.id).first()
    if existing:
        existing.status = "submitted"
        existing.submitted_reference = reference
        return existing

    verification = ReferralVerification(
        user_id=user.id,
        product_id=product.id,
        status="submitted",
        submitted_reference=reference,
    )
    db.session.add(verification)
    return verification


def approve_verification(verification, admin_user, note=None):
    verification.status = "approved"
    verification.reviewed_by_id = admin_user.id
    if note:
        verification.admin_note = note


def reject_verification(verification, admin_user, note=None):
    verification.status = "rejected"
    verification.reviewed_by_id = admin_user.id
    if note:
        verification.admin_note = note
