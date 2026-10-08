import React, { useState } from "react";
import api from "../services/api";

/** ADMIN only: create AUDITOR accounts (auditors cannot self-register). */
export default function CreateAuditorPanel() {
  const empty = { full_name: "", email: "", password: "", organization: "" };
  const [form, setForm] = useState(empty);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState(null);
  const [error, setError] = useState(null);

  const submit = async (e) => {
    e.preventDefault();
    setSaving(true);
    setMessage(null);
    setError(null);
    try {
      const created = await api.createUser({ ...form, role: "AUDITOR", organization: form.organization || null });
      setMessage(`Auditor account created for ${created.email}. Share the password with them securely.`);
      setForm(empty);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const input = "w-full border border-slate-200 rounded px-2 py-1.5 text-xs";
  return (
    <form onSubmit={submit} className="bg-white rounded-xl border border-slate-200 p-4 space-y-3 text-xs">
      <div>
        <h3 className="text-sm font-bold text-slate-900">Create auditor account</h3>
        <p className="text-[11px] text-slate-500">Auditors can approve plantations, so only an admin can create them.</p>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-2">
        <input className={input} placeholder="Full name" required value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
        <input className={input} type="email" placeholder="Email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
        <input className={input} type="password" placeholder="Initial password (min 8)" minLength={8} required value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
        <input className={input} placeholder="Organization (optional)" value={form.organization} onChange={(e) => setForm({ ...form, organization: e.target.value })} />
      </div>
      {message && <p className="text-emerald-800 bg-emerald-50 border border-emerald-200 rounded p-2">{message}</p>}
      {error && <p className="text-rose-800 bg-rose-50 border border-rose-200 rounded p-2">{error}</p>}
      <button disabled={saving} className="px-3 py-2 bg-[#1B3B2B] text-white rounded disabled:opacity-50">
        {saving ? "Creating…" : "Create auditor"}
      </button>
    </form>
  );
}
