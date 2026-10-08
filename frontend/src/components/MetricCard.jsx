import React from "react";

export default function MetricCard({ title, value, subtitle, icon: Icon, color = "slate", trend = null }) {
  return (
    <div className="bg-white rounded-lg border border-slate-200 p-4 relative">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-wider text-slate-500 mb-1">{title}</p>
          <h3 className="text-xl font-bold text-slate-900 tracking-tight font-mono">{value}</h3>
          {subtitle && (
            <p className="text-[11px] text-slate-500 mt-0.5">
              {subtitle}
            </p>
          )}
        </div>
        {Icon && (
          <div className="p-2 rounded bg-slate-50 text-slate-600 border border-slate-200/60">
            <Icon className="w-4 h-4 shrink-0" />
          </div>
        )}
      </div>
      {trend && (
        <div className="mt-2.5 pt-2.5 border-t border-slate-100 flex items-center justify-between text-[11px]">
          <span className="text-slate-400">{trend.label}</span>
          <span className="font-semibold text-slate-700">{trend.value}</span>
        </div>
      )}
    </div>
  );
}
