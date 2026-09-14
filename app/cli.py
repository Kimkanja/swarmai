import os
import click

from app.extensions import db


def register_cli(app):

    @app.cli.command("seed-admin")
    def seed_admin():
        """Create the initial admin user from ADMIN_EMAIL / ADMIN_PASSWORD env vars."""
        from app.models.user import User

        email = os.environ.get("ADMIN_EMAIL")
        password = os.environ.get("ADMIN_PASSWORD")

        if not email or not password:
            click.echo("Set ADMIN_EMAIL and ADMIN_PASSWORD in your environment first.")
            return

        existing = User.query.filter_by(email=email.lower()).first()
        if existing:
            existing.role = "admin"
            db.session.commit()
            click.echo(f"{email} already existed — promoted to admin.")
            return

        admin = User(
            full_name="Administrator",
            email=email.lower(),
            role="admin",
            referral_code=User.generate_referral_code(),
        )
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        click.echo(f"Admin user created: {email}")

    @app.cli.command("seed-products")
    def seed_products():
        """
        Seed the two launch products as placeholders. Content (pricing,
        descriptions, images) should be filled in from the admin panel —
        no prices or business facts are invented here.
        """
        from app.models.product import Product

        defaults = [
            dict(
                code="VERTEX_MILLIONAIRE",
                name="Vertex Millionaire",
                slug="vertex-millionaire",
                tagline="Our flagship automated trading system.",
                short_description="Configure this product's description from the admin dashboard.",
                status="draft",
                display_order=0,
                free_access_enabled=False,
                license_required=True,
            ),
            dict(
                code="PRODUCT_TWO",
                name="Second Product",
                slug="second-product",
                tagline="Rename and configure this from the admin dashboard.",
                short_description="Placeholder — replace with the second product's details.",
                status="draft",
                display_order=1,
                free_access_enabled=False,
                license_required=True,
            ),
        ]

        for data in defaults:
            if not Product.query.filter_by(code=data["code"]).first():
                db.session.add(Product(**data))
                click.echo(f"Created placeholder product: {data['name']}")
            else:
                click.echo(f"Product {data['code']} already exists — skipped.")

        db.session.commit()
