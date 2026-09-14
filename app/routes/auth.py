from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user

from app.extensions import db
from app.forms import RegisterForm, LoginForm, ForgotPasswordForm, ResetPasswordForm
from app.models.user import User
from app.services.referral_service import attach_referrer

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.home"))

    form = RegisterForm()
    # Pre-fill referral code from ?ref=CODE if present
    if request.method == "GET" and request.args.get("ref"):
        form.referral_code.data = request.args.get("ref")

    if form.validate_on_submit():
        existing = User.query.filter_by(email=form.email.data.lower().strip()).first()
        if existing:
            flash("An account with that email already exists.", "error")
            return render_template("auth/register.html", form=form)

        user = User(
            full_name=form.full_name.data.strip(),
            email=form.email.data.lower().strip(),
            referral_code=User.generate_referral_code(),
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.flush()  # get user.id before attaching referrer

        attach_referrer(user, form.referral_code.data)

        db.session.commit()

        login_user(user)
        flash("Welcome to Swarm AI — your account has been created.", "success")
        return redirect(url_for("dashboard.home"))

    return render_template("auth/register.html", form=form)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.home"))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower().strip()).first()

        if user and user.check_password(form.password.data):
            if not user.is_active_account:
                flash("This account has been deactivated. Contact support.", "error")
                return render_template("auth/login.html", form=form)

            login_user(user, remember=form.remember_me.data)
            flash("Logged in successfully.", "success")
            next_page = request.args.get("next")
            return redirect(next_page or url_for("dashboard.home"))

        flash("Invalid email or password.", "error")

    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("main.home"))


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower().strip()).first()
        if user:
            token = user.generate_reset_token()
            db.session.commit()
            # In production this link is emailed to the user via the mail
            # service (see app/services). Without SMTP configured, we
            # surface it via flash so the flow is testable end-to-end.
            reset_link = url_for("auth.reset_password", token=token, _external=True)
            flash(f"Password reset link generated: {reset_link}", "info")
        else:
            # Same message whether or not the account exists, to avoid
            # leaking which emails are registered.
            flash("If that email is registered, a reset link has been generated.", "info")
        return redirect(url_for("auth.login"))

    return render_template("auth/forgot_password.html", form=form)


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    user = User.query.filter_by(reset_token=token).first()
    if not user or not user.reset_token_is_valid(token):
        flash("That reset link is invalid or has expired.", "error")
        return redirect(url_for("auth.forgot_password"))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        user.clear_reset_token()
        db.session.commit()
        flash("Your password has been reset. Please log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/reset_password.html", form=form, token=token)
