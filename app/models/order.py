from datetime import datetime

from app.extensions import db


class Order(db.Model):
    """
    A purchase record. Payment processing itself is abstracted behind
    app/services/payment_service.py — no payment provider is wired in
    here since none was supplied; this model just tracks the result.
    """

    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False, index=True)

    amount = db.Column(db.Numeric(10, 2))
    currency = db.Column(db.String(10), default="USD")

    # pending -> paid -> fulfilled  (or: failed / cancelled)
    status = db.Column(db.String(20), nullable=False, default="pending")

    payment_reference = db.Column(db.String(255))  # external gateway transaction id, once integrated
    access_method = db.Column(db.String(20), nullable=False, default="purchase")  # purchase | affiliate | admin_grant

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship("User", back_populates="orders")
    product = db.relationship("Product", back_populates="orders")
    license = db.relationship("License", back_populates="order", uselist=False)
