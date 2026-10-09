"""
Ground-photo storage, validation, signed access links and per-plantation photo bookkeeping.

* Files live in settings.UPLOAD_DIR under server-generated names; the client's filename is
  never used as a path.
* A file is accepted only if it decodes as an allowed image format (the extension and the
  browser's MIME type are not trusted on their own). The stored extension comes from the
  decoded format.
* Photos are not publicly served. API responses contain short-lived signed links
  (/uploads/<file>?exp=..&sig=..) that are only handed to users allowed to see the plantation.
"""
import hashlib
import hmac
import logging
import os
import re
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, UploadFile, status
from PIL import ExifTags, Image
from sqlalchemy.orm import Session

from ..config import settings
from ..models.plantation import Plantation
from ..models.plantation_photo import PhotoStatus, PlantationPhoto
from .ai.ai_vision_service import validate_image_file

logger = logging.getLogger(__name__)

SAFE_FILENAME_RE = re.compile(r"^[A-Za-z0-9_\-]+\.(jpg|jpeg|png|webp|tif|tiff)$")
FORMAT_EXTENSION = {"JPEG": ".jpg", "MPO": ".jpg", "PNG": ".png", "WEBP": ".webp", "TIFF": ".tif"}
ACCEPTED_MIME_PREFIXES = ("image/",)
ACCEPTED_GENERIC_MIME = {"", "application/octet-stream"}  # some mobile clients send these for photos


# ---------------------------------------------------------------- signed links

def _signature(filename: str, exp: int) -> str:
    msg = f"{filename}|{exp}".encode()
    return hmac.new(settings.SECRET_KEY.encode(), msg, hashlib.sha256).hexdigest()[:32]


def sign_upload_url(image_url: Optional[str]) -> Optional[str]:
    """'/uploads/<file>' → '/uploads/<file>?exp=..&sig=..'. Expiry is rounded to the hour so
    the same link is reused (and cached by the browser) for a while."""
    if not image_url:
        return image_url
    filename = os.path.basename(image_url.split("?", 1)[0].strip())
    if not SAFE_FILENAME_RE.match(filename):
        return None
    ttl = max(60, int(settings.PHOTO_URL_TTL_S))
    exp = (int(time.time()) // ttl + 2) * ttl     # valid for between 1 and 2 TTLs
    return f"/uploads/{filename}?exp={exp}&sig={_signature(filename, exp)}"


def verify_upload_signature(filename: str, exp: Optional[str], sig: Optional[str]) -> bool:
    if not (filename and exp and sig) or not SAFE_FILENAME_RE.match(filename):
        return False
    try:
        exp_i = int(exp)
    except ValueError:
        return False
    if exp_i < time.time():
        return False
    return hmac.compare_digest(_signature(filename, exp_i), sig)


def strip_upload_url(image_url: Optional[str]) -> Optional[str]:
    """Signed or unsigned link → canonical '/uploads/<file>' (what is stored in the DB)."""
    if not image_url:
        return image_url
    return "/uploads/" + os.path.basename(image_url.split("?", 1)[0].strip())


def upload_path(filename: str) -> Optional[str]:
    """Path of a stored file inside UPLOAD_DIR, or None (never resolves outside it)."""
    filename = os.path.basename((filename or "").split("?", 1)[0])
    if not SAFE_FILENAME_RE.match(filename):
        return None
    path = os.path.join(settings.UPLOAD_DIR, filename)
    return path if os.path.isfile(path) else None


# ---------------------------------------------------------------- validation + storage

def sanitize_original_name(name: Optional[str]) -> Optional[str]:
    if not name:
        return None
    base = os.path.basename(name.replace("\\", "/"))
    base = re.sub(r"[^A-Za-z0-9 ._\-()]", "_", base).strip()
    return base[:120] or None


async def store_validated_image(file: UploadFile, prefix: str) -> Tuple[str, Dict[str, Any]]:
    """Stream an upload to disk with a size limit and keep it only if it decodes as an allowed image.

    Returns (stored filename, info). Raises HTTPException (400/413/415) and leaves no file behind
    on any failure.
    """
    content_type = (file.content_type or "").lower()
    if not content_type.startswith(ACCEPTED_MIME_PREFIXES) and content_type not in ACCEPTED_GENERIC_MIME:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                            detail=f"Unsupported file type '{content_type}'. Upload a JPEG, PNG, WEBP or TIFF photo.")
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    tmp_name = f"{prefix}_{uuid.uuid4().hex[:12]}.part"
    tmp_path = os.path.join(settings.UPLOAD_DIR, tmp_name)
    written = 0
    try:
        with open(tmp_path, "wb") as out:
            while chunk := await file.read(1024 * 1024):
                written += len(chunk)
                if written > settings.MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=413,
                                        detail=f"Photo exceeds the {settings.MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit.")
                out.write(chunk)
        ok, reason, info = validate_image_file(tmp_path)
        if not ok:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=reason)
        ext = FORMAT_EXTENSION.get(info["format"])
        if not ext:
            raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                                detail=f"Unsupported image format '{info['format']}'.")
        filename = tmp_name[: -len(".part")] + ext
        os.replace(tmp_path, os.path.join(settings.UPLOAD_DIR, filename))
        return filename, info
    except BaseException:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def remove_stored_file(filename: str) -> None:
    path = upload_path(filename)
    if path:
        try:
            os.remove(path)
        except OSError:
            logger.warning("Could not remove %s", filename)


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def read_exif(path: str) -> Dict[str, Any]:
    """Capture time, GPS and camera from EXIF, if the file has them. Reported, not verified."""
    out: Dict[str, Any] = {"exif_capture_time": None, "exif_gps": None, "exif_camera": None}
    try:
        with Image.open(path) as img:
            exif = img.getexif()
            if not exif:
                return out
            tags = {ExifTags.TAGS.get(k, k): v for k, v in exif.items()}
            sub = exif.get_ifd(0x8769) or {}
            sub_tags = {ExifTags.TAGS.get(k, k): v for k, v in sub.items()}
            captured = sub_tags.get("DateTimeOriginal") or tags.get("DateTime")
            out["exif_capture_time"] = str(captured)[:32] if captured else None
            camera = " ".join(str(tags.get(k, "")).strip() for k in ("Make", "Model")).strip()
            out["exif_camera"] = camera[:80] or None
            gps = exif.get_ifd(0x8825) or {}
            if gps.get(2) and gps.get(4):
                def deg(v):
                    d, m, s = (float(x) for x in v)
                    return d + m / 60.0 + s / 3600.0
                lat, lon = deg(gps[2]), deg(gps[4])
                if gps.get(1) == "S":
                    lat = -lat
                if gps.get(3) == "W":
                    lon = -lon
                out["exif_gps"] = {"lat": round(lat, 6), "lon": round(lon, 6)}
    except Exception as exc:  # malformed EXIF must never block an upload
        logger.debug("EXIF read failed for %s: %s", path, exc)
    return out


def phash_distance(a: Optional[str], b: Optional[str]) -> Optional[int]:
    if not a or not b:
        return None
    try:
        import imagehash
        return int(imagehash.hex_to_hash(a) - imagehash.hex_to_hash(b))
    except Exception:
        return None


def compute_phash(path: str) -> Optional[str]:
    from .risk_engine import RiskEngine
    return RiskEngine.compute_image_hash(path)


def build_photo_record(plantation_id: int, filename: str, user_id: Optional[int],
                       original_name: Optional[str] = None) -> PlantationPhoto:
    path = upload_path(filename)
    photo = PlantationPhoto(plantation_id=plantation_id, filename=filename, uploaded_by=user_id,
                            original_name=sanitize_original_name(original_name),
                            uploaded_at=datetime.utcnow(), status=PhotoStatus.ACTIVE,
                            validation_status="VALID")
    if not path:
        photo.validation_status, photo.validation_error = "FILE_MISSING", "File not found on server."
        return photo
    ok, reason, info = validate_image_file(path)
    if not ok:
        photo.validation_status, photo.validation_error = "INVALID", reason
    else:
        photo.image_format, photo.width, photo.height = info["format"], info["width"], info["height"]
    photo.size_bytes = os.path.getsize(path)
    photo.sha256 = sha256_file(path)
    photo.phash = compute_phash(path) if ok else None
    for k, v in read_exif(path).items():
        setattr(photo, k, v)
    return photo


# ---------------------------------------------------------------- plantation bookkeeping

def active_photos(db: Session, plantation_id: int) -> List[PlantationPhoto]:
    return (db.query(PlantationPhoto)
            .filter(PlantationPhoto.plantation_id == plantation_id, PlantationPhoto.status == PhotoStatus.ACTIVE)
            .order_by(PlantationPhoto.id).all())


def refresh_cover(db: Session, plantation: Plantation) -> None:
    """plantation.image_url mirrors the first valid active photo (for single-photo clients)."""
    photos = [p for p in active_photos(db, plantation.id) if p.validation_status == "VALID"]
    plantation.image_url = f"/uploads/{photos[0].filename}" if photos else None


def mark_near_duplicate(db: Session, photo: PlantationPhoto) -> None:
    """Flag a photo that is a near-copy (pHash) of an earlier active photo of the same plot."""
    if not photo.phash:
        return
    for other in active_photos(db, photo.plantation_id):
        if other.id == photo.id or (photo.id is not None and other.id > photo.id):
            continue
        dist = phash_distance(photo.phash, other.phash)
        if dist is not None and dist <= settings.PHOTO_NEAR_DUPLICATE_DISTANCE:
            photo.duplicate_of_id = other.id
            return


def backfill_legacy_photos(db: Session) -> int:
    """Create a photo row for every plantation that has image_url but no photo rows yet."""
    created = 0
    with_rows = {pid for (pid,) in db.query(PlantationPhoto.plantation_id).distinct()}
    for plantation in db.query(Plantation).filter(Plantation.image_url.isnot(None)).all():
        if plantation.id in with_rows:
            continue
        filename = os.path.basename(plantation.image_url.split("?", 1)[0])
        if not filename:
            continue
        photo = build_photo_record(plantation.id, filename, plantation.farmer_id)
        photo.uploaded_at = plantation.updated_at or plantation.created_at or datetime.utcnow()
        db.add(photo)
        created += 1
    if created:
        db.commit()
    return created


def ensure_photo_rows(db: Session, plantation: Plantation) -> List[PlantationPhoto]:
    """Active photos; a plantation still holding only a legacy image_url gets its row first."""
    photos = active_photos(db, plantation.id)
    if photos or not plantation.image_url:
        return photos
    if not db.query(PlantationPhoto).filter(PlantationPhoto.plantation_id == plantation.id).first():
        filename = os.path.basename(plantation.image_url.split("?", 1)[0])
        if filename:
            db.add(build_photo_record(plantation.id, filename, plantation.farmer_id))
            db.flush()
    return active_photos(db, plantation.id)
