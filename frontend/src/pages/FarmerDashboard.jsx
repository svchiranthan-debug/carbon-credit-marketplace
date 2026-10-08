import React, { useState, useEffect } from "react";
import { useAuth } from "../context/AuthContext";
import api from "../services/api";
import StatusBadge from "../components/StatusBadge";
import LoadError from "../components/LoadError";
import { ArrowRight, RefreshCw, Plus } from "lucide-react";

export default function FarmerDashboard({ setCurrentView, setSelectedPlantationId }) {
  const { user } = useAuth();
  const [plantations, setPlantations] = useState([]);
  const [credits, setCredits] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);

  const fetchData = async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const [plList, crList] = await Promise.all([
        api.listPlantations(),
        api.getMyCredits()
      ]);
      setPlantations(plList || []);
      setCredits(crList || []);
    } catch (err) {
      setLoadError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleOpenDetails = (plantationId) => {
    setSelectedPlantationId(plantationId);
    setCurrentView("verification_report");
  };

  const primaryPlantation = plantations.length > 0 ? plantations[0] : null;
  const myCredits = credits.filter(c => plantations.some(p => p.id === c.plantation_id));
  const totalCarbonGenerated = myCredits.reduce((acc, c) => acc + c.carbon_quantity_tco2e, 0);
  const carbonAssetsCount = myCredits.length;

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 py-8 space-y-8 text-xs text-slate-800">
      <LoadError message={loadError} onRetry={fetchData} />
      {/* 1. Header with Authenticated Registered User Name */}
      <div className="flex flex-col sm:flex-row sm:items-baseline justify-between gap-2 border-b border-slate-200 pb-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">
            Good morning, {user?.full_name || "Farmer"}
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Manage your plantations, verification status and carbon assets.
          </p>
        </div>

        <button
          onClick={fetchData}
          className="text-slate-400 hover:text-slate-600 flex items-center gap-1 self-start sm:self-auto text-[11px]"
          title="Refresh data"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin text-slate-700" : ""}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* 2. Compact Overview Blocks */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="bg-white p-3.5 rounded border border-slate-200">
          <span className="text-[11px] font-medium text-slate-400 uppercase tracking-wider block">Plantations</span>
          <p className="text-lg font-bold text-slate-900 font-mono mt-1">
            {plantations.length}
          </p>
        </div>

        <div className="bg-white p-3.5 rounded border border-slate-200">
          <span className="text-[11px] font-medium text-slate-400 uppercase tracking-wider block">Verification</span>
          <div className="mt-1">
            {primaryPlantation ? (
              <StatusBadge status={primaryPlantation.status} size="sm" />
            ) : (
              <span className="text-slate-400 font-medium">None</span>
            )}
          </div>
        </div>

        <div className="bg-white p-3.5 rounded border border-slate-200">
          <span className="text-[11px] font-medium text-slate-400 uppercase tracking-wider block">Carbon Generated</span>
          <p className="text-lg font-bold text-slate-900 font-mono mt-1">
            {totalCarbonGenerated} tCO₂e
          </p>
        </div>

        <div className="bg-white p-3.5 rounded border border-slate-200">
          <span className="text-[11px] font-medium text-slate-400 uppercase tracking-wider block">Carbon Assets</span>
          <p className="text-lg font-bold text-slate-900 font-mono mt-1">
            {carbonAssetsCount}
          </p>
        </div>
      </div>

      {/* 3. ONE Primary Action (shown only if plantations exist to prevent duplication) */}
      {plantations.length > 0 && (
        <div>
          <button
            onClick={() => setCurrentView("create_plantation")}
            className="inline-flex items-center gap-1.5 px-4 py-2 bg-[#1B3B2B] hover:bg-[#142e21] text-white rounded text-xs font-semibold tracking-wide shadow-xs transition uppercase"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Register Plantation</span>
          </button>
        </div>
      )}

      {/* 4. Plantations Table */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-bold text-slate-900 uppercase tracking-wider">
            My Plantations
          </h2>
          <span className="text-[11px] text-slate-400">
            {plantations.length} record{plantations.length !== 1 ? "s" : ""}
          </span>
        </div>

        <div className="bg-white border border-slate-200 rounded overflow-hidden">
          <table className="w-full text-left">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200 text-slate-500 font-medium text-[11px]">
                <th className="py-2.5 px-4">Plantation</th>
                <th className="py-2.5 px-4">Location</th>
                <th className="py-2.5 px-4">Verification</th>
                <th className="py-2.5 px-4">Carbon</th>
                <th className="py-2.5 px-4">Status</th>
                <th className="py-2.5 px-4 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-slate-800">
              {plantations.length === 0 ? (
                <tr>
                  <td colSpan="6" className="py-12 text-center text-slate-500">
                    <p className="font-bold text-slate-900 uppercase tracking-wider text-xs">NO PLANTATIONS REGISTERED</p>
                    <p className="text-slate-500 text-xs mt-1">Register your first plantation boundary and evidence to begin verification.</p>
                    <button
                      onClick={() => setCurrentView("create_plantation")}
                      className="mt-4 inline-flex items-center gap-1.5 px-4 py-2 bg-[#1B3B2B] hover:bg-[#142e21] text-white rounded text-xs font-semibold tracking-wide transition uppercase shadow-xs"
                    >
                      <Plus className="w-3.5 h-3.5" />
                      <span>Register Plantation</span>
                    </button>
                  </td>
                </tr>
              ) : (
                plantations.map((p) => (
                  <tr key={p.id} className="hover:bg-slate-50/70 transition">
                    <td className="py-3 px-4 font-semibold text-slate-900">{p.name}</td>
                    <td className="py-3 px-4 text-slate-500">{p.location}</td>
                    <td className="py-3 px-4 font-mono text-slate-700">
                      {p.status === "VERIFIED" ? "Verified" : "Pending Audit"}
                    </td>
                    <td className="py-3 px-4 font-mono font-medium">
                      {p.status === "VERIFIED" ? `${Math.round(p.tree_count * 0.05)} tCO₂e` : "—"}
                    </td>
                    <td className="py-3 px-4">
                      <StatusBadge status={p.status} size="sm" />
                    </td>
                    <td className="py-3 px-4 text-right">
                      <button
                        onClick={() => handleOpenDetails(p.id)}
                        className="text-slate-700 hover:text-slate-900 font-medium inline-flex items-center gap-0.5"
                      >
                        <span>View Details</span>
                        <ArrowRight className="w-3 h-3" />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
