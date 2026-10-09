import React, { useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import api, { getImageUrl } from "../services/api";
import StatusBadge from "../components/StatusBadge";
import {
  AlertTriangle, ArrowLeft, ArrowRight, FileImage, History, RefreshCw, ShieldCheck, Upload, X,
} from "lucide-react";

/**
 * Verification Wall
 *
 * Shows exactly what the backend measured for one plantation and why it reached its decision.
 * Rules: missing numbers render as "—"; nothing is defaulted, simulated or inferred client-side;
 * credits are only shown as issued when the backend returns an issued credit.
 */

const DASH = "—";
const num = (v, digits = 1) => (v === null || v === undefined || Number.isNaN(Number(v)) ? DASH : Number(v).toFixed(digits));
const ACRES_PER_HA = 2.4710538;

const NDVI_SOURCE_LABEL = {
  SENTINEL2_COMPUTED: "Sentinel-2 (computed by backend)",
  REPORTED: "Reported by farmer — needs auditor confirmation",
};

function fmtDate(value) {
  if (!value) return null;
  return new Date(value).toLocaleString("en-IN", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

function Row({ label, value, mono = false }) {
  return (
    <div className="flex justify-between gap-3 py-1 border-b border-slate-100 last:border-0">
      <span className="text-slate-500">{label}</span>
      <span className={`text-right text-slate-900 ${mono ? "font-mono" : "font-medium"}`}>{value ?? DASH}</span>
    </div>
  );
}

function ModalityCard({ title, weight, score, contribution, status, children }) {
  return (
    <div className="border border-slate-200 rounded p-3 bg-white flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">{title}</span>
        <span className="text-[10px] font-mono text-slate-400">weight {weight}</span>
      </div>
      <div className="flex items-baseline gap-1">
        <span className="font-mono text-lg font-bold text-slate-900">{num(score)}</span>
        <span className="text-slate-400">/ 100</span>
        <span className="ml-auto font-mono text-[11px] text-slate-500">
          {contribution === null || contribution === undefined ? DASH : `+${num(contribution, 2)}`}
        </span>
      </div>
      <p className="text-[11px] text-slate-600 min-h-[2.5em]">{status || DASH}</p>
      <div className="text-[11px]">{children}</div>
    </div>
  );
}

export default function VerificationReportPage({ plantationId, setCurrentView, setSelectedCreditId }) {
  const { user } = useAuth();
  const isAuditor = user?.role === "ADMIN" || user?.role === "AUDITOR";
  const isFarmer = user?.role === "FARMER";

  const [plantation, setPlantation] = useState(null);
  const [verification, setVerification] = useState(null);
  const [history, setHistory] = useState([]);
  const [credit, setCredit] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actionError, setActionError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [showEvidence, setShowEvidence] = useState(false);
  const [decisionNotes, setDecisionNotes] = useState("");

  const load = async () => {
    if (!plantationId) return;
    setLoading(true);
    setError(null);
    try {
      const [pl, ver, hist, credits] = await Promise.all([
        api.getPlantation(plantationId),
        api.getPlantationVerification(plantationId),
        api.getVerificationHistory(plantationId),
        user?.role === "BUYER" ? api.listMarketplaceCredits({ status: "ALL" }) : api.getMyCredits(),
      ]);
      setPlantation(pl);
      setVerification(ver);
      setHistory(hist || []);
      setCredit((credits || []).find((c) => c.plantation_id === Number(plantationId)) || null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [plantationId]);

  const runAction = async (fn) => {
    setBusy(true);
    setActionError(null);
    try {
      await fn();
      await load();
    } catch (err) {
      setActionError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const runVerification = () => runAction(() => api.runVerification(plantationId));
  const decide = (decision) =>
    runAction(async () => {
      await api.updateAdminDecision(verification.id, decision, decisionNotes.trim());
      setDecisionNotes("");
    });

  if (loading) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-20 text-center text-xs text-slate-500">
        <RefreshCw className="w-5 h-5 animate-spin text-slate-700 mx-auto mb-2" />
        Loading verification wall…
      </div>
    );
  }

  if (error || !plantation || !verification) {
    return (
      <div className="max-w-xl mx-auto px-4 py-12 text-center text-xs">
        <div className="bg-white p-6 rounded border border-rose-200 space-y-3">
          <AlertTriangle className="w-6 h-6 text-rose-600 mx-auto" />
          <h3 className="text-sm font-bold text-slate-900">Could not load this plantation</h3>
          <p className="text-slate-600">{error || "No data returned."}</p>
          <button onClick={load} className="px-4 py-2 bg-[#1B3B2B] text-white rounded text-xs">Retry</button>
        </div>
      </div>
    );
  }

  const v = verification;
  const scored = v.overall_score !== null && v.overall_score !== undefined;
  const isLatest = v.is_persisted !== false && history.length > 0 && history[0].id === v.id;
  const evidenceLocked = Boolean(credit);
  const missingNow = v.current_missing_evidence || [];
  const ndvi = v.mean_ndvi ?? v.ndvi_value;

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 py-8 space-y-6 text-xs text-slate-800">
      {/* Header */}
      <div>
        <button
          onClick={() => setCurrentView(isAuditor ? "auditor_queue" : isFarmer ? "farmer_plantations" : "marketplace")}
          className="text-xs text-slate-500 hover:text-slate-900 mb-3 inline-flex items-center gap-1"
        >
          <ArrowLeft className="w-3.5 h-3.5" /> Back
        </button>
        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-2 border-b border-slate-200 pb-3">
          <div>
            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Verification Wall</span>
            <h1 className="text-xl font-bold text-slate-900">{plantation.name}</h1>
            <p className="text-slate-500 text-[11px]">Plot #{plantation.id} • {plantation.location}</p>
          </div>
          <div className="text-right space-y-1">
            <StatusBadge status={v.decision} />
            <p className="text-[11px] text-slate-400 font-mono">
              {v.is_persisted === false ? "Not yet verified" : `${v.id} • ${fmtDate(v.verified_at)}`}
            </p>
          </div>
        </div>
      </div>

      {actionError && (
        <div className="p-3 rounded border border-rose-200 bg-rose-50 text-rose-800 flex items-start gap-2">
          <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
          <span>{actionError}</span>
        </div>
      )}

      {/* Decision */}
      <section className="bg-white border border-slate-200 rounded p-5 space-y-3">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="text-xs font-bold uppercase tracking-wider text-slate-900">Decision</h2>
          <div className="font-mono">
            <span className="text-2xl font-bold text-slate-900">{num(v.overall_score)}</span>
            <span className="text-slate-400"> / 100</span>
          </div>
        </div>
        <p className="text-[11px] text-slate-500 font-mono">
          Score = 0.40 × NDVI ({num(v.ndvi_score)}) + 0.35 × CV ({num(v.cv_score)}) + 0.25 × SOC ({num(v.soc_score)})
          {" "}• approve ≥ 75 • review ≥ 55 • reject &lt; 55
        </p>
        {v.decision_reasons?.length > 0 && (
          <ul className="list-disc pl-5 space-y-1 text-slate-700">
            {v.decision_reasons.map((r, i) => <li key={i}>{r}</li>)}
          </ul>
        )}
        {v.decided_by && v.decided_by !== "VERIFICATION_ENGINE" && (
          <p className="text-[11px] text-slate-500">
            Decided by auditor <strong>{v.decided_by}</strong> (engine decision: {v.engine_decision || DASH})
            {v.auditor_notes ? ` — “${v.auditor_notes}”` : ""}
          </p>
        )}
        {missingNow.length > 0 && (
          <p className="text-amber-800 bg-amber-50 border border-amber-200 rounded p-2">
            Missing evidence: {missingNow.join(", ")}. The plantation stays PENDING until it is submitted.
          </p>
        )}
      </section>

      {/* Project + evidence */}
      <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white border border-slate-200 rounded p-4">
          <h3 className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-2">Project</h3>
          <Row label="Farmer" value={plantation.farmer_name} />
          <Row label="Area" value={`${num(plantation.area_hectares, 4)} ha (${num(plantation.area_hectares * ACRES_PER_HA, 2)} ac)`} mono />
          <Row label="Location" value={`${num(plantation.latitude, 5)}, ${num(plantation.longitude, 5)}`} mono />
          <Row label="Boundary" value={plantation.boundary ? `Drawn polygon (${plantation.boundary.length} points)` : "Centre point + area"} />
          <Row label="Trees" value={plantation.tree_count} mono />
          <Row label="Species" value={plantation.tree_species} />
          <Row label="Age" value={`${num(plantation.plantation_age_years)} yr`} mono />
          <Row label="Status" value={plantation.status} mono />
        </div>

        <div className="bg-white border border-slate-200 rounded p-4 md:col-span-2">
          <h3 className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-2">Submitted evidence</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="h-40 rounded border border-slate-200 bg-slate-50 overflow-hidden flex items-center justify-center">
              {plantation.image_url ? (
                <img src={getImageUrl(plantation.image_url)} alt="Ground evidence" className="w-full h-full object-cover" />
              ) : (
                <div className="text-center text-slate-400">
                  <FileImage className="w-6 h-6 mx-auto mb-1" />
                  Ground photo not provided
                </div>
              )}
            </div>
            <div>
              <Row label="Boundary" value={v.evidence_status?.boundary} mono />
              <Row label="Ground photo" value={v.evidence_status?.ground_imagery} mono />
              <Row label="Soil carbon" value={v.evidence_status?.soil_carbon} mono />
              <Row label="Satellite NDVI" value={v.evidence_status?.satellite_ndvi} mono />
              <Row label="SOC submitted" value={plantation.soil_soc_pct ? `${plantation.soil_soc_pct}%` : DASH} mono />
              <Row label="Reported NDVI" value={plantation.ndvi_reported_value ?? DASH} mono />
            </div>
          </div>
        </div>
      </section>

      {/* Modalities */}
      <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <ModalityCard title="Satellite NDVI" weight="0.40" score={v.ndvi_score} contribution={v.ndvi_contribution} status={v.ndvi_status}>
          <Row label="Mean NDVI" value={num(ndvi, 3)} mono />
          <Row label="Min / Max" value={`${num(v.min_ndvi, 2)} / ${num(v.max_ndvi, 2)}`} mono />
          <Row label="Canopy ≥0.40" value={v.vegetation_coverage_pct == null ? DASH : `${num(v.vegetation_coverage_pct)}%`} mono />
          <Row label="Source" value={NDVI_SOURCE_LABEL[v.ndvi_provenance] || "Unavailable"} />
          <Row
            label="Cloud-free"
            value={v.evidence_snapshot?.ndvi_measurement?.clear_pixel_pct != null ? `${v.evidence_snapshot.ndvi_measurement.clear_pixel_pct}% of plot` : DASH}
            mono
          />
          <Row label="Acquired" value={v.acquisition_date} mono />
          {v.ndvi_provenance === "SENTINEL2_COMPUTED" && (
            <Row label="Scene" value={v.evidence_snapshot?.ndvi_measurement?.scene_id} mono />
          )}
          {!v.ndvi_provenance && v.evidence_snapshot?.ndvi_measurement?.unavailable_reason && (
            <p className="text-[11px] text-amber-800 bg-amber-50 border border-amber-200 rounded p-2 mt-2 break-words">
              Why unavailable: {v.evidence_snapshot.ndvi_measurement.unavailable_reason}
            </p>
          )}
        </ModalityCard>
        <ModalityCard title="Ground photo (CV)" weight="0.35" score={v.cv_score} contribution={v.cv_contribution} status={v.cv_detection_status}>
          <Row label="Predicted class" value={v.ai_predicted_class} mono />
          <Row label="Confidence" value={v.ai_confidence_pct == null ? DASH : `${num(v.ai_confidence_pct)}%`} mono />
          <Row label="Image quality" value={num(v.image_quality_score)} mono />
          <Row label="Model" value={v.ai_model_name ? `${v.ai_model_name} ${v.ai_model_version || ""}` : DASH} />
        </ModalityCard>
        <ModalityCard title="Soil organic carbon" weight="0.25" score={v.soc_score} contribution={v.soc_contribution} status={v.soc_status}>
          <Row label="SOC" value={v.soc_pct == null ? DASH : `${v.soc_pct}%`} mono />
          <Row label="Depth" value={plantation.soil_depth_cm ? `${plantation.soil_depth_cm} cm` : DASH} mono />
          <Row label="Soil type" value={plantation.soil_type} />
        </ModalityCard>
      </section>

      {/* Risk (only when assessed) */}
      {v.risk_level && (
        <section className={`rounded border p-4 ${v.risk_level === "HIGH" ? "border-rose-200 bg-rose-50" : v.risk_level === "MEDIUM" ? "border-amber-200 bg-amber-50" : "border-slate-200 bg-white"}`}>
          <div className="flex justify-between font-bold">
            <span className="uppercase tracking-wider text-[11px]">Fraud / risk check</span>
            <span className="font-mono">{v.risk_level} • {num(v.risk_score, 0)} / 100</span>
          </div>
          {v.risk_factors?.length ? (
            <ul className="list-disc pl-5 mt-2 space-y-1">{v.risk_factors.map((f, i) => <li key={i}>{f}</li>)}</ul>
          ) : (
            <p className="mt-1 text-slate-600">No risk factors triggered.</p>
          )}
        </section>
      )}

      {/* Carbon credit */}
      <section className="bg-white border border-slate-200 rounded p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h3 className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Carbon credit</h3>
          {credit ? (
            <p className="mt-1">
              <span className="font-mono font-bold">{credit.id}</span> • {credit.carbon_quantity_tco2e} tCO₂e • {credit.status}
              {" "}• chain: {credit.blockchain_status || "NOT_RECORDED"}
            </p>
          ) : (
            <p className="mt-1 text-slate-600">
              {v.decision === "APPROVED"
                ? "Approved — no credit has been issued yet."
                : "Not eligible. Credits are issued only after an APPROVED verification."}
            </p>
          )}
        </div>
        {credit ? (
          <button
            onClick={() => { setSelectedCreditId(credit.id); setCurrentView("credit_details"); }}
            className="px-3 py-2 border border-slate-300 rounded inline-flex items-center gap-1"
          >
            View credit <ArrowRight className="w-3.5 h-3.5" />
          </button>
        ) : v.decision === "APPROVED" && (isFarmer || user?.role === "ADMIN") ? (
          <button disabled={busy} onClick={() => runAction(() => api.generateCredits(plantationId))}
                  className="px-3 py-2 bg-[#1B3B2B] text-white rounded disabled:opacity-50">
            Issue credit
          </button>
        ) : null}
      </section>

      {/* Actions */}
      {(isFarmer || isAuditor) && (
        <section className="bg-white border border-slate-200 rounded p-4 space-y-3">
          <h3 className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Actions</h3>
          {evidenceLocked && <p className="text-slate-500">Evidence and decision are locked because a credit has been issued.</p>}
          <div className="flex flex-wrap gap-2">
            {isFarmer && !evidenceLocked && (
              <button onClick={() => setShowEvidence(true)} className="px-3 py-2 border border-slate-300 rounded inline-flex items-center gap-1">
                <Upload className="w-3.5 h-3.5" /> Submit / update evidence
              </button>
            )}
            {!evidenceLocked && (
              <button disabled={busy} onClick={runVerification}
                      className="px-3 py-2 bg-[#1B3B2B] text-white rounded inline-flex items-center gap-1 disabled:opacity-50">
                <RefreshCw className={`w-3.5 h-3.5 ${busy ? "animate-spin" : ""}`} /> Run verification
              </button>
            )}
          </div>

          {isAuditor && !evidenceLocked && isLatest && (
            <div className="border-t border-slate-100 pt-3 space-y-2">
              <p className="font-semibold flex items-center gap-1"><ShieldCheck className="w-4 h-4" /> Auditor decision</p>
              <textarea
                value={decisionNotes}
                onChange={(e) => setDecisionNotes(e.target.value)}
                placeholder="Notes (required when changing the engine's decision)"
                className="w-full border border-slate-200 rounded p-2 text-xs"
                rows={2}
              />
              <div className="flex flex-wrap gap-2">
                <button disabled={busy || !scored} onClick={() => decide("APPROVED")}
                        title={scored ? "" : "Approval needs all three modality scores"}
                        className="px-3 py-2 bg-[#1B3B2B] text-white rounded disabled:opacity-40">Approve</button>
                <button disabled={busy} onClick={() => decide("REVIEW")} className="px-3 py-2 border border-amber-300 text-amber-900 rounded">Keep in review</button>
                <button disabled={busy} onClick={() => decide("REJECTED")} className="px-3 py-2 border border-rose-300 text-rose-800 rounded">Reject</button>
              </div>
              {!scored && <p className="text-slate-500">Approval is disabled: this verification is not fully scored.</p>}
            </div>
          )}
        </section>
      )}

      {/* History */}
      {history.length > 0 && (
        <section className="bg-white border border-slate-200 rounded p-4">
          <button onClick={() => setShowHistory(!showHistory)} className="flex items-center gap-1 font-semibold">
            <History className="w-4 h-4" /> Verification history ({history.length})
          </button>
          {showHistory && (
            <table className="w-full mt-2 text-[11px]">
              <thead><tr className="text-left text-slate-400"><th>ID</th><th>Date</th><th>Decision</th><th>Score</th><th>NDVI source</th></tr></thead>
              <tbody>
                {history.map((h) => (
                  <tr key={h.id} className="border-t border-slate-100 font-mono">
                    <td>{h.id}</td><td>{fmtDate(h.verified_at)}</td><td>{h.decision}</td>
                    <td>{num(h.overall_score)}</td><td>{h.ndvi_provenance || DASH}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      )}

      {v.limitations_disclaimer && <p className="text-[10px] text-slate-400">{v.limitations_disclaimer}</p>}

      {showEvidence && (
        <EvidenceModal
          plantation={plantation}
          onClose={() => setShowEvidence(false)}
          onSaved={async () => { setShowEvidence(false); await runVerification(); }}
        />
      )}
    </div>
  );
}

function EvidenceModal({ plantation, onClose, onSaved }) {
  // Fields start from what the farmer already submitted — never from example values.
  const [file, setFile] = useState(null);
  const [soc, setSoc] = useState(plantation.soil_soc_pct ?? "");
  const [depth, setDepth] = useState(plantation.soil_depth_cm ?? "");
  const [soilType, setSoilType] = useState(plantation.soil_type ?? "");
  const [ndviValue, setNdviValue] = useState(plantation.ndvi_reported_value ?? "");
  const [ndviSource, setNdviSource] = useState(plantation.ndvi_reported_source ?? "");
  const [ndviDate, setNdviDate] = useState(plantation.ndvi_reported_date ?? "");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState(null);

  const submit = async (e) => {
    e.preventDefault();
    setSaving(true);
    setErr(null);
    try {
      const body = {};
      if (file) body.image_url = (await api.uploadImage(file)).image_url;
      if (soc !== "") body.soil_soc_pct = Number(soc);
      if (depth !== "") body.soil_depth_cm = Number(depth);
      if (soilType.trim()) body.soil_type = soilType.trim();
      const anyNdvi = ndviValue !== "" || ndviSource.trim() || ndviDate;
      if (anyNdvi) {
        if (ndviValue === "" || !ndviSource.trim() || !ndviDate) {
          throw new Error("Reported NDVI needs a value, its source and the acquisition date.");
        }
        Object.assign(body, { ndvi_reported_value: Number(ndviValue), ndvi_reported_source: ndviSource.trim(), ndvi_reported_date: ndviDate });
      }
      if (Object.keys(body).length === 0) throw new Error("Nothing to submit.");
      await api.updatePlantationEvidence(plantation.id, body);
      await onSaved();
    } catch (error) {
      setErr(error.message);
    } finally {
      setSaving(false);
    }
  };

  const input = "w-full border border-slate-200 rounded px-2 py-1.5 text-xs";
  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center p-4 z-50">
      <form onSubmit={submit} className="bg-white rounded-lg w-full max-w-lg p-5 space-y-3 text-xs max-h-[90vh] overflow-y-auto">
        <div className="flex justify-between items-center">
          <h3 className="font-bold text-sm">Submit evidence</h3>
          <button type="button" onClick={onClose}><X className="w-4 h-4" /></button>
        </div>
        <label className="block space-y-1">
          <span className="font-semibold">Ground photograph {plantation.image_url ? "(replace)" : ""}</span>
          <input type="file" accept="image/jpeg,image/png,image/webp,image/tiff" onChange={(e) => setFile(e.target.files[0] || null)} />
        </label>
        <div className="grid grid-cols-3 gap-2">
          <label className="space-y-1"><span>SOC %</span><input className={input} type="number" step="0.01" min="0.01" max="10" value={soc} onChange={(e) => setSoc(e.target.value)} placeholder="from soil test" /></label>
          <label className="space-y-1"><span>Depth cm</span><input className={input} type="number" min="1" max="300" value={depth} onChange={(e) => setDepth(e.target.value)} /></label>
          <label className="space-y-1"><span>Soil type</span><input className={input} value={soilType} onChange={(e) => setSoilType(e.target.value)} /></label>
        </div>
        <fieldset className="border border-slate-200 rounded p-2 space-y-2">
          <legend className="px-1 font-semibold">Reported NDVI (optional)</legend>
          <p className="text-slate-500">Only if you measured NDVI yourself (e.g. Copernicus Browser). Reported NDVI always requires auditor review.</p>
          <div className="grid grid-cols-3 gap-2">
            <input className={input} type="number" step="0.001" min="-1" max="1" placeholder="value" value={ndviValue} onChange={(e) => setNdviValue(e.target.value)} />
            <input className={input} placeholder="source" value={ndviSource} onChange={(e) => setNdviSource(e.target.value)} />
            <input className={input} type="date" value={ndviDate} onChange={(e) => setNdviDate(e.target.value)} />
          </div>
        </fieldset>
        {err && <p className="text-rose-700 bg-rose-50 border border-rose-200 rounded p-2">{err}</p>}
        <div className="flex justify-end gap-2">
          <button type="button" onClick={onClose} className="px-3 py-2 border border-slate-300 rounded">Cancel</button>
          <button disabled={saving} className="px-3 py-2 bg-[#1B3B2B] text-white rounded disabled:opacity-50">
            {saving ? "Saving…" : "Save and re-verify"}
          </button>
        </div>
      </form>
    </div>
  );
}
