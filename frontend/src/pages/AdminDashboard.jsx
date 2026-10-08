import React, { useState, useEffect } from "react";
import { useAuth } from "../context/AuthContext";
import api from "../services/api";
import StatusBadge from "../components/StatusBadge";
import LoadError from "../components/LoadError";
import MetricCard from "../components/MetricCard";
import CreateAuditorPanel from "../components/CreateAuditorPanel";
import { 
  ShieldCheck, 
  Users, 
  Trees, 
  Clock, 
  Award, 
  ShoppingBag, 
  RefreshCw, 
  CheckCircle, 
  
  

} from "lucide-react";

export default function AdminDashboard({ setCurrentView, setSelectedPlantationId }) {
  const { user } = useAuth();
  const [metrics, setMetrics] = useState(null);
  const [verificationQueue, setVerificationQueue] = useState([]);
  const [auditLogs, setAuditLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [selectedVerification, setSelectedVerification] = useState(null);
  const [reviewNote, setReviewNote] = useState("");

  const loadData = async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const [met, queue, logs] = await Promise.all([
        api.getAdminMetrics(),
        api.getVerificationQueue(),
        api.getAuditLogs()
      ]);
      setMetrics(met);
      setVerificationQueue(queue || []);
      setAuditLogs(logs || []);
    } catch (err) {
      setLoadError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleReviewAction = async (decision) => {
    if (!selectedVerification) return;
    setActionLoading(true);
    try {
      await api.reviewVerification(selectedVerification.id, {
        decision,
        // Real notes only: the backend requires them when overriding the engine decision.
        notes: reviewNote.trim()
      });
      setSelectedVerification(null);
      setReviewNote("");
      loadData();
    } catch (err) {
      setLoadError(`Decision not saved: ${err.message}`);
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6 text-xs">
      <LoadError message={loadError} onRetry={loadData} />
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-slate-200">
        <div>
          <span className="text-xs font-semibold uppercase tracking-wider text-forest-800">Registry Administration</span>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight mt-0.5">
            Auditor Dashboard
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Auditor: {user?.full_name} • Smallholder Carbon Credit Registry
          </p>
        </div>

        <div className="flex items-center gap-2 self-start sm:self-auto">
          <button
            onClick={() => setCurrentView("auditor_queue")}
            className="px-3 py-1.5 bg-[#1B3B2B] hover:bg-[#142e21] text-white rounded text-xs font-semibold tracking-wide transition flex items-center gap-1.5"
          >
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>Verification Queue</span>
          </button>
          <button
            onClick={loadData}
            className="p-1.5 border border-slate-200 hover:bg-slate-50 rounded text-slate-600 flex items-center gap-1"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin text-forest-800" : ""}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Metrics Row (Total Farmers, Plantations, Pending Verifications, Credits Issued, Credits Sold) */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
        <MetricCard
          title="Total Farmers"
          value={metrics?.total_farmers ?? 2}
          subtitle="Registered custodians"
          icon={Users}
          color="forest"
        />
        <MetricCard
          title="Plantations"
          value={metrics?.total_plantations ?? 4}
          subtitle="Documented plots"
          icon={Trees}
          color="forest"
        />
        <MetricCard
          title="Pending Verifications"
          value={metrics?.pending_verifications ?? 1}
          subtitle="Awaiting audit review"
          icon={Clock}
          color="amber"
        />
        <MetricCard
          title="Credits Issued"
          value={`${metrics?.credits_issued ?? 2}`}
          subtitle="Issued certificates"
          icon={Award}
          color="forest"
        />
        <MetricCard
          title="Credits Sold"
          value={`${metrics?.credits_sold ?? 1}`}
          subtitle="Retired by buyers"
          icon={ShoppingBag}
          color="slate"
        />
      </div>

      {/* Verification Audit Queue */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <div className="p-5 border-b border-slate-100 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-bold text-slate-900">Verification Audit Queue</h3>
            <p className="text-[11px] text-slate-500">Plantation assessments requiring human auditor sign-off</p>
          </div>
          <span className="px-2.5 py-1 bg-amber-50 text-amber-800 border border-amber-200 rounded font-semibold text-[11px]">
            {verificationQueue.length} Active Queue
          </span>
        </div>

        {loading ? (
          <div className="py-8 text-center text-slate-400">Loading verification queue...</div>
        ) : verificationQueue.length === 0 ? (
          <div className="py-8 text-center text-slate-500">
            <CheckCircle className="w-6 h-6 text-forest-700 mx-auto mb-1" />
            <p className="font-semibold text-slate-700">All submissions have been audited.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200/80 text-slate-500 font-semibold">
                  <th className="py-3 px-4">Verification ID</th>
                  <th className="py-3 px-4">Plantation</th>
                  <th className="py-3 px-4">Satellite (40%)</th>
                  <th className="py-3 px-4">Photo (35%)</th>
                  <th className="py-3 px-4">Soil (25%)</th>
                  <th className="py-3 px-4">Score</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700">
                {verificationQueue.map((item) => (
                  <tr key={item.id || `preview-${item.plantation_id}`} className="hover:bg-slate-50 transition">
                    <td className="py-3.5 px-4 font-mono font-semibold text-slate-900">
                      {item.id}
                    </td>
                    <td className="py-3.5 px-4 font-medium text-slate-800">
                      {item.plantation_name || `Plot #${item.plantation_id}`}
                    </td>
                    <td className="py-3.5 px-4 font-mono text-slate-600">
                      {item.ndvi_score != null ? `${Number(item.ndvi_score).toFixed(1)}/100` : "—"}
                    </td>
                    <td className="py-3.5 px-4 font-mono text-slate-600">
                      {item.cv_score != null ? `${Number(item.cv_score).toFixed(1)}/100` : "—"}
                    </td>
                    <td className="py-3.5 px-4 font-mono text-slate-600">
                      {item.soc_score != null ? `${Number(item.soc_score).toFixed(1)}/100` : "—"}
                    </td>
                    <td className="py-3.5 px-4 font-mono font-bold text-[#1B3B2B]">
                      {item.overall_score != null ? Number(item.overall_score).toFixed(1) : "Pending"}
                    </td>
                    <td className="py-3.5 px-4">
                      <StatusBadge status={item.decision} size="sm" />
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <button
                          onClick={() => {
                            setSelectedPlantationId(item.plantation_id);
                            setCurrentView("verification_report");
                          }}
                          className="px-2.5 py-1 border border-slate-200 rounded hover:bg-slate-100 text-slate-700 font-medium"
                        >
                          Inspect
                        </button>
                        <button
                          onClick={() => setSelectedVerification(item)}
                          disabled={!item.id}
                          title={item.id ? "" : "No verification has been run yet"}
                          className="px-2.5 py-1 bg-forest-800 text-white rounded hover:bg-forest-900 font-semibold disabled:opacity-40"
                        >
                          Review
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Review Modal Dialog */}
      {selectedVerification && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4">
          <div className="bg-white rounded-xl max-w-md w-full p-6 shadow-xl border border-slate-200 space-y-4">
            <h3 className="text-base font-bold text-slate-900">
              Audit Review: {selectedVerification.id}
            </h3>

            <div className="p-3 bg-slate-50 rounded-lg border border-slate-100 space-y-1">
              <p className="font-semibold text-slate-800">{selectedVerification.plantation_name}</p>
              <p className="text-slate-500">
                Composite Score: <strong className="font-mono text-slate-800">{selectedVerification.overall_score != null ? `${Number(selectedVerification.overall_score).toFixed(1)}/100` : "Pending Evaluation"}</strong>
              </p>
              <p className="text-slate-500">Current Status: <StatusBadge status={selectedVerification.decision} size="sm" /></p>
            </div>

            <div>
              <label className="block font-medium text-slate-700 mb-1">Auditor Review Notes</label>
              <textarea
                rows={3}
                value={reviewNote}
                onChange={(e) => setReviewNote(e.target.value)}
                placeholder="Enter audit rationale (e.g. verified canopy coverage meets threshold)..."
                className="w-full px-3 py-2 rounded-lg border border-slate-200 text-xs focus:outline-none focus:ring-1 focus:ring-forest-700"
              />
            </div>

            <div className="grid grid-cols-3 gap-2 pt-2">
              <button
                type="button"
                disabled={actionLoading || selectedVerification.overall_score == null}
                title={selectedVerification.overall_score == null ? "Approval needs a fully scored verification" : ""}
                onClick={() => handleReviewAction("APPROVED")}
                className="py-2 bg-forest-800 hover:bg-forest-900 text-white font-bold rounded-lg text-xs disabled:opacity-40"
              >
                Approve
              </button>

              <button
                type="button"
                disabled={actionLoading}
                onClick={() => handleReviewAction("REVIEW")}
                className="py-2 bg-amber-600 hover:bg-amber-700 text-white font-bold rounded-lg text-xs"
              >
                Request Review
              </button>

              <button
                type="button"
                disabled={actionLoading}
                onClick={() => handleReviewAction("REJECTED")}
                className="py-2 bg-rose-600 hover:bg-rose-700 text-white font-bold rounded-lg text-xs"
              >
                Reject
              </button>
            </div>

            <button
              type="button"
              onClick={() => setSelectedVerification(null)}
              className="w-full py-1.5 text-slate-500 hover:text-slate-700 text-center font-medium"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {user?.role === "ADMIN" && <CreateAuditorPanel />}

      {/* System Audit Log */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <div className="p-4 border-b border-slate-100 flex items-center justify-between">
          <h3 className="text-sm font-bold text-slate-900">System Audit Trail</h3>
          <span className="text-[11px] text-slate-400">Chronological activity record</span>
        </div>

        <div className="divide-y divide-slate-100 max-h-56 overflow-y-auto">
          {auditLogs && auditLogs.length > 0 ? (
            auditLogs.slice(0, 6).map((log) => (
              <div key={log.id} className="p-3 text-[11px] flex items-center justify-between hover:bg-slate-50">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-slate-400">{log.action}</span>
                  <span className="font-semibold text-slate-800">{log.details}</span>
                </div>
                <span className="text-slate-400 font-mono">{log.timestamp ? new Date(log.timestamp).toLocaleTimeString() : ""}</span>
              </div>
            ))
          ) : (
            <div className="p-4 text-center text-slate-400 text-xs">No audit logs recorded yet.</div>
          )}
        </div>
      </div>
    </div>
  );
}
