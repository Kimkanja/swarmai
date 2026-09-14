from functools import wraps

from flask import abort
from flask_login import current_user, login_required


def admin_required(view_func):
    """
    Protects a route so only authenticated users with role == 'admin'
    can access it. Role is always read from the database via
    current_user — never trusted from the request (form field, header,
    query string, etc).
    """
    @wraps(view_func)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return view_func(*args, **kwargs)
    return wrapped
