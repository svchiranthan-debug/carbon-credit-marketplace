"""Authentication and role isolation (replaces test_role_auth / test_portal_auth_routing / test_auditor_dashboard_access)."""
import uuid

from conftest import login, plantation_payload, register


def test_register_and_login_each_self_service_role(client):
    for role in ("FARMER", "BUYER"):
        email = f"{role.lower()}_{uuid.uuid4().hex[:8]}@test.example"
        r = client.post("/api/auth/register", json={"email": email, "password": "TestPass@123", "full_name": f"{role} One", "role": role})
        assert r.status_code == 201, r.text
        assert r.json()["user"]["role"] == role
        r = client.post("/api/auth/login", json={"email": email.upper(), "password": "TestPass@123", "role": role})
        assert r.status_code == 200
        me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"})
        assert me.json()["email"] == email


def test_admin_and_auditor_roles_cannot_self_register(client):
    for role in ("ADMIN", "AUDITOR"):
        r = client.post("/api/auth/register", json={"email": f"x{uuid.uuid4().hex[:6]}@test.example", "password": "TestPass@123", "full_name": "X", "role": role})
        assert r.status_code == 422, role
    assert "administrator" in str(r.json()["detail"])


def test_only_admin_can_create_auditors(client):
    body = {"email": f"aud_{uuid.uuid4().hex[:6]}@test.example", "password": "TestPass@123", "full_name": "New Auditor", "role": "AUDITOR"}
    farmer, _ = register(client, "FARMER")
    auditor, _ = register(client, "AUDITOR")
    assert client.post("/api/users", json=body).status_code == 401
    assert client.post("/api/users", headers=farmer, json=body).status_code == 403
    assert client.post("/api/users", headers=auditor, json=body).status_code == 403
    admin = login(client, "admin@agrocarbon.demo")
    r = client.post("/api/users", headers=admin, json=body)
    assert r.status_code == 201 and r.json()["role"] == "AUDITOR"
    assert client.post("/api/users", headers=admin, json=body).status_code == 400  # duplicate email
    assert client.post("/api/users", headers=admin, json={**body, "email": "x" + body["email"], "role": "ADMIN"}).status_code == 422
    assert client.post("/api/auth/login", json={"email": body["email"], "password": "TestPass@123"}).json()["user"]["role"] == "AUDITOR"


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
