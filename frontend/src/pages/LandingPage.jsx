import React from "react";
import { useAuth } from "../context/AuthContext";
import { Trees, ShoppingBag, ShieldCheck, ArrowRight } from "lucide-react";
import { getRoleDashboardView } from "../utils/roleRouting";

export default function LandingPage({ setCurrentView, setPortalRole }) {
  const { user, isAuthenticated, role } = useAuth();

  const handlePortalClick = (targetRole) => {
    if (setPortalRole) {
      setPortalRole(targetRole);
    }
    
    // If the user is already authenticated with this exact role, route to their dashboard directly
    const current = (role || "").toUpperCase();
    // ADMIN uses the auditor portal
    if (isAuthenticated && (current === targetRole || (current === "ADMIN" && targetRole === "AUDITOR"))) {
      setCurrentView(getRoleDashboardView(role));
    } else {
      // Otherwise route to the portal's login page
      setCurrentView("login");
    }
  };

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 py-16 text-slate-800 space-y-12">
      {/* Title & Concise Description */}
      <div className="text-center space-y-4">
        <div className="space-y-1">
          <h1 className="text-2xl sm:text-4xl font-extrabold text-slate-900 tracking-tight leading-tight uppercase">
            Carbon Credit Marketplace
          </h1>
          <h2 className="text-lg sm:text-2xl font-bold text-slate-700 tracking-tight leading-snug uppercase">
            with Multi-Modal Verification
          </h2>
        </div>

        <p className="text-xs sm:text-sm text-slate-600 max-w-2xl mx-auto leading-relaxed">
          Decentralized verification platform for smallholder agroforestry carbon credits. 
          Ground photographs, soil carbon analysis, and satellite NDVI indices independently audit carbon sequestration before asset issuance.
        </p>
      </div>

      {/* Prominent Section: ACCESS PLATFORM (Section 1 & 9 Requirement) */}
      <div className="space-y-4">
        <div className="text-center">
          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest block">
            PORTAL SELECTION
          </span>
          <h3 className="text-base font-bold text-slate-900 uppercase tracking-wider mt-0.5">
            ACCESS PLATFORM
          </h3>
          <p className="text-xs text-slate-500 mt-0.5">
            Choose your portal to enter your dedicated workflow.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2">
          {/* FARMER PORTAL */}
          <div className="bg-white rounded-lg border border-slate-200 p-5 flex flex-col justify-between hover:border-slate-300 transition shadow-xs">
            <div className="space-y-3">
              <div className="w-9 h-9 rounded bg-[#1B3B2B] text-white flex items-center justify-center">
                <Trees className="w-5 h-5" />
              </div>
              <div>
                <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
                  PRODUCER / CUSTODIAN
                </span>
                <h4 className="text-sm font-bold text-slate-900 uppercase tracking-wider">
                  FARMER
                </h4>
                <p className="text-[11px] font-semibold text-[#1B3B2B] mt-0.5 uppercase tracking-wide">
                  REGISTER & VERIFY PLANTATIONS
                </p>
              </div>
              <p className="text-xs text-slate-500 leading-relaxed">
                Register plantations, submit evidence and manage carbon assets.
              </p>
            </div>

            <div className="pt-4 mt-2 border-t border-slate-100">
              <button
                onClick={() => handlePortalClick("FARMER")}
                className="w-full py-2 bg-[#1B3B2B] hover:bg-[#142e21] text-white rounded text-xs font-semibold uppercase tracking-wide transition flex items-center justify-center gap-1.5 shadow-xs"
              >
                <span>FARMER PORTAL</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          {/* BUYER PORTAL */}
          <div className="bg-white rounded-lg border border-slate-200 p-5 flex flex-col justify-between hover:border-slate-300 transition shadow-xs">
            <div className="space-y-3">
              <div className="w-9 h-9 rounded bg-slate-900 text-white flex items-center justify-center">
                <ShoppingBag className="w-5 h-5" />
              </div>
              <div>
                <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
                  CORPORATE ENTITY
                </span>
                <h4 className="text-sm font-bold text-slate-900 uppercase tracking-wider">
                  BUYER
                </h4>
                <p className="text-[11px] font-semibold text-slate-800 mt-0.5 uppercase tracking-wide">
                  ACQUIRE & RETIRE CARBON ASSETS
                </p>
              </div>
              <p className="text-xs text-slate-500 leading-relaxed">
                Explore verified carbon assets and manage your ESG portfolio.
              </p>
            </div>

            <div className="pt-4 mt-2 border-t border-slate-100">
              <button
                onClick={() => handlePortalClick("BUYER")}
                className="w-full py-2 bg-slate-900 hover:bg-slate-800 text-white rounded text-xs font-semibold uppercase tracking-wide transition flex items-center justify-center gap-1.5 shadow-xs"
              >
                <span>BUYER PORTAL</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          {/* AUDITOR PORTAL */}
          <div className="bg-white rounded-lg border border-slate-200 p-5 flex flex-col justify-between hover:border-slate-300 transition shadow-xs">
            <div className="space-y-3">
              <div className="w-9 h-9 rounded bg-slate-800 text-white flex items-center justify-center">
                <ShieldCheck className="w-5 h-5" />
              </div>
              <div>
                <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
                  INDEPENDENT AUDIT
                </span>
                <h4 className="text-sm font-bold text-slate-900 uppercase tracking-wider">
                  AUDITOR
                </h4>
                <p className="text-[11px] font-semibold text-slate-800 mt-0.5 uppercase tracking-wide">
                  REVIEW VERIFICATION EVIDENCE
                </p>
              </div>
              <p className="text-xs text-slate-500 leading-relaxed">
                Review plantation evidence and verification requests.
              </p>
            </div>

            <div className="pt-4 mt-2 border-t border-slate-100">
              <button
                onClick={() => handlePortalClick("AUDITOR")}
                className="w-full py-2 bg-slate-800 hover:bg-slate-700 text-white rounded text-xs font-semibold uppercase tracking-wide transition flex items-center justify-center gap-1.5 shadow-xs"
              >
                <span>AUDITOR PORTAL</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Clean Workflow Summary */}
      <div className="pt-4 space-y-3">
        <h4 className="text-xs font-bold text-slate-900 uppercase tracking-wider text-center">
          Verification Pipeline
        </h4>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 text-left">
          <div className="bg-white p-3.5 rounded border border-slate-200">
            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">01 / Boundary</span>
            <h5 className="font-bold text-slate-900 text-xs mt-1">Satellite Mapping</h5>
            <p className="text-slate-500 text-[11px] mt-0.5 leading-snug">
              Address geocoding and polygon boundary drawing on satellite imagery.
            </p>
          </div>

          <div className="bg-white p-3.5 rounded border border-slate-200">
            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">02 / Evidence</span>
            <h5 className="font-bold text-slate-900 text-xs mt-1">Ground & Soil Data</h5>
            <p className="text-slate-500 text-[11px] mt-0.5 leading-snug">
              Ground-level canopy photography and Soil Organic Carbon measurements.
            </p>
          </div>

          <div className="bg-white p-3.5 rounded border border-slate-200">
            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">03 / Multi-Modal</span>
            <h5 className="font-bold text-slate-900 text-xs mt-1">Composite Audit</h5>
            <p className="text-slate-500 text-[11px] mt-0.5 leading-snug">
              Score = 0.40(NDVI) + 0.35(CV) + 0.25(SOC) with strict evidence completeness.
            </p>
          </div>

          <div className="bg-white p-3.5 rounded border border-slate-200">
            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">04 / Lifecycle</span>
            <h5 className="font-bold text-slate-900 text-xs mt-1">Registry Provenance</h5>
            <p className="text-slate-500 text-[11px] mt-0.5 leading-snug">
              Issued on blockchain registry for corporate acquisition and permanent retirement.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
