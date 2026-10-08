import React, { useState, useEffect } from "react";
import { useAuth } from "../context/AuthContext";
import api from "../services/api";
import StatusBadge from "../components/StatusBadge";
import LoadError from "../components/LoadError";
import { Award, RefreshCw, ArrowRight, CheckCircle, Trees } from "lucide-react";

export default function FarmerCarbonAssetsPage({ setCurrentView, setSelectedCreditId }) {
  const { user } = useAuth();
  const [credits, setCredits] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);

  const fetchCredits = async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const data = await api.getMyCredits();
      setCredits(data || []);
    } catch (err) {
      setLoadError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCredits();
  }, []);

  const handleSelectAsset = (creditId) => {
    setSelectedCreditId(creditId);
    setCurrentView("credit_details");
  };

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 py-8 space-y-6 text-xs text-slate-800">
      <LoadError message={loadError} onRetry={fetchCredits} />
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-baseline justify-between gap-3 border-b border-slate-200 pb-4">
        <div>
          <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Carbon Credit Ledger</span>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">
            Issued Carbon Assets
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Verified carbon removal credits originated from {user?.full_name || "Farmer"}'s verified plantations.
          </p>
        </div>

        <div className="flex items-center gap-2 self-start sm:self-auto">
          <button
            onClick={fetchCredits}
            className="text-slate-400 hover:text-slate-600 flex items-center gap-1 text-[11px] px-2 py-1 rounded border border-slate-200 bg-white"
            title="Refresh assets"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin text-slate-700" : ""}`} />
            <span>Refresh</span>
          </button>

          <button
            onClick={() => setCurrentView("farmer_plantations")}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-slate-200 hover:bg-slate-50 text-slate-700 rounded text-xs font-semibold tracking-wide transition uppercase"
          >
            <Trees className="w-3.5 h-3.5" />
            <span>View Plantations</span>
          </button>
        </div>
      </div>

      {/* Main Content */}
      {loading ? (
        <div className="py-16 text-center text-slate-400 bg-white rounded border border-slate-200">
          <RefreshCw className="w-5 h-5 animate-spin mx-auto mb-2 text-slate-600" />
          <p>Loading carbon asset registry...</p>
        </div>
      ) : credits.length === 0 ? (
        /* Empty State */
        <div className="py-16 px-4 text-center bg-white rounded border border-slate-200 space-y-4">
          <div className="w-12 h-12 rounded-full bg-slate-100 flex items-center justify-center mx-auto text-slate-400">
            <Award className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-slate-900 uppercase tracking-wider">
              NO CARBON ASSETS
            </h2>
            <p className="text-xs text-slate-500 mt-1 max-w-lg mx-auto leading-relaxed">
              Carbon assets are not created merely by registering a plantation. An asset is issued only after:
              <br />
              <strong className="text-slate-700 font-semibold">Plantation Boundary</strong> → <strong className="text-slate-700 font-semibold">Evidence Complete</strong> → <strong className="text-slate-700 font-semibold">Multi-Modal Verification APPROVED</strong> → <strong className="text-slate-700 font-semibold">Carbon Estimation</strong> → <strong className="text-slate-700 font-semibold">Asset Issuance</strong>.
            </p>
          </div>

          <div className="pt-2">
            <button
              onClick={() => setCurrentView("farmer_plantations")}
              className="inline-flex items-center gap-1.5 px-5 py-2.5 bg-[#1B3B2B] hover:bg-[#142e21] text-white rounded text-xs font-semibold tracking-wide transition uppercase shadow-xs"
            >
              <Trees className="w-4 h-4" />
              <span>Go to Plantations & Complete Evidence</span>
            </button>
          </div>
        </div>
      ) : (
        /* Carbon Assets Table and Cards */
        <div className="space-y-4">
          <div className="flex items-center justify-between text-[11px] text-slate-400">
            <span className="font-semibold uppercase tracking-wider">Custody & Origination Ledger</span>
            <span>{credits.length} asset{credits.length !== 1 ? "s" : ""}</span>
          </div>

          <div className="bg-white border border-slate-200 rounded overflow-hidden">
            <table className="w-full text-left">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200 text-slate-500 font-medium text-[11px]">
                  <th className="py-2.5 px-4">Asset ID</th>
                  <th className="py-2.5 px-4">Plantation</th>
                  <th className="py-2.5 px-4">Quantity</th>
                  <th className="py-2.5 px-4">Verification Score</th>
                  <th className="py-2.5 px-4">Price</th>
                  <th className="py-2.5 px-4">Status</th>
                  <th className="py-2.5 px-4">Ownership</th>
                  <th className="py-2.5 px-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-800">
                {credits.map((c) => {
                  const issuedDate = c.created_at ? new Date(c.created_at).toLocaleDateString("en-IN", {
                    day: "numeric",
                    month: "short",
                    year: "numeric"
                  }) : "Recent";

                  // Display lifecycle: ISSUED / AVAILABLE / ACQUIRED / RETIRED
                  let lifecycleStatus = c.status;
                  if (c.status === "SOLD") lifecycleStatus = "ACQUIRED";
                  if (c.is_retired || c.status === "RETIRED") lifecycleStatus = "RETIRED";

                  const isAcquired = c.status === "SOLD";
                  const isRetired = c.is_retired || c.status === "RETIRED";
                  const ownershipText = isRetired 
                    ? "Permanently Retired" 
                    : isAcquired 
                    ? "Corporate Buyer" 
                    : "Farmer Custody (Available)";

                  const totalPrice = Math.round(c.carbon_quantity_tco2e * c.price_per_tco2e);

                  return (
                    <tr key={c.id} className="hover:bg-slate-50/70 transition">
                      <td className="py-3 px-4">
                        <span className="font-mono font-bold text-slate-900 block">{c.id}</span>
                        <span className="text-[10px] text-slate-400">{issuedDate}</span>
                      </td>

                      <td className="py-3 px-4">
                        <span className="font-semibold text-slate-900 block">{c.plantation_name || "Agroforest Plot"}</span>
                        <span className="text-[10px] text-slate-400">{c.location || "Karnataka"}</span>
                      </td>

                      <td className="py-3 px-4 font-mono font-bold text-slate-900">
                        {c.carbon_quantity_tco2e} tCO₂e
                      </td>

                      <td className="py-3 px-4 font-mono">
                        {c.verification_score ? (
                          <span className="inline-flex items-center gap-1 font-semibold text-emerald-800 bg-emerald-50 px-1.5 py-0.5 rounded border border-emerald-200 text-[11px]">
                            <CheckCircle className="w-3 h-3 text-emerald-600" />
                            <span>{c.verification_score.toFixed(1)} / 100</span>
                          </span>
                        ) : (
                          <span className="text-slate-400">Verified</span>
                        )}
                      </td>

                      <td className="py-3 px-4 font-mono">
                        <span className="font-bold text-slate-900 block">₹{totalPrice.toLocaleString()}</span>
                        <span className="text-[10px] text-slate-400">₹{c.price_per_tco2e}/tCO₂e</span>
                      </td>

                      <td className="py-3 px-4">
                        <StatusBadge status={lifecycleStatus} size="sm" />
                      </td>

                      <td className="py-3 px-4 text-[11px] text-slate-600">
                        {ownershipText}
                      </td>

                      <td className="py-3 px-4 text-right">
                        <button
                          onClick={() => handleSelectAsset(c.id)}
                          className="text-slate-700 hover:text-slate-900 font-semibold inline-flex items-center gap-0.5"
                        >
                          <span>View Details</span>
                          <ArrowRight className="w-3 h-3" />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Blockchain Provenance Details Cards */}
          <div className="space-y-3 pt-2">
            <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
              On-Chain Audit Records
            </h3>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {credits.map((c) => (
                <div key={`prov-${c.id}`} className="bg-white p-3.5 rounded border border-slate-200 space-y-2 text-[11px]">
                  <div className="flex items-center justify-between border-b border-slate-100 pb-2">
                    <span className="font-mono font-bold text-slate-900">{c.id}</span>
                    <span className="font-semibold text-emerald-800 bg-emerald-50 px-1.5 py-0.5 rounded text-[10px] border border-emerald-200">
                      CHAIN: {c.blockchain_status || "NOT_RECORDED"}
                    </span>
                  </div>

                  <div className="space-y-1 font-mono text-[10px] text-slate-600">
                    <div className="flex justify-between">
                      <span className="text-slate-400">Smart Contract:</span>
                      <span className="truncate max-w-[200px]">{c.blockchain_contract_address || "—"}</span>
                    </div>

                    <div className="flex justify-between">
                      <span className="text-slate-400">Transaction Hash:</span>
                      <span className="truncate max-w-[200px] text-slate-900 font-medium">
                        {c.blockchain_tx_hash ? c.blockchain_tx_hash : "— (not recorded on-chain)"}
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
