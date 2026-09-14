import secrets
from datetime import datetime

from app.extensions import db


def _format_license_key(raw_hex: str) -> str:
    """Turn a hex string into XXXX-XXXX-XXXX-XXXX groups."""
    raw_hex = raw_hex.upper()
    groups = [raw_hex[i:i + 4] for i in range(0, len(raw_hex), 4)]
    return "-".join(groups)


class License(db.Model):
    """
    A single license: one user, one product, one key.

    The key itself is the credential an EA presents to the validation
    API — it must be unpredictable, so it's generated from
    secrets.token_hex (CSPRNG), never from a counter or user data.
    """

    __tablename__ = "licenses"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False, index=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=True)

    license_key = db.Column(db.String(40), unique=True, nullable=False, index=True)

    # active: usable | suspended: temporarily blocked | revoked: permanently blocked
    status = db.Column(db.String(20), nullable=False, default="active")

    access_method = db.Column(db.String(20), nullable=False, default="purchase")  # purchase | affiliate | admin_grant

    max_activations = db.Column(db.Integer, nullable=True)  # null = unlimited

    issued_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=True)  # null = never expires
    revoked_at = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text)

    user = db.relationship("User", back_populates="licenses")
    product = db.relationship("Product", back_populates="licenses")
    order = db.relationship("Order", back_populates="license", uselist=False)
    bindings = db.relationship("LicenseBinding", back_populates="license", cascade="all, delete-orphan")

    @staticmethod
    def generate_key():
        while True:
            key = _format_license_key(secrets.token_hex(8))  # 16 hex chars -> 4 groups of 4
            if not License.query.filter_by(license_key=key).first():
                return key

    @property
    def is_expired(self):
        return bool(self.expires_at and self.expires_at < datetime.utcnow())

    @property
    def is_usable(self):
        return self.status == "active" and not self.is_expired

    @property
    def active_binding_count(self):
        return sum(1 for b in self.bindings if b.is_active)

    def __repr__(self):
        return f"<License {self.license_key} status={self.status}>"


class LicenseBinding(db.Model):
    """
    Links a license to a specific trading account / terminal, so the
    EA-side validation can enforce activation limits per license.
    """

    __tablename__ = "license_bindings"

    id = db.Column(db.Integer, primary_key=True)
    license_id = db.Column(db.Integer, db.ForeignKey("licenses.id"), nullable=False, index=True)

    account_identifier = db.Column(db.String(120), nullable=False)  # broker account number / terminal id
    terminal_id = db.Column(db.String(120))
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    activated_at = db.Column(db.DateTime, default=datetime.utcnow)
    deactivated_at = db.Column(db.DateTime, nullable=True)

    license = db.relationship("License", back_populates="bindings")

    __table_args__ = (
        db.UniqueConstraint("license_id", "account_identifier", name="uq_license_account"),
    )


class ValidationLog(db.Model):
    """Every /api/license/validate call, for auditing and rate limiting."""

    __tablename__ = "validation_logs"

    id = db.Column(db.Integer, primary_key=True)
    license_key = db.Column(db.String(40), index=True)
    account_identifier = db.Column(db.String(120))
    result = db.Column(db.String(30), nullable=False)
    ea_version = db.Column(db.String(40))
    ip_address = db.Column(db.String(64))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
