import React, { useEffect, useState } from "react";
import { API_ORIGIN, TUNNEL_HEADERS } from "../services/api";

// Backend photos are fetched with the same headers as API calls and shown from a blob URL.
// A plain <img src> cannot send headers, so behind a tunnel such as ngrok's free plan it would
// receive the tunnel's HTML warning page instead of the photo. Other URLs (local previews,
// blob:/data: URLs, other hosts) are used as they are.
const cache = new Map(); // backend URL -> Promise<blob URL | null>

function load(url) {
  if (!cache.has(url)) {
    cache.set(
      url,
      fetch(url, { headers: TUNNEL_HEADERS })
        .then((res) => (res.ok ? res.blob() : null))
        .then((blob) => (blob && blob.type.startsWith("image/") ? URL.createObjectURL(blob) : null))
        .catch(() => null),
    );
  }
  return cache.get(url);
}

const isBackendUrl = (src) => typeof src === "string" && src.startsWith(`${API_ORIGIN}/`);

export default function BackendImage({ src, ...props }) {
  const [resolved, setResolved] = useState(() => (isBackendUrl(src) ? null : src));

  useEffect(() => {
    if (!isBackendUrl(src)) {
      setResolved(src);
      return undefined;
    }
    let cancelled = false;
    setResolved(null);
    load(src).then((blobUrl) => {
      if (cancelled) return;
      if (blobUrl) setResolved(blobUrl);
      else {
        cache.delete(src); // allow a retry later
        setResolved(src); // fall back to a plain load, so the caller's onError still fires
      }
    });
    return () => {
      cancelled = true;
    };
  }, [src]);

  if (!resolved) return <div className={props.className} aria-busy="true" />;
  return <img src={resolved} {...props} />;
}
