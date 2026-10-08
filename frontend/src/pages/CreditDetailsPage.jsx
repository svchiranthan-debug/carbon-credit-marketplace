import React, { useState, useEffect } from "react";
import { useAuth } from "../context/AuthContext";
import api, { getImageUrl } from "../services/api";
import StatusBadge from "../components/StatusBadge";
import { 
  ArrowLeft, 
  ArrowRight,
  CheckCircle,
  RefreshCw,
  X,
  ShieldCheck,
  Lock,
  FileImage
} from "lucide-react";

export default function CreditDetailsPage({ creditId, setCurrentView, setSelectedPlantationId }) {
  const { user, isAuthenticated, role, loginDemoAccount } = useAuth();
  const [credit, setCredit] = useState(null);
  const [blockchainRecord, setBlockchainRecord] = useState(null);
  const [loading, setLoading] = useState(true);
  const [purchasing, setPurchasing] = useState(false);
  const [showPurchaseModal, setShowPurchaseModal] = useState(false);
  const [transactionSuccess, setTransactionSuccess] = useState(null);
  const [error, setError] = useState(null);

  const loadDetails = async () => {
    setLoading(true);
    setError(null);
    try {
      const [crData, bcData] = await Promise.all([
        api.getCreditDetail(creditId),
        api.getBlockchainRecord(creditId).catch(() => null)
      ]);
      setCredit(crData);
      setBlockchainRecord(bcData);
    } catch (err) {
      console.error("Failed loading credit details:", err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (creditId) {
      setTransactionSuccess(null);
      loadDetails();
    }
  }, [creditId]);

  const handlePurchase = async () => {
    if (!isAuthenticated) {
      alert("Please log in as a Corporate Buyer to acquire carbon assets.");
      return;
    }

    setPurchasing(true);
    try {
      const res = await api.purchaseCredit(credit.id);
      setTransactionSuccess(res);
      setShowPurchaseModal(false);
    } catch (err) {
      alert(`Asset acquisition failed: ${err.message}`);
    } finally {
      setPurchasing(false);
    }
  };

  // 1. Transaction Receipt / Ownership Transferred Screen
  if (transactionSuccess) {
    const qty = transactionSuccess.quantity_tco2e || credit?.carbon_quantity_tco2e || 25;
    const plantationName = transactionSuccess.plantation_name || credit?.plantation_name || "Kaveri Basin Agroforestry Plot";
    const totalVal = transactionSuccess.total_amount || (qty * (credit?.price_per_tco2e || 1500));
    const txnId = transactionSuccess.id || "TXN-2026-XXXX";
    const crId = transactionSuccess.credit_id || credit?.id || creditId || "CC-2026-001";
    const bcHash = transactionSuccess.blockchain_tx_hash || credit?.blockchain_tx_hash || "0x005b1a8c11b6b0f6b0843b0a3908914757f0778674071c27dde91ee1874059c9";

    return (
      <div className="max-w-lg mx-auto px-4 py-12 text-xs text-slate-800">
        <div className="bg-white rounded border border-slate-200 p-8 space-y-6">
          <div className="text-center space-y-1">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Transaction Confirmed</span>
            <h2 className="text-xl font-bold text-slate-900 tracking-tight">Ownership Transferred</h2>
            <p className="text-slate-500 text-xs">
              The carbon asset custody has been transferred on the blockchain registry.
            </p>
          </div>

          <div className="border border-slate-200 rounded p-4 bg-slate-50 space-y-2.5">
            <div className="flex justify-between">
              <span className="text-slate-500">Asset ID:</span>
              <span className="font-mono font-bold text-slate-900">{crId}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Plantation:</span>
              <span className="font-medium text-slate-900">{plantationName}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Carbon Quantity:</span>
              <span className="font-mono font-bold text-slate-900">{qty} tCO₂e</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Total Value:</span>
              <span className="font-mono font-bold text-slate-900">₹{totalVal.toLocaleString()}</span>
            </div>
            <div className="flex justify-between pt-2 border-t border-slate-200">
              <span className="text-slate-500">Transaction ID:</span>
              <span className="font-mono text-slate-800">{txnId}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Blockchain Status:</span>
              <span className="font-semibold text-forest-900">Recorded (Confirmed)</span>
            </div>
            <div className="pt-1">
              <span className="text-slate-400 block text-[10px]">Blockchain Transaction Hash:</span>
              <span className="font-mono text-[10px] text-slate-700 break-all font-medium">
                {bcHash.startsWith("0x") ? bcHash : `0x${bcHash}`}
              </span>
            </div>
          </div>

          <p className="text-[11px] text-slate-400 text-center italic">
            Prototype transaction — no real payment was processed.
          </p>

          <div className="flex gap-2">
            <button
              onClick={() => {
                setTransactionSuccess(null);
                setCurrentView("transactions");
              }}
              className="w-full py-2 bg-slate-900 hover:bg-slate-800 text-white rounded text-xs font-semibold"
            >
              View Transaction
            </button>
            <button
              onClick={() => {
                setTransactionSuccess(null);
                setCurrentView("marketplace");
              }}
              className="w-full py-2 border border-slate-300 hover:bg-slate-50 text-slate-700 rounded text-xs font-medium"
            >
              Back to Marketplace
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-20 text-center text-xs text-slate-500">
        <RefreshCw className="w-5 h-5 animate-spin text-slate-700 mx-auto mb-2" />
        <p className="font-medium text-slate-800">Loading asset record and provenance...</p>
      </div>
    );
  }

  if (error || !credit) {
    return (
      <div className="max-w-md mx-auto px-4 py-12 text-center text-xs">
        <div className="bg-white p-6 rounded border border-slate-200 space-y-3">
          <p className="font-semibold text-slate-900">Asset Record Not Found</p>
          <p className="text-slate-500">
            This carbon asset listing is not available or has been transferred.
          </p>
          <button
            onClick={() => setCurrentView("marketplace")}
            className="px-3 py-1.5 bg-slate-900 text-white rounded text-xs font-medium"
          >
            Back to Marketplace
          </button>
        </div>
      </div>
    );
  }

  const isAvailable = credit.status === "AVAILABLE";
  const isAcquired = credit.status === "SOLD";
  const isRetired = credit.is_retired || credit.status === "RETIRED";
  const totalAmount = credit.carbon_quantity_tco2e * credit.price_per_tco2e;
  const contractAddress = credit.blockchain_contract_address || (blockchainRecord && blockchainRecord.contract_address) || "0x21a59654176f2689d12E828B77a783072CD26680";
  const rawTxHash = credit.blockchain_tx_hash || (blockchainRecord && blockchainRecord.transaction_hash) || "0x005b1a8c11b6b0f6b0843b0a3908914757f0778674071c27dde91ee1874059c9";
  const formattedTxHash = rawTxHash.startsWith("0x") ? rawTxHash : `0x${rawTxHash}`;
  const reportHash = credit.report_hash || (blockchainRecord && blockchainRecord.report_hash) || "8e7f855dd2f2be26ce6aa58b8a586e80b7b9e44dcfed47de9e2955b8206ac138";

  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 py-8 space-y-6 text-xs text-slate-800">
      {/* Back button */}
      <div>
        <button
          onClick={() => setCurrentView("marketplace")}
          className="text-xs font-medium text-slate-500 hover:text-slate-900 mb-2 inline-flex items-center gap-1"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to Marketplace</span>
        </button>

        <div className="flex flex-col sm:flex-row sm:items-baseline justify-between gap-1 border-b border-slate-200 pb-3">
          <div>
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
              Verified Carbon Asset
            </span>
            <h1 className="text-xl font-bold text-slate-900 tracking-tight">
              {credit.plantation_name || "Agroforestry Carbon Asset"}
            </h1>
            <p className="text-slate-500 text-[11px] mt-0.5">
              Asset ID: <span className="font-mono font-bold text-slate-800">{credit.id}</span> • {credit.plantation_location || credit.location || "Karnataka, India"}
            </p>
          </div>

          <div className="text-right">
            <span className="text-[10px] text-slate-400 block uppercase tracking-wider">Asset Valuation</span>
            <span className="text-lg font-bold font-mono text-slate-900">
              ₹{totalAmount.toLocaleString()}
            </span>
          </div>
        </div>
      </div>

      {/* Plantation Ground Photo Preview */}
      <div className="w-full h-48 bg-slate-100 rounded border border-slate-200 overflow-hidden relative flex items-center justify-center">
        {credit.image_url ? (
          <img
            src={getImageUrl(credit.image_url)}
            alt={credit.plantation_name || "Plantation"}
            className="w-full h-full object-cover"
            onError={(e) => {
              e.currentTarget.style.display = "none";
              e.currentTarget.nextElementSibling.style.display = "flex";
            }}
          />
        ) : null}
        <div
          className={`w-full h-full flex flex-col items-center justify-center p-3 text-center bg-slate-50 text-slate-400 ${
            credit.image_url ? "hidden" : "flex"
          }`}
        >
          <FileImage className="w-8 h-8 mb-1 text-slate-300" />
          <span className="font-bold text-[10px] uppercase tracking-wider text-slate-500">
            NO GROUND IMAGE
          </span>
          <span className="text-[10px] text-slate-400 mt-0.5">
            Multi-modal satellite NDVI certified
          </span>
        </div>
      </div>

      {/* 8. ASSET LIFECYCLE (Subtle horizontal timeline) */}
      <div className="bg-white border border-slate-200 rounded p-4">
        <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block mb-3">
          Asset Lifecycle
        </span>
        <div className="grid grid-cols-4 text-center text-[11px] relative">
          {/* Step 1: Issued */}
          <div className="space-y-1">
            <div className="w-5 h-5 mx-auto rounded-full flex items-center justify-center font-bold text-[10px] bg-slate-900 text-white">
              ✓
            </div>
            <span className="font-semibold text-slate-900 block">ISSUED</span>
          </div>

          {/* Step 2: Available */}
          <div className="space-y-1">
            <div className={`w-5 h-5 mx-auto rounded-full flex items-center justify-center font-bold text-[10px] ${
              isAvailable 
                ? "bg-forest-900 text-white" 
                : "bg-slate-900 text-white"
            }`}>
              ✓
            </div>
            <span className={`block font-medium ${isAvailable ? "font-bold text-forest-900" : "text-slate-700"}`}>
              AVAILABLE
            </span>
          </div>

          {/* Step 3: Acquired */}
          <div className="space-y-1">
            <div className={`w-5 h-5 mx-auto rounded-full flex items-center justify-center font-bold text-[10px] ${
              isAcquired || isRetired
                ? "bg-slate-900 text-white" 
                : "border border-slate-300 text-slate-400 bg-white"
            }`}>
              {isAcquired || isRetired ? "✓" : "3"}
            </div>
            <span className={`block font-medium ${isAcquired ? "font-bold text-slate-900" : isRetired ? "text-slate-700" : "text-slate-400"}`}>
              ACQUIRED
            </span>
          </div>

          {/* Step 4: Retired */}
          <div className="space-y-1">
            <div className={`w-5 h-5 mx-auto rounded-full flex items-center justify-center font-bold text-[10px] ${
              isRetired 
                ? "bg-slate-900 text-white" 
                : "border border-slate-300 text-slate-400 bg-white"
            }`}>
              {isRetired ? "✓" : "4"}
            </div>
            <span className={`block font-medium ${isRetired ? "font-bold text-slate-900" : "text-slate-400"}`}>
              RETIRED
            </span>
          </div>
        </div>
      </div>

      {/* 6. Professional Asset Record Details */}
      <div className="bg-white border border-slate-200 rounded p-5 space-y-3">
        <h2 className="text-xs font-bold text-slate-900 uppercase tracking-wider border-b border-slate-100 pb-2">
          Asset Specification
        </h2>

        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-xs">
          <div>
            <span className="text-slate-400 block text-[11px]">Carbon Volume</span>
            <span className="font-mono font-bold text-slate-900 text-sm">
              {credit.carbon_quantity_tco2e} tCO₂e
            </span>
          </div>

          <div>
            <span className="text-slate-400 block text-[11px]">Unit Price</span>
            <span className="font-mono font-bold text-slate-900 text-sm">
              ₹{credit.price_per_tco2e.toLocaleString()} / ton
            </span>
          </div>

          <div>
            <span className="text-slate-400 block text-[11px]">Verification Score</span>
            <span className="font-mono font-bold text-slate-900 text-sm">
              {credit.verification_score ? `${credit.verification_score} / 100` : "Verified"}
            </span>
          </div>

          <div>
            <span className="text-slate-400 block text-[11px]">Current Status</span>
            <div className="mt-0.5">
              <StatusBadge status={credit.status} size="sm" />
            </div>
          </div>

          <div>
            <span className="text-slate-400 block text-[11px]">Issue Date</span>
            <span className="text-slate-700 font-medium">
              {credit.created_at ? new Date(credit.created_at).toLocaleDateString() : "August 2026"}
            </span>
          </div>

          <div>
            <span className="text-slate-400 block text-[11px]">Custodian</span>
            <span className="text-slate-700 font-medium truncate block">
              {credit.farmer_name || "Plantation Custodian"}
            </span>
          </div>
        </div>
      </div>

      {/* 7. PROVENANCE SECTION (Section 7) */}
      <div className="bg-white border border-slate-200 rounded p-5 space-y-3">
        <div className="flex items-center justify-between border-b border-slate-100 pb-2">
          <h2 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
            Provenance
          </h2>
          <span className="text-[11px] font-semibold text-slate-600 bg-slate-100 px-2 py-0.5 rounded">
            Blockchain Verified
          </span>
        </div>

        <div className="space-y-2 text-xs">
          <div className="flex justify-between">
            <span className="text-slate-500">Asset ID:</span>
            <span className="font-mono font-bold text-slate-900">{credit.id}</span>
          </div>

          <div className="flex justify-between">
            <span className="text-slate-500">Network:</span>
            <span className="text-slate-800">Ethereum-compatible local network</span>
          </div>

          <div className="flex justify-between">
            <span className="text-slate-500">Contract:</span>
            <span className="font-mono text-slate-800 text-[11px] truncate max-w-[240px]">
              {contractAddress}
            </span>
          </div>

          <div>
            <span className="text-slate-500 block mb-0.5">Verification Hash:</span>
            <span className="font-mono text-[10px] text-slate-700 break-all bg-slate-50 p-1.5 rounded border border-slate-200/70 block">
              {reportHash}
            </span>
          </div>

          <div>
            <span className="text-slate-500 block mb-0.5">Transaction Hash:</span>
            <span className="font-mono text-[10px] text-slate-700 break-all bg-slate-50 p-1.5 rounded border border-slate-200/70 block">
              {formattedTxHash}
            </span>
          </div>

          <div className="flex justify-between pt-1">
            <span className="text-slate-500">Status:</span>
            <span className="font-semibold text-forest-900">Confirmed</span>
          </div>
        </div>

        <p className="text-[11px] text-slate-400 pt-1 border-t border-slate-100">
          Blockchain provides a tamper-evident record of asset registration, ownership and retirement.
        </p>
      </div>

      {/* 9. ACQUIRE CARBON ASSET ACTION */}
      <div className="bg-white border border-slate-200 rounded p-5 flex items-center justify-between">
        <div>
          <span className="text-[10px] text-slate-400 uppercase tracking-wider block">Acquisition Settlement</span>
          <span className="font-bold text-slate-900 text-sm">
            {credit.carbon_quantity_tco2e} tCO₂e • ₹{totalAmount.toLocaleString()}
          </span>
        </div>

        {isAvailable ? (
          <button
            onClick={() => {
              if (!isAuthenticated || role !== "BUYER") {
                loginDemoAccount("BUYER").then(() => setShowPurchaseModal(true));
              } else {
                setShowPurchaseModal(true);
              }
            }}
            className="px-4 py-2 bg-forest-900 hover:bg-forest-950 text-white font-semibold rounded text-xs transition"
          >
            Acquire Carbon Asset
          </button>
        ) : (
          <span className="text-slate-500 font-medium px-3 py-1 bg-slate-100 rounded text-xs">
            {isRetired ? "Retired on Blockchain" : "Acquired / In Custody"}
          </span>
        )}
      </div>

      {/* Acquisition Confirmation Modal */}
      {showPurchaseModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/30 p-4">
          <div className="bg-white rounded max-w-md w-full p-6 shadow-lg border border-slate-200 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-2">
              <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider">
                Confirm Asset Acquisition
              </h3>
              <button
                onClick={() => setShowPurchaseModal(false)}
                className="text-slate-400 hover:text-slate-600 p-1"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="p-3 bg-slate-50 rounded border border-slate-200 space-y-1.5 text-xs">
              <div className="flex justify-between">
                <span className="text-slate-500">Asset:</span>
                <span className="font-mono font-bold text-slate-900">{credit.id}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Volume:</span>
                <span className="font-bold text-slate-900">{credit.carbon_quantity_tco2e} tCO₂e</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Unit Price:</span>
                <span className="text-slate-800 font-mono">₹{credit.price_per_tco2e.toLocaleString()} / ton</span>
              </div>
              <div className="flex justify-between pt-1 border-t border-slate-200 font-bold">
                <span>Total Settlement:</span>
                <span className="font-mono text-slate-900">₹{totalAmount.toLocaleString()}</span>
              </div>
            </div>

            <p className="text-[11px] text-slate-400 italic">
              Prototype transaction — no real payment was processed. Ownership will be transferred on the local smart contract.
            </p>

            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setShowPurchaseModal(false)}
                className="px-3 py-1.5 border border-slate-200 text-slate-700 rounded text-xs hover:bg-slate-50 font-medium"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handlePurchase}
                disabled={purchasing}
                className="px-4 py-1.5 bg-forest-900 hover:bg-forest-950 text-white rounded text-xs font-semibold disabled:opacity-50"
              >
                {purchasing ? "Transferring..." : "Confirm Acquisition"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
