"""Authentication and role isolation (replaces test_role_auth / test_portal_auth_routing / test_auditor_dashboard_access)."""
import uuid

from conftest import login, plantation_payload, register


def test_register_and_login_each_self_service_role(client):
    for role in ("FARMER", "BUYER", "AUDITOR"):
        email = f"{role.lower()}_{uuid.uuid4().hex[:8]}@test.example"
        r = client.post("/api/auth/register", json={"email": email, "password": "TestPass@123", "full_name": f"{role} One", "role": role})
        assert r.status_code == 201, r.text
        assert r.json()["user"]["role"] == role
        r = client.post("/api/auth/login", json={"email": email.upper(), "password": "TestPass@123", "role": role})
        assert r.status_code == 200
        me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"})
        assert me.json()["email"] == email


def test_admin_role_cannot_self_register(client):
    r = client.post("/api/auth/register", json={"email": f"x{uuid.uuid4().hex[:6]}@test.example", "password": "TestPass@123", "full_name": "X", "role": "ADMIN"})
    assert r.status_code == 422


def test_registration_validation(client):
    bad = [
        {"email": "not-an-email", "password": "TestPass@123", "full_name": "A", "role": "FARMER"},
        {"email": "a@test.example", "password": "short", "full_name": "A", "role": "FARMER"},
        {"email": "a@test.example", "password": "TestPass@123", "full_name": "   ", "role": "FARMER"},
        {"email": "a@test.example", "password": "TestPass@123", "full_name": "A", "role": "WIZARD"},
    ]
    for body in bad:
        assert client.post("/api/auth/register", json=body).status_code == 422, body


def test_duplicate_email_rejected(client):
    email = f"dup_{uuid.uuid4().hex[:6]}@test.example"
    body = {"email": email, "password": "TestPass@123", "full_name": "A", "role": "BUYER"}
    assert client.post("/api/auth/register", json=body).status_code == 201
    assert client.post("/api/auth/register", json=body).status_code == 400


def test_wrong_password_and_missing_token(client):
    assert client.post("/api/auth/login", json={"email": "farmer@agrocarbon.demo", "password": "nope"}).status_code == 401
    assert client.get("/api/plantations").status_code == 401
    assert client.get("/api/plantations", headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_role_isolation(client):
    farmer, _ = register(client, "FARMER")
    buyer, _ = register(client, "BUYER")
    auditor, _ = register(client, "AUDITOR")
    admin = login(client, "admin@agrocarbon.demo")

    for h in (auditor, admin):
        assert client.get("/api/admin/verifications", headers=h).status_code == 200
        assert client.get("/api/admin/metrics", headers=h).status_code == 200
    for h in (farmer, buyer):
        assert client.get("/api/admin/verifications", headers=h).status_code == 403
        assert client.get("/api/admin/metrics", headers=h).status_code == 403

    # Only farmers register plantations
    for h in (buyer, auditor):
        assert client.post("/api/plantations", headers=h, json=plantation_payload()).status_code == 403
    assert client.post("/api/plantations", headers=farmer, json=plantation_payload()).status_code == 201

    # Farmers cannot buy
    assert client.post("/api/marketplace/credits/CC-NOPE/purchase", headers=farmer, json={}).status_code == 403
