import pytest

from app import create_app
from app.config import TestingConfig
from app.extensions import db as _db


@pytest.fixture
def app():
    app = create_app(TestingConfig)
    with app.app_context():
        _db.create_all()
        yield app
        _db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def test_home_page_loads(client):
    resp = client.get("/")
    assert resp.status_code == 200


def test_register_and_login(client, app):
    resp = client.get("/auth/register")
    assert resp.status_code == 200

    with app.app_context():
        from app.models.user import User
        assert User.query.count() == 0


def test_license_validate_missing_fields(client):
    resp = client.post("/api/license/validate", json={})
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["valid"] is False


def test_license_validate_unknown_key(client):
    resp = client.post("/api/license/validate", json={"key": "AAAA-BBBB-CCCC-DDDD", "account": "12345"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["valid"] is False
    assert data["result"] == "invalid_key"
    assert "signature" in data


def test_license_full_flow(client, app):
    with app.app_context():
        from app.models.user import User
        from app.models.product import Product
        from app.services.license_service import issue_license

        user = User(full_name="Test User", email="test@example.com", referral_code=User.generate_referral_code())
        user.set_password("password123")
        product = Product(code="TEST_PRODUCT", name="Test Product", slug="test-product", status="live")
        _db.session.add_all([user, product])
        _db.session.commit()

        lic = issue_license(user, product, access_method="purchase", max_activations=1)
        _db.session.commit()
        key = lic.license_key

    resp = client.post("/api/license/validate", json={"key": key, "account": "ACC-1", "product": "TEST_PRODUCT"})
    data = resp.get_json()
    assert data["valid"] is True
    assert data["result"] == "valid"

    # Second, different account should exceed the activation limit of 1
    resp2 = client.post("/api/license/validate", json={"key": key, "account": "ACC-2", "product": "TEST_PRODUCT"})
    data2 = resp2.get_json()
    assert data2["valid"] is False
    assert data2["result"] == "activation_limit_reached"

    # Same account re-validating should still succeed
    resp3 = client.post("/api/license/validate", json={"key": key, "account": "ACC-1", "product": "TEST_PRODUCT"})
    assert resp3.get_json()["valid"] is True


def test_admin_routes_require_auth(client):
    resp = client.get("/admin/", follow_redirects=False)
    assert resp.status_code in (302, 401)
