import React from "react";
import { AlertTriangle } from "lucide-react";

/** Shown instead of empty/fallback data when the backend call failed. */
export default function LoadError({ message, onRetry }) {
  if (!message) return null;
  return (
    <div className="p-3 rounded border border-rose-200 bg-rose-50 text-rose-800 text-xs flex items-start gap-2">
      <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
      <span className="flex-1">{message}</span>
      {onRetry && (
        <button onClick={onRetry} className="underline font-semibold">
          Retry
        </button>
      )}
    </div>
  );
}
