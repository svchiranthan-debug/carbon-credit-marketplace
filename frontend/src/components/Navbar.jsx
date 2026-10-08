import React from "react";
import { useAuth } from "../context/AuthContext";
import { 
  Menu, 
  LogOut,
  User,

} from "lucide-react";
import { getRoleDashboardView } from "../utils/roleRouting";

export default function Navbar({ setCurrentView, toggleSidebar, setPortalRole }) {
  const { user, isAuthenticated, role, logout } = useAuth();

  const handleBrandClick = () => {
    if (!isAuthenticated) {
      setCurrentView("landing");
    } else {
      setCurrentView(getRoleDashboardView(role));
    }
  };

  const handlePortalClick = (targetRole) => {
    if (setPortalRole) setPortalRole(targetRole);
    setCurrentView("login");
  };

  return (
    <nav className="bg-white border-b border-slate-200 sticky top-0 z-30">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-14 items-center">
          {/* Left: Mobile Toggle & Official Project Title */}
          <div className="flex items-center gap-3">
            {isAuthenticated && (
              <button
                onClick={toggleSidebar}
                className="lg:hidden p-1.5 text-slate-600 hover:text-slate-900 rounded hover:bg-slate-100"
                aria-label="Toggle navigation"
              >
                <Menu className="w-4 h-4" />
              </button>
            )}

            <button
              onClick={handleBrandClick}
              className="flex items-center gap-2.5 text-left focus:outline-none"
            >
              <div className="w-7 h-7 rounded bg-[#1B3B2B] text-white flex items-center justify-center font-bold text-xs tracking-wider">
                CC
              </div>
              <div className="flex flex-col">
                <span className="font-extrabold text-slate-900 text-xs sm:text-sm tracking-tight leading-tight uppercase">
                  Carbon Credit Marketplace
                </span>
                <span className="text-[10px] text-slate-500 font-semibold tracking-wider uppercase leading-none mt-0.5">
                  with Multi-Modal Verification
                </span>
              </div>
            </button>
          </div>

          {/* Right: Authenticated User Info / Public Navigation */}
          <div className="flex items-center gap-3">
            {!isAuthenticated ? (
              <div className="flex items-center gap-1.5 sm:gap-2">
                <button
                  onClick={() => setCurrentView("marketplace")}
                  className="hidden md:inline-block px-2.5 py-1 text-xs text-slate-600 hover:text-slate-900 font-medium"
                >
                  Marketplace
                </button>
                <button
                  onClick={() => handlePortalClick("FARMER")}
                  className="px-2.5 py-1 text-[11px] font-semibold text-slate-700 hover:text-[#1B3B2B] hover:bg-slate-50 rounded border border-slate-200 transition uppercase tracking-wider"
                >
                  Farmer Portal
                </button>
                <button
                  onClick={() => handlePortalClick("BUYER")}
                  className="px-2.5 py-1 text-[11px] font-semibold text-slate-700 hover:text-[#1B3B2B] hover:bg-slate-50 rounded border border-slate-200 transition uppercase tracking-wider"
                >
                  Buyer Portal
                </button>
                <button
                  onClick={() => handlePortalClick("AUDITOR")}
                  className="px-2.5 py-1 text-[11px] font-semibold text-slate-700 hover:text-[#1B3B2B] hover:bg-slate-50 rounded border border-slate-200 transition uppercase tracking-wider"
                >
                  Auditor Portal
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-3">
                {/* Actual Authenticated User Display */}
                <div className="flex items-center gap-2 text-xs">
                  <div className="w-6 h-6 rounded-full bg-slate-100 border border-slate-200 flex items-center justify-center text-slate-600">
                    <User className="w-3.5 h-3.5" />
                  </div>
                  <div className="flex flex-col text-left">
                    <span className="font-bold text-slate-900 text-xs leading-none">
                      {user?.full_name || "Authenticated User"}
                    </span>
                    <span className="text-[10px] text-slate-400 font-medium uppercase tracking-wider mt-0.5">
                      {role || "Member"}
                    </span>
                  </div>
                </div>

                {/* Logout Action */}
                <button
                  onClick={() => {
                    logout();
                    if (setPortalRole) setPortalRole(null);
                    setCurrentView("landing");
                  }}
                  className="inline-flex items-center gap-1 px-2.5 py-1 text-xs text-slate-500 hover:text-rose-700 hover:bg-rose-50 rounded border border-slate-200 transition font-medium"
                  title="Log out of account"
                >
                  <LogOut className="w-3.5 h-3.5" />
                  <span className="hidden sm:inline">Logout</span>
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </nav>
  );
}
