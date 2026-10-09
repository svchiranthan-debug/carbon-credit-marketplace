import React, { forwardRef, useCallback, useEffect, useImperativeHandle, useRef, useState } from "react";
import { AlertCircle, Check, FileImage, Loader2, RotateCcw, X } from "lucide-react";
import api, { getImageUrl } from "../services/api";

// Must match backend limits (settings.MAX_PHOTOS_PER_PLANTATION / MAX_UPLOAD_BYTES); the server
// enforces them too and reports its own values from GET /plantations/{id}/photos.
const DEFAULT_MAX_PHOTOS = 10;
const DEFAULT_MAX_BYTES = 15 * 1024 * 1024;
const ACCEPTED_TYPES = ["image/jpeg", "image/png", "image/webp", "image/tiff"];

const GUIDANCE = [
  "A wide view of the whole plantation",
  "Tree canopy and vegetation",
  "Rows or spacing between trees",
  "Close-up of a few representative trees",
  "Ground or soil, where useful",
];

let nextKey = 1;

function fromServer(photo) {
  return { key: `p${photo.id}`, status: "uploaded", photo, preview: getImageUrl(photo.url), name: photo.original_name };
}

/**
 * Multi-photo ground evidence picker.
 *
 * - With a plantationId, photos upload immediately (one request per photo) and existing photos are listed.
 * - Without one (new registration), photos are queued; the parent calls ref.uploadAll(id) after creating
 *   the plantation, then passes the id so failed uploads can be retried.
 */
const PhotoEvidenceUploader = forwardRef(function PhotoEvidenceUploader({ plantationId, onCountChange, readOnly = false }, ref) {
  const [items, setItems] = useState([]);
  const [limits, setLimits] = useState({ max_photos: DEFAULT_MAX_PHOTOS, max_bytes: DEFAULT_MAX_BYTES });
  const [loadError, setLoadError] = useState(null);
  const itemsRef = useRef(items);
  useEffect(() => {
    itemsRef.current = items;
  }, [items]);

  const update = (key, patch) => setItems((cur) => cur.map((it) => (it.key === key ? { ...it, ...patch } : it)));

  const reload = useCallback(async (id) => {
    if (!id) return;
    try {
      const res = await api.listPhotos(id);
      setLimits({ max_photos: res.max_photos, max_bytes: res.max_bytes });
      setItems((cur) => [
        ...res.photos.map(fromServer),
        // keep local items that are not on the server (failed / rejected) so they can be retried or removed
        ...cur.filter((it) => it.status === "failed" || it.status === "rejected"),
      ]);
      setLoadError(null);
    } catch (err) {
      setLoadError(err.message || "Could not load photos.");
    }
  }, []);

  useEffect(() => {
    reload(plantationId);
  }, [plantationId, reload]);

  const usable = items.filter((it) => it.status === "uploaded" || it.status === "queued" || it.status === "uploading");
  useEffect(() => {
    onCountChange?.(usable.length);
  }, [usable.length, onCountChange]);

  // Object URLs for local previews are released when the component goes away.
  useEffect(() => () => itemsRef.current.forEach((it) => it.localUrl && URL.revokeObjectURL(it.localUrl)), []);

  const uploadItem = async (id, item) => {
    update(item.key, { status: "uploading", error: null });
    try {
      const photo = await api.uploadPhoto(id, item.file);
      if (item.localUrl) URL.revokeObjectURL(item.localUrl);
      update(item.key, { status: "uploaded", photo, preview: getImageUrl(photo.url), file: null, localUrl: null });
      return true;
    } catch (err) {
      update(item.key, { status: "failed", error: err.message || "Upload failed." });
      return false;
    }
  };

  useImperativeHandle(ref, () => ({
    async uploadAll(id) {
      let ok = 0;
      let failed = 0;
      for (const item of itemsRef.current.filter((it) => it.status === "queued" || it.status === "failed")) {
        // sequential: keeps the server's photo limit and duplicate checks predictable
        if (await uploadItem(id, item)) ok += 1;
        else failed += 1;
      }
      return { ok, failed };
    },
  }));

  const addFiles = async (fileList) => {
    const files = Array.from(fileList || []);
    if (!files.length) return;
    let room = limits.max_photos - usable.length;
    const added = [];
    for (const file of files) {
      const item = { key: `n${nextKey++}`, file, name: file.name };
      if (!ACCEPTED_TYPES.includes(file.type)) {
        added.push({ ...item, status: "rejected", error: "Not a JPEG, PNG, WEBP or TIFF photo." });
      } else if (file.size > limits.max_bytes) {
        added.push({ ...item, status: "rejected", error: `Larger than ${Math.round(limits.max_bytes / 1048576)} MB.` });
      } else if (items.some((it) => it.file && it.file.name === file.name && it.file.size === file.size && it.file.lastModified === file.lastModified)) {
        added.push({ ...item, status: "rejected", error: "This file is already selected." });
      } else if (room <= 0) {
        added.push({ ...item, status: "rejected", error: `Limit is ${limits.max_photos} photos.` });
      } else {
        room -= 1;
        const localUrl = URL.createObjectURL(file);
        added.push({ ...item, status: "queued", preview: localUrl, localUrl });
      }
    }
    setItems((cur) => [...cur, ...added]);
    if (plantationId) {
      for (const item of added.filter((it) => it.status === "queued")) {
        await uploadItem(plantationId, item);
      }
    }
  };

  const removeItem = async (item) => {
    if (item.status === "uploaded" && plantationId) {
      update(item.key, { status: "removing" });
      try {
        await api.removePhoto(plantationId, item.photo.id);
      } catch (err) {
        update(item.key, { status: "uploaded", error: err.message || "Could not remove photo." });
        return;
      }
    }
    if (item.localUrl) URL.revokeObjectURL(item.localUrl);
    setItems((cur) => cur.filter((it) => it.key !== item.key));
  };

  const uploadedCount = items.filter((it) => it.status === "uploaded").length;
  const queuedCount = items.filter((it) => it.status === "queued").length;

  return (
    <div className="space-y-3">
      {!readOnly && (
        <div className="rounded border border-slate-200 bg-slate-50 p-3 text-[11px] text-slate-600">
          <span className="font-semibold text-slate-800">Useful photos (up to {limits.max_photos}, at least one):</span>
          <ul className="list-disc pl-4 mt-1 grid sm:grid-cols-2 gap-x-4">
            {GUIDANCE.map((g) => <li key={g}>{g}</li>)}
          </ul>
          <p className="mt-1">Take genuine, sharp, well-lit photos of this plot. Blurry, duplicate or unrelated photos do not raise the score.</p>
        </div>
      )}

      {loadError && (
        <p className="text-[11px] text-red-700 bg-red-50 border border-red-200 rounded p-2 flex items-center gap-1">
          <AlertCircle className="w-3.5 h-3.5" /> {loadError}
        </p>
      )}

      <div className="flex items-center justify-between text-[11px]">
        <span className="font-semibold text-slate-800">
          {usable.length} / {limits.max_photos} photos
          {queuedCount > 0 && !plantationId && <span className="text-slate-500 font-normal"> · upload when you register</span>}
          {plantationId && uploadedCount > 0 && <span className="text-slate-500 font-normal"> · {uploadedCount} on server</span>}
        </span>
      </div>

      {items.length > 0 && (
        <ul className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
          {items.map((it) => (
            <li key={it.key} className="border border-slate-200 rounded overflow-hidden bg-white">
              <div className="relative h-24 bg-slate-100">
                {it.preview ? (
                  <img src={it.preview} alt={it.name || "Ground photo"} className="w-full h-full object-cover" />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-slate-400"><FileImage className="w-6 h-6" /></div>
                )}
                {!readOnly && it.status !== "uploading" && it.status !== "removing" && (
                  <button
                    type="button"
                    onClick={() => removeItem(it)}
                    className="absolute top-1 right-1 p-1 rounded bg-slate-900/75 text-white hover:bg-slate-900"
                    aria-label="Remove photo"
                    title="Remove photo"
                  >
                    <X className="w-3 h-3" />
                  </button>
                )}
              </div>
              <div className="p-1.5 text-[10px] space-y-0.5">
                <p className="truncate text-slate-700" title={it.name}>{it.name || "photo"}</p>
                <StatusLine item={it} onRetry={plantationId ? () => uploadItem(plantationId, it) : null} />
                {it.photo?.duplicate_of_id && (
                  <p className="text-amber-800">Near-duplicate of photo #{it.photo.duplicate_of_id}; counted once.</p>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}

      {!readOnly && usable.length < limits.max_photos && (
        <label className="border-2 border-dashed border-slate-200 hover:border-slate-400 rounded p-4 flex flex-col items-center justify-center cursor-pointer transition bg-slate-50/50 hover:bg-slate-50">
          <FileImage className="w-6 h-6 text-slate-400 mb-1" />
          <span className="font-semibold text-slate-800 text-xs uppercase tracking-wide">
            {items.length ? "Add more photos" : "Select ground photos"}
          </span>
          <span className="text-slate-400 text-[10px] mt-0.5">
            JPEG, PNG, WEBP or TIFF · up to {Math.round(limits.max_bytes / 1048576)} MB each · select several at once
          </span>
          <input
            type="file"
            multiple
            accept={ACCEPTED_TYPES.join(",")}
            onChange={(e) => {
              addFiles(e.target.files);
              e.target.value = "";
            }}
            className="hidden"
          />
        </label>
      )}
    </div>
  );
});

function StatusLine({ item, onRetry }) {
  switch (item.status) {
    case "queued":
      return <p className="text-slate-500">Ready to upload</p>;
    case "uploading":
      return <p className="text-slate-600 flex items-center gap-1"><Loader2 className="w-3 h-3 animate-spin" /> Uploading…</p>;
    case "removing":
      return <p className="text-slate-600 flex items-center gap-1"><Loader2 className="w-3 h-3 animate-spin" /> Removing…</p>;
    case "uploaded":
      return (
        <>
          <p className="text-emerald-800 flex items-center gap-1"><Check className="w-3 h-3" /> Uploaded</p>
          {item.error && <p className="text-red-700">{item.error}</p>}
        </>
      );
    case "failed":
      return (
        <div className="text-red-700 space-y-0.5">
          <p>Failed: {item.error}</p>
          {onRetry && (
            <button type="button" onClick={onRetry} className="inline-flex items-center gap-1 font-semibold underline">
              <RotateCcw className="w-3 h-3" /> Retry
            </button>
          )}
        </div>
      );
    case "rejected":
      return <p className="text-red-700">Not added: {item.error}</p>;
    default:
      return null;
  }
}

export default PhotoEvidenceUploader;
