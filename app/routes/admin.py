import os
from werkzeug.utils import secure_filename
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app

from app.extensions import db
from app.utils import admin_required
from app.models.user import User
from app.models.product import Product
from app.models.license import License
from app.models.referral import ReferralVerification
from app.models.settings import SiteSetting
from app.forms import ProductForm, LicenseIssueForm, UserSearchForm
from app.services.license_service import issue_license, revoke_license, set_license_status
from app.services.referral_service import approve_verification, reject_verification

admin_bp = Blueprint("admin", __name__)

ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}


def _allowed_image(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


# ---------------------------------------------------------------- overview
@admin_bp.route("/")
@admin_required
def overview():
    stats = {
        "users": User.query.count(),
        "products": Product.query.count(),
        "licenses": License.query.count(),
        "active_licenses": License.query.filter_by(status="active").count(),
        "pending_verifications": ReferralVerification.query.filter_by(status="submitted").count(),
    }
    return render_template("admin/overview.html", stats=stats)


# ------------------------------------------------------------------- users
@admin_bp.route("/users")
@admin_required
def users():
    form = UserSearchForm(request.args, meta={"csrf": False})
    query = User.query
    if form.q.data:
        like = f"%{form.q.data.strip()}%"
        query = query.filter(db.or_(User.email.ilike(like), User.full_name.ilike(like)))
    all_users = query.order_by(User.created_at.desc()).all()
    return render_template("admin/users.html", users=all_users, form=form)


@admin_bp.route("/users/<int:user_id>")
@admin_required
def user_detail(user_id):
    user = User.query.get_or_404(user_id)
    return render_template("admin/user_detail.html", user=user)


@admin_bp.route("/users/<int:user_id>/toggle-active", methods=["POST"])
@admin_required
def toggle_user_active(user_id):
    user = User.query.get_or_404(user_id)
    user.is_active_account = not user.is_active_account
    db.session.commit()
    flash(f"{user.email} is now {'active' if user.is_active_account else 'deactivated'}.", "success")
    return redirect(url_for("admin.user_detail", user_id=user.id))


# ---------------------------------------------------------------- products
@admin_bp.route("/products")
@admin_required
def products():
    all_products = Product.query.order_by(Product.display_order).all()
    return render_template("admin/products.html", products=all_products)


@admin_bp.route("/products/new", methods=["GET", "POST"])
@admin_required
def product_new():
    form = ProductForm()
    if form.validate_on_submit():
        product = Product(status="draft")
        form.populate_obj(product)
        _handle_product_image(product)
        db.session.add(product)
        db.session.commit()
        flash("Product created.", "success")
        return redirect(url_for("admin.products"))
    return render_template("admin/product_form.html", form=form, product=None)


@admin_bp.route("/products/<int:product_id>/edit", methods=["GET", "POST"])
@admin_required
def product_edit(product_id):
    product = Product.query.get_or_404(product_id)
    form = ProductForm(obj=product)
    if form.validate_on_submit():
        form.populate_obj(product)
        _handle_product_image(product)
        db.session.commit()
        flash("Product updated.", "success")
        return redirect(url_for("admin.products"))
    return render_template("admin/product_form.html", form=form, product=product)


def _handle_product_image(product):
    file = request.files.get("image")
    if file and file.filename and _allowed_image(file.filename):
        filename = secure_filename(f"product_{product.code or 'new'}_{file.filename}")
        path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
        file.save(path)
        product.image_path = f"uploads/{filename}"


@admin_bp.route("/products/<int:product_id>/delete", methods=["POST"])
@admin_required
def product_delete(product_id):
    product = Product.query.get_or_404(product_id)
    if product.licenses.count() > 0 or product.orders.count() > 0:
        # Never hard-delete a product with history — retire it instead.
        product.status = "retired"
        db.session.commit()
        flash("Product has existing licenses/orders, so it was retired instead of deleted.", "info")
    else:
        db.session.delete(product)
        db.session.commit()
        flash("Product deleted.", "success")
    return redirect(url_for("admin.products"))


# ---------------------------------------------------------------- licenses
@admin_bp.route("/licenses")
@admin_required
def licenses():
    q = request.args.get("q", "").strip()
    query = License.query
    if q:
        query = query.filter(License.license_key.ilike(f"%{q}%"))
    all_licenses = query.order_by(License.issued_at.desc()).limit(500).all()
    return render_template("admin/licenses.html", licenses=all_licenses, q=q)


@admin_bp.route("/licenses/issue", methods=["GET", "POST"])
@admin_required
def license_issue():
    form = LicenseIssueForm()
    form.product_id.choices = [(p.id, p.name) for p in Product.query.order_by(Product.name).all()]

    if form.validate_on_submit():
        user = User.query.filter_by(email=form.user_email.data.lower().strip()).first()
        if not user:
            flash("No user found with that email.", "error")
            return render_template("admin/license_issue.html", form=form)

        product = Product.query.get(form.product_id.data)
        lic = issue_license(
            user=user,
            product=product,
            access_method=form.access_method.data,
            max_activations=form.max_activations.data or None,
        )
        db.session.commit()
        flash(f"License {lic.license_key} issued to {user.email}.", "success")
        return redirect(url_for("admin.licenses"))

    return render_template("admin/license_issue.html", form=form)


@admin_bp.route("/licenses/<int:license_id>/status", methods=["POST"])
@admin_required
def license_set_status(license_id):
    lic = License.query.get_or_404(license_id)
    new_status = request.form.get("status")
    note = request.form.get("note")

    if new_status not in ("active", "suspended", "revoked"):
        flash("Invalid status.", "error")
        return redirect(url_for("admin.licenses"))

    if new_status == "revoked":
        revoke_license(lic, note=note)
    else:
        set_license_status(lic, new_status, note=note)

    db.session.commit()
    flash(f"License {lic.license_key} set to {new_status}.", "success")
    return redirect(url_for("admin.licenses"))


# --------------------------------------------------------------- referrals
@admin_bp.route("/referrals")
@admin_required
def referrals():
    verifications = ReferralVerification.query.order_by(ReferralVerification.created_at.desc()).all()
    return render_template("admin/referrals.html", verifications=verifications)


@admin_bp.route("/referrals/<int:verification_id>/approve", methods=["POST"])
@admin_required
def referral_approve(verification_id):
    from flask_login import current_user

    verification = ReferralVerification.query.get_or_404(verification_id)
    approve_verification(verification, current_user, note=request.form.get("note"))

    # Approving grants the free license for that product.
    existing = verification.user.licenses.filter_by(product_id=verification.product_id).first()
    if not existing:
        issue_license(
            user=verification.user,
            product=verification.product,
            access_method="affiliate",
            max_activations=1,
        )

    db.session.commit()
    flash("Verification approved and license issued.", "success")
    return redirect(url_for("admin.referrals"))


@admin_bp.route("/referrals/<int:verification_id>/reject", methods=["POST"])
@admin_required
def referral_reject(verification_id):
    from flask_login import current_user

    verification = ReferralVerification.query.get_or_404(verification_id)
    reject_verification(verification, current_user, note=request.form.get("note"))
    db.session.commit()
    flash("Verification rejected.", "info")
    return redirect(url_for("admin.referrals"))


# ---------------------------------------------------------------- settings
@admin_bp.route("/settings", methods=["GET", "POST"])
@admin_required
def settings():
    if request.method == "POST":
        SiteSetting.set("maintenance_mode", "true" if request.form.get("maintenance_mode") else "false")
        SiteSetting.set("validation_cache_hours", request.form.get("validation_cache_hours", "6"))
        SiteSetting.set("grace_period_hours", request.form.get("grace_period_hours", "72"))
        db.session.commit()
        flash("Settings saved.", "success")
        return redirect(url_for("admin.settings"))

    settings_map = {
        "maintenance_mode": SiteSetting.get_bool("maintenance_mode", False),
        "validation_cache_hours": SiteSetting.get("validation_cache_hours", "6"),
        "grace_period_hours": SiteSetting.get("grace_period_hours", "72"),
    }
    return render_template("admin/settings.html", settings=settings_map)
