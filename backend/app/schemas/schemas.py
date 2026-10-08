import re
from datetime import date, datetime
from typing import Any, Optional, List, Dict
from pydantic import BaseModel, Field, field_validator, model_validator

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# Public sign-up. AUDITOR accounts can approve plantations, so only an ADMIN may create them
# (POST /api/users); ADMIN accounts are created with seed_data.py or directly in the database.
SELF_REGISTER_ROLES = {"FARMER", "BUYER"}
ADMIN_CREATABLE_ROLES = {"FARMER", "BUYER", "AUDITOR"}


def _clean(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = value.strip()
    return value or None

# --- AUTH SCHEMAS ---
class UserBase(BaseModel):
    email: str
    full_name: str
    role: str = "FARMER"
    phone: Optional[str] = None
    organization: Optional[str] = None

class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        v = v.strip().lower()
        if not EMAIL_RE.match(v):
            raise ValueError("Enter a valid email address.")
        return v

    @field_validator("full_name")
    @classmethod
    def _name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Full name is required.")
        return v

    @field_validator("role")
    @classmethod
    def _role(cls, v: str) -> str:
        v = (v or "").strip().upper()
        if v not in SELF_REGISTER_ROLES:
            if v == "AUDITOR":
                raise ValueError("Auditor accounts are created by a platform administrator.")
            raise ValueError("Role must be FARMER or BUYER.")
        return v


class AdminUserCreate(UserCreate):
    """Used by an ADMIN to create accounts, including AUDITOR."""

    @field_validator("role")
    @classmethod
    def _role(cls, v: str) -> str:
        v = (v or "").strip().upper()
        if v not in ADMIN_CREATABLE_ROLES:
            raise ValueError("Role must be one of FARMER, BUYER, AUDITOR.")
        return v

class UserLogin(BaseModel):
    email: str
    password: str
    role: Optional[str] = None


class UserResponse(UserBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

class TokenData(BaseModel):
    email: Optional[str] = None
    role: Optional[str] = None

# --- PLANTATION SCHEMAS ---
class ReportedNDVIMixin(BaseModel):
    """NDVI measured outside this backend (e.g. Copernicus Browser). All three fields go together."""
    ndvi_reported_value: Optional[float] = Field(None, ge=-1, le=1, examples=[0.68])
    ndvi_reported_source: Optional[str] = Field(None, max_length=200, examples=["Copernicus Browser, Sentinel-2 L2A NDVI"])
    ndvi_reported_date: Optional[str] = Field(None, examples=["2026-09-20"], description="Acquisition date, YYYY-MM-DD")

    @field_validator("ndvi_reported_source")
    @classmethod
    def _src(cls, v):
        return _clean(v)

    @field_validator("ndvi_reported_date")
    @classmethod
    def _date(cls, v):
        v = _clean(v)
        if v is None:
            return None
        try:
            d = date.fromisoformat(v)
        except ValueError:
            raise ValueError("ndvi_reported_date must be YYYY-MM-DD.")
        if d > date.today():
            raise ValueError("ndvi_reported_date cannot be in the future.")
        return d.isoformat()

    @model_validator(mode="after")
    def _ndvi_complete(self):
        fields = (self.ndvi_reported_value, self.ndvi_reported_source, self.ndvi_reported_date)
        if any(f is not None for f in fields) and not all(f is not None for f in fields):
            raise ValueError("Reported NDVI needs ndvi_reported_value, ndvi_reported_source and ndvi_reported_date together.")
        return self


BOUNDARY_AREA_TOLERANCE = 0.15  # declared area must be within 15% of the drawn polygon's area


class PlantationCreate(ReportedNDVIMixin):
    name: str = Field(..., min_length=1, max_length=200, examples=["Kaveri River Agroforestry Plot"])
    farmer_name: Optional[str] = Field(None, max_length=200, examples=["Ramesh Kumar"])
    location: str = Field(..., min_length=1, max_length=300, examples=["Mandya, Karnataka, India"])
    latitude: float = Field(..., ge=-90, le=90, examples=[12.5218])
    longitude: float = Field(..., ge=-180, le=180, examples=[76.8951])
    area_hectares: float = Field(..., gt=0, le=10000, examples=[0.4047])
    plantation_age_years: float = Field(..., ge=0, le=200, examples=[4.0])
    tree_count: int = Field(..., gt=0, le=10_000_000, examples=[500])
    tree_species: str = Field(..., min_length=1, max_length=300, examples=["Areca"])
    plantation_type: str = Field(..., min_length=1, max_length=100, examples=["Agroforestry"])
    sustainable_practice: Optional[str] = Field(None, max_length=200)
    image_url: Optional[str] = Field(None, max_length=500)
    # Drawn boundary as [[lat, lng], ...] (3-500 vertices). Optional: plots registered from the
    # mobile app may only have a centre point and area.
    boundary: Optional[List[List[float]]] = Field(None, examples=[[[12.7591, 75.2008], [12.7591, 75.2014], [12.7585, 75.2014], [12.7585, 75.2008]]])

    # Soil inputs (optional at registration; verification stays PENDING without them)
    soil_soc_pct: Optional[float] = Field(None, gt=0, le=10, examples=[1.85])
    soil_depth_cm: Optional[float] = Field(None, gt=0, le=300, examples=[30.0])
    soil_type: Optional[str] = Field(None, max_length=100, examples=["Red Sandy Loam"])

    @field_validator("name", "location", "tree_species", "plantation_type")
    @classmethod
    def _required_text(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("This field cannot be blank.")
        return v

    @field_validator("farmer_name", "sustainable_practice", "image_url", "soil_type")
    @classmethod
    def _optional_text(cls, v):
        return _clean(v)

    @field_validator("boundary")
    @classmethod
    def _boundary_points(cls, v):
        if v is None:
            return None
        if not 3 <= len(v) <= 500:
            raise ValueError("boundary needs between 3 and 500 [lat, lng] points.")
        cleaned = []
        for pt in v:
            if len(pt) != 2:
                raise ValueError("Each boundary point must be [lat, lng].")
            lat, lng = float(pt[0]), float(pt[1])
            if not (-90 <= lat <= 90 and -180 <= lng <= 180):
                raise ValueError("Boundary point out of range.")
            cleaned.append([lat, lng])
        if cleaned[0] == cleaned[-1]:
            cleaned = cleaned[:-1]
        if len({tuple(p) for p in cleaned}) < 3:
            raise ValueError("boundary needs at least 3 distinct points.")
        return cleaned

    @model_validator(mode="after")
    def _boundary_consistent(self):
        if not self.boundary:
            return self
        from ..services.geometry import polygon_area_hectares
        poly_ha = polygon_area_hectares(self.boundary)
        if poly_ha <= 0:
            raise ValueError("boundary polygon has zero area.")
        if abs(self.area_hectares - poly_ha) > BOUNDARY_AREA_TOLERANCE * poly_ha:
            raise ValueError(
                f"area_hectares ({self.area_hectares}) does not match the drawn boundary ({poly_ha:.4f} ha)."
            )
        lats = [p[0] for p in self.boundary]
        lngs = [p[1] for p in self.boundary]
        if not (min(lats) <= self.latitude <= max(lats) and min(lngs) <= self.longitude <= max(lngs)):
            raise ValueError("latitude/longitude must lie within the drawn boundary.")
        return self


class PlantationEvidenceUpdate(ReportedNDVIMixin):
    image_url: Optional[str] = Field(None, max_length=500)
    soil_soc_pct: Optional[float] = Field(None, gt=0, le=10, examples=[1.85])
    soil_depth_cm: Optional[float] = Field(None, gt=0, le=300, examples=[30.0])
    soil_type: Optional[str] = Field(None, max_length=100, examples=["Red Sandy Loam"])

    @field_validator("image_url", "soil_type")
    @classmethod
    def _optional_text(cls, v):
        return _clean(v)


class PlantationResponse(BaseModel):
    id: int
    farmer_id: int
    name: str
    farmer_name: str
    location: str
    latitude: float
    longitude: float
    area_hectares: float
    boundary: Optional[List[List[float]]] = None
    plantation_age_years: float
    tree_count: int
    tree_species: str
    plantation_type: str
    sustainable_practice: Optional[str] = None
    image_url: Optional[str] = None
    soil_soc_pct: Optional[float] = None
    soil_depth_cm: Optional[float] = None
    soil_type: Optional[str] = None
    ndvi_reported_value: Optional[float] = None
    ndvi_reported_source: Optional[str] = None
    ndvi_reported_date: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# --- MODALITY & VERIFICATION SCHEMAS ---
class NDVIAnalysisResult(BaseModel):
    ndvi_value: Optional[float] = None
    ndvi_score: Optional[float] = None
    vegetation_status: str
    historical_diff_pct: Optional[float] = None
    band_breakdown: Optional[dict] = None
    satellite_source: str = "Simulated Sentinel-2 / Landsat-8 Baseline"

class CVAnalysisResult(BaseModel):
    image_quality_score: Optional[float] = None
    vegetation_detection_score: Optional[float] = None
    cv_score: Optional[float] = None
    detection_status: str
    detected_canopy_pct: Optional[float] = None
    methodology: str = "ExG Spectral Greenness & Texture Variance Analysis"

class SOCAnalysisResult(BaseModel):
    soc_pct: Optional[float] = None
    soc_score: Optional[float] = None
    soil_status: str
    baseline_benchmark: str

class VerificationFormulaBreakdown(BaseModel):
    ndvi_score: Optional[float] = None
    ndvi_weight: float = 0.40
    ndvi_contribution: Optional[float] = None
    
    cv_score: Optional[float] = None
    cv_weight: float = 0.35
    cv_contribution: Optional[float] = None
    
    soc_score: Optional[float] = None
    soc_weight: float = 0.25
    soc_contribution: Optional[float] = None
    
    total_score: Optional[float] = None
    formula_text: str = "Verification Score = (0.40 × NDVI) + (0.35 × CV) + (0.25 × SOC)"

class VerificationRunRequest(BaseModel):
    plantation_id: int = Field(..., gt=0)
    ground_image_path: Optional[str] = Field(None, max_length=500, description="An /uploads/<file> URL returned by an upload endpoint")
    soc_sample_pct: Optional[float] = Field(None, gt=0, le=10)

class VerificationResponse(BaseModel):
    id: Optional[str] = None            # None when no verification has been run yet (preview)
    is_persisted: bool = True
    plantation_id: int
    plantation_status: Optional[str] = None
    tree_count: Optional[int] = None
    tree_species: Optional[str] = None
    plantation_name: Optional[str] = None
    farmer_name: Optional[str] = None
    location: Optional[str] = None
    area_hectares: Optional[float] = None
    image_url: Optional[str] = None
    
    # Modality 1
    ndvi_value: Optional[float] = None
    ndvi_score: Optional[float] = None
    ndvi_status: Optional[str] = None
    
    # Modality 2
    image_quality_score: Optional[float] = None
    vegetation_detection_score: Optional[float] = None
    cv_score: Optional[float] = None
    cv_detection_status: Optional[str] = None
    
    # Modality 3
    soc_pct: Optional[float] = None
    soc_score: Optional[float] = None
    soc_status: Optional[str] = None
    
    # Weights & Contributions
    ndvi_weight: float = 0.40
    cv_weight: float = 0.35
    soc_weight: float = 0.25
    ndvi_contribution: Optional[float] = None
    cv_contribution: Optional[float] = None
    soc_contribution: Optional[float] = None
    
    overall_score: Optional[float] = None
    decision: str  # APPROVED, REVIEW, REJECTED, PENDING
    evidence_summary: Optional[str] = None
    evidence_status: Optional[Dict[str, str]] = None
    missing_evidence: Optional[List[str]] = None
    current_missing_evidence: Optional[List[str]] = None
    decision_reasons: Optional[List[str]] = None
    evidence_snapshot: Optional[Dict[str, Any]] = None
    engine_decision: Optional[str] = None
    decided_by: Optional[str] = None
    auditor_notes: Optional[str] = None
    ndvi_provenance: Optional[str] = None
    limitations_disclaimer: Optional[str] = None
    verified_at: Optional[datetime] = None

    # Satellite & Remote Sensing Provenance
    is_real_satellite: Optional[bool] = False
    satellite_source: Optional[str] = None
    acquisition_date: Optional[str] = None
    mean_ndvi: Optional[float] = None
    min_ndvi: Optional[float] = None
    max_ndvi: Optional[float] = None
    vegetation_coverage_pct: Optional[float] = None

    # AI Deep Learning Vision
    ai_model_name: Optional[str] = None
    ai_model_version: Optional[str] = None
    ai_predicted_class: Optional[str] = None
    ai_confidence_pct: Optional[float] = None
    prediction_label: Optional[str] = None

    # Risk & Fraud Detection Assessment
    risk_score: Optional[float] = None
    risk_level: Optional[str] = None
    risk_factors: Optional[List[str]] = None
    risk_explanation: Optional[str] = None

    class Config:
        from_attributes = True

# --- CARBON ESTIMATION SCHEMAS ---
class CarbonEstimateRequest(BaseModel):
    tree_count: int
    sequestration_rate: Optional[float] = 0.05  # tCO2e/tree/year
    species_factor: Optional[float] = 1.0
    practice_factor: Optional[float] = 1.0

class CarbonEstimateResponse(BaseModel):
    plantation_id: int
    tree_count: int
    sequestration_rate_per_tree: float
    estimated_carbon_tco2e: float
    issuable_credits: float
    suggested_price_inr: float
    assumptions_summary: str
    is_eligible_for_issuance: bool
    eligibility_reason: str

class IssueCreditsRequest(BaseModel):
    price_per_tco2e: Optional[float] = Field(None, gt=0, le=1_000_000)

# --- CREDIT & MARKETPLACE SCHEMAS ---
class CreditResponse(BaseModel):
    id: str
    plantation_id: int
    verification_id: str
    owner_id: int
    carbon_quantity_tco2e: float
    price_per_tco2e: float
    currency: str
    status: str
    tree_count: int
    sequestration_rate: float
    created_at: datetime
    
    # Expanded details for marketplace
    plantation_name: Optional[str] = None
    location: Optional[str] = None
    farmer_name: Optional[str] = None
    verification_score: Optional[float] = None
    verification_decision: Optional[str] = None
    image_url: Optional[str] = None
    ndvi_score: Optional[float] = None
    cv_score: Optional[float] = None
    soc_score: Optional[float] = None
    ndvi_provenance: Optional[str] = None
    plantation_status: Optional[str] = None
    is_listed: Optional[bool] = None  # True only if the credit currently meets every marketplace rule

    # Blockchain audit layer
    blockchain_tx_hash: Optional[str] = None
    blockchain_contract_address: Optional[str] = None
    blockchain_status: Optional[str] = None
    report_hash: Optional[str] = None
    retirement_tx_hash: Optional[str] = None
    is_retired: Optional[bool] = False
    retired_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# --- TRANSACTION SCHEMAS ---
class PurchaseRequest(BaseModel):
    # Credits are sold as whole lots. If given, the quantity must equal the lot size.
    quantity_tco2e: Optional[float] = Field(None, gt=0)

class TransactionResponse(BaseModel):
    id: str
    credit_id: str
    buyer_id: int
    buyer_name: Optional[str] = None
    seller_id: int
    seller_name: Optional[str] = None
    plantation_name: Optional[str] = None
    quantity_tco2e: float
    unit_price: float
    total_amount: float
    currency: str
    status: str
    payment_method: str
    certificate_id: Optional[str] = None
    blockchain_tx_hash: Optional[str] = None
    blockchain_status: Optional[str] = None
    notes: Optional[str] = None
    timestamp: datetime

    class Config:
        from_attributes = True

class BlockchainRecordResponse(BaseModel):
    credit_id: str
    on_chain: bool                      # True only if the record below was read from the contract
    source: str                         # "CONTRACT" or "DATABASE_ONLY"
    blockchain_status: Optional[str] = None
    plantation_id: int
    carbon_quantity_tco2e: float
    report_hash: Optional[str] = None
    owner_address: Optional[str] = None
    issued_at_timestamp: Optional[int] = None
    is_retired: bool
    retired_at_timestamp: Optional[int] = None
    contract_address: Optional[str] = None
    transaction_hash: Optional[str] = None
    status: str
    note: Optional[str] = None

# --- ADMIN SCHEMAS ---
class AdminDecisionRequest(BaseModel):
    decision: str  # APPROVED, REJECTED, REVIEW
    notes: Optional[str] = Field(None, max_length=2000)

    @field_validator("decision")
    @classmethod
    def _decision(cls, v: str) -> str:
        v = (v or "").strip().upper()
        if v not in {"APPROVED", "REJECTED", "REVIEW"}:
            raise ValueError("decision must be APPROVED, REJECTED or REVIEW.")
        return v

class AdminMetricsResponse(BaseModel):
    total_farmers: int
    total_buyers: int
    total_plantations: int
    pending_verifications: int
    approved_plantations: int
    review_plantations: int
    rejected_plantations: int
    credits_issued_count: int
    total_carbon_credits_tco2e: float
    total_transactions_count: int
    total_transaction_volume_inr: float

class AuditLogResponse(BaseModel):
    id: int
    user_email: Optional[str] = None
    user_role: Optional[str] = None
    action: str
    target_type: str
    target_id: str
    details: Optional[str] = None
    timestamp: datetime

    class Config:
        from_attributes = True
