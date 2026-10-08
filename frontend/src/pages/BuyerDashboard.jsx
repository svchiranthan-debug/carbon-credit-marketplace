import React, { useState, useEffect } from "react";
import { useAuth } from "../context/AuthContext";
import api from "../services/api";
import StatusBadge from "../components/StatusBadge";
import LoadError from "../components/LoadError";
import { RefreshCw, ArrowRight, Lock, X } from "lucide-react";

export default function BuyerDashboard({ setCurrentView }) {
  const { user } = useAuth();
  const [transactions, setTransactions] = useState([]);
  const [allCredits, setAllCredits] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);
  const [retiringCreditId, setRetiringCreditId] = useState(null);
  const [retirementModalCredit, setRetirementModalCredit] = useState(null);
  const [retiredEvent, setRetiredEvent] = useState(null);

  const loadData = async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const [txList, crList] = await Promise.all([
        api.listTransactions(),
        api.getMyCredits()
      ]);
      setTransactions(txList || []);
      setAllCredits(crList || []);
    } catch (err) {
      setLoadError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  // Compute portfolio metrics
  const myCredits = allCredits.filter(c => c.owner_id === user?.id);
  const carbonAcquiredTCO2e = transactions.reduce((acc, tx) => acc + tx.quantity_tco2e, 0);
  const carbonRetiredTCO2e = myCredits.filter(c => c.is_retired || c.status === "RETIRED").reduce((acc, c) => acc + c.carbon_quantity_tco2e, 0);
  const activeAssetsCount = myCredits.filter(c => !c.is_retired && c.status !== "RETIRED").length;

  const handleRetire = async (credit) => {
    setRetiringCreditId(credit.id);
    try {
      const res = await api.retireCredit(credit.id);
      setRetiredEvent({
        creditId: credit.id,
        quantity: credit.carbon_quantity_tco2e,
        txHash: res.blockchain_tx_hash || null,
        chainStatus: res.blockchain_status,
      });
      setRetirementModalCredit(null);
      loadData();
    } catch (err) {
      setLoadError(`Retirement failed: ${err.message}`);
    } finally {
      setRetiringCreditId(null);
    }
  };

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 py-8 space-y-8 text-xs text-slate-800">
      <LoadError message={loadError} onRetry={loadData} />
      {/* 1. Header */}
      <div className="flex flex-col sm:flex-row sm:items-baseline justify-between gap-2 border-b border-slate-200 pb-3">
        <div>
          <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Corporate Account</span>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">
            ESG Portfolio
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            {user?.organization ? `${user.organization} • ` : ""}Account: {user?.full_name || "Buyer"}
          </p>
        </div>

        <button
          onClick={loadData}
          className="text-slate-400 hover:text-slate-600 flex items-center gap-1 text-[11px] self-start sm:self-auto"
          title="Refresh portfolio"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin text-forest-800" : ""}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* 11. Permanent Retirement Event Banner */}
      {retiredEvent && (
        <div className="bg-white border border-slate-300 rounded p-6 space-y-3">
          <div className="flex items-center justify-between border-b border-slate-100 pb-2">
            <span className="text-[11px] font-bold uppercase tracking-widest text-slate-400">
              Lifecycle Event
            </span>
            <button
              onClick={() => setRetiredEvent(null)}
              className="text-slate-400 hover:text-slate-600 p-1"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>

          <div>
            <h2 className="text-base font-bold text-slate-900 uppercase tracking-wide">
              Carbon Asset Retired
            </h2>
            <p className="font-mono text-lg font-bold text-slate-900 mt-0.5">
              {retiredEvent.creditId} • {retiredEvent.quantity} tCO₂e
            </p>
            <div className="mt-1">
              <span className="inline-block bg-slate-100 text-slate-800 px-2 py-0.5 rounded text-[11px] font-semibold border border-slate-200">
                Status: RETIRED
              </span>
            </div>
          </div>

          <p className="text-xs text-slate-700 font-medium pt-1">
            This asset can no longer be transferred or sold.
          </p>

          <div className="bg-slate-50 p-2.5 rounded border border-slate-200 text-[11px] font-mono text-slate-600 break-all">
            Blockchain Retirement Tx: {retiredEvent.txHash || `— (${retiredEvent.chainStatus || "NOT_RECORDED"}: not recorded on-chain)`}
          </div>
        </div>
      )}

      {/* 10. Compact Overview (Section 10) */}
      <div className="grid grid-cols-3 gap-3">
        <div className="bg-white p-3.5 rounded border border-slate-200">
          <span className="text-[11px] font-medium text-slate-400 uppercase tracking-wider block">Carbon Acquired</span>
          <p className="text-lg font-bold text-slate-900 font-mono mt-1">
            {carbonAcquiredTCO2e.toFixed(1)} tCO₂e
          </p>
        </div>

        <div className="bg-white p-3.5 rounded border border-slate-200">
          <span className="text-[11px] font-medium text-slate-400 uppercase tracking-wider block">Carbon Retired</span>
          <p className="text-lg font-bold text-slate-900 font-mono mt-1">
            {carbonRetiredTCO2e.toFixed(1)} tCO₂e
          </p>
        </div>

        <div className="bg-white p-3.5 rounded border border-slate-200">
          <span className="text-[11px] font-medium text-slate-400 uppercase tracking-wider block">Active Assets</span>
          <p className="text-lg font-bold text-slate-900 font-mono mt-1">
            {activeAssetsCount}
          </p>
        </div>
      </div>

      {/* Your Carbon Assets Table */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
            Your Carbon Assets
          </h2>
          <button
            onClick={() => setCurrentView("marketplace")}
            className="text-slate-600 hover:text-slate-900 text-xs font-medium inline-flex items-center gap-1"
          >
            <span>Explore Marketplace</span>
            <ArrowRight className="w-3 h-3" />
          </button>
        </div>

        <div className="bg-white border border-slate-200 rounded overflow-hidden">
          {myCredits.length === 0 ? (
            <div className="py-10 text-center text-slate-500">
              <p className="font-medium text-slate-700">No carbon assets in portfolio yet.</p>
              <button
                onClick={() => setCurrentView("marketplace")}
                className="mt-2 text-xs font-semibold text-forest-900 hover:underline"
              >
                Acquire Verified Assets in Marketplace →
              </button>
            </div>
          ) : (
            <table className="w-full text-left">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200 text-slate-500 font-medium text-[11px]">
                  <th className="py-2.5 px-4">Asset ID</th>
                  <th className="py-2.5 px-4">Project</th>
                  <th className="py-2.5 px-4">Quantity</th>
                  <th className="py-2.5 px-4">Verification</th>
                  <th className="py-2.5 px-4">Ownership</th>
                  <th className="py-2.5 px-4">Status</th>
                  <th className="py-2.5 px-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-800">
                {myCredits.map((cr) => {
                  const isRet = cr.is_retired || cr.status === "RETIRED";

                  return (
                    <tr key={cr.id} className="hover:bg-slate-50/70 transition">
                      <td className="py-3 px-4 font-mono font-bold text-slate-900">
                        {cr.id}
                      </td>
                      <td className="py-3 px-4 font-medium text-slate-900">
                        {cr.plantation_name || "Agroforestry Project"}
                      </td>
                      <td className="py-3 px-4 font-mono font-medium">
                        {cr.carbon_quantity_tco2e} tCO₂e
                      </td>
                      <td className="py-3 px-4 font-mono">
                        {cr.verification_score ? `${cr.verification_score} / 100` : "Verified"}
                      </td>
                      <td className="py-3 px-4 text-slate-600">
                        {user?.organization || "Portfolio Holding"}
                      </td>
                      <td className="py-3 px-4">
                        <StatusBadge status={cr.status} size="sm" />
                      </td>
                      <td className="py-3 px-4 text-right">
                        {isRet ? (
                          <span className="text-slate-400 font-medium text-[11px] inline-flex items-center gap-1">
                            <Lock className="w-3 h-3" />
                            <span>Retired</span>
                          </span>
                        ) : (
                          <button
                            onClick={() => setRetirementModalCredit(cr)}
                            className="px-2.5 py-1 bg-slate-900 hover:bg-slate-800 text-white rounded text-[11px] font-medium transition"
                          >
                            Retire Carbon Asset
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* Confirmation Modal for Permanent Retirement */}
      {retirementModalCredit && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/30 p-4">
          <div className="bg-white rounded max-w-md w-full p-6 shadow-lg border border-slate-200 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-2">
              <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider">
                Retire Carbon Asset
              </h3>
              <button
                onClick={() => setRetirementModalCredit(null)}
                className="text-slate-400 hover:text-slate-600 p-1"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="p-3 bg-slate-50 rounded border border-slate-200 space-y-1.5 text-xs">
              <div className="flex justify-between">
                <span className="text-slate-500">Asset ID:</span>
                <span className="font-mono font-bold text-slate-900">{retirementModalCredit.id}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Volume to Retire:</span>
                <span className="font-mono font-bold text-slate-900">{retirementModalCredit.carbon_quantity_tco2e} tCO₂e</span>
              </div>
            </div>

            <div className="p-3 bg-amber-50 rounded border border-amber-200 text-amber-900 text-[11px] leading-relaxed">
              <strong>Permanent Asset Event:</strong> Retiring this asset executes `retireCredit()` on the blockchain smart contract. <em>Retired credits cannot be transferred or sold again.</em>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setRetirementModalCredit(null)}
                className="px-3 py-1.5 border border-slate-200 text-slate-700 rounded text-xs hover:bg-slate-50 font-medium"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={retiringCreditId !== null}
                onClick={() => handleRetire(retirementModalCredit)}
                className="px-4 py-1.5 bg-forest-900 hover:bg-forest-950 text-white rounded text-xs font-semibold disabled:opacity-50"
              >
                {retiringCreditId ? "Executing On-Chain..." : "Confirm Retirement"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
