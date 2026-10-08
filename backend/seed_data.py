import os
import datetime
from PIL import Image, ImageDraw
from app.database import SessionLocal, engine, Base
from app.models.user import User, UserRole
from app.models.plantation import Plantation, PlantationStatus
from app.models.verification import Verification, VerificationDecision
from app.models.credit import Credit, CreditStatus
from app.models.transaction import Transaction, TransactionStatus
from app.models.audit_log import AuditLog
from app.core.security import get_password_hash
from app.services.blockchain_service import BlockchainService
from app.config import settings

def create_sample_image(filename: str, main_color: tuple, accent_color: tuple, label: str):
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    img_path = os.path.join(settings.UPLOAD_DIR, filename)
    try:
        from ml.prepare_dataset import generate_plantation_image, generate_non_plantation_image
        if "dry" in filename or "non" in filename:
            img = generate_non_plantation_image(99, (512, 512)).resize((800, 600))
        elif "coorg" in filename:
            img = generate_plantation_image(77, (512, 512)).resize((800, 600))
        else:
            img = generate_plantation_image(42, (512, 512)).resize((800, 600))
    except Exception:
        img = Image.new("RGB", (800, 600), color=main_color)
        draw = ImageDraw.Draw(img)
        for i in range(20, 780, 60):
            for j in range(50, 550, 70):
                draw.ellipse([i-25, j-25, i+25, j+25], fill=accent_color)
                draw.rectangle([i-4, j+20, i+4, j+50], fill=(101, 67, 33))
    img.save(img_path)
    return f"/uploads/{filename}"

def seed():
    print("🌱 Initializing Database and Seeding Demo Data...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        # Create Sample Images
        img1 = create_sample_image("kaveri_agroforestry.jpg", (34, 139, 34), (46, 175, 46), "Dense Teak Canopy (82% NDVI)")
        img2 = create_sample_image("coorg_orchard.jpg", (60, 140, 70), (85, 170, 85), "Mixed Agroforestry Plot")
        img3 = create_sample_image("deccan_dryplot.jpg", (180, 160, 120), (140, 150, 80), "Semi-Arid Land (Sparse Vegetation)")

        pwd = get_password_hash("Demo@123")
        
        # 1. Users
        # Farmers
        farmer1 = User(
            email="farmer@agrocarbon.demo",
            hashed_password=pwd,
            full_name="Ramesh Kumar",
            role=UserRole.FARMER.value,
            phone="+91 98450 11223",
            organization="Kaveri Smallholder Farmers Cooperative"
        )
        farmer2 = User(
            email="farmer2@agrocarbon.demo",
            hashed_password=pwd,
            full_name="Lakshmi Devi",
            role=UserRole.FARMER.value,
            phone="+91 94480 33445",
            organization="Coorg Sustainable Growers Alliance"
        )
        # Buyers
        buyer1 = User(
            email="buyer@ecocorp.demo",
            hashed_password=pwd,
            full_name="Arun Mehta",
            role=UserRole.BUYER.value,
            phone="+91 98110 55667",
            organization="EcoCorp Solutions India Ltd (ESG Portfolio)"
        )
        buyer2 = User(
            email="buyer2@greeninvest.demo",
            hashed_password=pwd,
            full_name="Priya Sharma",
            role=UserRole.BUYER.value,
            phone="+91 99220 77889",
            organization="GreenInvest Climate Capital"
        )
        # Admin
        admin = User(
            email="admin@agrocarbon.demo",
            hashed_password=pwd,
            full_name="Dr. Sunita Rao",
            role=UserRole.ADMIN.value,
            phone="+91 80234 99001",
            organization="AgroCarbon Verification Authority (Admin & Lead Auditor)"
        )
        
        db.add_all([farmer1, farmer2, buyer1, buyer2, admin])
        db.commit()
        db.refresh(farmer1)
        db.refresh(farmer2)
        db.refresh(buyer1)
        db.refresh(buyer2)
        db.refresh(admin)
        print("✅ Demo Users Created:")
        print("   - Farmer 1: farmer@agrocarbon.demo / Demo@123")
        print("   - Farmer 2: farmer2@agrocarbon.demo / Demo@123")
        print("   - Buyer 1:  buyer@ecocorp.demo / Demo@123")
        print("   - Buyer 2:  buyer2@greeninvest.demo / Demo@123")
        print("   - Admin:    admin@agrocarbon.demo / Demo@123")

        # 2. Plantations
        p1 = Plantation(
            farmer_id=farmer1.id,
            name="Kaveri Basin Agroforestry Plot",
            farmer_name=farmer1.full_name,
            location="Mandya, Karnataka, India",
            latitude=12.5218,
            longitude=76.8951,
            area_hectares=2.5,
            plantation_age_years=4.0,
            tree_count=500,
            tree_species="Teak, Neem, Melia Dubia",
            plantation_type="Agroforestry",
            sustainable_practice="Standard Organic Agroforestry",
            image_url=img1,
            soil_soc_pct=1.80,
            soil_depth_cm=45.0,
            soil_type="Red Sandy Loam",
            status=PlantationStatus.VERIFIED.value
        )
        
        p2 = Plantation(
            farmer_id=farmer2.id,
            name="Western Ghats Mixed Canopy Orchard",
            farmer_name=farmer2.full_name,
            location="Madikeri, Coorg, Karnataka, India",
            latitude=12.4244,
            longitude=75.7382,
            area_hectares=3.0,
            plantation_age_years=2.0,
            tree_count=350,
            tree_species="Silver Oak, Coffee Shade Trees",
            plantation_type="Mixed",
            sustainable_practice="Agroforestry Intercropping",
            image_url=img2,
            soil_soc_pct=1.35,
            soil_depth_cm=35.0,
            soil_type="Loam",
            status=PlantationStatus.REVIEW.value
        )

        p3 = Plantation(
            farmer_id=farmer1.id,
            name="Deccan Semi-Arid Experimental Plot",
            farmer_name=farmer1.full_name,
            location="Ballari, Karnataka, India",
            latitude=15.1394,
            longitude=76.9214,
            area_hectares=1.2,
            plantation_age_years=1.0,
            tree_count=80,
            tree_species="Acacia Sparse",
            plantation_type="Timber",
            sustainable_practice="Standard Maintenance",
            image_url=img3,
            soil_soc_pct=0.45,
            soil_depth_cm=15.0,
            soil_type="Sandy",
            status=PlantationStatus.REJECTED.value
        )

        p4 = Plantation(
            farmer_id=farmer2.id,
            name="Cauvery Riverbed Native Agroforest",
            farmer_name=farmer2.full_name,
            location="Kushalnagar, Karnataka, India",
            latitude=12.4600,
            longitude=75.9600,
            area_hectares=4.0,
            plantation_age_years=6.0,
            tree_count=800,
            tree_species="Bamboo, Mahogany, Teak",
            plantation_type="Agroforestry",
            sustainable_practice="Biochar & Organic Composting",
            image_url=img1,
            soil_soc_pct=2.40,
            soil_depth_cm=50.0,
            soil_type="Alluvial",
            status=PlantationStatus.VERIFIED.value
        )

        db.add_all([p1, p2, p3, p4])
        db.commit()
        db.refresh(p1)
        db.refresh(p2)
        db.refresh(p3)
        db.refresh(p4)

        # 3. Verifications
        # P1: APPROVED (Score 78.6 — Benchmark Showcase Case)
        # NDVI: 82 * 0.40 = 32.8 | CV: 78 * 0.35 = 27.3 | SOC: 74 * 0.25 = 18.5 -> Total: 78.6
        v1 = Verification(
            id="VER-2026-001",
            plantation_id=p1.id,
            ndvi_value=0.72,
            ndvi_score=82.0,
            ndvi_status="Healthy",
            ndvi_historical_diff=4.2,
            image_quality_score=91.0,
            vegetation_detection_score=76.0,
            cv_score=78.0,
            cv_detection_status="Vegetation Coverage: 76%",
            soc_pct=1.80,
            soc_score=74.0,
            soc_status="Soil Score: 74/100 (Optimal Baseline)",
            ndvi_weight=0.40,
            cv_weight=0.35,
            soc_weight=0.25,
            ndvi_contribution=32.8,
            cv_contribution=27.3,
            soc_contribution=18.5,
            overall_score=78.6,
            decision=VerificationDecision.APPROVED.value,
            evidence_summary="Multi-modal verification confirmed Healthy NDVI (0.72), 76% CV Vegetation Coverage, and 1.8% Soil Organic Carbon.",
            limitations_disclaimer="Prototype verification model — not a certified carbon registry verification.",
            verified_at=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=5)
        )

        # P2: REVIEW (Score 68.0)
        v2 = Verification(
            id="VER-2026-002",
            plantation_id=p2.id,
            ndvi_value=0.56,
            ndvi_score=68.0,
            ndvi_status="Moderate Vegetation Cover",
            ndvi_historical_diff=1.8,
            image_quality_score=78.0,
            vegetation_detection_score=65.0,
            cv_score=68.0,
            cv_detection_status="Vegetation Coverage: 58%",
            soc_pct=1.35,
            soc_score=68.0,
            soc_status="Developing Baseline",
            ndvi_weight=0.40,
            cv_weight=0.35,
            soc_weight=0.25,
            ndvi_contribution=27.2,
            cv_contribution=23.8,
            soc_contribution=17.0,
            overall_score=68.0,
            decision=VerificationDecision.REVIEW.value,
            evidence_summary="Canopy index falls in intermediate review bracket (55.0 - 74.9). Flagged for human auditor review.",
            limitations_disclaimer="Prototype verification model — not a certified carbon registry verification.",
            verified_at=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=2)
        )

        # P3: REJECTED (Score 44.0)
        v3 = Verification(
            id="VER-2026-003",
            plantation_id=p3.id,
            ndvi_value=0.30,
            ndvi_score=40.0,
            ndvi_status="Degraded / Low Vegetation Index",
            ndvi_historical_diff=-3.2,
            image_quality_score=65.0,
            vegetation_detection_score=42.0,
            cv_score=46.0,
            cv_detection_status="Vegetation Coverage: 22%",
            soc_pct=0.45,
            soc_score=48.0,
            soc_status="Depleted Organic Carbon (<0.6%)",
            ndvi_weight=0.40,
            cv_weight=0.35,
            soc_weight=0.25,
            ndvi_contribution=16.0,
            cv_contribution=16.1,
            soc_contribution=12.0,
            overall_score=44.1,
            decision=VerificationDecision.REJECTED.value,
            evidence_summary="Insufficient canopy density and depleted soil organic carbon. Fails verification threshold (55.0).",
            limitations_disclaimer="Prototype verification model — not a certified carbon registry verification.",
            verified_at=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)
        )

        # P4: APPROVED (Score 88.5)
        v4 = Verification(
            id="VER-2026-004",
            plantation_id=p4.id,
            ndvi_value=0.82,
            ndvi_score=90.0,
            ndvi_status="Vigorous High-Density Canopy",
            ndvi_historical_diff=6.1,
            image_quality_score=95.0,
            vegetation_detection_score=88.0,
            cv_score=90.0,
            cv_detection_status="Vegetation Coverage: 88%",
            soc_pct=2.40,
            soc_score=88.0,
            soc_status="Optimal Carbon Density",
            ndvi_weight=0.40,
            cv_weight=0.35,
            soc_weight=0.25,
            ndvi_contribution=36.0,
            cv_contribution=31.5,
            soc_contribution=22.0,
            overall_score=89.5,
            decision=VerificationDecision.APPROVED.value,
            evidence_summary="High biomass agroforestry verified across all three modalities.",
            limitations_disclaimer="Prototype verification model — not a certified carbon registry verification.",
            verified_at=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=4)
        )

        db.add_all([v1, v2, v3, v4])
        db.commit()

        # 4. Carbon Credits with Blockchain Registration
        # Deploy fresh contract instance on local Ethereum chain for clean seed state
        BlockchainService.deploy_contract(force_new=True)

        # Report hashes from verification certificates
        h1 = BlockchainService.compute_report_hash(v1)
        h2 = BlockchainService.compute_report_hash(v4)

        # Register on local Ethereum Smart Contract
        bc1 = BlockchainService.register_credit_on_chain("CC-2026-001", p1.id, 25.0, h1)
        bc2 = BlockchainService.register_credit_on_chain("CC-2026-002", p4.id, 52.0, h2)
        bc_tr = BlockchainService.transfer_credit_on_chain("CC-2026-002")

        # Credit 1: Available for purchase from Farmer 1 (25 tCO2e @ ₹1,500 = ₹37,500)
        c1 = Credit(
            id="CC-2026-001",
            plantation_id=p1.id,
            verification_id=v1.id,
            owner_id=farmer1.id,
            carbon_quantity_tco2e=25.0,
            price_per_tco2e=1500.0,
            currency="INR",
            status=CreditStatus.AVAILABLE.value,
            tree_count=p1.tree_count,
            sequestration_rate=0.05,
            estimation_notes="Number of Trees: 500 | Base Factor: 0.05 tCO2e/tree/year | Species Multiplier: 1.0 | Practice Multiplier: 1.0 | Estimated Carbon: 25 tCO2e | Prototype Credits: 25",
            blockchain_tx_hash=bc1.get("tx_hash"),
            blockchain_contract_address=bc1.get("contract_address"),
            blockchain_status=bc1.get("status", "CONFIRMED"),
            report_hash=h1,
            is_retired=0,
            created_at=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=4)
        )

        # Credit 2: Sold to Buyer 1 (EcoCorp)
        c2 = Credit(
            id="CC-2026-002",
            plantation_id=p4.id,
            verification_id=v4.id,
            owner_id=buyer1.id,  # Transferred to buyer
            carbon_quantity_tco2e=52.0,
            price_per_tco2e=1600.0,
            currency="INR",
            status=CreditStatus.SOLD.value,
            tree_count=p4.tree_count,
            sequestration_rate=0.05,
            estimation_notes="(800 trees) × (0.05 tCO2e/tree) × Species Factor (1.30) = 52.0 tCO2e",
            blockchain_tx_hash=bc_tr.get("tx_hash", bc2.get("tx_hash")),
            blockchain_contract_address=bc2.get("contract_address"),
            blockchain_status=bc2.get("status", "CONFIRMED"),
            report_hash=h2,
            is_retired=0,
            created_at=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=3)
        )

        db.add_all([c1, c2])
        db.commit()

        # 5. Completed Transaction
        t1 = Transaction(
            id="TXN-2026-0001",
            credit_id=c2.id,
            buyer_id=buyer1.id,
            seller_id=farmer2.id,
            quantity_tco2e=52.0,
            unit_price=1600.0,
            total_amount=83200.0,
            currency="INR",
            status=TransactionStatus.COMPLETED.value,
            payment_method="PROTOTYPE_INSTANT_ESCROW",
            certificate_id="CERT-OFFSET-2026-89A4B",
            blockchain_tx_hash=bc_tr.get("tx_hash"),
            notes="Prototype Transaction — Transferred on-chain to buyer portfolio.",
            timestamp=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=2)
        )
        db.add(t1)

        # 6. Audit Logs
        a1 = AuditLog(
            user_id=admin.id,
            user_email=admin.email,
            user_role=admin.role,
            action="SYSTEM_INITIALIZATION",
            target_type="System",
            target_id="INIT",
            details="System initialized with baseline demo datasets and verification parameters."
        )
        a2 = AuditLog(
            user_id=buyer1.id,
            user_email=buyer1.email,
            user_role=buyer1.role,
            action="CREDIT_PURCHASE_COMPLETED",
            target_type="Transaction",
            target_id=t1.id,
            details=f"Buyer {buyer1.email} purchased {c2.carbon_quantity_tco2e} tCO2e ({c2.id}) for ₹{t1.total_amount}."
        )
        db.add_all([a1, a2])
        db.commit()

        print("✅ Demo Data Seeding Completed Successfully!")
        print(f"   - Plantations: 4 (2 Verified, 1 Review, 1 Rejected)")
        print(f"   - Credits: 2 (1 Available, 1 Sold)")
        print(f"   - Transactions: 1 Completed")
    except Exception as e:
        db.rollback()
        print(f"❌ Error seeding data: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed()
