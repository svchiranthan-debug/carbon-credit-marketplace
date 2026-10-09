import React, { useCallback, useEffect, useState } from "react";
import { AlertTriangle, ChevronLeft, ChevronRight, FileImage, X } from "lucide-react";
import api, { getImageUrl } from "../services/api";

const DASH = "—";
const CLASS_LABEL = {
  plantation: "Plantation / tree canopy",
  non_plantation: "Non-plantation",
  unclear_evidence: "Unclear evidence",
};

function fmt(value) {
  if (!value) return DASH;
  const d = new Date(value.endsWith?.("Z") || value.includes?.("+") ? value : `${value}Z`);
  return Number.isNaN(d.getTime()) ? String(value) : d.toLocaleString();
}

/** Warnings for one photo. Model output is a prediction, never presented as a verified fact. */
function photoWarnings(photo, entry, lowPct) {
  const w = [];
  if (photo.validation_status !== "VALID") w.push(`Invalid: ${photo.validation_error || photo.validation_status}`);
  if (photo.classification_error) w.push(`Not classified: ${photo.classification_error}`);
  if (photo.duplicate_of_id) w.push(`Near-duplicate of photo #${photo.duplicate_of_id} (counted once)`);
  if (photo.confidence_pct != null && photo.confidence_pct < lowPct) w.push(`Low confidence (< ${lowPct}%)`);
  if (photo.predicted_class === "non_plantation") w.push("Classified as non-plantation");
  if (photo.predicted_class === "unclear_evidence") w.push("Classified as unclear (blur, dark or obstructed)");
  if (entry && !entry.used_in_score && photo.validation_status === "VALID" && !photo.duplicate_of_id) {
    w.push("Not used in the last score");
  }
  return w;
}

/**
 * All ground photos of a plantation with per-photo classifier results, warnings and a
 * full-size viewer. ``verification`` (optional) adds the aggregate CV result and which photos
 * were used in that verification's score.
 */
export default function PhotoGallery({ plantationId, verification, refreshKey }) {
  const [photos, setPhotos] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(null); // index in photos

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api.listPhotos(plantationId)
      .then((res) => { if (!cancelled) { setPhotos(res.photos || []); setError(null); } })
      .catch((err) => { if (!cancelled) setError(err.message || "Could not load photos."); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [plantationId, refreshKey]);

  const agg = verification?.evidence_snapshot?.cv_measurement?.aggregation || null;
  const lowPct = agg?.low_confidence_threshold_pct ?? 60;
  const entries = Object.fromEntries((verification?.evidence_snapshot?.photos || []).map((e) => [e.photo_id, e]));

  const step = useCallback((d) => setOpen((i) => (i === null ? i : (i + d + photos.length) % photos.length)), [photos.length]);
  useEffect(() => {
    if (open === null) return undefined;
    const onKey = (e) => {
      if (e.key === "ArrowRight") step(1);
      else if (e.key === "ArrowLeft") step(-1);
      else if (e.key === "Escape") setOpen(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, step]);

  if (loading) return <p className="text-slate-500 text-[11px]">Loading photos…</p>;
  if (error) return <p className="text-rose-700 bg-rose-50 border border-rose-200 rounded p-2 text-[11px]">{error}</p>;
  if (!photos.length) {
    return (
      <div className="h-32 rounded border border-slate-200 bg-slate-50 flex items-center justify-center text-center text-slate-400">
        <div><FileImage className="w-6 h-6 mx-auto mb-1" />Ground photos not provided</div>
      </div>
    );
  }

  const current = open !== null ? photos[open] : null;

  return (
    <div className="space-y-2">
      {agg && (
        <div className={`text-[11px] rounded border p-2 ${agg.flags?.length ? "border-amber-200 bg-amber-50 text-amber-900" : "border-slate-200 bg-slate-50 text-slate-700"}`}>
          <strong>Photo score:</strong> {verification.cv_score ?? DASH} ({agg.method}; {agg.photos_scored} of {agg.photos_submitted} photos scored
          {agg.duplicates ? `, ${agg.duplicates} duplicate${agg.duplicates > 1 ? "s" : ""} ignored` : ""}
          {agg.per_photo_scores?.length ? `; per-photo scores ${agg.per_photo_scores.join(", ")}` : ""})
          {agg.flags?.includes("CONFLICTING") && <p className="font-semibold mt-0.5">⚠ Photos disagree: some show plantation, some do not.</p>}
          {agg.flags?.includes("LOW_CONFIDENCE") && <p className="font-semibold mt-0.5">⚠ Classifier confidence is low for most photos.</p>}
        </div>
      )}

      <ul className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
        {photos.map((p, i) => {
          const warnings = photoWarnings(p, entries[p.id], lowPct);
          return (
            <li key={p.id}>
              <button type="button" onClick={() => setOpen(i)}
                      className={`w-full text-left border rounded overflow-hidden bg-white hover:border-slate-400 ${warnings.length ? "border-amber-300" : "border-slate-200"}`}>
                <div className="h-24 bg-slate-100">
                  <img src={getImageUrl(p.url)} alt={`Ground photo ${i + 1}`} className="w-full h-full object-cover" loading="lazy" />
                </div>
                <div className="p-1.5 text-[10px] space-y-0.5">
                  <p className="font-semibold text-slate-800">#{p.id} · {p.predicted_class ? CLASS_LABEL[p.predicted_class] : "not classified yet"}</p>
                  <p className="text-slate-500">{p.confidence_pct != null ? `${p.confidence_pct}% confidence · score ${p.cv_score}` : DASH}</p>
                  {warnings.length > 0 && (
                    <p className="text-amber-800 flex items-start gap-1"><AlertTriangle className="w-3 h-3 shrink-0 mt-px" />{warnings[0]}{warnings.length > 1 ? ` (+${warnings.length - 1})` : ""}</p>
                  )}
                </div>
              </button>
            </li>
          );
        })}
      </ul>
      <p className="text-[10px] text-slate-400">Classes and confidences are model predictions, not verified facts.</p>

      {current && (
        <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-2 sm:p-6" role="dialog" aria-modal="true"
             onClick={(e) => e.target === e.currentTarget && setOpen(null)}>
          <div className="bg-white rounded-lg w-full max-w-5xl max-h-[95vh] overflow-y-auto grid md:grid-cols-3">
            <div className="relative md:col-span-2 bg-black flex items-center justify-center min-h-[40vh]">
              <img src={getImageUrl(current.url)} alt={`Ground photo #${current.id}`} className="max-h-[80vh] w-full object-contain" />
              {photos.length > 1 && (
                <>
                  <button type="button" onClick={() => step(-1)} aria-label="Previous photo"
                          className="absolute left-2 top-1/2 -translate-y-1/2 p-2 rounded-full bg-white/80 hover:bg-white"><ChevronLeft className="w-5 h-5" /></button>
                  <button type="button" onClick={() => step(1)} aria-label="Next photo"
                          className="absolute right-2 top-1/2 -translate-y-1/2 p-2 rounded-full bg-white/80 hover:bg-white"><ChevronRight className="w-5 h-5" /></button>
                </>
              )}
            </div>
            <div className="p-4 text-[11px] space-y-2">
              <div className="flex justify-between items-center">
                <h4 className="font-bold text-sm">Photo #{current.id} <span className="text-slate-400 font-normal">({open + 1} of {photos.length})</span></h4>
                <button type="button" onClick={() => setOpen(null)} aria-label="Close"><X className="w-4 h-4" /></button>
              </div>
              <Detail label="Classifier prediction" value={current.predicted_class ? CLASS_LABEL[current.predicted_class] : DASH} />
              <Detail label="Confidence" value={current.confidence_pct != null ? `${current.confidence_pct}%` : DASH} />
              <Detail label="Photo score" value={current.cv_score ?? DASH} />
              {current.class_probabilities && (
                <Detail label="All classes" value={Object.entries(current.class_probabilities).map(([k, v]) => `${CLASS_LABEL[k] || k} ${v}%`).join(" · ")} />
              )}
              <Detail label="Used in last score" value={entries[current.id] ? (entries[current.id].used_in_score ? "Yes" : "No") : DASH} />
              <Detail label="Uploaded" value={fmt(current.uploaded_at)} />
              <Detail label="Taken (EXIF, unverified)" value={current.exif_capture_time || DASH} />
              <Detail label="Camera (EXIF)" value={current.exif_camera || DASH} />
              <Detail label="GPS (EXIF, unverified)" value={current.exif_gps ? `${current.exif_gps.lat}, ${current.exif_gps.lon}` : DASH} />
              <Detail label="File" value={`${current.image_format || DASH} ${current.width || ""}×${current.height || ""}, ${current.size_bytes ? Math.round(current.size_bytes / 1024) + " KB" : DASH}`} />
              <Detail label="Original name" value={current.original_name || DASH} />
              <Detail label="SHA-256" value={current.sha256 ? `${current.sha256.slice(0, 16)}…` : DASH} />
              {photoWarnings(current, entries[current.id], lowPct).map((w) => (
                <p key={w} className="text-amber-900 bg-amber-50 border border-amber-200 rounded p-1.5 flex gap-1"><AlertTriangle className="w-3.5 h-3.5 shrink-0" />{w}</p>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Detail({ label, value }) {
  return (
    <div className="flex justify-between gap-3 border-b border-slate-100 pb-1">
      <span className="text-slate-500">{label}</span>
      <span className="text-right text-slate-900 break-all">{value}</span>
    </div>
  );
}
