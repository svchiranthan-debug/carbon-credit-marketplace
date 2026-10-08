"""Persistence and read-model helpers for verification results (shared by routers)."""
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from ..models.audit_log import AuditLog
from ..models.plantation import Plantation, PlantationStatus
from ..models.user import User
from ..models.verification import Verification, VerificationDecision
from .verification_engine import VerificationEngine

DECISION_TO_PLANTATION_STATUS = {
    VerificationDecision.APPROVED.value: PlantationStatus.VERIFIED.value,
    VerificationDecision.REVIEW.value: PlantationStatus.REVIEW.value,
    VerificationDecision.REJECTED.value: PlantationStatus.REJECTED.value,
    VerificationDecision.PENDING.value: PlantationStatus.SUBMITTED.value,
}

_PERSISTED_FIELDS = [
    "ndvi_value", "ndvi_score", "ndvi_status", "ndvi_historical_diff", "is_real_satellite",
    "satellite_source", "acquisition_date", "mean_ndvi", "min_ndvi", "max_ndvi",
    "vegetation_coverage_pct", "ndvi_provenance",
    "image_quality_score", "vegetation_detection_score", "cv_score", "cv_detection_status",
    "ai_model_name", "ai_model_version", "ai_predicted_class", "ai_confidence_pct", "image_phash",
    "soc_pct", "soc_score", "soc_status",
    "ndvi_weight", "cv_weight", "soc_weight", "ndvi_contribution", "cv_contribution", "soc_contribution",
    "overall_score", "decision", "engine_decision", "decided_by",
    "risk_score", "risk_level", "risk_factors", "risk_explanation",
    "decision_reasons", "evidence_snapshot", "evidence_status", "missing_evidence", "evidence_summary", "limitations_disclaimer", "verified_at",
]


def latest_verification(db: Session, plantation_id: int) -> Optional[Verification]:
    return (
        db.query(Verification)
        .filter(Verification.plantation_id == plantation_id)
        .order_by(Verification.verified_at.desc())
        .first()
    )


def persist_verification(result: Dict[str, Any], plantation: Plantation, actor: User, db: Session) -> Verification:
    verification = Verification(id=result["id"], plantation_id=plantation.id,
                                **{k: result.get(k) for k in _PERSISTED_FIELDS})
    db.add(verification)
    plantation.status = DECISION_TO_PLANTATION_STATUS[result["decision"]]
    db.add(AuditLog(
        user_id=actor.id,
        user_email=actor.email,
        user_role=actor.role,
        action="VERIFICATION_AUDIT_EXECUTED",
        target_type="Verification",
        target_id=verification.id,
        details=(
            f"Verification run for plantation #{plantation.id}: score {result.get('overall_score')} "
            f"→ {result['decision']}. Reasons: {' | '.join(result.get('decision_reasons') or [])[:900]}"
        ),
    ))
    db.commit()
    db.refresh(verification)
    return verification


def hydrate(verification: Any, plantation: Optional[Plantation]) -> Any:
    """Attach plantation display fields and the current evidence checklist to a verification."""
    if plantation is not None:
        verification.plantation_name = plantation.name
        verification.farmer_name = plantation.farmer_name
        verification.location = plantation.location
        verification.area_hectares = plantation.area_hectares
        verification.tree_count = plantation.tree_count
        verification.tree_species = plantation.tree_species
        verification.plantation_status = plantation.status
        verification.image_url = plantation.image_url
        audit = VerificationEngine.check_evidence_completeness(plantation)
        stored = getattr(verification, "evidence_status", None)
        if not isinstance(stored, dict):
            verification.evidence_status = audit["evidence_status"]
        verification.current_missing_evidence = audit["missing_modalities"]
        if getattr(verification, "missing_evidence", None) is None:
            verification.missing_evidence = audit["missing_modalities"]
    return verification


class PreviewVerification:
    """A non-persisted, read-only 'not yet verified' view for plantations with no verification run."""

    def __init__(self, plantation: Plantation):
        audit = VerificationEngine.check_evidence_completeness(plantation)
        self.id = None
        self.is_persisted = False
        self.plantation_id = plantation.id
        for field in _PERSISTED_FIELDS:
            setattr(self, field, None)
        self.ndvi_weight = VerificationEngine.WEIGHT_NDVI
        self.cv_weight = VerificationEngine.WEIGHT_CV
        self.soc_weight = VerificationEngine.WEIGHT_SOC
        self.ndvi_status = "PENDING"
        self.cv_detection_status = audit["evidence_status"]["ground_imagery"]
        self.soc_status = audit["evidence_status"]["soil_carbon"]
        self.soc_pct = plantation.soil_soc_pct if audit["has_soil"] else None
        self.is_real_satellite = False
        self.decision = VerificationDecision.PENDING.value
        self.risk_factors = []
        self.evidence_status = audit["evidence_status"]
        self.missing_evidence = audit["missing_modalities"]
        missing = audit["missing_modalities"]
        self.decision_reasons = (
            [f"Missing required evidence: {m}." for m in missing]
            + ["No verification has been run for this plantation yet."]
        )
        self.evidence_summary = (
            f"Not yet verified. Missing: {', '.join(missing)}." if missing
            else "Not yet verified. All required evidence is present; run verification to score it."
        )
        self.limitations_disclaimer = "No verification has been run yet."
        self.verified_at = None
        hydrate(self, plantation)
