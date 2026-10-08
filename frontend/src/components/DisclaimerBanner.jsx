import React, { useState } from "react";
import { Info, X, ShieldCheck } from "lucide-react";

export default function DisclaimerBanner() {
  const [showModal, setShowModal] = useState(false);

  return (
    <>
      <div className="bg-slate-900 text-slate-200 text-xs px-4 py-1.5 flex items-center justify-between border-b border-slate-800">
        <div className="flex items-center gap-2 overflow-hidden text-[11px]">
          <span className="bg-slate-800 text-slate-300 font-semibold text-[10px] uppercase tracking-wider px-1.5 py-0.5 rounded border border-slate-700">
            Prototype
          </span>
          <p className="truncate text-slate-300">
            Verification Model: <span className="font-mono text-slate-200">0.40(NDVI) + 0.35(CV) + 0.25(SOC)</span> • Multi-Modal Verification Protocol
          </p>
        </div>
        <button
          onClick={() => setShowModal(true)}
          className="flex items-center gap-1 text-slate-400 hover:text-white font-medium text-[11px] shrink-0 ml-4 transition"
        >
          <Info className="w-3 h-3" />
          <span>Methodology</span>
        </button>
      </div>

      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4">
          <div className="bg-white rounded-xl max-w-xl w-full p-6 shadow-xl border border-slate-200 relative max-h-[90vh] overflow-y-auto">
            <button
              onClick={() => setShowModal(false)}
              className="absolute top-4 right-4 text-slate-400 hover:text-slate-600 p-1 rounded-md"
            >
              <X className="w-5 h-5" />
            </button>

            <div className="flex items-center gap-3 mb-4">
              <div className="p-2.5 bg-forest-50 text-forest-800 rounded-lg border border-forest-200">
                <ShieldCheck className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-base font-bold text-slate-900">Verification & Carbon Estimation Model</h3>
                <p className="text-xs text-slate-500">Academic Project Architecture Specification</p>
              </div>
            </div>

            <div className="space-y-4 text-xs text-slate-600">
              <div className="p-3.5 bg-slate-50 rounded-lg border border-slate-200">
                <h4 className="font-semibold text-slate-900 text-sm mb-1.5">Verification Formula</h4>
                <div className="font-mono bg-white p-2.5 rounded border border-slate-200 text-forest-800 text-xs font-semibold mb-2">
                  Score = (0.40 × Satellite NDVI) + (0.35 × Photo CV) + (0.25 × Soil Organic Carbon)
                </div>
                <div className="grid grid-cols-3 gap-2 text-center pt-1">
                  <div className="p-2 bg-emerald-50 rounded border border-emerald-200">
                    <span className="font-bold text-emerald-900 text-sm">≥ 75.0</span>
                    <p className="text-[11px] text-emerald-800 font-medium">VERIFIED</p>
                  </div>
                  <div className="p-2 bg-amber-50 rounded border border-amber-200">
                    <span className="font-bold text-amber-900 text-sm">55.0 - 74.9</span>
                    <p className="text-[11px] text-amber-800 font-medium">UNDER REVIEW</p>
                  </div>
                  <div className="p-2 bg-rose-50 rounded border border-rose-200">
                    <span className="font-bold text-rose-900 text-sm">&lt; 55.0</span>
                    <p className="text-[11px] text-rose-800 font-medium">NOT VERIFIED</p>
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-3 gap-2.5">
                <div className="p-2.5 bg-slate-50 rounded-lg border border-slate-200">
                  <span className="font-bold text-slate-900 block mb-0.5">🛰️ Satellite (40%)</span>
                  <p className="text-[11px] text-slate-600">NDVI vegetation health & density analysis.</p>
                </div>
                <div className="p-2.5 bg-slate-50 rounded-lg border border-slate-200">
                  <span className="font-bold text-slate-900 block mb-0.5">📷 Ground Photo (35%)</span>
                  <p className="text-[11px] text-slate-600">Canopy greenness & tree coverage.</p>
                </div>
                <div className="p-2.5 bg-slate-50 rounded-lg border border-slate-200">
                  <span className="font-bold text-slate-900 block mb-0.5">🌱 Soil SOC (25%)</span>
                  <p className="text-[11px] text-slate-600">Soil Organic Carbon retention tier.</p>
                </div>
              </div>

              <div className="p-3 bg-forest-50/70 rounded-lg border border-forest-200 text-slate-700">
                <h4 className="font-semibold text-forest-900 text-xs mb-1">Carbon Calculation (tCO₂e)</h4>
                <p className="text-[11px] text-slate-600 leading-relaxed font-mono">
                  Carbon = Trees × 0.05 tCO₂e/tree/year × Species Factor × Practice Factor.
                  1 Credit = 1 Metric Ton CO₂e sequestered.
                </p>
              </div>

              <div className="p-2.5 bg-amber-50 rounded-lg border border-amber-200 text-amber-900 text-[11px]">
                <strong>Academic Prototype Notice:</strong> Demonstrates multi-modal verification logic for smallholder agroforestry plots. Prototype calculation — not a certified commercial registry certificate.
              </div>
            </div>

            <div className="mt-5 flex justify-end">
              <button
                onClick={() => setShowModal(false)}
                className="px-4 py-2 bg-slate-900 text-white rounded-lg text-xs font-semibold hover:bg-slate-800"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
