from datetime import datetime

from app.extensions import db


class ReferralVerification(db.Model):
    """
    Tracks a user's progress through the affiliate/free-access route for
    a given product (e.g. "opened a broker account under our link").

    The exact requirements are admin-editable (see Product.affiliate_requirements)
    so this model just tracks status, not the specific business rule.
    """

    __tablename__ = "referral_verifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False, index=True)

    # pending -> submitted -> approved | rejected
    status = db.Column(db.String(20), nullable=False, default="pending")

    submitted_reference = db.Column(db.String(255))  # e.g. broker account number the user submitted
    admin_note = db.Column(db.Text)

    reviewed_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship("User", foreign_keys=[user_id])
    product = db.relationship("Product")
    reviewed_by = db.relationship("User", foreign_keys=[reviewed_by_id])

    __table_args__ = (
        db.UniqueConstraint("user_id", "product_id", name="uq_referral_user_product"),
    )
