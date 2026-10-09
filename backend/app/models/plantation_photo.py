"""Ground photographs submitted as evidence for a plantation (one row per photo)."""
from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint

from ..database import Base


class PhotoStatus:
    ACTIVE = "ACTIVE"      # part of the evidence used for verification
    REMOVED = "REMOVED"    # withdrawn by the farmer before verification; file is kept for audit


class PlantationPhoto(Base):
    __tablename__ = "plantation_photos"
    # Older databases can have one file shared by several plantations, so filenames are
    # unique per plantation rather than globally.
    __table_args__ = (UniqueConstraint("plantation_id", "filename", name="uq_photo_plantation_filename"),)

    id = Column(Integer, primary_key=True, index=True)
    plantation_id = Column(Integer, ForeignKey("plantations.id"), nullable=False, index=True)
    filename = Column(String, nullable=False)                # stored name inside UPLOAD_DIR (server-generated)
    original_name = Column(String, nullable=True)            # sanitised client filename, display only
    image_format = Column(String, nullable=True)             # format detected by decoding (JPEG/PNG/WEBP/TIFF)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    size_bytes = Column(Integer, nullable=True)
    sha256 = Column(String, nullable=True, index=True)
    phash = Column(String, nullable=True)
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    status = Column(String, nullable=False, default=PhotoStatus.ACTIVE)
    validation_status = Column(String, nullable=False, default="VALID")  # VALID | FILE_MISSING | INVALID
    validation_error = Column(String, nullable=True)
    duplicate_of_id = Column(Integer, nullable=True)         # near-duplicate of an earlier photo of this plot
    # Provenance read from the file's EXIF data, if present (not verified by the server)
    exif_capture_time = Column(String, nullable=True)
    exif_gps = Column(JSON, nullable=True)                   # {"lat": .., "lon": ..}
    exif_camera = Column(String, nullable=True)
    # Latest classifier result (also copied into each verification's evidence snapshot)
    predicted_class = Column(String, nullable=True)
    confidence_pct = Column(Float, nullable=True)
    cv_score = Column(Float, nullable=True)
    class_probabilities = Column(JSON, nullable=True)
    model_version = Column(String, nullable=True)
    classified_at = Column(DateTime, nullable=True)
    classification_error = Column(String, nullable=True)
