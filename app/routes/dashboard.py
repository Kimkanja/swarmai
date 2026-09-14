from flask import Blueprint, render_template, flash, redirect, url_for
from flask_login import login_required, current_user

from app.extensions import db
from app.forms import ProfileForm

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
@login_required
def home():
    licenses = current_user.licenses.order_by(None).all()
    return render_template("dashboard/home.html", licenses=licenses)


@dashboard_bp.route("/licenses")
@login_required
def licenses():
    user_licenses = current_user.licenses.all()
    return render_template("dashboard/licenses.html", licenses=user_licenses)


@dashboard_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    form = ProfileForm(obj=current_user)
    if form.validate_on_submit():
        current_user.full_name = form.full_name.data.strip()
        current_user.country = form.country.data
        current_user.phone = form.phone.data
        db.session.commit()
        flash("Profile updated.", "success")
        return redirect(url_for("dashboard.profile"))

    return render_template("dashboard/profile.html", form=form)
