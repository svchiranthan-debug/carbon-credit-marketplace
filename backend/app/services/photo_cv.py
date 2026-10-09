"""
Multi-photo ground-evidence assessment.

The existing classifier (MobileNetV3-Small, unchanged) is run on every valid photo. The
plantation-level CV result is then derived as follows:

1. Invalid or missing files are listed with their error and never scored.
2. Duplicates are removed: a photo whose SHA-256 matches, or whose perceptual hash is within
   PHOTO_NEAR_DUPLICATE_DISTANCE of, an earlier photo of the same plot counts once.
3. The CV score is the LOWER MEDIAN of the per-photo CV scores of the remaining unique photos
   (each per-photo score is the classifier's existing class+confidence → 0-100 mapping). The
   median is robust: one good photo cannot lift several poor or unrelated ones, and a single
   outlier cannot dominate. The lower median is always an actual photo's score, so the result
   stays within the existing 0-100 range. Scores are never summed.
4. Flags that cap an otherwise APPROVED decision at REVIEW (an auditor must look):
     LOW_CONFIDENCE  the median photo, or more than half of the unique photos, are below
                     CV_LOW_CONFIDENCE_PCT confidence
     CONFLICTING     at least one photo is classified 'plantation' and at least one other is
                     confidently classified 'non_plantation'
5. If no photo could be scored, the CV modality is unavailable and verification stays PENDING
   (existing rule). More photos never fill in missing NDVI or SOC.
"""
from datetime import datetime
from statistics import median_low
from typing import Any, Dict, List

from ..config import settings
from ..models.plantation_photo import PlantationPhoto
from .ai.ai_vision_service import validate_image_file
from .ai.cv_service import CVService
from .photo_store import phash_distance, upload_path

AGGREGATION_METHOD = "lower median of unique valid photos"


def assess_photos(photos: List[PlantationPhoto]) -> Dict[str, Any]:
    per_photo: List[Dict[str, Any]] = []
    unique: List[PlantationPhoto] = []
    results: Dict[int, Dict[str, Any]] = {}

    for photo in photos:
        path = upload_path(photo.filename)
        ok, reason, _ = validate_image_file(path) if path else (False, "File not found on server.", {})
        photo.validation_status = "VALID" if ok else ("FILE_MISSING" if not path else "INVALID")
        photo.validation_error = None if ok else reason
        entry: Dict[str, Any] = {
            "photo_id": photo.id, "filename": photo.filename,
            "uploaded_at": photo.uploaded_at.isoformat() if photo.uploaded_at else None,
            "sha256": photo.sha256, "phash": photo.phash,
            "valid": ok, "error": None if ok else reason,
            "duplicate_of": None, "used_in_score": False,
            "predicted_class": None, "confidence_pct": None, "cv_score": None,
        }
        per_photo.append(entry)
        if not ok:
            continue

        # Deduplicate against earlier unique photos of this plot
        dup_of = None
        for kept in unique:
            same = photo.sha256 and kept.sha256 == photo.sha256
            dist = phash_distance(photo.phash, kept.phash)
            if same or (dist is not None and dist <= settings.PHOTO_NEAR_DUPLICATE_DISTANCE):
                dup_of = kept.id
                break
        photo.duplicate_of_id = dup_of
        entry["duplicate_of"] = dup_of

        cv = CVService.analyze_image(path)
        results[photo.id] = cv
        photo.classified_at = datetime.utcnow()
        photo.model_version = cv.get("model_version")
        if cv["available"]:
            photo.predicted_class, photo.confidence_pct = cv["predicted_class"], cv["confidence_pct"]
            photo.cv_score, photo.class_probabilities = cv["cv_score"], cv["class_probabilities"]
            photo.classification_error = None
        else:
            photo.predicted_class = photo.confidence_pct = photo.cv_score = None
            photo.class_probabilities = None
            photo.classification_error = cv.get("reason")
        entry.update(predicted_class=photo.predicted_class, confidence_pct=photo.confidence_pct,
                     cv_score=photo.cv_score, error=photo.classification_error)
        if dup_of is None:
            unique.append(photo)

    usable = [p for p in unique if results.get(p.id, {}).get("available")]
    summary = {
        "method": AGGREGATION_METHOD,
        "photos_submitted": len(photos),
        "photos_valid": sum(1 for e in per_photo if e["valid"]),
        "photos_unique": len(unique),
        "photos_scored": len(usable),
        "duplicates": sum(1 for e in per_photo if e["duplicate_of"] is not None),
        "low_confidence_threshold_pct": settings.CV_LOW_CONFIDENCE_PCT,
        "flags": [],
        "representative_photo_id": None,
    }

    if not usable:
        if not unique:
            reason = "No valid ground photograph."
        else:
            first = results.get(unique[0].id, {})
            reason = first.get("reason") or "The classifier could not score any photo."
        return {
            "available": False, "reason": reason,
            "predicted_class": None, "prediction_label": None, "confidence_pct": None, "class_probabilities": {},
            "model_name": None, "model_version": None, "training_data": None,
            "image_quality_score": None, "vegetation_detection_score": None, "cv_score": None,
            "cv_detection_status": "NOT AVAILABLE" if unique else "NOT PROVIDED",
            "aggregation": summary, "photos": per_photo, "flags": [], "representative_path": None,
            "unique_paths": [upload_path(p.filename) for p in unique],
        }

    for p in usable:
        next(e for e in per_photo if e["photo_id"] == p.id)["used_in_score"] = True

    score = median_low([p.cv_score for p in usable])
    rep = next(p for p in usable if p.cv_score == score)
    rep_cv = results[rep.id]
    low = settings.CV_LOW_CONFIDENCE_PCT

    flags: List[str] = []
    n_low = sum(1 for p in usable if (p.confidence_pct or 0) < low)
    if (rep.confidence_pct or 0) < low or n_low * 2 > len(usable):
        flags.append("LOW_CONFIDENCE")
    classes = [p.predicted_class for p in usable]
    if "plantation" in classes and any(p.predicted_class == "non_plantation" and (p.confidence_pct or 0) >= low
                                       for p in usable):
        flags.append("CONFLICTING")
    summary.update(flags=flags, representative_photo_id=rep.id,
                   class_counts={c: classes.count(c) for c in sorted(set(classes))},
                   per_photo_scores=[p.cv_score for p in usable])

    n = len(usable)
    status = rep_cv["cv_detection_status"]
    if n > 1:
        status = f"{status} — median of {n} unique photos"
    return {
        **rep_cv,
        "cv_score": score,
        "cv_detection_status": status,
        "aggregation": summary,
        "photos": per_photo,
        "flags": flags,
        "representative_path": upload_path(rep.filename),
        "unique_paths": [upload_path(p.filename) for p in unique],
    }
