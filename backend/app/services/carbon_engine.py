import uuid
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from ..config import settings
from ..models.plantation import Plantation, PlantationStatus
from ..models.verification import Verification, VerificationDecision
from ..models.credit import Credit, CreditStatus
from ..models.audit_log import AuditLog
from .blockchain_service import BlockchainService

class CreditIssuanceError(Exception):
    """Raised when a credit cannot be issued; the message is safe to show to API clients."""


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
        
        # Eligibility is decided by the latest verification (see issue_credit_for_plantation)
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
    ) -> Credit:
        """
        Idempotently mints the carbon credit lot for a plantation.

        Raises CreditIssuanceError unless ALL of the following hold:
          * the given verification is the plantation's latest verification,
          * its decision is APPROVED and it has a computed overall score,
          * the plantation status is VERIFIED,
          * the estimated quantity is greater than zero.
        """
        if verification is None or verification.plantation_id != plantation.id:
            raise CreditIssuanceError("A verification record for this plantation is required.")
        if verification.decision != VerificationDecision.APPROVED.value:
            raise CreditIssuanceError(f"Verification decision is {verification.decision}; only APPROVED verifications can issue credits.")
        if verification.overall_score is None:
            raise CreditIssuanceError("Verification has no computed score; credits cannot be issued.")
        if plantation.status != PlantationStatus.VERIFIED.value:
            raise CreditIssuanceError(f"Plantation status is {plantation.status}; it must be VERIFIED.")
        latest = (
            db.query(Verification)
            .filter(Verification.plantation_id == plantation.id)
            .order_by(Verification.verified_at.desc())
            .first()
        )
        if latest is None or latest.id != verification.id:
            raise CreditIssuanceError("Only the latest verification of a plantation can issue credits.")

        existing = db.query(Credit).filter(Credit.plantation_id == plantation.id).first()
        if existing:
            return existing

        estimate = cls.calculate_estimate(plantation)
        carbon_qty = estimate["estimated_carbon_tco2e"]
        if carbon_qty is None or carbon_qty <= 0:
            raise CreditIssuanceError("Estimated sequestration is zero; no credits can be issued.")
        price = price_per_tco2e if price_per_tco2e is not None else settings.BASE_CREDIT_PRICE_INR
        if price <= 0:
            raise CreditIssuanceError("Price per tCO2e must be greater than zero.")

        credit_id = f"CC-{datetime.utcnow():%Y}-{uuid.uuid4().hex[:6].upper()}"
        report_hash = BlockchainService.compute_report_hash(verification)
        bc_res = BlockchainService.register_credit_on_chain(
            credit_id=credit_id,
            plantation_id=plantation.id,
            carbon_quantity_tco2e=carbon_qty,
            report_hash=report_hash,
            owner_user_id=plantation.farmer_id,
        )

        credit = Credit(
            id=credit_id,
            plantation_id=plantation.id,
            verification_id=verification.id,
            owner_id=plantation.farmer_id,
            carbon_quantity_tco2e=carbon_qty,
            price_per_tco2e=price,
            currency="INR",
            status=CreditStatus.AVAILABLE.value,
            tree_count=plantation.tree_count,
            sequestration_rate=estimate["sequestration_rate_per_tree"],
            estimation_notes=estimate["assumptions_summary"],
            blockchain_tx_hash=bc_res.get("tx_hash"),
            blockchain_contract_address=bc_res.get("contract_address"),
            blockchain_status=bc_res["status"],
            report_hash=report_hash,
            is_retired=0
        )
        db.add(credit)
        chain_note = (
            f"On-chain tx {bc_res['tx_hash']}." if bc_res["status"] == "CONFIRMED"
            else f"Not recorded on-chain ({bc_res.get('reason')})."
        )
        db.add(AuditLog(
            user_id=issuer_user_id,
            user_email=issuer_email or "system",
            user_role=issuer_role or "SYSTEM",
            action="CARBON_CREDIT_ISSUED",
            target_type="Credit",
            target_id=credit.id,
            details=(
                f"Issued {carbon_qty} tCO2e ({credit.id}) for plantation #{plantation.id} from APPROVED "
                f"verification {verification.id} (score {verification.overall_score}). {chain_note}"
            ),
        ))
        db.commit()
        db.refresh(credit)
        return credit
