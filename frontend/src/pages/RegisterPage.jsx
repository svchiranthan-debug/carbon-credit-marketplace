import React, { useState } from "react";
import { useAuth } from "../context/AuthContext";
import { Lock, Mail, User, AlertCircle, ArrowRight, ShoppingBag, Trees, CheckCircle } from "lucide-react";

const ROLE_OPTIONS = [
  {
    id: "FARMER",
    title: "Farmer",
    description: "Register plantations and submit evidence",
    icon: Trees,
  },
  {
    id: "BUYER",
    title: "Buyer",
    description: "Acquire verified carbon assets and manage retirement",
    icon: ShoppingBag,
  },
];
// Auditor accounts can approve plantations, so they are created by a platform admin, not by sign-up.

export default function RegisterPage({ setCurrentView, portalRole, setPortalRole }) {
  const { register } = useAuth();
  const [formData, setFormData] = useState({
    full_name: "",
    email: "",
    password: "",
    confirm_password: "",
    role: portalRole === "FARMER" || portalRole === "BUYER" ? portalRole : "", // Pre-select from portal card
    phone: "",
    organization: ""
  });
  const [registeredUser, setRegisteredUser] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);

    // Validation
    if (!formData.full_name.trim()) {
      setError("Please enter your full name.");
      return;
    }
    if (!formData.email.trim()) {
      setError("Please enter your email address.");
      return;
    }
    if (!formData.password) {
      setError("Please enter a password.");
      return;
    }
    if (formData.password.length < 6) {
      setError("Password must be at least 6 characters.");
      return;
    }
    if (formData.password !== formData.confirm_password) {
      setError("Passwords do not match.");
      return;
    }
    if (!formData.role) {
      setError("Please select your account type (Farmer, Buyer, or Auditor).");
      return;
    }

    setLoading(true);
    try {
      const payload = {
        full_name: formData.full_name.trim(),
        email: formData.email.trim(),
        password: formData.password,
        role: formData.role.toUpperCase(),
        phone: formData.phone.trim() || null,
        organization: formData.organization.trim() || null
      };
      const user = await register(payload);
      setRegisteredUser(user);
    } catch (err) {
      setError(err.message || "Registration failed. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  // Section 8: Registration successful -> "Account created successfully" -> Continue to Login
  if (registeredUser) {
    return (
      <div className="min-h-[85vh] flex items-center justify-center px-4 py-12">
        <div className="max-w-md w-full">
          <div className="bg-white rounded-xl border border-slate-200 p-8 shadow-xs text-center space-y-5">
            <div className="w-12 h-12 rounded-full bg-emerald-50 text-emerald-700 flex items-center justify-center mx-auto border border-emerald-200">
              <CheckCircle className="w-6 h-6" />
            </div>
            <div>
              <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest block">
                REGISTRATION CONFIRMED
              </span>
              <h1 className="text-xl font-bold text-slate-900 tracking-tight uppercase mt-1">
                Account Created Successfully
              </h1>
              <p className="text-xs text-slate-500 mt-1">
                Your <strong className="text-slate-800">{registeredUser.role}</strong> account has been registered with the platform.
              </p>
            </div>

            <div className="bg-slate-50 p-4 rounded border border-slate-200 text-left text-xs space-y-2">
              <div className="flex justify-between">
                <span className="text-slate-500">Full Name:</span>
                <span className="font-semibold text-slate-900">{registeredUser.full_name}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Email:</span>
                <span className="font-mono text-slate-800">{registeredUser.email}</span>
              </div>
              <div className="flex justify-between pt-1 border-t border-slate-200">
                <span className="text-slate-500 font-medium">Account Role:</span>
                <span className="font-bold text-[#1B3B2B] uppercase">{registeredUser.role}</span>
              </div>
            </div>

            <button
              onClick={() => {
                if (setPortalRole) setPortalRole(registeredUser.role);
                setCurrentView("login");
              }}
              className="w-full py-2.5 bg-[#1B3B2B] hover:bg-[#142e21] text-white font-semibold rounded-lg shadow-xs transition flex items-center justify-center gap-1.5 tracking-wide uppercase text-xs"
            >
              <span>Continue to Sign In</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-[85vh] flex items-center justify-center px-4 py-12">
      <div className="max-w-lg w-full">
        <div className="bg-white rounded-xl border border-slate-200 p-8 shadow-xs">
          <div className="text-center mb-6">
            <div className="w-10 h-10 rounded-lg bg-[#1B3B2B] text-white flex items-center justify-center mx-auto mb-3 font-bold text-sm tracking-wider">
              CC
            </div>
            <h1 className="text-xl font-bold text-slate-900 tracking-tight uppercase">
              Create Your Account
            </h1>
            <p className="text-xs text-slate-500 mt-1">
              Carbon Credit Marketplace with Multi-Modal Verification
            </p>
          </div>

          {error && (
            <div className="mb-4 p-3 bg-rose-50 border border-rose-200 rounded-lg flex items-center gap-2 text-rose-700 text-xs">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4 text-xs">
            {/* Full Name */}
            <div>
              <label className="block font-semibold text-slate-700 mb-1">
                Full Name <span className="text-rose-500">*</span>
              </label>
              <div className="relative">
                <User className="w-4 h-4 absolute left-3 top-2.5 text-slate-400" />
                <input
                  type="text"
                  required
                  value={formData.full_name}
                  onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
                  placeholder="Enter your full name"
                  className="w-full pl-9 pr-3 py-2 rounded-lg border border-slate-200 focus:outline-none focus:ring-1 focus:ring-slate-900 bg-white"
                />
              </div>
            </div>

            {/* Email */}
            <div>
              <label className="block font-semibold text-slate-700 mb-1">
                Email <span className="text-rose-500">*</span>
              </label>
              <div className="relative">
                <Mail className="w-4 h-4 absolute left-3 top-2.5 text-slate-400" />
                <input
                  type="email"
                  required
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  placeholder="name@organization.com"
                  className="w-full pl-9 pr-3 py-2 rounded-lg border border-slate-200 focus:outline-none focus:ring-1 focus:ring-slate-900 bg-white"
                />
              </div>
            </div>

            {/* Password & Confirm Password Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block font-semibold text-slate-700 mb-1">
                  Password <span className="text-rose-500">*</span>
                </label>
                <div className="relative">
                  <Lock className="w-4 h-4 absolute left-3 top-2.5 text-slate-400" />
                  <input
                    type="password"
                    required
                    value={formData.password}
                    onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                    placeholder="At least 6 characters"
                    className="w-full pl-9 pr-3 py-2 rounded-lg border border-slate-200 focus:outline-none focus:ring-1 focus:ring-slate-900 bg-white"
                  />
                </div>
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">
                  Confirm Password <span className="text-rose-500">*</span>
                </label>
                <div className="relative">
                  <Lock className="w-4 h-4 absolute left-3 top-2.5 text-slate-400" />
                  <input
                    type="password"
                    required
                    value={formData.confirm_password}
                    onChange={(e) => setFormData({ ...formData, confirm_password: e.target.value })}
                    placeholder="Repeat password"
                    className="w-full pl-9 pr-3 py-2 rounded-lg border border-slate-200 focus:outline-none focus:ring-1 focus:ring-slate-900 bg-white"
                  />
                </div>
              </div>
            </div>

            {/* ACCOUNT TYPE / ROLE SELECTION (Radio Cards) */}
            <div className="pt-2">
              <label className="block font-semibold text-slate-700 uppercase tracking-wider text-[11px] mb-2">
                Account Type <span className="text-rose-500">*</span>
              </label>

              <div className="space-y-2">
                {portalRole === "AUDITOR" && (
                  <p className="text-[11px] text-amber-800 bg-amber-50 border border-amber-200 rounded p-2">
                    Auditor accounts are created by the platform administrator. Ask your admin for an
                    auditor login, or register below as a farmer or buyer.
                  </p>
                )}
                {ROLE_OPTIONS.map((opt) => {
                  const Icon = opt.icon;
                  const isSelected = formData.role === opt.id;
                  return (
                    <div
                      key={opt.id}
                      onClick={() => setFormData({ ...formData, role: opt.id })}
                      className={`cursor-pointer rounded-lg border p-3 flex items-start gap-3 transition ${
                        isSelected
                          ? "border-[#1B3B2B] bg-emerald-50/40 ring-1 ring-[#1B3B2B]"
                          : "border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50/50"
                      }`}
                    >
                      {/* Radio dot */}
                      <div className="mt-0.5 shrink-0">
                        <div
                          className={`w-4 h-4 rounded-full border flex items-center justify-center transition ${
                            isSelected
                              ? "border-[#1B3B2B] bg-[#1B3B2B]"
                              : "border-slate-300 bg-white"
                          }`}
                        >
                          {isSelected && <div className="w-1.5 h-1.5 rounded-full bg-white" />}
                        </div>
                      </div>

                      {/* Icon */}
                      <div
                        className={`p-1.5 rounded shrink-0 ${
                          isSelected ? "bg-[#1B3B2B] text-white" : "bg-slate-100 text-slate-600"
                        }`}
                      >
                        <Icon className="w-4 h-4" />
                      </div>

                      {/* Content */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between">
                          <span className="font-bold text-slate-900 text-xs">{opt.title}</span>
                          {isSelected && (
                            <span className="text-[10px] uppercase font-bold text-[#1B3B2B] tracking-wider">
                              Selected
                            </span>
                          )}
                        </div>
                        <p className="text-[11px] text-slate-500 mt-0.5 leading-snug">
                          {opt.description}
                        </p>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Optional Organization / Phone */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
              <div>
                <label className="block font-medium text-slate-500 mb-1 text-[11px]">
                  Phone Number (Optional)
                </label>
                <input
                  type="text"
                  value={formData.phone}
                  onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                  placeholder="+91 98450 ..."
                  className="w-full px-3 py-1.5 rounded-lg border border-slate-200 focus:outline-none focus:ring-1 focus:ring-slate-900 bg-white text-xs"
                />
              </div>

              <div>
                <label className="block font-medium text-slate-500 mb-1 text-[11px]">
                  Organization (Optional)
                </label>
                <input
                  type="text"
                  value={formData.organization}
                  onChange={(e) => setFormData({ ...formData, organization: e.target.value })}
                  placeholder="e.g. Coorg Sustainable Alliance"
                  className="w-full px-3 py-1.5 rounded-lg border border-slate-200 focus:outline-none focus:ring-1 focus:ring-slate-900 bg-white text-xs"
                />
              </div>
            </div>

            {/* Submit Button */}
            <button
              type="submit"
              disabled={loading || !formData.role}
              className="w-full py-2.5 bg-[#1B3B2B] hover:bg-[#142e21] text-white font-semibold rounded-lg shadow-xs transition flex items-center justify-center gap-1.5 disabled:opacity-50 mt-4 tracking-wide uppercase text-xs"
            >
              <span>{loading ? "Creating Account..." : "Create Account"}</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </form>

          <div className="mt-6 pt-4 border-t border-slate-100 text-center text-xs text-slate-500">
            Already have an account?{" "}
            <button
              onClick={() => setCurrentView("login")}
              className="font-semibold text-[#1B3B2B] hover:underline"
            >
              Sign in here
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
