import uuid
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from ..config import settings
from ..models.plantation import Plantation, PlantationStatus
from ..models.verification import Verification, VerificationDecision
from ..models.credit import Credit, CreditStatus
from ..models.audit_log import AuditLog
from .blockchain_service import BlockchainService

class CarbonEngine:
    """
    Carbon Sequestration Estimation & Credit Issuance Engine.
    
    Calculation Methodology (Transparent Prototype Model):
    - Annual Sequestration = Tree Count × Sequestration Rate (default 0.05 tCO2e/tree/year)
    - Multipliers: Species coefficient (fast growing vs hardwood), Sustainable practice bonus
    - Issuable Credits: 1 Credit = 1 Metric Ton CO2 equivalent (1 tCO2e)
    
    Constraints:
    - Credits can strictly only be issued for plantations with 'APPROVED' verification decision.
    """

    SPECIES_FACTORS = {
        "Teak": 1.15,
        "Neem": 1.05,
        "Melia Dubia": 1.25,      # Fast biomass accumulation
        "Bamboo": 1.30,
        "Mango": 0.95,
        "Casuarina": 1.10,
        "Mahogany": 1.20,
        "Eucalyptus": 1.15,
        "Subabul": 1.20,
        "Mixed / Native": 1.00
    }

    PRACTICE_FACTORS = {
        "Standard Organic Agroforestry": 1.00,
        "Organic Mulching & Drip Irrigation": 1.10,
        "Agroforestry Intercropping": 1.08,
        "Biochar & Organic Composting": 1.12,
        "Zero Chemical Tillage": 1.05,
        "Standard Maintenance": 1.00
    }

    @classmethod
    def calculate_estimate(
        cls,
        plantation: Plantation,
        custom_rate_per_tree: float = None
    ) -> Dict[str, Any]:
        rate = custom_rate_per_tree or settings.DEFAULT_SEQUESTRATION_RATE_PER_TREE
        
        # Check species factor
        species_factor = 1.0
        for sp, factor in cls.SPECIES_FACTORS.items():
            if sp.lower() in (plantation.tree_species or "").lower():
                species_factor = factor
                break
                
        # Check practice factor
        practice_factor = 1.0
        for pr, factor in cls.PRACTICE_FACTORS.items():
            if pr.lower() in (plantation.sustainable_practice or "").lower():
                practice_factor = factor
                break
                
        base_carbon = (plantation.tree_count or 0) * rate
        adjusted_carbon = round(base_carbon * species_factor * practice_factor, 1)
        
        # Check verification eligibility
        is_approved = (plantation.status == PlantationStatus.VERIFIED.value)
        
        assumptions = (
            f"Formula: ({plantation.tree_count} trees) × ({rate} tCO2e/tree) × "
            f"Species Factor ({species_factor}) × Practice Factor ({practice_factor}) = {adjusted_carbon} tCO2e. "
            f"Assumes 1 carbon credit = 1 metric ton of sequestered CO2."
        )
        
        return {
            "plantation_id": plantation.id,
            "tree_count": plantation.tree_count,
            "sequestration_rate_per_tree": rate,
            "species_factor": species_factor,
            "practice_factor": practice_factor,
            "estimated_carbon_tco2e": adjusted_carbon,
            "issuable_credits": adjusted_carbon,
            "suggested_price_inr": settings.BASE_CREDIT_PRICE_INR,
            "assumptions_summary": assumptions,
            "is_eligible_for_issuance": is_approved,
            "eligibility_reason": "Plantation is officially AI-VERIFIED and approved." if is_approved else "Plantation must have APPROVED verification status to issue credits."
        }

    @classmethod
    def issue_credit_for_plantation(
        cls,
        plantation: Plantation,
        verification: Verification,
        db: Session,
        price_per_tco2e: Optional[float] = None,
        issuer_user_id: Optional[int] = None,
        issuer_email: Optional[str] = None,
        issuer_role: Optional[str] = None
    ) -> Optional[Credit]:
        """
        Idempotently mints a Carbon Credit asset and registers it on-chain for an APPROVED plantation.
        Ensures the asset is persisted in the database with status 'AVAILABLE'.
        """
        # Guard: Only APPROVED verifications can be minted
        if not verification or verification.decision != VerificationDecision.APPROVED.value:
            return None

        # Check if already minted
        existing = db.query(Credit).filter(Credit.plantation_id == plantation.id).first()
        if existing:
            return existing

        estimate = cls.calculate_estimate(plantation)
        carbon_qty = estimate["estimated_carbon_tco2e"]
        if carbon_qty <= 0:
            carbon_qty = max(1.0, round((plantation.tree_count or 100) * 0.05, 1))

        credit_id = f"CC-2026-{uuid.uuid4().hex[:5].upper()}"

        # On-Chain registration
        report_hash = BlockchainService.compute_report_hash(verification)
        bc_res = BlockchainService.register_credit_on_chain(
            credit_id=credit_id,
            plantation_id=plantation.id,
            carbon_quantity_tco2e=carbon_qty,
            report_hash=report_hash
        )

        credit = Credit(
            id=credit_id,
            plantation_id=plantation.id,
            verification_id=verification.id,
            owner_id=plantation.farmer_id,
            carbon_quantity_tco2e=carbon_qty,
            price_per_tco2e=price_per_tco2e or settings.BASE_CREDIT_PRICE_INR,
            currency="INR",
            status=CreditStatus.AVAILABLE.value,
            tree_count=plantation.tree_count or 0,
            sequestration_rate=estimate["sequestration_rate_per_tree"],
            estimation_notes=estimate["assumptions_summary"],
            blockchain_tx_hash=bc_res.get("tx_hash"),
            blockchain_contract_address=bc_res.get("contract_address"),
            blockchain_status=bc_res.get("status", "CONFIRMED"),
            report_hash=report_hash,
            is_retired=0
        )
        db.add(credit)

        audit = AuditLog(
            user_id=issuer_user_id or plantation.farmer_id,
            user_email=issuer_email or "system@agrocarbon.demo",
            user_role=issuer_role or "SYSTEM",
            action="CARBON_CREDIT_ISSUED",
            target_type="Credit",
            target_id=credit.id,
            details=f"Issued {carbon_qty} tCO2e carbon credit ({credit.id}) for verified plantation #{plantation.id} ('{plantation.name}'). Status: AVAILABLE."
        )
        db.add(audit)
        db.commit()
        db.refresh(credit)
        return credit
