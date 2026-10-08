"""
Multi-modal verification engine.

    Verification Score = 0.40 × NDVI score + 0.35 × CV score + 0.25 × SOC score

Status pipeline:  PENDING  →  (verification run)  →  APPROVED | REVIEW | REJECTED

Rules (enforced here and covered by tests/test_verification_engine_rules.py):
  1. Required evidence: plantation boundary (centroid + area), a valid ground photograph,
     and a soil organic carbon (SOC) measurement. If any is missing the decision is PENDING.
  2. Every modality score must be measured. If NDVI cannot be obtained (satellite
     unavailable and no reported NDVI), or the photo classifier cannot run, the decision
     is PENDING. Missing values are returned as null — never defaulted or simulated.
  3. With all three scores: >= 75 → APPROVED, >= 55 → REVIEW, < 55 → REJECTED.
  4. HIGH fraud risk downgrades APPROVED to REVIEW.
  5. Reported (not backend-computed) NDVI downgrades APPROVED to REVIEW, so a human
     auditor must confirm it before any credit can be issued.
  6. Every result carries ``decision_reasons`` (why) and ``evidence_snapshot`` (the exact
     inputs used), which are persisted with the verification for auditability.
  7. Credits are never issued here. They are minted only from a persisted APPROVED
     verification (see CarbonEngine.issue_credit_for_plantation).
"""
import hashlib
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from ..config import settings
from ..models.plantation import Plantation
from ..models.verification import VerificationDecision
from .ai.ai_vision_service import validate_image_file
from .ai.cv_service import CVService
from .ai.ndvi_service import NDVIService, PROVENANCE_REPORTED
from .ai.soc_service import SOCService
from .risk_engine import RiskEngine

ENGINE_NAME = "VERIFICATION_ENGINE"
ENGINE_VERSION = "2.0"


def resolve_upload_path(image_url: Optional[str]) -> Optional[str]:
    """Maps a stored '/uploads/<file>' URL to a file inside UPLOAD_DIR (never outside it)."""
    if not image_url:
        return None
    filename = os.path.basename(image_url.strip())
    if not filename or filename in (".", ".."):
        return None
    candidate = os.path.join(settings.UPLOAD_DIR, filename)
    return candidate if os.path.isfile(candidate) else None


def _sha256(path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


class VerificationEngine:
    WEIGHT_NDVI = 0.40
    WEIGHT_CV = 0.35
    WEIGHT_SOC = 0.25

    THRESHOLD_APPROVED = 75.0
    THRESHOLD_REVIEW = 55.0

    # ------------------------------------------------------------------
    # Evidence completeness (cheap; no network or model calls)
    # ------------------------------------------------------------------
    @classmethod
    def check_evidence_completeness(cls, plantation: Plantation) -> Dict[str, Any]:
        has_boundary = (
            plantation.latitude is not None
            and plantation.longitude is not None
            and plantation.area_hectares is not None
            and plantation.area_hectares > 0
        )

        image_path = resolve_upload_path(plantation.image_url)
        image_ok, image_reason, _ = validate_image_file(image_path)
        if plantation.image_url and not image_path:
            image_reason = "Ground photograph URL does not point to an uploaded file."

        has_soil = plantation.soil_soc_pct is not None and 0 < plantation.soil_soc_pct <= 10
        has_reported_ndvi = (
            plantation.ndvi_reported_value is not None
            and bool(plantation.ndvi_reported_source)
            and bool(plantation.ndvi_reported_date)
        )

        missing: List[str] = []
        if not has_boundary:
            missing.append("Plantation boundary")
        if not image_ok:
            missing.append("Ground imagery")
        if not has_soil:
            missing.append("Soil carbon data")

        return {
            "is_complete": not missing,
            "has_boundary": has_boundary,
            "has_ground_image": image_ok,
            "ground_image_issue": None if image_ok else image_reason,
            "has_soil": has_soil,
            "has_reported_ndvi": has_reported_ndvi,
            "image_path": image_path if image_ok else None,
            "missing_modalities": missing,
            "evidence_status": {
                "boundary": "PROVIDED" if has_boundary else "NOT PROVIDED",
                "ground_imagery": "PROVIDED" if image_ok else ("INVALID" if plantation.image_url else "NOT PROVIDED"),
                "soil_carbon": "PROVIDED" if has_soil else "NOT PROVIDED",
                # NDVI is measured during a verification run; before that it is pending.
                "satellite_ndvi": "REPORTED" if has_reported_ndvi else "PENDING",
            },
        }

    # ------------------------------------------------------------------
    # Full verification run
    # ------------------------------------------------------------------
    @classmethod
    def _snapshot(cls, plantation: Plantation, image_path: Optional[str]) -> Dict[str, Any]:
        return {
            "engine_version": ENGINE_VERSION,
            "latitude": plantation.latitude,
            "longitude": plantation.longitude,
            "area_hectares": plantation.area_hectares,
            "tree_count": plantation.tree_count,
            "image_url": plantation.image_url,
            "image_sha256": _sha256(image_path),
            "soil_soc_pct": plantation.soil_soc_pct,
            "soil_depth_cm": plantation.soil_depth_cm,
            "soil_type": plantation.soil_type,
            "ndvi_reported_value": plantation.ndvi_reported_value,
            "ndvi_reported_source": plantation.ndvi_reported_source,
            "ndvi_reported_date": plantation.ndvi_reported_date,
            "weights": {"ndvi": cls.WEIGHT_NDVI, "cv": cls.WEIGHT_CV, "soc": cls.WEIGHT_SOC},
            "thresholds": {"approved": cls.THRESHOLD_APPROVED, "review": cls.THRESHOLD_REVIEW},
        }

    @classmethod
    def _base_result(cls, plantation: Plantation) -> Dict[str, Any]:
        return {
            "id": f"VER-{datetime.utcnow():%Y}-{uuid.uuid4().hex[:8].upper()}",
            "plantation_id": plantation.id,
            "ndvi_weight": cls.WEIGHT_NDVI,
            "cv_weight": cls.WEIGHT_CV,
            "soc_weight": cls.WEIGHT_SOC,
            "ndvi_value": None, "ndvi_score": None, "ndvi_status": "PENDING", "ndvi_historical_diff": None,
            "mean_ndvi": None, "min_ndvi": None, "max_ndvi": None, "vegetation_coverage_pct": None,
            "is_real_satellite": False, "satellite_source": None, "acquisition_date": None, "ndvi_provenance": None,
            "image_quality_score": None, "vegetation_detection_score": None, "cv_score": None,
            "cv_detection_status": "NOT PROVIDED",
            "ai_model_name": None, "ai_model_version": None, "ai_predicted_class": None,
            "ai_confidence_pct": None, "prediction_label": None, "image_phash": None,
            "soc_pct": None, "soc_score": None, "soc_status": "NOT PROVIDED",
            "ndvi_contribution": None, "cv_contribution": None, "soc_contribution": None,
            "overall_score": None,
            "risk_score": None, "risk_level": None, "risk_factors": [], "risk_explanation": None,
            "decided_by": ENGINE_NAME,
            "verified_at": datetime.utcnow(),
        }

    @classmethod
    def run_verification(
        cls,
        plantation: Plantation,
        db: Optional[Session] = None,
        **_ignored: Any,
    ) -> Dict[str, Any]:
        result = cls._base_result(plantation)
        audit = cls.check_evidence_completeness(plantation)
        result["evidence_status"] = dict(audit["evidence_status"])
        result["evidence_snapshot"] = cls._snapshot(plantation, audit["image_path"])
        reasons: List[str] = []

        # ---- Rule 1: required submitted evidence --------------------------------
        if not audit["is_complete"]:
            for item in audit["missing_modalities"]:
                reasons.append(f"Missing required evidence: {item}.")
            if audit["ground_image_issue"] and plantation.image_url:
                reasons.append(f"Ground photograph rejected: {audit['ground_image_issue']}")
            reasons.append("Decision PENDING: no score is computed until all required evidence is submitted.")
            # Show the SOC value the farmer did submit, if any (it is real input, not a score).
            if audit["has_soil"]:
                result["soc_pct"] = round(plantation.soil_soc_pct, 2)
                result["soc_status"] = "PROVIDED (not scored until evidence is complete)"
            return cls._finish(result, VerificationDecision.PENDING.value, reasons, audit["missing_modalities"],
                               summary=f"Verification pending. Missing: {', '.join(audit['missing_modalities'])}.")

        # ---- Rule 2: measure each modality ---------------------------------------
        ndvi = NDVIService.analyze_ndvi(
            latitude=plantation.latitude,
            longitude=plantation.longitude,
            area_hectares=plantation.area_hectares,
            reported_value=plantation.ndvi_reported_value,
            reported_source=plantation.ndvi_reported_source,
            reported_date=plantation.ndvi_reported_date,
        )
        cv = CVService.analyze_image(audit["image_path"])
        soc = SOCService.evaluate_soc(plantation.soil_soc_pct, plantation.soil_depth_cm, plantation.soil_type)

        result.update({
            "ndvi_value": ndvi["ndvi_value"], "mean_ndvi": ndvi["mean_ndvi"],
            "min_ndvi": ndvi["min_ndvi"], "max_ndvi": ndvi["max_ndvi"],
            "vegetation_coverage_pct": ndvi["vegetation_coverage_pct"],
            "ndvi_score": ndvi["ndvi_score"], "ndvi_status": ndvi["vegetation_status"],
            "is_real_satellite": ndvi["is_real_satellite"], "satellite_source": ndvi["satellite_source"],
            "acquisition_date": ndvi["acquisition_date"], "ndvi_provenance": ndvi["provenance"],
            "image_quality_score": cv["image_quality_score"],
            "vegetation_detection_score": cv["vegetation_detection_score"],
            "cv_score": cv["cv_score"], "cv_detection_status": cv["cv_detection_status"],
            "ai_model_name": cv["model_name"], "ai_model_version": cv["model_version"],
            "ai_predicted_class": cv["predicted_class"], "ai_confidence_pct": cv["confidence_pct"],
            "prediction_label": cv["prediction_label"],
            "soc_pct": soc["soc_pct"], "soc_score": soc["soc_score"], "soc_status": soc["soil_status"],
        })
        result["evidence_status"]["satellite_ndvi"] = (
            "COMPUTED" if ndvi["provenance"] == "SENTINEL2_COMPUTED"
            else "REPORTED" if ndvi["provenance"] == PROVENANCE_REPORTED
            else "UNAVAILABLE"
        )
        result["evidence_snapshot"]["ndvi_measurement"] = {
            k: ndvi.get(k) for k in ("provenance", "satellite_source", "acquisition_date", "cloud_cover_pct", "valid_pixel_count")
        }
        result["evidence_snapshot"]["cv_measurement"] = {
            "model_name": cv["model_name"], "model_version": cv["model_version"],
            "class_probabilities": cv["class_probabilities"], "training_data": cv.get("training_data"),
        }

        unavailable: List[str] = []
        if not ndvi["available"]:
            unavailable.append("Satellite NDVI")
            reasons.append(
                f"Satellite NDVI unavailable: {ndvi.get('reason')} Provide a reported NDVI value with its "
                "source and acquisition date, or re-run when the satellite service is reachable."
            )
        if not cv["available"]:
            unavailable.append("Ground photo analysis")
            reasons.append(f"Ground photo could not be analysed: {cv.get('reason')}")
        if soc["soc_score"] is None:
            unavailable.append("Soil carbon score")
            reasons.append("Soil organic carbon value is missing or out of range (0-10%).")

        for label, value in (("NDVI", ndvi["ndvi_score"]), ("CV", cv["cv_score"]), ("SOC", soc["soc_score"])):
            if value is not None:
                reasons.append(f"{label} modality measured: score {value}/100.")

        if unavailable:
            reasons.append("Decision PENDING: an overall score requires all three modality scores.")
            return cls._finish(result, VerificationDecision.PENDING.value, reasons, unavailable,
                               summary=f"Verification pending. Unavailable: {', '.join(unavailable)}.")

        # ---- Rule 3: weighted score and thresholds --------------------------------
        ndvi_c = round(cls.WEIGHT_NDVI * ndvi["ndvi_score"], 2)
        cv_c = round(cls.WEIGHT_CV * cv["cv_score"], 2)
        soc_c = round(cls.WEIGHT_SOC * soc["soc_score"], 2)
        overall = round(ndvi_c + cv_c + soc_c, 1)
        result.update({"ndvi_contribution": ndvi_c, "cv_contribution": cv_c,
                       "soc_contribution": soc_c, "overall_score": overall})

        reasons = [
            f"NDVI {ndvi['mean_ndvi']} ({'Sentinel-2 computed' if ndvi['provenance'] != PROVENANCE_REPORTED else 'reported: ' + str(plantation.ndvi_reported_source)}) "
            f"→ score {ndvi['ndvi_score']} × {cls.WEIGHT_NDVI} = {ndvi_c}.",
            f"Ground photo classified as '{cv['predicted_class']}' ({cv['confidence_pct']}% confidence) "
            f"→ score {cv['cv_score']} × {cls.WEIGHT_CV} = {cv_c}.",
            f"Soil organic carbon {soc['soc_pct']}% → score {soc['soc_score']} × {cls.WEIGHT_SOC} = {soc_c}.",
            f"Overall score {overall}/100.",
        ]
        if overall >= cls.THRESHOLD_APPROVED:
            decision = VerificationDecision.APPROVED.value
            reasons.append(f"Score ≥ {cls.THRESHOLD_APPROVED} approval threshold.")
        elif overall >= cls.THRESHOLD_REVIEW:
            decision = VerificationDecision.REVIEW.value
            reasons.append(f"Score between {cls.THRESHOLD_REVIEW} and {cls.THRESHOLD_APPROVED}: requires auditor review.")
        else:
            decision = VerificationDecision.REJECTED.value
            reasons.append(f"Score below {cls.THRESHOLD_REVIEW} rejection threshold.")

        # ---- Rule 4: fraud / risk ---------------------------------------------------
        risk = RiskEngine.evaluate_risk(
            plantation=plantation, ndvi_res=ndvi, cv_res=cv, soc_res=soc,
            image_path=audit["image_path"], db=db,
        )
        result.update({
            "risk_score": risk["risk_score"], "risk_level": risk["risk_level"],
            "risk_factors": risk["risk_factors"], "risk_explanation": risk["explanation"],
            "image_phash": risk.get("image_phash"),
        })
        for factor in risk["risk_factors"]:
            reasons.append(f"Risk factor: {factor}.")
        if risk["requires_auditor_review"] and decision == VerificationDecision.APPROVED.value:
            decision = VerificationDecision.REVIEW.value
            reasons.append(f"HIGH risk ({risk['risk_score']}/100): approval downgraded to auditor REVIEW.")

        # ---- Rule 5: reported NDVI needs human confirmation ----------------------
        if ndvi["provenance"] == PROVENANCE_REPORTED and decision == VerificationDecision.APPROVED.value:
            decision = VerificationDecision.REVIEW.value
            reasons.append("NDVI was reported, not computed by the backend: approval requires auditor confirmation.")

        summary = (
            f"Overall score {overall}/100 → {decision}. NDVI {ndvi['mean_ndvi']} ({ndvi['provenance']}), "
            f"photo '{cv['predicted_class']}' {cv['confidence_pct']}%, SOC {soc['soc_pct']}%, risk {risk['risk_level']}."
        )
        return cls._finish(result, decision, reasons, [], summary=summary)

    @staticmethod
    def _finish(result: Dict[str, Any], decision: str, reasons: List[str], missing: List[str], summary: str) -> Dict[str, Any]:
        result["decision"] = decision
        result["engine_decision"] = decision
        result["decision_reasons"] = reasons
        result["missing_evidence"] = missing
        result["evidence_summary"] = summary
        result["limitations_disclaimer"] = (
            "Prototype verification — not a certified carbon-registry methodology. The ground-photo "
            "classifier was trained only on synthetic images and has no real-world validation. "
            "Carbon quantities use a simple per-tree sequestration assumption."
        )
        return result
