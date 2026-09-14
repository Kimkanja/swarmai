from app.extensions import db


class SiteSetting(db.Model):
    """
    Simple key/value store for platform settings an admin should be able
    to change without a code deploy (maintenance mode, cache windows, etc).
    """

    __tablename__ = "site_settings"

    key = db.Column(db.String(100), primary_key=True)
    value = db.Column(db.Text)
    description = db.Column(db.String(255))

    @staticmethod
    def get(key, default=None):
        row = SiteSetting.query.get(key)
        return row.value if row else default

    @staticmethod
    def set(key, value, description=None):
        row = SiteSetting.query.get(key)
        if row:
            row.value = value
        else:
            row = SiteSetting(key=key, value=value, description=description)
            db.session.add(row)
        return row

    @staticmethod
    def get_bool(key, default=False):
        val = SiteSetting.get(key)
        if val is None:
            return default
        return str(val).lower() in ("1", "true", "yes", "on")
