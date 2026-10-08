import React, { useState } from "react";
import { useAuth } from "../context/AuthContext";
import api from "../services/api";
import PlantationMap from "../components/PlantationMap";
import { 
  ArrowRight, 
  ArrowLeft, 
  FileImage, 
  AlertCircle, 
  Check, 
  
  

} from "lucide-react";

export default function CreatePlantationPage({ setCurrentView, setSelectedPlantationId }) {
  const { user } = useAuth();
  const [currentStep, setCurrentStep] = useState(1); // 1: Plantation, 2: Location, 3: Evidence, 4: Review
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  
  const [imageFile, setImageFile] = useState(null);
  const [imagePreview, setImagePreview] = useState(null);
  const [createdPlantation, setCreatedPlantation] = useState(null);

  const [formData, setFormData] = useState({
    name: "",
    farmer_name: user?.full_name || "",
    location: "",
    latitude: 12.9716, // Default map center (Karnataka region)
    longitude: 77.5946,
    area_hectares: 0,
    area_sqm: 0,
    plantation_age_years: 2.0,
    tree_count: "",
    tree_species: "",
    plantation_type: "Agroforestry",
    sustainable_practice: "Standard Organic Agroforestry",
    image_url: null,
    soil_soc_pct: "",
    soil_depth_cm: "",
    soil_type: ""
  });

  const handleImageChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      setImageFile(file);
      setImagePreview(URL.createObjectURL(file));
    }
  };

  const handleRemoveImage = () => {
    setImageFile(null);
    setImagePreview(null);
    setFormData({ ...formData, image_url: null });
  };

  // Callback from PlantationMap when user draws/edits polygon
  const handleUpdateGeometry = (geoData) => {
    setFormData(prev => ({
      ...prev,
      latitude: geoData.latitude,
      longitude: geoData.longitude,
      area_hectares: geoData.area_hectares,
      area_sqm: geoData.area_sqm
    }));
  };

  // Callback from PlantationMap when user picks an address-level geocoding result
  const handleLocationFound = (loc) => {
    setFormData(prev => ({
      ...prev,
      location: loc.displayName || loc.name,
      latitude: loc.latitude,
      longitude: loc.longitude
    }));
  };

  // Step Validation
  const validateStep1 = () => {
    if (!formData.name.trim()) {
      setError("Plantation name is required.");
      return false;
    }
    if (!formData.tree_count || parseInt(formData.tree_count, 10) <= 0) {
      setError("Number of trees must be greater than zero.");
      return false;
    }
    if (!formData.tree_species.trim()) {
      setError("Tree species information is required.");
      return false;
    }
    setError(null);
    return true;
  };

  const validateStep2 = () => {
    if (!formData.location.trim()) {
      setError("Plantation location or address is required. Please search or enter an address.");
      return false;
    }
    if (!formData.area_hectares || parseFloat(formData.area_hectares) <= 0) {
      setError("Plantation boundary must be drawn on the map to calculate the area.");
      return false;
    }
    if (formData.latitude === undefined || formData.longitude === undefined) {
      setError("Plantation coordinates are required.");
      return false;
    }
    setError(null);
    return true;
  };

  const validateStep3 = () => {
    if (formData.soil_soc_pct !== "" && formData.soil_soc_pct !== null && formData.soil_soc_pct !== undefined) {
      const soc = parseFloat(formData.soil_soc_pct);
      if (isNaN(soc) || soc < 0.1 || soc > 10.0) {
        setError("If providing soil data, Soil Organic Carbon (SOC) percentage must be between 0.1% and 10.0%.");
        return false;
      }
    }
    setError(null);
    return true;
  };

  // Step navigation handlers
  const handleGoToStep2 = () => {
    if (validateStep1()) setCurrentStep(2);
  };

  const handleGoToStep3 = () => {
    if (validateStep2()) setCurrentStep(3);
  };

  const handleGoToStep4 = () => {
    if (validateStep3()) setCurrentStep(4);
  };

  // Form submission
  const handleSubmit = async () => {
    setError(null);
    setLoading(true);

    try {
      let finalImageUrl = formData.image_url;

      if (imageFile) {
        const uploadRes = await api.uploadImage(imageFile);
        finalImageUrl = uploadRes.image_url;
      }

      const hasSoil = (formData.soil_soc_pct !== "" && formData.soil_soc_pct !== null && formData.soil_soc_pct !== undefined);

      const payload = {
        name: formData.name.trim(),
        farmer_name: formData.farmer_name || user?.full_name || "Farmer",
        location: formData.location.trim(),
        latitude: parseFloat(formData.latitude),
        longitude: parseFloat(formData.longitude),
        area_hectares: parseFloat(formData.area_hectares),
        plantation_age_years: parseFloat(formData.plantation_age_years || 2.0),
        tree_count: parseInt(formData.tree_count, 10),
        tree_species: formData.tree_species.trim(),
        plantation_type: formData.plantation_type || "Agroforestry",
        sustainable_practice: formData.sustainable_practice || "Standard Organic Agroforestry",
        image_url: finalImageUrl || null,
        soil_soc_pct: hasSoil ? parseFloat(formData.soil_soc_pct) : null,
        soil_depth_cm: (hasSoil && formData.soil_depth_cm) ? parseFloat(formData.soil_depth_cm) : null,
        soil_type: (hasSoil && formData.soil_type) ? formData.soil_type : null
      };

      const newPlantation = await api.createPlantation(payload);
      setCreatedPlantation(newPlantation);
    } catch (err) {
      console.error("Plantation registration error:", err);
      setError(err.message || "Unable to create plantation. Please check connection and try again.");
    } finally {
      setLoading(false);
    }
  };

  // If plantation successfully registered, show confirmation
  if (createdPlantation) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-12 text-xs text-slate-800">
        <div className="bg-white border border-slate-200 rounded-lg p-6 sm:p-8 space-y-6 shadow-xs">
          <div className="flex items-center gap-3 pb-4 border-b border-slate-100">
            <div className="w-9 h-9 rounded bg-[#1B3B2B] text-white flex items-center justify-center font-bold">
              <Check className="w-5 h-5" />
            </div>
            <div>
              <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-widest block">
                Registration Confirmed
              </span>
              <h1 className="text-xl font-bold text-slate-900 tracking-tight uppercase">
                Plantation Registered
              </h1>
            </div>
          </div>

          {/* Plantation Summary Record */}
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 bg-slate-50 p-4 rounded border border-slate-200">
            <div>
              <span className="text-slate-400 block mb-0.5 text-[11px]">Plantation ID</span>
              <p className="font-bold text-slate-900 font-mono">#{createdPlantation.id}</p>
            </div>
            <div>
              <span className="text-slate-400 block mb-0.5 text-[11px]">Plantation Name</span>
              <p className="font-semibold text-slate-900">{createdPlantation.name}</p>
            </div>
            <div>
              <span className="text-slate-400 block mb-0.5 text-[11px]">Farmer</span>
              <p className="font-semibold text-slate-900">{createdPlantation.farmer_name}</p>
            </div>
            <div>
              <span className="text-slate-400 block mb-0.5 text-[11px]">Location</span>
              <p className="font-medium text-slate-800">{createdPlantation.location}</p>
            </div>
            <div>
              <span className="text-slate-400 block mb-0.5 text-[11px]">Defined Area</span>
              <p className="font-mono font-bold text-[#1B3B2B]">{createdPlantation.area_hectares} ha</p>
            </div>
            <div>
              <span className="text-slate-400 block mb-0.5 text-[11px]">Trees</span>
              <p className="font-mono text-slate-800">{createdPlantation.tree_count}</p>
            </div>
          </div>

          <p className="text-slate-600 leading-relaxed">
            Your plantation record and geospatial boundary have been submitted. You can run multi-modal verification once all evidence modalities are present.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-4 border-t border-slate-100">
            <button
              onClick={() => setCurrentView("farmer_dashboard")}
              className="w-full sm:w-auto px-4 py-2 border border-slate-200 hover:bg-slate-50 text-slate-700 font-medium rounded text-xs transition"
            >
              Back to Dashboard
            </button>

            <button
              onClick={() => {
                setSelectedPlantationId(createdPlantation.id);
                setCurrentView("verification_report");
              }}
              className="w-full sm:w-auto px-5 py-2.5 bg-[#1B3B2B] hover:bg-[#142e21] text-white font-semibold rounded text-xs tracking-wide transition inline-flex items-center justify-center gap-1.5 shadow-xs uppercase"
            >
              <span>View Verification Report</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 py-8 text-xs text-slate-800">
      {/* Back to Dashboard */}
      <button
        onClick={() => setCurrentView("farmer_dashboard")}
        className="text-xs font-semibold text-slate-500 hover:text-slate-800 mb-4 inline-flex items-center gap-1"
      >
        <ArrowLeft className="w-3.5 h-3.5" />
        <span>Return to Dashboard</span>
      </button>

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-baseline justify-between gap-2 border-b border-slate-200 pb-4 mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight uppercase">Register Plantation</h1>
          <p className="text-xs text-slate-500 mt-1">
            4-step guided registration for plantation boundary, trees, and verification evidence.
          </p>
        </div>
      </div>

      {/* Error Message Display */}
      {error && (
        <div className="mb-6 p-3 bg-rose-50 border border-rose-200 rounded flex items-center gap-2 text-rose-700 text-xs">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* 4-Step Stepper Header */}
      <div className="grid grid-cols-4 gap-2 mb-8 text-xs">
        {[
          { step: 1, title: "01 PLANTATION" },
          { step: 2, title: "02 LOCATION" },
          { step: 3, title: "03 EVIDENCE" },
          { step: 4, title: "04 REVIEW" }
        ].map((s) => (
          <div 
            key={s.step} 
            className={`pb-2 border-b-2 font-medium transition ${
              currentStep === s.step 
                ? "border-[#1B3B2B] text-slate-900 font-bold" 
                : currentStep > s.step 
                  ? "border-emerald-700 text-slate-600" 
                  : "border-slate-200 text-slate-400"
            }`}
          >
            {s.title}
          </div>
        ))}
      </div>

      {/* STEP 1: PLANTATION DETAILS */}
      {currentStep === 1 && (
        <div className="bg-white p-6 rounded border border-slate-200 space-y-4 shadow-xs">
          <h2 className="text-sm font-bold text-slate-900 pb-2 border-b border-slate-100 uppercase tracking-wider">
            Plantation Details
          </h2>

          <div>
            <label className="block font-semibold text-slate-700 mb-1">
              Plantation Name <span className="text-rose-500">*</span>
            </label>
            <input
              type="text"
              required
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              placeholder="e.g. Kaveri Agroforestry Plot"
              className="w-full px-3 py-2 rounded border border-slate-200 focus:outline-none focus:border-slate-400 bg-white"
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block font-semibold text-slate-700 mb-1">Plantation Type</label>
              <select
                value={formData.plantation_type}
                onChange={(e) => setFormData({ ...formData, plantation_type: e.target.value })}
                className="w-full px-3 py-2 rounded border border-slate-200 focus:outline-none focus:border-slate-400 bg-white"
              >
                <option value="Agroforestry">Agroforestry</option>
                <option value="Silvopasture">Silvopasture</option>
                <option value="Farm Forestry">Farm Forestry</option>
                <option value="Orchard">Orchard</option>
              </select>
            </div>

            <div>
              <label className="block font-semibold text-slate-700 mb-1">
                Tree Species <span className="text-rose-500">*</span>
              </label>
              <input
                type="text"
                required
                value={formData.tree_species}
                onChange={(e) => setFormData({ ...formData, tree_species: e.target.value })}
                placeholder="e.g. Teak, Neem, Melia Dubia"
                className="w-full px-3 py-2 rounded border border-slate-200 focus:outline-none focus:border-slate-400 bg-white"
              />
            </div>

            <div>
              <label className="block font-semibold text-slate-700 mb-1">
                Number of Trees <span className="text-rose-500">*</span>
              </label>
              <input
                type="number"
                min="1"
                required
                value={formData.tree_count}
                onChange={(e) => setFormData({ ...formData, tree_count: e.target.value })}
                placeholder="e.g. 500"
                className="w-full px-3 py-2 rounded border border-slate-200 focus:outline-none focus:border-slate-400 bg-white font-mono"
              />
            </div>

            <div>
              <label className="block font-semibold text-slate-700 mb-1">Plantation Age (Years)</label>
              <input
                type="number"
                step="0.5"
                min="0"
                required
                value={formData.plantation_age_years}
                onChange={(e) => setFormData({ ...formData, plantation_age_years: e.target.value })}
                className="w-full px-3 py-2 rounded border border-slate-200 focus:outline-none focus:border-slate-400 bg-white font-mono"
              />
            </div>
          </div>

          <div className="pt-4 flex justify-end">
            <button
              type="button"
              onClick={handleGoToStep2}
              className="px-5 py-2.5 bg-[#1B3B2B] hover:bg-[#142e21] text-white font-semibold rounded inline-flex items-center gap-1.5 transition uppercase text-xs"
            >
              <span>Continue to Location</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      )}

      {/* STEP 2: LOCATION & BOUNDARY */}
      {currentStep === 2 && (
        <div className="bg-white p-6 rounded border border-slate-200 space-y-4 shadow-xs">
          <div className="pb-2 border-b border-slate-100 flex flex-col sm:flex-row sm:items-center justify-between gap-1">
            <h2 className="text-sm font-bold text-slate-900 uppercase tracking-wider">
              Location & Geospatial Boundary
            </h2>
            <span className="text-[11px] text-slate-500">
              Address-level search + satellite polygon drawing
            </span>
          </div>

          {/* Location text address */}
          <div>
            <label className="block font-semibold text-slate-700 mb-1">
              Plantation Address / Locality <span className="text-rose-500">*</span>
            </label>
            <input
              type="text"
              required
              value={formData.location}
              onChange={(e) => setFormData({ ...formData, location: e.target.value })}
              placeholder="Search via map above or type: Basavanagudi 1st Cross, Shivamogga"
              className="w-full px-3 py-2 rounded border border-slate-200 focus:outline-none focus:border-slate-400 bg-white text-xs"
            />
          </div>

          {/* Leaflet Geospatial Satellite Map with Address-level Search */}
          <PlantationMap 
            initialLatitude={formData.latitude}
            initialLongitude={formData.longitude}
            initialArea={formData.area_hectares}
            onUpdateGeometry={handleUpdateGeometry}
            onLocationFound={handleLocationFound}
          />

          {/* SELECTED LOCATION SUMMARY (Section 17 & 18) */}
          <div className="bg-slate-50 p-4 rounded-lg border border-slate-200 text-xs space-y-2">
            <div className="flex items-center justify-between border-b border-slate-200 pb-1.5">
              <span className="font-bold text-slate-800 uppercase tracking-wider text-[10px]">
                Selected Location Summary
              </span>
              <span className="text-[10px] text-slate-400 font-medium">Live Geocoded & Calculated</span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
              <div>
                <span className="text-[11px] text-slate-500 block">Address</span>
                <p className="font-semibold text-slate-900 text-xs break-words">
                  {formData.location || "Not selected yet (search location on map)"}
                </p>
              </div>

              <div>
                <span className="text-[11px] text-slate-500 block">Boundary Status</span>
                <p className="font-semibold text-xs">
                  {formData.area_hectares > 0 ? (
                    <span className="text-emerald-700 flex items-center gap-1 font-bold">
                      <Check className="w-3.5 h-3.5" /> Defined
                    </span>
                  ) : (
                    <span className="text-amber-700">Pending (Draw boundary polygon)</span>
                  )}
                </p>
              </div>

              <div>
                <span className="text-[11px] text-slate-500 block">Latitude</span>
                <p className="font-mono text-slate-900 font-bold">
                  {formData.latitude !== undefined ? Number(formData.latitude).toFixed(6) : "—"}
                </p>
              </div>

              <div>
                <span className="text-[11px] text-slate-500 block">Longitude</span>
                <p className="font-mono text-slate-900 font-bold">
                  {formData.longitude !== undefined ? Number(formData.longitude).toFixed(6) : "—"}
                </p>
              </div>

              <div className="sm:col-span-2 bg-white p-2.5 rounded border border-slate-200 flex items-center justify-between">
                <div>
                  <span className="text-[10px] uppercase font-bold text-slate-400 block">Calculated Plantation Area</span>
                  <span className="text-sm font-bold text-[#1B3B2B] font-mono">
                    {formData.area_hectares > 0 ? `${formData.area_hectares} ha` : "0.00 ha"}
                  </span>
                </div>
                {formData.area_hectares > 0 && (
                  <span className="text-xs font-mono text-slate-500">
                    {formData.area_sqm ? formData.area_sqm.toLocaleString() : Math.round(formData.area_hectares * 10000).toLocaleString()} m²
                  </span>
                )}
              </div>
            </div>
          </div>

          <div className="pt-4 flex justify-between items-center">
            <button
              type="button"
              onClick={() => setCurrentStep(1)}
              className="px-4 py-2 border border-slate-200 text-slate-700 font-medium rounded hover:bg-slate-50"
            >
              Back
            </button>
            <button
              type="button"
              onClick={handleGoToStep3}
              className="px-5 py-2.5 bg-[#1B3B2B] hover:bg-[#142e21] text-white font-semibold rounded inline-flex items-center gap-1.5 transition uppercase text-xs"
            >
              <span>Continue to Evidence</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      )}

      {/* STEP 3: EVIDENCE (Ground Image, Soil Data) */}
      {currentStep === 3 && (
        <div className="bg-white p-6 rounded border border-slate-200 space-y-6 shadow-xs">
          <div className="pb-2 border-b border-slate-100 flex flex-col sm:flex-row sm:items-center justify-between gap-1">
            <h2 className="text-sm font-bold text-slate-900 uppercase tracking-wider">
              Plantation Evidence Submission
            </h2>
            <span className="text-[11px] text-slate-500">
              Ground imagery and soil data required for final verification scoring
            </span>
          </div>

          {/* 1. SATELLITE / LOCATION BOUNDARY STATUS */}
          <div className="p-4 rounded border border-slate-200 bg-slate-50/70 space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold text-slate-700 uppercase tracking-wider">
                SATELLITE / LOCATION BOUNDARY
              </span>
              {formData.area_hectares > 0 ? (
                <span className="inline-flex items-center gap-1 text-emerald-800 font-semibold bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200 text-[11px]">
                  <Check className="w-3.5 h-3.5" /> Defined ({formData.area_hectares} ha)
                </span>
              ) : (
                <span className="text-amber-800 bg-amber-50 px-2 py-0.5 rounded border border-amber-200 text-[11px] font-medium">
                  ○ Boundary pending
                </span>
              )}
            </div>
            <p className="text-slate-500 text-[11px]">
              Centroid: ({Number(formData.latitude).toFixed(4)}, {Number(formData.longitude).toFixed(4)}) • {formData.location || "Location mapped"}
            </p>
          </div>

          {/* 2. GROUND IMAGERY (COMPUTER VISION) */}
          <div className="p-4 rounded border border-slate-200 bg-white space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <span className="text-[11px] font-bold text-slate-900 uppercase tracking-wider block">
                  GROUND IMAGERY (COMPUTER VISION)
                </span>
                <span className="text-[11px] text-slate-500">
                  Ground-level photograph required for automated canopy foliage analysis.
                </span>
              </div>
              {(imagePreview || formData.image_url) ? (
                <span className="inline-flex items-center gap-1 text-emerald-800 font-semibold bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200 text-[11px]">
                  <Check className="w-3.5 h-3.5" /> Provided
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 text-slate-600 bg-slate-100 px-2 py-0.5 rounded border border-slate-200 text-[11px] font-medium">
                  ○ Not provided
                </span>
              )}
            </div>

            {(imagePreview || formData.image_url) ? (
              <div className="relative rounded border border-slate-200 overflow-hidden max-w-sm">
                <img 
                  src={imagePreview || formData.image_url} 
                  alt="Plantation preview" 
                  className="w-full h-36 object-cover" 
                />
                <button
                  type="button"
                  onClick={handleRemoveImage}
                  className="absolute top-2 right-2 px-2 py-1 bg-slate-900/80 text-white rounded text-[11px] font-medium hover:bg-slate-900"
                >
                  Change / Remove Photo
                </button>
              </div>
            ) : (
              <label className="border-2 border-dashed border-slate-200 hover:border-slate-400 rounded p-5 flex flex-col items-center justify-center cursor-pointer transition bg-slate-50/50 hover:bg-slate-50">
                <FileImage className="w-6 h-6 text-slate-400 mb-1" />
                <span className="font-semibold text-slate-800 text-xs uppercase tracking-wide">Upload Ground Image</span>
                <span className="text-slate-400 text-[10px] mt-0.5">JPEG, PNG, or WebP up to 10MB</span>
                <input
                  type="file"
                  accept="image/*"
                  onChange={handleImageChange}
                  className="hidden"
                />
              </label>
            )}
          </div>

          {/* 3. SOIL / SOC */}
          <div className="p-4 rounded border border-slate-200 bg-white space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <span className="text-[11px] font-bold text-slate-900 uppercase tracking-wider block">
                  SOIL ORGANIC CARBON (SOC)
                </span>
                <span className="text-[11px] text-slate-500">
                  Sub-surface laboratory sample or field measurement for carbon density baseline.
                </span>
              </div>
              {(formData.soil_soc_pct && parseFloat(formData.soil_soc_pct) > 0) ? (
                <span className="inline-flex items-center gap-1 text-emerald-800 font-semibold bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200 text-[11px]">
                  <Check className="w-3.5 h-3.5" /> Provided ({formData.soil_soc_pct}%)
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 text-slate-600 bg-slate-100 px-2 py-0.5 rounded border border-slate-200 text-[11px] font-medium">
                  ○ Not provided
                </span>
              )}
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-1">
              <div>
                <label className="block font-medium text-slate-700 mb-1 text-[11px]">Soil organic carbon (%)</label>
                <input
                  type="number"
                  step="0.01"
                  min="0.1"
                  max="10.0"
                  value={formData.soil_soc_pct}
                  onChange={(e) => setFormData({ ...formData, soil_soc_pct: e.target.value })}
                  placeholder="e.g. 1.85"
                  className="w-full px-3 py-2 rounded border border-slate-200 focus:outline-none focus:border-slate-400 bg-white font-mono"
                />
              </div>

              <div>
                <label className="block font-medium text-slate-700 mb-1 text-[11px]">Sampling Depth (cm)</label>
                <input
                  type="number"
                  step="5"
                  min="5"
                  max="200"
                  value={formData.soil_depth_cm}
                  onChange={(e) => setFormData({ ...formData, soil_depth_cm: e.target.value })}
                  placeholder="e.g. 45"
                  className="w-full px-3 py-2 rounded border border-slate-200 focus:outline-none focus:border-slate-400 bg-white font-mono"
                />
              </div>

              <div>
                <label className="block font-medium text-slate-700 mb-1 text-[11px]">Soil Classification</label>
                <select
                  value={formData.soil_type}
                  onChange={(e) => setFormData({ ...formData, soil_type: e.target.value })}
                  className="w-full px-3 py-2 rounded border border-slate-200 focus:outline-none focus:border-slate-400 bg-white"
                >
                  <option value="">Select soil type</option>
                  <option value="Red Sandy Loam">Red Sandy Loam</option>
                  <option value="Loam">Loam</option>
                  <option value="Alluvial">Alluvial</option>
                  <option value="Black Soil">Black Soil</option>
                  <option value="Clay">Clay</option>
                  <option value="Sandy">Sandy</option>
                </select>
              </div>
            </div>
          </div>

          <div className="pt-4 flex justify-between items-center border-t border-slate-100">
            <button
              type="button"
              onClick={() => setCurrentStep(2)}
              className="px-4 py-2 border border-slate-200 text-slate-700 font-medium rounded hover:bg-slate-50"
            >
              Back
            </button>
            <button
              type="button"
              onClick={handleGoToStep4}
              className="px-5 py-2.5 bg-[#1B3B2B] hover:bg-[#142e21] text-white font-semibold rounded inline-flex items-center gap-1.5 transition uppercase text-xs"
            >
              <span>Continue to Review</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      )}

      {/* STEP 4: REVIEW */}
      {currentStep === 4 && (
        <div className="bg-white p-6 rounded border border-slate-200 space-y-5 shadow-xs">
          <h2 className="text-sm font-bold text-slate-900 pb-2 border-b border-slate-100 uppercase tracking-wider">
            Review Plantation Details & Verification Readiness
          </h2>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 p-4 bg-slate-50 rounded border border-slate-200">
            <div>
              <span className="text-slate-400 block mb-0.5 text-[11px]">Plantation Name</span>
              <p className="font-bold text-slate-900">{formData.name || "Untitled Plot"}</p>
            </div>
            <div>
              <span className="text-slate-400 block mb-0.5 text-[11px]">Farmer</span>
              <p className="font-bold text-slate-900">{formData.farmer_name || user?.full_name || "Farmer"}</p>
            </div>
            <div>
              <span className="text-slate-400 block mb-0.5 text-[11px]">Location</span>
              <p className="font-medium text-slate-800 break-words">{formData.location}</p>
            </div>
            <div>
              <span className="text-slate-400 block mb-0.5 text-[11px]">Coordinates</span>
              <p className="font-mono text-slate-900 font-semibold">
                {Number(formData.latitude).toFixed(6)}, {Number(formData.longitude).toFixed(6)}
              </p>
            </div>
            <div>
              <span className="text-slate-400 block mb-0.5 text-[11px]">Boundary</span>
              <p className="font-semibold text-emerald-700">
                {formData.area_hectares > 0 ? "Defined" : "Not defined"}
              </p>
            </div>
            <div>
              <span className="text-slate-400 block mb-0.5 text-[11px]">Calculated Area</span>
              <p className="font-mono font-bold text-[#1B3B2B]">
                {formData.area_hectares} ha {formData.area_sqm ? `(${formData.area_sqm.toLocaleString()} m²)` : ""}
              </p>
            </div>
            <div>
              <span className="text-slate-400 block mb-0.5 text-[11px]">Tree Count</span>
              <p className="font-mono font-bold text-slate-900">{formData.tree_count} trees</p>
            </div>
            <div>
              <span className="text-slate-400 block mb-0.5 text-[11px]">Tree Species</span>
              <p className="font-semibold text-slate-800">{formData.tree_species}</p>
            </div>
            <div>
              <span className="text-slate-400 block mb-0.5 text-[11px]">Plantation Type</span>
              <p className="font-semibold text-slate-800">{formData.plantation_type}</p>
            </div>
          </div>

          {/* Evidence Completeness Status Card */}
          <div className="p-4 bg-white border border-slate-200 rounded space-y-2">
            <span className="font-semibold text-slate-800 block text-xs uppercase tracking-wide">
              Evidence Status:
            </span>
            <div className="space-y-1.5 text-xs text-slate-700">
              <div className="flex items-center gap-2">
                <Check className="w-4 h-4 text-emerald-700 shrink-0" />
                <span>
                  <strong>Plantation Boundary:</strong> Defined ({formData.area_hectares} ha)
                </span>
              </div>
              <div className="flex items-center gap-2">
                {(imagePreview || formData.image_url) ? (
                  <Check className="w-4 h-4 text-emerald-700 shrink-0" />
                ) : (
                  <span className="w-4 h-4 rounded-full border border-slate-400 inline-block shrink-0" />
                )}
                <span>
                  <strong>Ground Imagery:</strong> {(imagePreview || formData.image_url) ? "Provided" : "Not provided — can be uploaded later"}
                </span>
              </div>
              <div className="flex items-center gap-2">
                {(formData.soil_soc_pct && parseFloat(formData.soil_soc_pct) > 0) ? (
                  <Check className="w-4 h-4 text-emerald-700 shrink-0" />
                ) : (
                  <span className="w-4 h-4 rounded-full border border-slate-400 inline-block shrink-0" />
                )}
                <span>
                  <strong>Soil Carbon:</strong> {(formData.soil_soc_pct && parseFloat(formData.soil_soc_pct) > 0) ? `Provided (${formData.soil_soc_pct}% SOC)` : "Not provided — can be submitted later"}
                </span>
              </div>
            </div>

            {(!imagePreview && !formData.image_url) || (!formData.soil_soc_pct || parseFloat(formData.soil_soc_pct) <= 0) ? (
              <div className="mt-3 p-2.5 bg-amber-50 border border-amber-200 rounded text-amber-800 text-[11px] leading-relaxed">
                <strong>Notice:</strong> Verification will remain <strong>PENDING</strong> until both ground imagery and soil carbon data are provided. No carbon credits will be issued until verification is completed.
              </div>
            ) : null}
          </div>

          <div className="pt-4 flex justify-between items-center border-t border-slate-100">
            <button
              type="button"
              onClick={() => setCurrentStep(3)}
              className="px-4 py-2 border border-slate-200 text-slate-700 font-medium rounded hover:bg-slate-50"
            >
              Back
            </button>

            <button
              type="button"
              onClick={handleSubmit}
              disabled={loading}
              className="px-6 py-2.5 bg-[#1B3B2B] hover:bg-[#142e21] text-white font-bold rounded text-xs transition inline-flex items-center gap-2 shadow-xs disabled:opacity-50 tracking-wide uppercase"
            >
              <span>{loading ? "Creating Plantation..." : "CREATE PLANTATION"}</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
