import React, { useState } from "react";
import { useAuth } from "../context/AuthContext";
import { Lock, Mail, AlertCircle, ArrowRight, ArrowLeft } from "lucide-react";
import { getRoleDashboardView } from "../utils/roleRouting";

export default function LoginPage({ setCurrentView, portalRole, setPortalRole }) {
  const { login, error: authError } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const portalTitle = 
    portalRole === "FARMER" ? "Farmer Portal Sign In" :
    portalRole === "BUYER" ? "Buyer Portal Sign In" :
    portalRole === "AUDITOR" ? "Auditor Portal Sign In" :
    "Sign In to Your Account";

  const portalDescription =
    portalRole === "FARMER" ? "Access your registered plantations, ground evidence, and carbon assets." :
    portalRole === "BUYER" ? "Access verified environmental credits and corporate ESG portfolio holdings." :
    portalRole === "AUDITOR" ? "Access plantation verification queue, review evidence, and audit logs." :
    "Carbon Credit Marketplace with Multi-Modal Verification";

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);

    if (!email.trim()) {
      setError("Please enter your email address.");
      return;
    }
    if (!password) {
      setError("Please enter your password.");
      return;
    }

    setLoading(true);
    try {
      // Role is determined strictly by the backend from the authenticated user record in database
      const user = await login(email.trim(), password);

      // Explicit role-based routing (Section 5: NEVER default unknown role to FARMER)
      const targetView = getRoleDashboardView(user.role);
      setCurrentView(targetView);
    } catch (err) {
      setError(err.message || "Invalid email or password.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-[85vh] flex items-center justify-center px-4 py-12">
      <div className="max-w-md w-full">
        {/* Back to Portal Selection */}
        <button
          onClick={() => {
            if (setPortalRole) setPortalRole(null);
            setCurrentView("landing");
          }}
          className="text-xs font-medium text-slate-500 hover:text-slate-900 mb-3 inline-flex items-center gap-1"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to Portal Selection</span>
        </button>

        <div className="bg-white rounded-xl border border-slate-200 p-8 shadow-xs">
          <div className="text-center mb-6">
            <div className="w-10 h-10 rounded-lg bg-[#1B3B2B] text-white flex items-center justify-center mx-auto mb-3 font-bold text-sm tracking-wider">
              CC
            </div>
            <h1 className="text-xl font-bold text-slate-900 tracking-tight uppercase">
              {portalTitle}
            </h1>
            <p className="text-xs text-slate-500 mt-1 max-w-xs mx-auto">
              {portalDescription}
            </p>
          </div>

          {(error || authError) && (
            <div className="mb-4 p-3 bg-rose-50 border border-rose-200 rounded-lg flex items-center gap-2 text-rose-700 text-xs">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{error || authError}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4 text-xs">
            <div>
              <label className="block font-semibold text-slate-700 mb-1">Email Address</label>
              <div className="relative">
                <Mail className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@organization.com"
                  className="w-full pl-9 pr-3 py-2 rounded-lg border border-slate-200 focus:outline-none focus:ring-1 focus:ring-slate-900 bg-white"
                />
              </div>
            </div>

            <div>
              <label className="block font-semibold text-slate-700 mb-1">Password</label>
              <div className="relative">
                <Lock className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full pl-9 pr-3 py-2 rounded-lg border border-slate-200 focus:outline-none focus:ring-1 focus:ring-slate-900 bg-white"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 bg-[#1B3B2B] hover:bg-[#142e21] text-white font-semibold rounded-lg shadow-xs transition flex items-center justify-center gap-1.5 disabled:opacity-50 mt-2 tracking-wide uppercase text-xs"
            >
              <span>{loading ? "Signing in..." : "Sign In"}</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </form>

          <div className="mt-6 pt-4 border-t border-slate-100 text-center text-xs text-slate-500">
            {portalRole === "AUDITOR" ? (
              <span>Auditor accounts are created by the platform administrator.</span>
            ) : (<>
            Don't have an account yet?{" "}
            <button
              onClick={() => {
                if (setPortalRole) setPortalRole(portalRole);
                setCurrentView("register");
              }}
              className="font-semibold text-[#1B3B2B] hover:underline"
            >
              Create an account
            </button>
            </>)}
          </div>
        </div>
      </div>
    </div>
  );
}
