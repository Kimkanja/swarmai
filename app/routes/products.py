from flask import Blueprint, render_template, redirect, url_for, flash, abort, current_app
from flask_login import login_required, current_user

from app.extensions import db
from app.models.product import Product
from app.models.order import Order
from app.services.referral_service import submit_referral_verification
from app.forms import ReferralVerificationForm

products_bp = Blueprint("products", __name__)


@products_bp.route("/")
def catalog():
    products = Product.query.filter_by(status="live").order_by(Product.display_order).all()
    return render_template("public/products.html", products=products)


@products_bp.route("/<slug>")
def detail(slug):
    product = Product.query.filter_by(slug=slug).first_or_404()
    if product.status != "live" and not (current_user.is_authenticated and current_user.is_admin):
        abort(404)

    verification_form = ReferralVerificationForm()

    existing_verification = None
    existing_license = None
    if current_user.is_authenticated:
        from app.models.referral import ReferralVerification
        existing_verification = ReferralVerification.query.filter_by(
            user_id=current_user.id, product_id=product.id
        ).first()
        existing_license = current_user.licenses.filter_by(product_id=product.id).first()

    return render_template(
        "public/product_detail.html",
        product=product,
        verification_form=verification_form,
        existing_verification=existing_verification,
        existing_license=existing_license,
    )


@products_bp.route("/<slug>/buy", methods=["POST"])
@login_required
def buy(slug):
    """
    No automated payment gateway is used — purchases are manual. This
    records the buyer's intent as a pending order (so the admin sees it
    under Admin -> Products/Licenses) and sends them to Telegram, at the
    product's own fixed price, to complete payment and get their license
    issued by an admin.
    """
    product = Product.query.filter_by(slug=slug, status="live").first_or_404()

    order = Order(
        user_id=current_user.id,
        product_id=product.id,
        amount=product.price,
        currency=product.currency,
        status="pending",
        access_method="purchase",
    )
    db.session.add(order)
    db.session.commit()

    telegram_link = product.telegram_link(default_url=current_app.config.get("SUPPORT_TELEGRAM_URL", ""))

    if telegram_link:
        flash(f"Your order for {product.name} ({product.display_price}) has been recorded — message us on Telegram to complete payment.", "info")
        return redirect(telegram_link)

    flash(
        f"Your order for {product.name} ({product.display_price}) has been recorded. "
        f"Contact {current_app.config['SUPPORT_EMAIL']} to complete your purchase.",
        "info",
    )
    return redirect(url_for("products.detail", slug=slug))


@products_bp.route("/<slug>/free-access", methods=["POST"])
@login_required
def request_free_access(slug):
    product = Product.query.filter_by(slug=slug, status="live").first_or_404()

    if not product.free_access_enabled:
        flash("Free access is not available for this product.", "error")
        return redirect(url_for("products.detail", slug=slug))

    form = ReferralVerificationForm()
    if form.validate_on_submit():
        submit_referral_verification(current_user, product, form.submitted_reference.data.strip())
        db.session.commit()
        flash("Submitted for review. We'll notify you once it's approved.", "success")
    else:
        flash("Please provide a valid reference.", "error")

    return redirect(url_for("products.detail", slug=slug))
