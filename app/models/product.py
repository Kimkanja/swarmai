from datetime import datetime

from app.extensions import db


class Product(db.Model):
    """
    A trading software product. Everything shown on the public product
    pages and used to drive pricing/access logic is database-driven so
    an admin can add a third, fourth, etc. product without code changes.
    """

    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)

    code = db.Column(db.String(64), unique=True, nullable=False, index=True)  # e.g. VERTEX_MILLIONAIRE
    name = db.Column(db.String(150), nullable=False)
    slug = db.Column(db.String(150), unique=True, nullable=False, index=True)
    tagline = db.Column(db.String(255))

    short_description = db.Column(db.String(500))
    description = db.Column(db.Text)
    features = db.Column(db.Text)  # newline-separated bullet points, rendered as a list

    status = db.Column(db.String(20), nullable=False, default="draft")  # draft | live | retired
    display_order = db.Column(db.Integer, nullable=False, default=0)

    # --- Pricing (configurable, never invented) ---
    price = db.Column(db.Numeric(10, 2), nullable=True)  # null = "contact us" / TBD
    currency = db.Column(db.String(10), nullable=False, default="USD")
    purchase_url = db.Column(db.String(500))  # optional external checkout link, if ever used

    # Manual purchase route: buyers message this Telegram contact to pay and
    # get their license issued — no automated payment gateway is used.
    # Falls back to the site-wide SUPPORT_TELEGRAM_URL when left blank.
    telegram_url = db.Column(db.String(300))

    # --- Access methods ---
    free_access_enabled = db.Column(db.Boolean, nullable=False, default=False)
    affiliate_requirements = db.Column(db.Text)  # admin-editable free text describing the affiliate route

    # --- Software metadata ---
    version = db.Column(db.String(40))
    platform = db.Column(db.String(40))  # e.g. MT4, MT5
    download_url = db.Column(db.String(500))
    license_required = db.Column(db.Boolean, nullable=False, default=True)

    image_path = db.Column(db.String(300))  # relative path under static/uploads

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    licenses = db.relationship("License", back_populates="product", lazy="dynamic")
    orders = db.relationship("Order", back_populates="product", lazy="dynamic")

    @property
    def feature_list(self):
        if not self.features:
            return []
        return [line.strip() for line in self.features.splitlines() if line.strip()]

    @property
    def is_live(self):
        return self.status == "live"

    @property
    def display_price(self):
        if self.price is None:
            return "Contact us"
        return f"{self.currency} {self.price:,.2f}"

    def telegram_link(self, default_url="", prefill=True):
        """
        Effective Telegram contact link for buying this product: the
        product's own override if set, otherwise the site-wide default.
        With prefill=True, appends a ready-to-send message naming the
        product and its price so the buyer doesn't have to type it out.
        """
        base = (self.telegram_url or default_url or "").strip()
        if not base:
            return ""
        if not prefill:
            return base
        from urllib.parse import quote
        text = f"Hi, I'd like to purchase {self.name} ({self.display_price})."
        separator = "&" if "?" in base else "?"
        return f"{base}{separator}text={quote(text)}"

    def __repr__(self):
        return f"<Product {self.code}>"
