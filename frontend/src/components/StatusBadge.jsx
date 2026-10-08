import React from "react";
import { CheckCircle, Clock, AlertTriangle, XCircle, ShieldCheck, Lock } from "lucide-react";

export default function StatusBadge({ status, size = "md" }) {
  const norm = (status || "").toUpperCase();

  const configs = {
    APPROVED: {
      bg: "bg-forest-50 text-forest-900 border-forest-200",
      icon: CheckCircle,
      label: "VERIFIED",
    },
    VERIFIED: {
      bg: "bg-forest-50 text-forest-900 border-forest-200",
      icon: ShieldCheck,
      label: "VERIFIED",
    },
    AVAILABLE: {
      bg: "bg-forest-50 text-forest-900 border-forest-200",
      icon: CheckCircle,
      label: "AVAILABLE",
    },
    ACQUIRED: {
      bg: "bg-slate-100 text-slate-800 border-slate-200",
      icon: CheckCircle,
      label: "ACQUIRED",
    },
    RETIRED: {
      bg: "bg-slate-100 text-slate-700 border-slate-300",
      icon: Lock,
      label: "RETIRED",
    },
    REVIEW: {
      bg: "bg-amber-50 text-amber-900 border-amber-200",
      icon: AlertTriangle,
      label: "UNDER REVIEW",
    },
    PENDING: {
      bg: "bg-slate-100 text-slate-700 border-slate-200",
      icon: Clock,
      label: "PENDING",
    },
    SUBMITTED: {
      bg: "bg-slate-100 text-slate-700 border-slate-200",
      icon: Clock,
      label: "SUBMITTED",
    },
    REJECTED: {
      bg: "bg-rose-50 text-rose-800 border-rose-200",
      icon: XCircle,
      label: "NOT VERIFIED",
    },
    SOLD: {
      bg: "bg-slate-100 text-slate-700 border-slate-200",
      icon: CheckCircle,
      label: "ACQUIRED",
    },
    COMPLETED: {
      bg: "bg-forest-50 text-forest-900 border-forest-200",
      icon: CheckCircle,
      label: "COMPLETED",
    },
    DRAFT: {
      bg: "bg-slate-100 text-slate-600 border-slate-200",
      icon: Clock,
      label: "DRAFT",
    }
  };

  const config = configs[norm] || {
    bg: "bg-slate-100 text-slate-700 border-slate-200",
    icon: Clock,
    label: norm,
  };

  const IconComponent = config.icon;
  const isSmall = size === "sm";

  return (
    <span
      className={`inline-flex items-center gap-1 font-medium border rounded ${config.bg} ${
        isSmall ? "px-1.5 py-0.5 text-[11px]" : "px-2 py-0.5 text-xs"
      }`}
    >
      <IconComponent className={isSmall ? "w-3 h-3 shrink-0" : "w-3.5 h-3.5 shrink-0"} />
      <span className="tracking-wide">{config.label}</span>
    </span>
  );
}
