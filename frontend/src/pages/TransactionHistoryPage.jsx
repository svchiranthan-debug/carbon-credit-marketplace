import React, { useState, useEffect } from "react";
import { useAuth } from "../context/AuthContext";
import api from "../services/api";
import StatusBadge from "../components/StatusBadge";
import LoadError from "../components/LoadError";
import { 
  
  Search, 
  
  FileText, 
  
  RefreshCw,
  
  
  X
} from "lucide-react";

export default function TransactionHistoryPage({ setCurrentView, setSelectedCreditId }) {
  const { user } = useAuth();
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedTx, setSelectedTx] = useState(null);

  const fetchTransactions = async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const data = await api.listTransactions();
      setTransactions(data || []);
    } catch (err) {
      setLoadError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTransactions();
  }, []);

  const filtered = transactions.filter(t => 
    t.id.toLowerCase().includes(searchTerm.toLowerCase()) ||
    t.credit_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
    (t.plantation_name && t.plantation_name.toLowerCase().includes(searchTerm.toLowerCase())) ||
    (t.buyer_name && t.buyer_name.toLowerCase().includes(searchTerm.toLowerCase())) ||
    (t.seller_name && t.seller_name.toLowerCase().includes(searchTerm.toLowerCase()))
  );

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6 text-xs">
      <LoadError message={loadError} onRetry={fetchTransactions} />
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-slate-200">
        <div>
          <span className="text-xs font-semibold uppercase tracking-wider text-forest-800">Financial Ledger</span>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight mt-0.5">
            Transaction Ledger
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Verified record of carbon credit purchases and custodian settlements.
          </p>
        </div>

        <button
          onClick={fetchTransactions}
          className="p-2 border border-slate-200 hover:bg-slate-50 rounded-lg text-slate-600 flex items-center gap-1.5 self-start sm:self-auto"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin text-forest-800" : ""}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Search Bar */}
      <div className="bg-white p-3.5 rounded-xl border border-slate-200">
        <div className="relative">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
          <input
            type="text"
            placeholder="Search by Transaction ID, Credit ID, Buyer, or Farmer..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-9 pr-3 py-2 rounded-lg border border-slate-200 focus:outline-none focus:ring-1 focus:ring-forest-700 bg-white"
          />
        </div>
      </div>

      {/* Transactions Table */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        {loading ? (
          <div className="py-12 text-center text-slate-400">Loading ledger records...</div>
        ) : filtered.length === 0 ? (
          <div className="py-12 text-center text-slate-500">
            <FileText className="w-8 h-8 text-slate-300 mx-auto mb-2" />
            <p className="font-semibold text-slate-700">No transactions found.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200/80 text-slate-500 font-semibold">
                  <th className="py-3 px-4">Transaction ID</th>
                  <th className="py-3 px-4">Credit ID</th>
                  <th className="py-3 px-4">Buyer</th>
                  <th className="py-3 px-4">Farmer / Custodian</th>
                  <th className="py-3 px-4">Carbon Volume</th>
                  <th className="py-3 px-4">Total Amount</th>
                  <th className="py-3 px-4">Date</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4 text-right">Receipt</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700">
                {filtered.map((tx) => (
                  <tr key={tx.id} className="hover:bg-slate-50 transition">
                    <td className="py-3.5 px-4 font-mono font-semibold text-slate-900">
                      {tx.id}
                    </td>
                    <td className="py-3.5 px-4 font-mono text-slate-600">
                      {tx.credit_id}
                    </td>
                    <td className="py-3.5 px-4 font-medium text-slate-800">
                      {tx.buyer_name || "Corporate Buyer"}
                    </td>
                    <td className="py-3.5 px-4 text-slate-600">
                      {tx.seller_name || "Farmer Custodian"}
                    </td>
                    <td className="py-3.5 px-4 font-mono font-medium text-slate-900">
                      {tx.quantity_tco2e} tCO₂e
                    </td>
                    <td className="py-3.5 px-4 font-mono font-bold text-slate-900">
                      ₹{tx.total_amount.toLocaleString()}
                    </td>
                    <td className="py-3.5 px-4 text-slate-500">
                      {new Date(tx.timestamp).toLocaleDateString()}
                    </td>
                    <td className="py-3.5 px-4">
                      <StatusBadge status={tx.status} size="sm" />
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      <button
                        onClick={() => setSelectedTx(tx)}
                        className="px-2.5 py-1 border border-slate-200 rounded hover:bg-slate-100 font-medium text-slate-700"
                      >
                        Receipt
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Transaction Receipt Modal */}
      {selectedTx && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4">
          <div className="bg-white rounded-xl max-w-md w-full p-6 shadow-xl border border-slate-200 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <div>
                <h3 className="text-base font-bold text-slate-900">Transaction Receipt</h3>
                <p className="text-[11px] font-mono text-slate-400">{selectedTx.id}</p>
              </div>
              <button onClick={() => setSelectedTx(null)} className="text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-4 bg-slate-50 rounded-lg border border-slate-100 space-y-2 text-xs">
              <div className="flex justify-between">
                <span className="text-slate-500">Certificate ID:</span>
                <span className="font-mono font-bold text-forest-800">{selectedTx.certificate_id}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Credit Reference:</span>
                <span className="font-mono font-semibold text-slate-800">{selectedTx.credit_id}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Buyer:</span>
                <span className="font-semibold text-slate-800">{selectedTx.buyer_name}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Farmer:</span>
                <span className="font-semibold text-slate-800">{selectedTx.seller_name}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Carbon Offset:</span>
                <span className="font-mono font-bold text-slate-900">{selectedTx.quantity_tco2e} tCO₂e</span>
              </div>
              <div className="flex justify-between pt-2 border-t border-slate-200 font-bold text-sm text-slate-900">
                <span>Total Settled:</span>
                <span className="font-mono text-forest-800">₹{selectedTx.total_amount.toLocaleString()}</span>
              </div>
            </div>

            <div className="p-2.5 bg-slate-100 rounded text-[11px] text-slate-500 text-center">
              Prototype transaction — no real payment processed.
            </div>

            <button
              onClick={() => setSelectedTx(null)}
              className="w-full py-2 bg-slate-900 hover:bg-slate-800 text-white rounded-lg font-semibold"
            >
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
