import React, { useState, useEffect } from "react";
import { useAuth } from "../context/AuthContext";
import api, { getImageUrl } from "../services/api";
import StatusBadge from "../components/StatusBadge";
import LoadError from "../components/LoadError";
import { ShieldCheck, RefreshCw, ArrowRight, FileImage, AlertTriangle, MapPin, Calendar } from "lucide-react";

export default function AuditorQueuePage({ setCurrentView, setSelectedPlantationId }) {
  const { user } = useAuth();
  const [queue, setQueue] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);
  const [filterStatus, setFilterStatus] = useState("ALL");

  const loadQueue = async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const data = await api.getVerificationQueue();
      setQueue(data || []);
    } catch (err) {
      setLoadError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadQueue();
  }, []);

  const handleSelectQueueItem = (plantationId) => {
    setSelectedPlantationId(plantationId);
    setCurrentView("verification_report");
  };

  const filteredQueue = queue.filter((item) => {
    if (filterStatus === "ALL") return true;
    return (item.decision || "").toUpperCase() === filterStatus.toUpperCase();
  });

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 py-8 space-y-6 text-xs text-slate-800">
      <LoadError message={loadError} onRetry={loadQueue} />
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-baseline justify-between gap-3 border-b border-slate-200 pb-4">
        <div>
          <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Independent Audit Registry</span>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">
            Verification Queue
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Plantation evidence audit & multi-modal verification reviews • Auditor: {user?.full_name || "Lead Auditor"}
          </p>
        </div>

        <div className="flex items-center gap-2 self-start sm:self-auto">
          <button
            onClick={loadQueue}
            className="text-slate-400 hover:text-slate-600 flex items-center gap-1 text-[11px] px-2 py-1 rounded border border-slate-200 bg-white"
            title="Refresh queue"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin text-slate-700" : ""}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1">
        {["ALL", "PENDING", "REVIEW", "APPROVED", "REJECTED"].map((st) => (
          <button
            key={st}
            onClick={() => setFilterStatus(st)}
            className={`px-3 py-1.5 rounded text-xs font-semibold uppercase tracking-wider transition ${
              filterStatus === st
                ? "bg-[#1B3B2B] text-white"
                : "bg-white text-slate-600 border border-slate-200 hover:bg-slate-50"
            }`}
          >
            {st}
          </button>
        ))}
      </div>

      {/* Main Content */}
      {loading ? (
        <div className="py-16 text-center text-slate-400 bg-white rounded border border-slate-200">
          <RefreshCw className="w-5 h-5 animate-spin mx-auto mb-2 text-slate-600" />
          <p>Loading verification queue...</p>
        </div>
      ) : filteredQueue.length === 0 ? (
        <div className="py-16 px-4 text-center bg-white rounded border border-slate-200 space-y-2">
          <ShieldCheck className="w-8 h-8 text-slate-300 mx-auto" />
          <p className="font-bold text-slate-900 text-xs uppercase tracking-wider">NO VERIFICATION REQUESTS</p>
          <p className="text-slate-500 text-xs">No plantation verification requests matching the selected filter.</p>
        </div>
      ) : (
        <div className="space-y-3">
          <div className="flex items-center justify-between text-[11px] text-slate-400">
            <span className="font-semibold uppercase tracking-wider">Queue Items</span>
            <span>{filteredQueue.length} record{filteredQueue.length !== 1 ? "s" : ""}</span>
          </div>

          <div className="grid grid-cols-1 gap-4">
            {filteredQueue.map((item) => {
              const hasGroundImage = Boolean(item.image_url);
              const photoAgg = item.evidence_snapshot?.cv_measurement?.aggregation;
              const photoCount = photoAgg?.photos_submitted ?? (hasGroundImage ? null : 0);
              const hasSoil = Boolean(item.soc_score !== null || item.soc_pct !== null);
              const regDate = item.verified_at ? new Date(item.verified_at).toLocaleDateString("en-IN", {
                day: "numeric",
                month: "short",
                year: "numeric"
              }) : "Recent";

              return (
                <div
                  key={item.id || `preview-${item.plantation_id}`}
                  className="bg-white border border-slate-200 rounded p-4 flex flex-col md:flex-row items-start md:items-center justify-between gap-4 hover:border-slate-300 transition shadow-xs"
                >
                  {/* Left: Thumbnail & Main Info */}
                  <div className="flex items-start gap-4 flex-1">
                    <div className="w-24 h-24 rounded bg-slate-100 border border-slate-200 overflow-hidden flex-shrink-0 flex items-center justify-center">
                      {hasGroundImage ? (
                        <img
                          src={getImageUrl(item.image_url)}
                          alt={item.plantation_name || "Plot"}
                          className="w-full h-full object-cover"
                          onError={(e) => {
                            e.currentTarget.style.display = "none";
                            e.currentTarget.nextElementSibling.style.display = "flex";
                          }}
                        />
                      ) : null}
                      <div
                        className={`w-full h-full flex flex-col items-center justify-center p-1 text-center bg-slate-50 text-slate-400 ${
                          hasGroundImage ? "hidden" : "flex"
                        }`}
                      >
                        <FileImage className="w-5 h-5 text-slate-300 mb-0.5" />
                        <span className="text-[8px] font-bold uppercase leading-tight text-slate-500">
                          GROUND IMAGE NOT PROVIDED
                        </span>
                      </div>
                    </div>

                    <div className="space-y-1.5">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-mono font-bold text-slate-900 text-xs">
                          Plot #{item.plantation_id}
                        </span>
                        <span className="text-slate-300">•</span>
                        <h2 className="text-sm font-bold text-slate-900">
                          {item.plantation_name || "—"}
                        </h2>
                        <StatusBadge status={item.decision} size="sm" />
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded border uppercase ${
                          item.risk_level === "HIGH"
                            ? "bg-rose-100 text-rose-900 border-rose-300"
                            : item.risk_level === "MEDIUM"
                            ? "bg-amber-100 text-amber-900 border-amber-300"
                            : "bg-emerald-100 text-emerald-900 border-emerald-300"
                        }`}>
                          {item.risk_level ? `${item.risk_level} RISK (${item.risk_score})` : "RISK NOT ASSESSED"}
                        </span>
                      </div>

                      <div className="flex items-center gap-3 text-slate-500 text-[11px] flex-wrap">
                        <span>Farmer: <strong className="text-slate-700">{item.farmer_name || "—"}</strong></span>
                        <span>•</span>
                        <div className="flex items-center gap-1">
                          <MapPin className="w-3 h-3 text-slate-400" />
                          <span>{item.location || "—"}</span>
                        </div>
                        <span>•</span>
                        <div className="flex items-center gap-1">
                          <Calendar className="w-3 h-3 text-slate-400" />
                          <span>{regDate}</span>
                        </div>
                      </div>

                      {/* Evidence Completeness Badges */}
                      <div className="flex items-center gap-2 pt-1 flex-wrap">
                        <span className="text-[10px] text-slate-400 uppercase font-semibold">Evidence:</span>
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-700 border border-slate-200">
                          Boundary: {item.area_hectares ? `${item.area_hectares} ha` : "Provided"}
                        </span>
                        <span className={`text-[10px] px-1.5 py-0.5 rounded border ${
                          item.ndvi_provenance === "SENTINEL2_COMPUTED" ? "bg-emerald-50 text-emerald-900 border-emerald-200" : "bg-slate-100 text-slate-700 border-slate-200"
                        }`}>
                          NDVI: {item.ndvi_provenance === "SENTINEL2_COMPUTED" ? "Sentinel-2 computed" : item.ndvi_provenance === "REPORTED" ? "Reported" : "Not available"}
                        </span>
                        <span className={`text-[10px] px-1.5 py-0.5 rounded border ${
                          hasGroundImage ? "bg-emerald-50 text-emerald-800 border-emerald-200" : "bg-amber-50 text-amber-800 border-amber-200"
                        }`}>
                          Ground Photos: {hasGroundImage ? (photoCount ? `${photoCount} (${photoAgg.photos_scored} scored)` : "Provided") : "Not Provided"}
                        </span>
                        {photoAgg?.flags?.length > 0 && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-50 text-amber-900 border border-amber-200">
                            Photo check: {photoAgg.flags.map((f) => (f === "CONFLICTING" ? "photos disagree" : "low confidence")).join(", ")}
                          </span>
                        )}
                        {item.ai_confidence_pct !== null && item.ai_confidence_pct !== undefined && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-50 text-blue-900 border border-blue-200">
                            AI: {item.ai_predicted_class || "—"} ({item.ai_confidence_pct}%)
                          </span>
                        )}
                        <span className={`text-[10px] px-1.5 py-0.5 rounded border ${
                          hasSoil ? "bg-emerald-50 text-emerald-800 border-emerald-200" : "bg-amber-50 text-amber-800 border-amber-200"
                        }`}>
                          Soil SOC: {item.soc_pct ? `${item.soc_pct}%` : hasSoil ? "Provided" : "Not Provided"}
                        </span>
                      </div>

                      {/* Warning bar for suspicious risk items */}
                      {item.risk_factors && item.risk_factors.length > 0 && (
                        <div className="text-[10px] text-rose-800 bg-rose-50 border border-rose-200 rounded p-1.5 mt-1 font-medium flex items-center gap-1.5">
                          <AlertTriangle className="w-3 h-3 text-rose-600 flex-shrink-0" />
                          <span><strong>Risk Warning:</strong> {item.risk_factors[0]}</span>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Middle: Scores Breakdown */}
                  <div className="grid grid-cols-3 gap-2 bg-slate-50 p-2.5 rounded border border-slate-100 text-center text-[10px] w-full md:w-auto md:min-w-[240px]">
                    <div>
                      <span className="text-slate-400 block font-medium">NDVI (40%)</span>
                      <span className="font-mono font-bold text-slate-900 text-xs">
                        {item.ndvi_score !== null ? `${item.ndvi_score.toFixed(1)}` : "—"}
                      </span>
                      <span className="block text-[9px] text-slate-400 truncate max-w-[70px] mx-auto">
                        {item.ndvi_score !== null ? item.ndvi_status?.split(" ")[0] || "Active" : "Pending"}
                      </span>
                    </div>

                    <div>
                      <span className="text-slate-400 block font-medium">CV (35%)</span>
                      <span className="font-mono font-bold text-slate-900 text-xs">
                        {item.cv_score !== null ? `${item.cv_score.toFixed(1)}` : "—"}
                      </span>
                      <span className="block text-[9px] text-slate-400 truncate max-w-[70px] mx-auto">
                        {item.cv_score !== null ? "Analyzed" : "Missing"}
                      </span>
                    </div>

                    <div>
                      <span className="text-slate-400 block font-medium">SOC (25%)</span>
                      <span className="font-mono font-bold text-slate-900 text-xs">
                        {item.soc_score !== null ? `${item.soc_score.toFixed(1)}` : "—"}
                      </span>
                      <span className="block text-[9px] text-slate-400 truncate max-w-[70px] mx-auto">
                        {item.soc_score !== null ? `${item.soc_pct || ""}%` : "Missing"}
                      </span>
                    </div>
                  </div>

                  {/* Right: Review Action */}
                  <div className="flex md:flex-col items-center justify-end gap-2 w-full md:w-auto flex-shrink-0">
                    <button
                      onClick={() => handleSelectQueueItem(item.plantation_id)}
                      className="w-full md:w-auto px-4 py-2 bg-[#1B3B2B] hover:bg-[#142e21] text-white rounded text-xs font-semibold tracking-wide transition inline-flex items-center justify-center gap-1 shadow-xs uppercase"
                    >
                      <span>Review Evidence</span>
                      <ArrowRight className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
