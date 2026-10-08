import React from "react";
import { useAuth } from "../context/AuthContext";
import { 
  LayoutDashboard, 
  Trees, 
  ShoppingBag, 
  FileText, 
  ShieldCheck, 
  
  Award,
  X,
  LogOut
} from "lucide-react";

export default function Sidebar({ currentView, setCurrentView, isOpen, onClose }) {
  const { user, role, logout } = useAuth();

  if (!user) return null;

  const isFarmer = role === "FARMER";
  const isBuyer = role === "BUYER";
  const isAdmin = role === "ADMIN" || role === "AUDITOR";

  const handleNav = (view) => {
    setCurrentView(view);
    if (onClose) onClose();
  };

  const navItemClass = (active) => `
    w-full flex items-center gap-2.5 px-3 py-2 rounded text-xs font-medium transition text-left
    ${active 
      ? "bg-slate-100 text-slate-900 font-semibold" 
      : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"}
  `;

  return (
    <>
      {/* Mobile Backdrop */}
      {isOpen && (
        <div 
          className="fixed inset-0 z-40 bg-slate-900/30 lg:hidden"
          onClick={onClose}
        />
      )}

      {/* Sidebar Container */}
      <aside 
        className={`fixed top-0 bottom-0 left-0 z-40 w-56 bg-white border-r border-slate-200 flex flex-col justify-between transition-transform duration-200 ease-in-out lg:translate-x-0 ${
          isOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div>
          {/* Top Brand / Context */}
          <div className="h-14 flex items-center justify-between px-4 border-b border-slate-100">
            <div>
              <span className="text-xs font-bold text-slate-900 tracking-tight block">Carbon Registry</span>
              <span className="text-[10px] text-slate-400 font-medium">
                {isFarmer ? "Farmer Portal" : isBuyer ? "ESG Portfolio" : "Auditor Console"}
              </span>
            </div>

            <button 
              onClick={onClose}
              className="lg:hidden text-slate-400 hover:text-slate-600 p-1 rounded"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Navigation Menu strictly following section 12 */}
          <div className="p-3 space-y-0.5">
            {/* FARMER: Dashboard, Plantations, Carbon Assets, Marketplace */}
            {isFarmer && (
              <>
                <button
                  onClick={() => handleNav("farmer_dashboard")}
                  className={navItemClass(currentView === "farmer_dashboard")}
                >
                  <LayoutDashboard className="w-4 h-4 text-slate-500" />
                  <span>Dashboard</span>
                </button>

                <button
                  onClick={() => handleNav("farmer_plantations")}
                  className={navItemClass(currentView === "farmer_plantations")}
                >
                  <Trees className="w-4 h-4 text-slate-500" />
                  <span>Plantations</span>
                </button>

                <button
                  onClick={() => handleNav("farmer_carbon_assets")}
                  className={navItemClass(currentView === "farmer_carbon_assets")}
                >
                  <Award className="w-4 h-4 text-slate-500" />
                  <span>Carbon Assets</span>
                </button>

                <button
                  onClick={() => handleNav("marketplace")}
                  className={navItemClass(currentView === "marketplace")}
                >
                  <ShoppingBag className="w-4 h-4 text-slate-500" />
                  <span>Marketplace</span>
                </button>
              </>
            )}

            {/* BUYER: Portfolio, Marketplace, Transactions */}
            {isBuyer && (
              <>
                <button
                  onClick={() => handleNav("buyer_dashboard")}
                  className={navItemClass(currentView === "buyer_dashboard")}
                >
                  <LayoutDashboard className="w-4 h-4 text-slate-500" />
                  <span>Portfolio</span>
                </button>

                <button
                  onClick={() => handleNav("marketplace")}
                  className={navItemClass(currentView === "marketplace" || currentView === "credit_details")}
                >
                  <ShoppingBag className="w-4 h-4 text-slate-500" />
                  <span>Marketplace</span>
                </button>

                <button
                  onClick={() => handleNav("transactions")}
                  className={navItemClass(currentView === "transactions")}
                >
                  <FileText className="w-4 h-4 text-slate-500" />
                  <span>Transactions</span>
                </button>
              </>
            )}

            {/* ADMIN / AUDITOR: Overview, Verification Queue, Marketplace, Logout */}
            {isAdmin && (
              <>
                <button
                  onClick={() => handleNav("admin_dashboard")}
                  className={navItemClass(currentView === "admin_dashboard")}
                >
                  <LayoutDashboard className="w-4 h-4 text-slate-500" />
                  <span>Overview</span>
                </button>

                <button
                  onClick={() => handleNav("auditor_queue")}
                  className={navItemClass(currentView === "auditor_queue")}
                >
                  <ShieldCheck className="w-4 h-4 text-slate-500" />
                  <span>Verification Queue</span>
                </button>

                <button
                  onClick={() => handleNav("marketplace")}
                  className={navItemClass(currentView === "marketplace")}
                >
                  <ShoppingBag className="w-4 h-4 text-slate-500" />
                  <span>Marketplace</span>
                </button>

                {role === "ADMIN" && (
                  <button
                    onClick={() => handleNav("transactions")}
                    className={navItemClass(currentView === "transactions")}
                  >
                    <FileText className="w-4 h-4 text-slate-500" />
                    <span>Audit Logs</span>
                  </button>
                )}
              </>
            )}
          </div>
        </div>

        {/* Bottom Profile and Logout */}
        <div className="p-3 border-t border-slate-100 bg-slate-50/60">
          <div className="flex items-center justify-between">
            <div className="min-w-0 pr-2">
              <p className="text-xs font-medium text-slate-900 truncate">{user.full_name}</p>
              <p className="text-[11px] text-slate-400 truncate">{user.organization || user.role}</p>
            </div>
            <button
              onClick={logout}
              className="p-1 text-slate-400 hover:text-rose-600 rounded transition"
              title="Sign out"
            >
              <LogOut className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}
