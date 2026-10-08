"""
Single source of truth for which credits may appear (and be bought) in the marketplace.

A credit lot is LISTED only if ALL of the following hold:
  1. credit.status is AVAILABLE and it is not retired;
  2. its plantation's status is VERIFIED;
  3. the verification it was issued from is that plantation's LATEST verification,
     has decision APPROVED and a computed overall score;
  4. that verification records where its NDVI came from (ndvi_provenance). Verifications
     created before the evidence-integrity fixes have no provenance (their NDVI may have
     been simulated), so their credits are not listed;
  5. it is still owned by the plantation's farmer (primary sale; resale is not implemented).
"""
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from ..models.credit import Credit, CreditStatus
from ..models.plantation import Plantation, PlantationStatus
from ..models.verification import Verification, VerificationDecision
from .verification_store import latest_verification


def listing_check(credit: Credit, db: Session) -> Tuple[bool, Optional[str]]:
    if credit.status != CreditStatus.AVAILABLE.value or credit.is_retired:
        return False, f"Credit is {credit.status}, not AVAILABLE."
    plantation = db.get(Plantation, credit.plantation_id)
    if plantation is None:
        return False, "Credit references a plantation that does not exist."
    if plantation.status != PlantationStatus.VERIFIED.value:
        return False, f"Plantation status is {plantation.status}, not VERIFIED."
    verification = db.get(Verification, credit.verification_id)
    if verification is None:
        return False, "Credit references a verification that does not exist."
    if verification.decision != VerificationDecision.APPROVED.value or verification.overall_score is None:
        return False, f"Issuing verification is {verification.decision}, not a scored APPROVED verification."
    latest = latest_verification(db, plantation.id)
    if latest is None or latest.id != verification.id:
        return False, "A newer verification supersedes the one this credit was issued from."
    if not verification.ndvi_provenance:
        return False, "Issuing verification has no recorded NDVI provenance (legacy record)."
    if credit.owner_id != plantation.farmer_id:
        return False, "Credit has already been transferred from the producing farmer."
    return True, None


def listed_credits(db: Session) -> List[Credit]:
    candidates = (
        db.query(Credit)
        .join(Plantation, Plantation.id == Credit.plantation_id)
        .join(Verification, Verification.id == Credit.verification_id)
        .filter(
            Credit.status == CreditStatus.AVAILABLE.value,
            Credit.is_retired == 0,
            Plantation.status == PlantationStatus.VERIFIED.value,
            Verification.decision == VerificationDecision.APPROVED.value,
            Verification.overall_score.isnot(None),
            Verification.ndvi_provenance.isnot(None),
            Credit.owner_id == Plantation.farmer_id,
        )
        .order_by(Credit.created_at.desc())
        .all()
    )
    return [c for c in candidates if listing_check(c, db)[0]]


def hydrate_credit(credit: Credit, db: Session) -> Credit:
    plantation = db.get(Plantation, credit.plantation_id)
    if plantation:
        credit.plantation_name = plantation.name
        credit.location = plantation.location
        credit.farmer_name = plantation.farmer_name
        credit.image_url = plantation.image_url
        credit.plantation_status = plantation.status
    verification = db.get(Verification, credit.verification_id)
    if verification:
        credit.verification_score = verification.overall_score
        credit.verification_decision = verification.decision
        credit.ndvi_score = verification.ndvi_score
        credit.cv_score = verification.cv_score
        credit.soc_score = verification.soc_score
        credit.ndvi_provenance = verification.ndvi_provenance
    credit.is_listed = listing_check(credit, db)[0]
    return credit
