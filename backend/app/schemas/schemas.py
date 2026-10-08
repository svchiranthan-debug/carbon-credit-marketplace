from datetime import datetime
from typing import Optional, List, Dict
from pydantic import BaseModel, Field

# --- AUTH SCHEMAS ---
class UserBase(BaseModel):
    email: str
    full_name: str
    role: str = "FARMER"
    phone: Optional[str] = None
    organization: Optional[str] = None

class UserCreate(UserBase):
    password: str

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
class PlantationCreate(BaseModel):
    name: str = Field(..., example="Kaveri River Agroforestry Plot")
    farmer_name: str = Field(..., example="Ramesh Kumar")
    location: str = Field(..., example="Mandya, Karnataka, India")
    latitude: float = Field(..., ge=-90, le=90, example=12.5218)
    longitude: float = Field(..., ge=-180, le=180, example=76.8951)
    area_hectares: float = Field(..., gt=0, example=2.5)
    plantation_age_years: float = Field(..., ge=0, example=4.0)
    tree_count: int = Field(..., gt=0, example=500)
    tree_species: str = Field(..., example="Teak, Neem, Melia Dubia")
    plantation_type: str = Field(..., example="Agroforestry")
    sustainable_practice: Optional[str] = Field(None, example="Organic Mulching & Drip Irrigation")
    image_url: Optional[str] = None
    
    # Soil inputs (Optional during initial draft registration with boundary only)
    soil_soc_pct: Optional[float] = Field(None, ge=0, le=10, example=1.85)
    soil_depth_cm: Optional[float] = Field(None, ge=0, le=300, example=45.0)
    soil_type: Optional[str] = Field(None, example="Red Sandy Loam")

class PlantationEvidenceUpdate(BaseModel):
    image_url: Optional[str] = None
    soil_soc_pct: Optional[float] = Field(None, ge=0, le=10, example=1.85)
    soil_depth_cm: Optional[float] = Field(None, ge=0, le=300, example=45.0)
    soil_type: Optional[str] = Field(None, example="Red Sandy Loam")

class PlantationResponse(PlantationCreate):
    id: int
    farmer_id: int
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
    plantation_id: int
    ground_image_path: Optional[str] = None
    soc_sample_pct: Optional[float] = None

class VerificationResponse(BaseModel):
    id: str
    plantation_id: int
    plantation_name: Optional[str] = None
    farmer_name: Optional[str] = None
    location: Optional[str] = None
    area_hectares: Optional[float] = None
    image_url: Optional[str] = None
    
    # Modality 1
    ndvi_value: Optional[float] = None
    ndvi_score: Optional[float] = None
    ndvi_status: str
    
    # Modality 2
    image_quality_score: Optional[float] = None
    vegetation_detection_score: Optional[float] = None
    cv_score: Optional[float] = None
    cv_detection_status: str
    
    # Modality 3
    soc_pct: Optional[float] = None
    soc_score: Optional[float] = None
    soc_status: str
    
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
    limitations_disclaimer: str
    verified_at: datetime

    # Satellite & Remote Sensing Provenance
    is_real_satellite: Optional[bool] = False
    satellite_source: Optional[str] = None
    acquisition_date: Optional[str] = None
    mean_ndvi: Optional[float] = None
    min_ndvi: Optional[float] = None
    max_ndvi: Optional[float] = None
    vegetation_coverage_pct: Optional[float] = None

    # AI Deep Learning Vision
    ai_model_name: Optional[str] = "MobileNetV3-Plantation-v1"
    ai_model_version: Optional[str] = "1.0.0"
    ai_predicted_class: Optional[str] = None
    ai_confidence_pct: Optional[float] = None
    prediction_label: Optional[str] = None

    # Risk & Fraud Detection Assessment
    risk_score: Optional[float] = 0.0
    risk_level: Optional[str] = "LOW"
    risk_factors: Optional[List[str]] = []
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
    price_per_tco2e: Optional[float] = 1500.0

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

    # Blockchain audit layer
    blockchain_tx_hash: Optional[str] = None
    blockchain_contract_address: Optional[str] = None
    blockchain_status: Optional[str] = "CONFIRMED"
    report_hash: Optional[str] = None
    is_retired: Optional[bool] = False
    retired_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# --- TRANSACTION SCHEMAS ---
class PurchaseRequest(BaseModel):
    quantity_tco2e: Optional[float] = None  # None means buy all or full credit

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
    notes: str
    timestamp: datetime

    class Config:
        from_attributes = True

class BlockchainRecordResponse(BaseModel):
    credit_id: str
    plantation_id: int
    carbon_quantity_tco2e: float
    report_hash: str
    owner_address: str
    issued_at_timestamp: int
    is_retired: bool
    retired_at_timestamp: int
    contract_address: str
    transaction_hash: str
    status: str

# --- ADMIN SCHEMAS ---
class AdminDecisionRequest(BaseModel):
    decision: str  # APPROVED, REJECTED, REVIEW
    notes: Optional[str] = None

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
