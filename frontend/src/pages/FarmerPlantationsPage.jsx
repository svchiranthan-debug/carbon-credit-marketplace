import React, { useState, useEffect } from "react";
import { useAuth } from "../context/AuthContext";
import api, { getImageUrl } from "../services/api";
import StatusBadge from "../components/StatusBadge";
import { Trees, Plus, ArrowRight, RefreshCw, MapPin, Calendar, FileImage, ShieldCheck } from "lucide-react";

export default function FarmerPlantationsPage({ setCurrentView, setSelectedPlantationId }) {
  const { user } = useAuth();
  const [plantations, setPlantations] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchPlantations = async () => {
    setLoading(true);
    try {
      const data = await api.listPlantations();
      setPlantations(data || []);
    } catch (err) {
      console.error("Failed to load farmer plantations:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPlantations();
  }, []);

  const handleOpenDetails = (plantationId) => {
    setSelectedPlantationId(plantationId);
    setCurrentView("verification_report");
  };

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 py-8 space-y-6 text-xs text-slate-800">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-baseline justify-between gap-3 border-b border-slate-200 pb-4">
        <div>
          <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Landholding Portfolio</span>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">
            Registered Plantations
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Custody records for {user?.full_name || "Farmer"} • Smallholder Agroforestry Plots
          </p>
        </div>

        <div className="flex items-center gap-2 self-start sm:self-auto">
          <button
            onClick={fetchPlantations}
            className="text-slate-400 hover:text-slate-600 flex items-center gap-1 text-[11px] px-2 py-1 rounded border border-slate-200 bg-white"
            title="Refresh plantations"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin text-slate-700" : ""}`} />
            <span>Refresh</span>
          </button>

          <button
            onClick={() => setCurrentView("create_plantation")}
            className="inline-flex items-center gap-1.5 px-3.5 py-1.5 bg-[#1B3B2B] hover:bg-[#142e21] text-white rounded text-xs font-semibold tracking-wide transition shadow-xs uppercase"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Register Plantation</span>
          </button>
        </div>
      </div>

      {/* Main Content Area */}
      {loading ? (
        <div className="py-16 text-center text-slate-400 bg-white rounded border border-slate-200">
          <RefreshCw className="w-5 h-5 animate-spin mx-auto mb-2 text-slate-600" />
          <p>Loading registered plantations...</p>
        </div>
      ) : plantations.length === 0 ? (
        /* Empty State */
        <div className="py-16 px-4 text-center bg-white rounded border border-slate-200 space-y-4">
          <div className="w-12 h-12 rounded-full bg-slate-100 flex items-center justify-center mx-auto text-slate-400">
            <Trees className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-slate-900 uppercase tracking-wider">
              NO PLANTATIONS REGISTERED
            </h2>
            <p className="text-xs text-slate-500 mt-1 max-w-md mx-auto">
              You do not have any active registered plantations. Select your land boundary on the map and provide visual and soil evidence to begin multi-modal verification.
            </p>
          </div>
          <button
            onClick={() => setCurrentView("create_plantation")}
            className="inline-flex items-center gap-1.5 px-5 py-2.5 bg-[#1B3B2B] hover:bg-[#142e21] text-white rounded text-xs font-semibold tracking-wide transition uppercase shadow-xs"
          >
            <Plus className="w-4 h-4" />
            <span>REGISTER PLANTATION</span>
          </button>
        </div>
      ) : (
        /* Plantation Cards List */
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {plantations.map((p) => {
            const hasGroundImage = Boolean(p.image_url);
            const hasSoil = Boolean(p.soil_soc_pct && p.soil_soc_pct > 0);
            const areaM2 = Math.round((p.area_hectares || 0) * 10000);
            const regDate = p.created_at ? new Date(p.created_at).toLocaleDateString("en-IN", {
              day: "numeric",
              month: "short",
              year: "numeric"
            }) : "Recently registered";

            return (
              <div
                key={p.id}
                className="bg-white border border-slate-200 rounded overflow-hidden flex flex-col justify-between hover:border-slate-300 transition shadow-xs"
              >
                <div>
                  {/* Top Thumbnail or Ground Image Not Provided */}
                  <div className="w-full h-40 bg-slate-100 relative border-b border-slate-100 flex items-center justify-center overflow-hidden">
                    {hasGroundImage ? (
                      <img
                        src={getImageUrl(p.image_url)}
                        alt={p.name}
                        className="w-full h-full object-cover"
                        onError={(e) => {
                          e.currentTarget.style.display = "none";
                          e.currentTarget.nextElementSibling.style.display = "flex";
                        }}
                      />
                    ) : null}
                    <div
                      className={`w-full h-full flex flex-col items-center justify-center bg-slate-50 text-slate-400 p-4 ${
                        hasGroundImage ? "hidden" : "flex"
                      }`}
                    >
                      <FileImage className="w-8 h-8 mb-1.5 text-slate-300" />
                      <span className="font-bold text-[10px] uppercase tracking-wider text-slate-500">
                        GROUND IMAGE NOT PROVIDED
                      </span>
                      <span className="text-[10px] text-slate-400 mt-0.5">
                        Canopy photograph required for CV scoring
                      </span>
                    </div>

                    {/* Status badge pinned top right */}
                    <div className="absolute top-3 right-3">
                      <StatusBadge status={p.status} size="sm" />
                    </div>

                    <div className="absolute bottom-2 left-2 px-2 py-0.5 bg-slate-900/70 text-white rounded text-[10px] font-mono">
                      #{p.id}
                    </div>
                  </div>

                  {/* Body Info */}
                  <div className="p-4 space-y-3">
                    <div>
                      <h2 className="text-sm font-bold text-slate-900 tracking-tight">{p.name}</h2>
                      <div className="flex items-center gap-1 text-slate-500 text-[11px] mt-0.5">
                        <MapPin className="w-3 h-3 text-slate-400 flex-shrink-0" />
                        <span className="truncate">{p.location}</span>
                      </div>
                    </div>

                    {/* Metrics grid */}
                    <div className="grid grid-cols-2 gap-2 bg-slate-50 p-2.5 rounded border border-slate-100 text-[11px]">
                      <div>
                        <span className="text-slate-400 block text-[10px] uppercase font-medium">Boundary Area</span>
                        <span className="font-bold text-slate-900 font-mono">
                          {p.area_hectares} ha
                        </span>
                        <span className="text-slate-400 text-[10px] ml-1">
                          ({areaM2.toLocaleString()} m²)
                        </span>
                      </div>

                      <div>
                        <span className="text-slate-400 block text-[10px] uppercase font-medium">Registered</span>
                        <div className="flex items-center gap-1 text-slate-700 font-medium">
                          <Calendar className="w-3 h-3 text-slate-400" />
                          <span>{regDate}</span>
                        </div>
                      </div>

                      <div>
                        <span className="text-slate-400 block text-[10px] uppercase font-medium">Ground Image</span>
                        <span className={`font-semibold ${hasGroundImage ? "text-emerald-700" : "text-amber-700"}`}>
                          {hasGroundImage ? "PROVIDED" : "NOT PROVIDED"}
                        </span>
                      </div>

                      <div>
                        <span className="text-slate-400 block text-[10px] uppercase font-medium">Soil SOC Data</span>
                        <span className={`font-semibold ${hasSoil ? "text-emerald-700" : "text-amber-700"}`}>
                          {hasSoil ? `${p.soil_soc_pct}% SOC` : "NOT PROVIDED"}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Footer Action */}
                <div className="px-4 py-3 bg-slate-50/70 border-t border-slate-100 flex items-center justify-between">
                  <span className="text-[10px] text-slate-400 font-mono">
                    {p.tree_count} trees • {p.plantation_type || "Agroforestry"}
                  </span>

                  <button
                    onClick={() => handleOpenDetails(p.id)}
                    className="inline-flex items-center gap-1 px-3 py-1.5 bg-slate-900 hover:bg-slate-800 text-white rounded text-[11px] font-semibold transition"
                  >
                    <span>{p.status === "VERIFIED" ? "View Details" : "Continue Verification"}</span>
                    <ArrowRight className="w-3 h-3" />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
