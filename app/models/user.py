import secrets
from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import db


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)

    role = db.Column(db.String(20), nullable=False, default="user")  # 'user' | 'admin'
    is_active_account = db.Column(db.Boolean, nullable=False, default=True)

    country = db.Column(db.String(80))
    phone = db.Column(db.String(40))

    # Referral program
    referral_code = db.Column(db.String(16), unique=True, nullable=False, index=True)
    referred_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    referred_by = db.relationship("User", remote_side=[id], backref="referrals")

    # Password reset
    reset_token = db.Column(db.String(128), nullable=True, index=True)
    reset_token_expires_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    licenses = db.relationship("License", back_populates="user", lazy="dynamic")
    orders = db.relationship("Order", back_populates="user", lazy="dynamic")

    # --- Flask-Login required property ---
    # UserMixin already provides get_id() using self.id

    def set_password(self, raw_password):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password_hash, raw_password)

    @staticmethod
    def generate_referral_code():
        while True:
            code = secrets.token_hex(4).upper()  # 8 hex chars
            if not User.query.filter_by(referral_code=code).first():
                return code

    def generate_reset_token(self, expires_in_minutes=30):
        from datetime import timedelta
        self.reset_token = secrets.token_urlsafe(48)
        self.reset_token_expires_at = datetime.utcnow() + timedelta(minutes=expires_in_minutes)
        return self.reset_token

    def clear_reset_token(self):
        self.reset_token = None
        self.reset_token_expires_at = None

    def reset_token_is_valid(self, token):
        return (
            self.reset_token
            and secrets.compare_digest(self.reset_token, token)
            and self.reset_token_expires_at
            and self.reset_token_expires_at > datetime.utcnow()
        )

    @property
    def is_admin(self):
        return self.role == "admin"

    # UserMixin.is_active is a property by default; override to respect
    # our own is_active_account flag (admin can deactivate accounts).
    @property
    def is_active(self):
        return self.is_active_account

    def __repr__(self):
        return f"<User {self.email}>"
