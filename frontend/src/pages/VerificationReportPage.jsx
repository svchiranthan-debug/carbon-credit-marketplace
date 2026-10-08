import React, { useState, useEffect } from "react";
import { useAuth } from "../context/AuthContext";
import api, { getImageUrl } from "../services/api";
import StatusBadge from "../components/StatusBadge";
import { 
  CheckCircle, 
  AlertTriangle, 
  XCircle, 
  Clock, 
  ArrowLeft, 
  ArrowRight, 
  RefreshCw, 
  Award, 
  Upload, 
  FileImage, 
  Check, 
  X,
  MapPin,
  Calendar,
  Layers,
  Trees,
  ShieldCheck
} from "lucide-react";

export default function VerificationReportPage({ plantationId, setCurrentView, setSelectedCreditId }) {
  const { user } = useAuth();
  const [verification, setVerification] = useState(null);
  const [plantation, setPlantation] = useState(null);
  const [estimate, setEstimate] = useState(null);
  const [credit, setCredit] = useState(null);
  const [loading, setLoading] = useState(true);
  const [issuingCredits, setIssuingCredits] = useState(false);
  const [error, setError] = useState(null);

  // Evidence Completion Modal State
  const [showEvidenceModal, setShowEvidenceModal] = useState(false);
  const [evidenceFile, setEvidenceFile] = useState(null);
  const [evidencePreview, setEvidencePreview] = useState(null);
  const [evidenceSoilSoc, setEvidenceSoilSoc] = useState("1.80");
  const [evidenceSoilDepth, setEvidenceSoilDepth] = useState("45");
  const [evidenceSoilType, setEvidenceSoilType] = useState("Red Sandy Loam");
  const [submittingEvidence, setSubmittingEvidence] = useState(false);
  const [modalError, setModalError] = useState(null);

  const isAuditorOrAdmin = user?.role === "ADMIN" || user?.role === "AUDITOR";

  const loadData = async () => {
    if (!plantationId) return;
    setLoading(true);
    setError(null);
    try {
      const [ver, pl, est, allCredits] = await Promise.all([
        api.getPlantationVerification(plantationId).catch(() => null),
        api.getPlantation(plantationId),
        api.estimateCarbon(plantationId).catch(() => null),
        api.listMarketplaceCredits().catch(() => [])
      ]);

      setVerification(ver);
      setPlantation(pl);
      setEstimate(est);
      
      const matchedCredit = (allCredits || []).find(c => c.plantation_id === parseInt(plantationId, 10));
      setCredit(matchedCredit || null);

      if (pl?.soil_soc_pct) setEvidenceSoilSoc(String(pl.soil_soc_pct));
      if (pl?.soil_depth_cm) setEvidenceSoilDepth(String(pl.soil_depth_cm));
      if (pl?.soil_type) setEvidenceSoilType(pl.soil_type);
    } catch (err) {
      console.error("Error loading verification report:", err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [plantationId]);

  const handleGenerateCredits = async () => {
    setIssuingCredits(true);
    try {
      const newCredit = await api.generateCredits(plantationId);
      setCredit(newCredit);
    } catch (err) {
      alert(`Credit issuance error: ${err.message}`);
    } finally {
      setIssuingCredits(false);
    }
  };

  const handleEvidenceFileChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      setEvidenceFile(file);
      setEvidencePreview(URL.createObjectURL(file));
    }
  };

  const handleSubmitEvidence = async (e) => {
    e.preventDefault();
    setSubmittingEvidence(true);
    setModalError(null);

    try {
      let finalImageUrl = plantation?.image_url;

      if (evidenceFile) {
        const uploadRes = await api.uploadImage(evidenceFile);
        finalImageUrl = uploadRes.image_url;
      }

      const socVal = parseFloat(evidenceSoilSoc);
      if (isNaN(socVal) || socVal <= 0) {
        throw new Error("Please enter a valid Soil Organic Carbon percentage (> 0).");
      }

      await api.updatePlantationEvidence(plantationId, {
        image_url: finalImageUrl,
        soil_soc_pct: socVal,
        soil_depth_cm: parseFloat(evidenceSoilDepth) || 45.0,
        soil_type: evidenceSoilType || "Red Sandy Loam"
      });

      // Re-run verification engine with newly submitted complete evidence
      await api.runVerification(plantationId);
      setShowEvidenceModal(false);
      await loadData();
    } catch (err) {
      console.error("Evidence submission error:", err);
      setModalError(err.message || "Failed to submit evidence");
    } finally {
      setSubmittingEvidence(false);
    }
  };

  if (loading) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-20 text-center text-xs text-slate-500">
        <RefreshCw className="w-5 h-5 animate-spin text-slate-700 mx-auto mb-2" />
        <p className="font-medium text-slate-800">Loading verification audit report...</p>
      </div>
    );
  }

  if (error || !verification) {
    return (
      <div className="max-w-xl mx-auto px-4 py-12 text-center text-xs">
        <div className="bg-white p-6 rounded border border-slate-200 space-y-3">
          <AlertTriangle className="w-6 h-6 text-amber-600 mx-auto" />
          <h3 className="text-sm font-bold text-slate-900">Verification Record Pending</h3>
          <p className="text-slate-500">
            {error || "Verification analysis has not completed for this plot."}
          </p>
          <button
            onClick={() => api.runVerification(plantationId).then(() => loadData())}
            className="px-4 py-2 bg-[#1B3B2B] text-white font-medium rounded text-xs hover:bg-[#142e21]"
          >
            Execute Verification
          </button>
        </div>
      </div>
    );
  }

  const isPending = verification.decision === "PENDING" || verification.overall_score === null;
  const isApproved = verification.decision === "APPROVED";
  const isReview = verification.decision === "REVIEW";

  const hasGroundImage = Boolean(plantation?.image_url);
  const hasSoil = Boolean(plantation?.soil_soc_pct && plantation.soil_soc_pct > 0);
  const soilSocValue = plantation?.soil_soc_pct ? `${plantation.soil_soc_pct}%` : "Not provided";

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 py-8 space-y-8 text-xs text-slate-800">
      {/* Back button & report header */}
      <div>
        <button
          onClick={() => setCurrentView(isAuditorOrAdmin ? "auditor_queue" : "farmer_plantations")}
          className="text-xs font-medium text-slate-500 hover:text-slate-900 mb-3 inline-flex items-center gap-1"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to {isAuditorOrAdmin ? "Verification Queue" : "My Plantations"}</span>
        </button>

        <div className="flex flex-col sm:flex-row sm:items-baseline justify-between gap-1 border-b border-slate-200 pb-3">
          <div>
            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest block">
              AUDIT REPORT & MULTI-MODAL EVIDENCE
            </span>
            <h1 className="text-xl font-bold text-slate-900 uppercase tracking-wider">
              Verification Assessment
            </h1>
            <p className="text-slate-500 text-[11px] mt-0.5">
              {plantation?.name} • Plot #{plantation?.id} • Farmer: {plantation?.farmer_name || user?.full_name}
            </p>
          </div>
          <div className="text-[11px] text-slate-400 font-mono">
            Audit Date: {new Date(verification.verified_at).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}
          </div>
        </div>
      </div>

      {/* ============================================================ */}
      {/* SECTION A: PLANTATION EVIDENCE (SECTION 6 & 5 REQUIREMENT)   */}
      {/* ============================================================ */}
      <div className="bg-white border border-slate-200 rounded p-5 space-y-4">
        <div className="flex items-center justify-between border-b border-slate-100 pb-2">
          <h2 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
            Plantation Evidence
          </h2>
          <span className="text-[10px] text-slate-400 font-mono">
            {plantation?.location} • {plantation?.area_hectares} ha
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-stretch">
          {/* 1. GROUND PHOTOGRAPH EVIDENCE (AI VISION) */}
          <div className="border border-slate-200 rounded p-3 bg-slate-50 flex flex-col justify-between">
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
                  Ground Photo (AI Vision)
                </span>
                <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-slate-200 text-slate-700">
                  {verification.ai_model_name || "MobileNetV3"}
                </span>
              </div>
              <div className="w-full h-32 rounded bg-slate-200 overflow-hidden border border-slate-300 relative group flex items-center justify-center">
                {hasGroundImage ? (
                  <img
                    src={getImageUrl(plantation?.image_url)}
                    alt={plantation?.name || "Plantation"}
                    className="w-full h-full object-cover"
                    onError={(e) => {
                      e.currentTarget.style.display = "none";
                      e.currentTarget.nextElementSibling.style.display = "flex";
                    }}
                  />
                ) : null}
                <div
                  className={`w-full h-full flex flex-col items-center justify-center p-2 text-center bg-slate-100 ${
                    hasGroundImage ? "hidden" : "flex"
                  }`}
                >
                  <FileImage className="w-6 h-6 text-slate-300 mb-1" />
                  <span className="font-bold text-[9px] uppercase tracking-wider text-slate-600">
                    GROUND IMAGE NOT PROVIDED
                  </span>
                  <span className="text-[8px] text-slate-400 mt-0.5">
                    Field photo required for AI classification
                  </span>
                </div>
              </div>
              {hasGroundImage && verification.ai_confidence_pct !== null && (
                <div className="bg-white border border-slate-200 rounded p-2 text-[10px] space-y-0.5">
                  <div className="flex justify-between">
                    <span className="text-slate-500">AI Prediction:</span>
                    <strong className="text-slate-900 capitalize">{verification.ai_predicted_class || "Plantation"}</strong>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Confidence:</span>
                    <strong className="font-mono text-emerald-800">{verification.ai_confidence_pct}%</strong>
                  </div>
                </div>
              )}
            </div>

            <div className="mt-3 pt-2 border-t border-slate-200 flex items-center justify-between">
              <span className="text-slate-500 text-[11px]">AI Vision Status:</span>
              <span className={`font-bold text-[10px] px-2 py-0.5 rounded border ${
                hasGroundImage 
                  ? "bg-emerald-50 text-emerald-800 border-emerald-200" 
                  : "bg-amber-50 text-amber-800 border-amber-200"
              }`}>
                {hasGroundImage ? "CLASSIFIED" : "NOT PROVIDED"}
              </span>
            </div>
          </div>

          {/* 2. SOIL EVIDENCE */}
          <div className="border border-slate-200 rounded p-3 bg-slate-50 flex flex-col justify-between">
            <div className="space-y-2">
              <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
                Soil Evidence
              </span>
              <div className="space-y-1.5 text-xs">
                <div className="flex justify-between">
                  <span className="text-slate-500">SOC Content:</span>
                  <span className="font-mono font-bold text-slate-900">{soilSocValue}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Sampling Depth:</span>
                  <span className="font-mono text-slate-800">{plantation?.soil_depth_cm ? `${plantation.soil_depth_cm} cm` : "—"}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Soil Type:</span>
                  <span className="text-slate-800">{plantation?.soil_type || "Red Sandy Loam"}</span>
                </div>
              </div>
              <p className="text-[10px] text-slate-400 leading-relaxed pt-1">
                Calibrated against ICAR & SoilGrids benchmarks for agroforestry carbon sequestration.
              </p>
            </div>

            <div className="mt-3 pt-2 border-t border-slate-200 flex items-center justify-between">
              <span className="text-slate-500 text-[11px]">Status:</span>
              <span className={`font-bold text-[10px] px-2 py-0.5 rounded border ${
                hasSoil 
                  ? "bg-emerald-50 text-emerald-800 border-emerald-200" 
                  : "bg-amber-50 text-amber-800 border-amber-200"
              }`}>
                {hasSoil ? "PROVIDED" : "NOT PROVIDED"}
              </span>
            </div>
          </div>

          {/* 3. SATELLITE / NDVI EVIDENCE */}
          <div className="border border-slate-200 rounded p-3 bg-slate-50 flex flex-col justify-between">
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
                  Satellite / NDVI
                </span>
                <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded border uppercase ${
                  verification.is_real_satellite
                    ? "bg-emerald-100 text-emerald-900 border-emerald-300"
                    : "bg-amber-100 text-amber-900 border-amber-300"
                }`}>
                  {verification.is_real_satellite ? "REAL SATELLITE DATA" : "DEMO / PROTOTYPE DATA"}
                </span>
              </div>
              <div className="space-y-1.5 text-xs">
                <div className="flex justify-between">
                  <span className="text-slate-500">Coordinates:</span>
                  <span className="font-mono text-slate-900 text-[11px]">
                    {plantation?.latitude?.toFixed(4)}, {plantation?.longitude?.toFixed(4)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Mean NDVI:</span>
                  <span className="font-mono font-bold text-slate-900">
                    {verification.mean_ndvi !== null && verification.mean_ndvi !== undefined ? verification.mean_ndvi : (verification.ndvi_value || "—")}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Vegetation Cover:</span>
                  <span className="font-mono text-slate-800">
                    {verification.vegetation_coverage_pct ? `${verification.vegetation_coverage_pct}%` : "—"}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Sensor Platform:</span>
                  <span className="text-slate-800 text-[11px] truncate max-w-[130px]" title={verification.satellite_source}>
                    {verification.satellite_source ? verification.satellite_source.split(" (")[0] : "Sentinel-2 L2A"}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Acquisition:</span>
                  <span className="font-mono text-slate-800 text-[11px]">
                    {verification.acquisition_date || "Recent"}
                  </span>
                </div>
              </div>
              <p className="text-[10px] text-slate-400 leading-relaxed pt-1">
                {verification.ndvi_status || "Multi-spectral surface reflectance & vegetation index."}
              </p>
            </div>

            <div className="mt-3 pt-2 border-t border-slate-200 flex items-center justify-between">
              <span className="text-slate-500 text-[11px]">Status:</span>
              <span className={`font-bold text-[10px] px-2 py-0.5 rounded border ${
                verification.ndvi_score !== null 
                  ? "bg-emerald-50 text-emerald-800 border-emerald-200" 
                  : "bg-amber-50 text-amber-800 border-amber-200"
              }`}>
                {verification.ndvi_score !== null ? "CALCULATED" : "PENDING"}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* ============================================================ */}
      {/* SECTION B: MULTI-MODAL VERIFICATION (COMPOSITE FORMULA)     */}
      {/* ============================================================ */}
      <div className="bg-white border border-slate-200 rounded p-5 space-y-4">
        <div className="flex items-center justify-between border-b border-slate-100 pb-2">
          <div>
            <h2 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
              Multi-Modal Verification
            </h2>
            <p className="text-[11px] text-slate-500">
              Three-pillar weighted verification architecture
            </p>
          </div>
          <div className="bg-slate-50 border border-slate-200 px-2.5 py-1 rounded font-mono text-[11px] text-slate-700">
            Score = 0.40(NDVI) + 0.35(CV) + 0.25(SOC)
          </div>
        </div>

        {/* Modalities Breakdown Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div className="p-3 bg-slate-50 rounded border border-slate-100 space-y-1">
            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Modality 1 • 40%</span>
            <div className="font-bold text-slate-800">Satellite / NDVI</div>
            <div className="font-mono text-base font-extrabold text-slate-900">
              {verification.ndvi_score !== null ? `${verification.ndvi_score.toFixed(1)} / 100` : "—"}
            </div>
            <span className="text-[10px] text-slate-400 block">
              Contribution: {verification.ndvi_contribution !== null ? `+${verification.ndvi_contribution.toFixed(2)}` : "—"}
            </span>
          </div>

          <div className="p-3 bg-slate-50 rounded border border-slate-100 space-y-1">
            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Modality 2 • 35%</span>
            <div className="font-bold text-slate-800">Computer Vision (CV)</div>
            <div className="font-mono text-base font-extrabold text-slate-900">
              {verification.cv_score !== null ? `${verification.cv_score.toFixed(1)} / 100` : "—"}
            </div>
            <span className="text-[10px] text-slate-400 block">
              Contribution: {verification.cv_contribution !== null ? `+${verification.cv_contribution.toFixed(2)}` : "—"}
            </span>
          </div>

          <div className="p-3 bg-slate-50 rounded border border-slate-100 space-y-1">
            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Modality 3 • 25%</span>
            <div className="font-bold text-slate-800">Soil Carbon (SOC)</div>
            <div className="font-mono text-base font-extrabold text-slate-900">
              {verification.soc_score !== null ? `${verification.soc_score.toFixed(1)} / 100` : "—"}
            </div>
            <span className="text-[10px] text-slate-400 block">
              Contribution: {verification.soc_contribution !== null ? `+${verification.soc_contribution.toFixed(2)}` : "—"}
            </span>
          </div>
        </div>

        {/* RISK & FRAUD DETECTION ENGINE SUMMARY */}
        {verification.risk_score !== null && (
          <div className={`p-4 rounded border ${
            verification.risk_level === "HIGH"
              ? "bg-rose-50/70 border-rose-200 text-rose-900"
              : verification.risk_level === "MEDIUM"
              ? "bg-amber-50/70 border-amber-200 text-amber-900"
              : "bg-slate-50 border-slate-200 text-slate-800"
          } space-y-2`}>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-slate-700" />
                <span className="text-xs font-bold uppercase tracking-wider">
                  Risk & Fraud Detection Engine
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs">Risk Score: <strong>{verification.risk_score || 0} / 100</strong></span>
                <span className={`text-[10px] font-bold px-2 py-0.5 rounded border uppercase ${
                  verification.risk_level === "HIGH"
                    ? "bg-rose-100 text-rose-900 border-rose-300"
                    : verification.risk_level === "MEDIUM"
                    ? "bg-amber-100 text-amber-900 border-amber-300"
                    : "bg-emerald-100 text-emerald-900 border-emerald-300"
                }`}>
                  {verification.risk_level || "LOW"} RISK
                </span>
              </div>
            </div>

            {verification.risk_factors && verification.risk_factors.length > 0 ? (
              <div className="text-[11px] pt-1">
                <span className="font-semibold block mb-1">Identified Risk Factors:</span>
                <ul className="list-disc list-inside space-y-0.5 text-rose-800 font-medium">
                  {verification.risk_factors.map((rf, i) => (
                    <li key={i}>{rf}</li>
                  ))}
                </ul>
              </div>
            ) : (
              <p className="text-[11px] text-slate-500">
                Evidence signals are consistent. Deduplication pHash confirmed no duplicate submissions.
              </p>
            )}
          </div>
        )}

        {/* DECISION & COMPOSITE SCORE DISPLAY */}
        {isPending ? (
          /* Case 1: Incomplete Evidence State */
          <div className="bg-amber-50/60 border border-amber-200 rounded p-4 space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Clock className="w-5 h-5 text-amber-700" />
                <div>
                  <span className="text-sm font-extrabold text-amber-900 uppercase tracking-wider block">
                    VERIFICATION PENDING
                  </span>
                  <span className="text-[11px] text-amber-800">
                    Evidence is incomplete. Scores cannot be computed without physical ground photograph and soil data.
                  </span>
                </div>
              </div>
              <div className="text-right">
                <span className="text-[10px] uppercase font-bold text-amber-700 block">Composite Score</span>
                <span className="font-mono text-2xl font-black text-amber-800">—</span>
              </div>
            </div>

            {/* Missing Evidence List */}
            <div className="pt-2 border-t border-amber-200/60">
              <span className="text-[10px] font-bold uppercase tracking-wider text-amber-900 block mb-1">
                Missing Evidence:
              </span>
              <ul className="space-y-1 text-[11px] text-amber-900 font-medium">
                {!hasGroundImage && (
                  <li className="flex items-center gap-1.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-amber-600" />
                    <span>Ground Photograph: Canopy field photograph required for Computer Vision scoring</span>
                  </li>
                )}
                {!hasSoil && (
                  <li className="flex items-center gap-1.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-amber-600" />
                    <span>Soil SOC Measurement: Lab or sensor Organic Carbon percentage required for soil verification</span>
                  </li>
                )}
              </ul>
            </div>

            {/* Action button to complete evidence */}
            <div className="flex justify-end pt-2">
              <button
                onClick={() => setShowEvidenceModal(true)}
                className="px-5 py-2 bg-[#1B3B2B] hover:bg-[#142e21] text-white font-bold rounded text-xs transition inline-flex items-center gap-2 shadow-xs uppercase"
              >
                <Upload className="w-3.5 h-3.5" />
                <span>Submit Missing Evidence</span>
              </button>
            </div>
          </div>
        ) : (
          /* Case 2: Complete Evidence & Approved / Scored */
          <div className="bg-slate-50 border border-slate-200 rounded p-4 space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                {isApproved ? (
                  <CheckCircle className="w-5 h-5 text-emerald-700" />
                ) : isReview ? (
                  <AlertTriangle className="w-5 h-5 text-amber-600" />
                ) : (
                  <XCircle className="w-5 h-5 text-rose-600" />
                )}
                <div>
                  <span className="text-sm font-extrabold text-slate-900 uppercase tracking-wider block">
                    {isApproved ? "VERIFIED (APPROVED)" : isReview ? "UNDER AUDITOR REVIEW" : "REJECTED"}
                  </span>
                  <span className="text-[11px] text-slate-500">
                    Composite Verification Score calculated across all 3 independent evidence modalities.
                  </span>
                </div>
              </div>
              <div className="text-right">
                <span className="text-[10px] uppercase font-bold text-slate-400 block">Composite Score</span>
                <span className="font-mono text-2xl font-black text-slate-900">
                  {verification.overall_score?.toFixed(1)} <span className="text-xs font-normal text-slate-400">/ 100</span>
                </span>
              </div>
            </div>

            <div className="font-mono text-[11px] text-slate-600 pt-2 border-t border-slate-200">
              = 0.40({verification.ndvi_score?.toFixed(1)}) + 0.35({verification.cv_score?.toFixed(1)}) + 0.25({verification.soc_score?.toFixed(1)}) = <strong className="text-slate-900">{verification.overall_score?.toFixed(1)} / 100</strong>
            </div>
          </div>
        )}
      </div>

      {/* ============================================================ */}
      {/* SECTION C: CARBON ESTIMATION & ASSET ISSUANCE               */}
      {/* ============================================================ */}
      {isApproved && (
        <div className="bg-white border border-slate-200 rounded p-5 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-100 pb-3">
            <div>
              <h2 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
                Carbon Estimation & Asset Status
              </h2>
              <p className="text-[11px] text-slate-500 mt-0.5">
                Eligible for issuance based on APPROVED multi-modal verification
              </p>
            </div>
            <div className="font-mono font-bold text-base text-slate-900">
              {estimate?.estimated_carbon_tco2e || Math.round(plantation.tree_count * 0.05)} tCO₂e
            </div>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-[11px]">
            <div className="bg-slate-50 p-2.5 rounded border border-slate-100">
              <span className="text-slate-400 block text-[10px]">Tree Population</span>
              <span className="font-mono font-bold text-slate-800">{plantation.tree_count}</span>
            </div>
            <div className="bg-slate-50 p-2.5 rounded border border-slate-100">
              <span className="text-slate-400 block text-[10px]">Annual Rate</span>
              <span className="font-mono font-bold text-slate-800">0.05 tCO₂e/tree</span>
            </div>
            <div className="bg-slate-50 p-2.5 rounded border border-slate-100">
              <span className="text-slate-400 block text-[10px]">Benchmark Price</span>
              <span className="font-mono font-bold text-slate-800">₹1,500 / tCO₂e</span>
            </div>
            <div className="bg-slate-50 p-2.5 rounded border border-slate-100">
              <span className="text-slate-400 block text-[10px]">Asset Status</span>
              <span className="font-semibold text-emerald-800">{credit ? "ISSUED" : "ELIGIBLE"}</span>
            </div>
          </div>

          {credit ? (
            <div className="p-4 bg-emerald-50/50 border border-emerald-200 rounded flex flex-col sm:flex-row items-center justify-between gap-3">
              <div>
                <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-800 block">
                  Carbon Asset Active on Marketplace
                </span>
                <span className="font-mono font-bold text-slate-900 text-sm">{credit.id}</span>
                <span className="text-[11px] text-slate-500 block">
                  {credit.carbon_quantity_tco2e} tCO₂e • ₹{(credit.carbon_quantity_tco2e * credit.price_per_tco2e).toLocaleString()} Total Value
                </span>
              </div>
              <button
                onClick={() => {
                  setSelectedCreditId(credit.id);
                  setCurrentView("credit_details");
                }}
                className="px-4 py-2 bg-[#1B3B2B] hover:bg-[#142e21] text-white rounded text-xs font-semibold uppercase tracking-wide transition shadow-xs inline-flex items-center gap-1.5"
              >
                <span>View in Marketplace</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>
          ) : (
            <div className="flex justify-end pt-2">
              <button
                onClick={handleGenerateCredits}
                disabled={issuingCredits}
                className="px-6 py-2.5 bg-[#1B3B2B] hover:bg-[#142e21] text-white font-bold rounded text-xs transition inline-flex items-center gap-2 shadow-xs uppercase disabled:opacity-50"
              >
                <Award className="w-4 h-4" />
                <span>{issuingCredits ? "Minting On-Chain..." : "Issue Carbon Asset"}</span>
              </button>
            </div>
          )}
        </div>
      )}

      {/* EVIDENCE COMPLETION MODAL */}
      {showEvidenceModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/30 p-4">
          <div className="bg-white rounded max-w-lg w-full p-6 shadow-lg border border-slate-200 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-2">
              <div>
                <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider">
                  Complete Plantation Evidence
                </h3>
                <p className="text-slate-500 text-[11px] mt-0.5">
                  Supply physical ground photograph and soil SOC data.
                </p>
              </div>
              <button
                onClick={() => setShowEvidenceModal(false)}
                className="text-slate-400 hover:text-slate-600 p-1"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {modalError && (
              <div className="p-3 bg-rose-50 border border-rose-200 rounded text-rose-700 text-xs">
                {modalError}
              </div>
            )}

            <form onSubmit={handleSubmitEvidence} className="space-y-4 text-xs">
              {/* Ground Image Upload */}
              <div>
                <label className="block font-semibold text-slate-800 mb-1">
                  1. Field / Ground Photograph (Computer Vision)
                </label>
                <p className="text-slate-500 mb-2 text-[11px]">
                  Upload a clear ground photo of your plantation canopy.
                </p>

                {evidencePreview || plantation?.image_url ? (
                  <div className="relative rounded border border-slate-200 overflow-hidden max-w-xs">
                    <img 
                      src={evidencePreview || getImageUrl(plantation?.image_url)} 
                      alt="Ground evidence preview" 
                      className="w-full h-32 object-cover" 
                    />
                    <label className="absolute bottom-2 right-2 px-2 py-1 bg-slate-900/80 text-white rounded text-[10px] font-medium cursor-pointer hover:bg-slate-900">
                      Change Photo
                      <input type="file" accept="image/*" onChange={handleEvidenceFileChange} className="hidden" />
                    </label>
                  </div>
                ) : (
                  <label className="border-2 border-dashed border-slate-300 hover:border-slate-400 rounded p-4 flex flex-col items-center justify-center cursor-pointer transition bg-slate-50">
                    <FileImage className="w-6 h-6 text-slate-400 mb-1" />
                    <span className="font-semibold text-slate-800 text-xs">Select Ground Photograph</span>
                    <span className="text-slate-400 text-[10px] mt-0.5">JPEG, PNG, or WebP</span>
                    <input type="file" accept="image/*" onChange={handleEvidenceFileChange} className="hidden" />
                  </label>
                )}
              </div>

              {/* Soil Data Inputs */}
              <div className="pt-2 border-t border-slate-100 space-y-3">
                <label className="block font-semibold text-slate-800">
                  2. Soil Organic Carbon Measurement (SOC)
                </label>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <div>
                    <label className="block font-medium text-slate-600 mb-1 text-[11px]">Soil SOC (%)</label>
                    <input
                      type="number"
                      step="0.01"
                      min="0.1"
                      max="10.0"
                      value={evidenceSoilSoc}
                      onChange={(e) => setEvidenceSoilSoc(e.target.value)}
                      placeholder="e.g., 1.80"
                      className="w-full px-2.5 py-1.5 rounded border border-slate-200 focus:outline-none focus:ring-1 focus:ring-slate-700 bg-white"
                      required
                    />
                  </div>

                  <div>
                    <label className="block font-medium text-slate-600 mb-1 text-[11px]">Depth (cm)</label>
                    <input
                      type="number"
                      step="1"
                      min="5"
                      max="200"
                      value={evidenceSoilDepth}
                      onChange={(e) => setEvidenceSoilDepth(e.target.value)}
                      placeholder="45"
                      className="w-full px-2.5 py-1.5 rounded border border-slate-200 focus:outline-none focus:ring-1 focus:ring-slate-700 bg-white"
                    />
                  </div>

                  <div>
                    <label className="block font-medium text-slate-600 mb-1 text-[11px]">Soil Classification</label>
                    <select
                      value={evidenceSoilType}
                      onChange={(e) => setEvidenceSoilType(e.target.value)}
                      className="w-full px-2 py-1.5 rounded border border-slate-200 focus:outline-none focus:ring-1 focus:ring-slate-700 bg-white text-[11px]"
                    >
                      <option value="Red Sandy Loam">Red Sandy Loam</option>
                      <option value="Alluvial">Alluvial</option>
                      <option value="Black Soil (Vertisol)">Black Soil</option>
                      <option value="Clay Loam">Clay Loam</option>
                    </select>
                  </div>
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setShowEvidenceModal(false)}
                  className="px-3 py-1.5 border border-slate-200 text-slate-700 rounded text-xs hover:bg-slate-50 font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submittingEvidence}
                  className="px-5 py-1.5 bg-[#1B3B2B] hover:bg-[#142e21] text-white rounded text-xs font-semibold disabled:opacity-50"
                >
                  {submittingEvidence ? "Verifying..." : "Submit & Run Verification"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
