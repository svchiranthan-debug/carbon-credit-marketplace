import os
import logging
from typing import Dict, Any, Optional, List, Tuple
from PIL import Image
import imagehash
from sqlalchemy.orm import Session

from ..config import settings
from ..models.plantation import Plantation

logger = logging.getLogger(__name__)

class RiskEngine:
    """
    Transparent Risk & Fraud Detection Engine.
    
    Evaluates multi-modal evidence across 6 explainable security dimensions:
    1. Perceptual Image Hashing (Duplicate ground evidence across plantations)
    2. Deep Learning AI Vision Classification & Confidence
    3. Satellite NDVI vs Ground Evidence Consistency
    4. Agronomic Biomass & Tree Density Feasibility
    5. Soil Organic Carbon (SOC) Regional Baseline Plausibility
    6. Geospatial Boundary / Centroid Overlap
    
    Scores are strictly explainable (0–100) with detailed risk factors.
    High-risk cases (score >= 61) are automatically escalated to Auditor Review.
    """
    
    RISK_THRESHOLD_HIGH = 61.0
    RISK_THRESHOLD_MEDIUM = 31.0

    @classmethod
    def compute_image_hash(cls, image_path: Optional[str]) -> Optional[str]:
        """Computes a 64-bit perceptual hash (pHash) for image deduplication."""
        if not image_path or not os.path.exists(image_path):
            return None
        try:
            with Image.open(image_path) as img:
                return str(imagehash.phash(img))
        except Exception as e:
            logger.warning(f"Could not compute image hash: {e}")
            return None

    @classmethod
    def check_duplicate_image(
        cls,
        image_path: Optional[str],
        current_plantation_id: Optional[int] = None,
        db: Optional[Session] = None,
        image_paths: Optional[List[str]] = None,
    ) -> Tuple[bool, int, str]:
        """
        Detects ground photos reused from ANOTHER plantation (any of its active photos, or its
        legacy single image). Checks every photo in ``image_paths`` (or just ``image_path``).
        """
        paths = [p for p in (image_paths or [image_path]) if p and os.path.exists(p)]
        if not paths or db is None:
            return False, 0, ""

        try:
            from ..models.plantation_photo import PhotoStatus, PlantationPhoto

            candidates: List[Tuple[Plantation, str]] = []  # (other plantation, phash hex)
            rows = (db.query(PlantationPhoto, Plantation)
                    .join(Plantation, Plantation.id == PlantationPhoto.plantation_id)
                    .filter(PlantationPhoto.status == PhotoStatus.ACTIVE).all())
            covered = set()
            for photo, other in rows:
                if current_plantation_id and other.id == current_plantation_id:
                    continue
                covered.add(other.id)
                h = photo.phash or cls.compute_image_hash(os.path.join(settings.UPLOAD_DIR, photo.filename))
                if h:
                    candidates.append((other, h))
            for other in db.query(Plantation).filter(Plantation.image_url.isnot(None)).all():
                if other.id in covered or (current_plantation_id and other.id == current_plantation_id):
                    continue
                candidate_path = os.path.join(settings.UPLOAD_DIR, os.path.basename(other.image_url.split("?")[0]))
                if os.path.exists(candidate_path):
                    h = cls.compute_image_hash(candidate_path)
                    if h:
                        candidates.append((other, h))

            for path in paths:
                current_hash_str = cls.compute_image_hash(path)
                if not current_hash_str:
                    continue
                current_hash = imagehash.hex_to_hash(current_hash_str)
                for other, other_hash_str in candidates:
                    hamming_distance = current_hash - imagehash.hex_to_hash(other_hash_str)
                    # Hamming distance <= 4 indicates exact or near-identical image crop
                    if hamming_distance <= 4:
                        return True, 35, f"Duplicate ground image matches plantation #{other.id} ('{other.name}') (pHash distance: {hamming_distance})"
        except Exception as e:
            logger.warning(f"Duplicate scan error: {e}")

        return False, 0, ""

    @classmethod
    def evaluate_risk(
        cls,
        plantation: Plantation,
        ndvi_res: Dict[str, Any],
        cv_res: Dict[str, Any],
        soc_res: Dict[str, Any],
        image_path: Optional[str] = None,
        db: Optional[Session] = None,
        image_paths: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Evaluates transparent composite risk score and outputs list of explainable risk factors.
        """
        risk_score = 0
        risk_factors: List[str] = []
        factor_breakdown: List[Dict[str, Any]] = []

        # -------------------------------------------------------------
        # 1. PERCEPTUAL DUPLICATE IMAGE CHECK (+35 Risk)
        # -------------------------------------------------------------
        is_dup, dup_pts, dup_msg = cls.check_duplicate_image(
            image_path=image_path,
            current_plantation_id=plantation.id,
            db=db,
            image_paths=image_paths,
        )
        if is_dup:
            risk_score += dup_pts
            risk_factors.append(dup_msg)
            factor_breakdown.append({"category": "Evidence Integrity", "penalty": dup_pts, "detail": dup_msg})

        # -------------------------------------------------------------
        # 2. AI VISION CLASSIFICATION & CONFIDENCE (+20 to +40 Risk)
        # -------------------------------------------------------------
        pred_class = (cv_res.get("predicted_class") or "").lower()
        ai_conf = cv_res.get("confidence_pct", 0.0) or 0.0

        if pred_class == "non_plantation":
            penalty = 40
            msg = f"AI Vision classified ground evidence as Non-Plantation/Urban ({ai_conf}% confidence)"
            risk_score += penalty
            risk_factors.append(msg)
            factor_breakdown.append({"category": "AI Vision", "penalty": penalty, "detail": msg})
        elif pred_class == "unclear_evidence":
            penalty = 25
            msg = f"AI Vision detected unclear/obstructed evidence ({ai_conf}% confidence)"
            risk_score += penalty
            risk_factors.append(msg)
            factor_breakdown.append({"category": "AI Vision", "penalty": penalty, "detail": msg})
        elif ai_conf < 60.0 and pred_class == "plantation":
            penalty = 15
            msg = f"Marginal AI Vision confidence ({ai_conf}%) on canopy classification"
            risk_score += penalty
            risk_factors.append(msg)
            factor_breakdown.append({"category": "AI Vision", "penalty": penalty, "detail": msg})

        # -------------------------------------------------------------
        # 3. SATELLITE NDVI VS GROUND EVIDENCE CROSS-CHECK (+25 to +30 Risk)
        # -------------------------------------------------------------
        mean_ndvi = ndvi_res.get("mean_ndvi") or ndvi_res.get("ndvi_value") or 0.0
        cv_score = cv_res.get("cv_score") or 0.0

        if mean_ndvi >= 0.70 and cv_score < 40.0:
            penalty = 30
            msg = f"Satellite NDVI indicates dense canopy ({mean_ndvi:.2f}) but ground photo shows barren/non-vegetative ground (Score: {cv_score})"
            risk_score += penalty
            risk_factors.append(msg)
            factor_breakdown.append({"category": "Cross-Modality", "penalty": penalty, "detail": msg})
        elif mean_ndvi < 0.35 and cv_score >= 80.0:
            penalty = 25
            msg = f"Ground photo reports high foliage (Score: {cv_score}) but Satellite NDVI indicates degraded/sparse cover ({mean_ndvi:.2f})"
            risk_score += penalty
            risk_factors.append(msg)
            factor_breakdown.append({"category": "Cross-Modality", "penalty": penalty, "detail": msg})

        # -------------------------------------------------------------
        # 4. AGRONOMIC TREE DENSITY & AREA ANOMALY (+15 to +25 Risk)
        # -------------------------------------------------------------
        area = plantation.area_hectares or 0.1
        tree_count = plantation.tree_count or 0
        density = tree_count / max(area, 0.05)

        if density > 2500.0:
            penalty = 25
            msg = f"Abnormally high tree density ({int(density)} trees/ha) exceeding biological limits"
            risk_score += penalty
            risk_factors.append(msg)
            factor_breakdown.append({"category": "Agronomic Feasibility", "penalty": penalty, "detail": msg})
        elif density < 20.0 and tree_count > 0:
            penalty = 15
            msg = f"Very low tree density ({int(density)} trees/ha) for carbon credit project"
            risk_score += penalty
            risk_factors.append(msg)
            factor_breakdown.append({"category": "Agronomic Feasibility", "penalty": penalty, "detail": msg})

        # -------------------------------------------------------------
        # 5. SOIL ORGANIC CARBON (SOC) PLAUSIBILITY (+20 Risk)
        # -------------------------------------------------------------
        soc_pct = plantation.soil_soc_pct or 0.0
        soil_type = (plantation.soil_type or "").lower()
        if "sandy" in soil_type and soc_pct > 3.5:
            penalty = 20
            msg = f"Claimed SOC of {soc_pct}% is unusually elevated for Sandy soil baseline"
            risk_score += penalty
            risk_factors.append(msg)
            factor_breakdown.append({"category": "Soil Plausibility", "penalty": penalty, "detail": msg})
        elif soc_pct > 5.5:
            penalty = 20
            msg = f"Claimed SOC of {soc_pct}% exceeds regional non-wetland ceiling"
            risk_score += penalty
            risk_factors.append(msg)
            factor_breakdown.append({"category": "Soil Plausibility", "penalty": penalty, "detail": msg})

        # -------------------------------------------------------------
        # 6. CENTROID COORDINATE OVERLAP (+30 Risk)
        # -------------------------------------------------------------
        if db is not None and plantation.latitude and plantation.longitude:
            overlap = db.query(Plantation).filter(
                Plantation.id != plantation.id,
                Plantation.latitude.between(plantation.latitude - 0.0001, plantation.latitude + 0.0001),
                Plantation.longitude.between(plantation.longitude - 0.0001, plantation.longitude + 0.0001)
            ).first()
            if overlap:
                penalty = 30
                msg = f"Geographic coordinates overlap with previously registered plantation #{overlap.id} ('{overlap.name}')"
                risk_score += penalty
                risk_factors.append(msg)
                factor_breakdown.append({"category": "Geospatial Integrity", "penalty": penalty, "detail": msg})

        # Normalization and Risk Level determination
        final_risk_score = min(100, max(0, risk_score))
        
        if final_risk_score >= cls.RISK_THRESHOLD_HIGH:
            risk_level = "HIGH"
            explanation = "High risk detected. Requires mandatory auditor review due to critical fraud/integrity indicators."
        elif final_risk_score >= cls.RISK_THRESHOLD_MEDIUM:
            risk_level = "MEDIUM"
            explanation = "Moderate risk factors detected. Cross-modality discrepancies or marginal confidence present."
        else:
            risk_level = "LOW"
            explanation = "Low risk profile. Evidence signals are mutually consistent with expected agronomic baselines."

        return {
            "risk_score": final_risk_score,
            "risk_level": risk_level,
            "risk_factors": risk_factors,
            "factor_breakdown": factor_breakdown,
            "explanation": explanation,
            "requires_auditor_review": risk_level == "HIGH",
            "image_phash": cls.compute_image_hash(image_path)
        }
