from flask import Blueprint, render_template

from app.models.product import Product

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def home():
    products = Product.query.filter_by(status="live").order_by(Product.display_order).all()
    return render_template("public/home.html", products=products)


@main_bp.route("/how-it-works")
def how_it_works():
    return render_template("public/how_it_works.html")


@main_bp.route("/faq")
def faq():
    return render_template("public/faq.html")


@main_bp.route("/contact")
def contact():
    return render_template("public/contact.html")
