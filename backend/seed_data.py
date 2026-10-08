"""
Seed demo accounts (and one boundary-only demo plantation) into the database.

    python seed_data.py            # add missing demo data; never deletes anything
    python seed_data.py --reset    # DROP ALL TABLES first (asks for confirmation)

What is seeded:
  * Demo user accounts for each role (password: Demo@123).
  * One 1-acre areca plantation with boundary data only. It has no photo, soil or NDVI
    evidence, so its verification is PENDING until a farmer submits real evidence.

What is deliberately NOT seeded: verification results, scores, carbon credits,
transactions or blockchain records. Those only come from running the real pipeline.
"""
import argparse
import sys

from app.core.security import get_password_hash
from app.database import Base, SessionLocal, engine, init_db
from app.models.audit_log import AuditLog
from app.models.plantation import Plantation, PlantationStatus
from app.models.user import User, UserRole

DEMO_PASSWORD = "Demo@123"

DEMO_USERS = [
    ("farmer@agrocarbon.demo", "Ramesh Kumar", UserRole.FARMER, "Demo Farmers Cooperative"),
    ("farmer2@agrocarbon.demo", "Lakshmi Devi", UserRole.FARMER, "Demo Growers Alliance"),
    ("buyer@ecocorp.demo", "Arun Mehta", UserRole.BUYER, "Demo ESG Buyer Ltd"),
    ("buyer2@greeninvest.demo", "Priya Sharma", UserRole.BUYER, "Demo Climate Fund"),
    ("auditor@agrocarbon.demo", "Kiran Shetty", UserRole.AUDITOR, "Demo Verification Desk"),
    ("admin@agrocarbon.demo", "Sunita Rao", UserRole.ADMIN, "Platform Administration"),
]

DEMO_PLANTATION = {
    "name": "Demo 1-Acre Areca Plot (boundary only)",
    "location": "Puttur, Dakshina Kannada, Karnataka, India",
    "latitude": 12.7590,
    "longitude": 75.2010,
    "area_hectares": 0.4047,  # 1 acre
    "plantation_age_years": 8.0,
    "tree_count": 500,
    "tree_species": "Areca",
    "plantation_type": "Agroforestry",
    "sustainable_practice": None,
}


def seed(reset: bool = False) -> None:
    if reset:
        Base.metadata.drop_all(bind=engine)
    init_db()

    db = SessionLocal()
    try:
        pwd = get_password_hash(DEMO_PASSWORD)
        users = {}
        for email, name, role, org in DEMO_USERS:
            user = db.query(User).filter(User.email == email).first()
            if user is None:
                user = User(email=email, hashed_password=pwd, full_name=name, role=role.value, organization=org)
                db.add(user)
                db.flush()
                print(f"  + user {email} ({role.value})")
            users[email] = user

        farmer = users["farmer@agrocarbon.demo"]
        exists = db.query(Plantation).filter(
            Plantation.farmer_id == farmer.id, Plantation.name == DEMO_PLANTATION["name"]
        ).first()
        if exists is None:
            p = Plantation(farmer_id=farmer.id, farmer_name=farmer.full_name,
                           status=PlantationStatus.SUBMITTED.value, **DEMO_PLANTATION)
            db.add(p)
            db.flush()
            db.add(AuditLog(user_id=farmer.id, user_email=farmer.email, user_role=farmer.role,
                            action="PLANTATION_REGISTERED", target_type="Plantation", target_id=str(p.id),
                            details="Demo boundary-only plantation seeded (no evidence; verification PENDING)."))
            print(f"  + plantation #{p.id} {p.name}")
        db.commit()
        print(f"Seed complete. Demo password for all accounts: {DEMO_PASSWORD}")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--reset", action="store_true", help="drop all tables before seeding (destroys data)")
    parser.add_argument("--yes", action="store_true", help="skip the --reset confirmation prompt")
    args = parser.parse_args()
    if args.reset and not args.yes:
        if input("This deletes ALL data in the configured database. Type 'reset' to continue: ").strip() != "reset":
            sys.exit("Aborted.")
    seed(reset=args.reset)
