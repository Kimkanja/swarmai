from flask import Blueprint, render_template, url_for
from flask_login import login_required, current_user

referral_bp = Blueprint("referral", __name__)


@referral_bp.route("/")
@login_required
def home():
    referral_link = url_for("auth.register", ref=current_user.referral_code, _external=True)
    referred_users = current_user.referrals  # backref from User.referred_by
    return render_template(
        "dashboard/referrals.html",
        referral_link=referral_link,
        referred_users=referred_users,
    )
