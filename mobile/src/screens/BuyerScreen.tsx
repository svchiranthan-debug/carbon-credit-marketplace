import React, { useState, useEffect } from "react";
import {
  View,
  Text,
  TouchableOpacity,
  ScrollView,
  ActivityIndicator,
  Alert,
  StyleSheet
} from "react-native";
import { api } from "../services/api";

export default function BuyerScreen() {
  const [tab, setTab] = useState<"MARKETPLACE" | "PORTFOLIO">("MARKETPLACE");
  const [credits, setCredits] = useState<any[]>([]);
  const [portfolio, setPortfolio] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [processingId, setProcessingId] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const loadMarketplace = async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const data = await api.getMarketplaceCredits();
      setCredits(data || []);
    } catch (err: any) {
      setLoadError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const loadPortfolio = async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const data = await api.getBuyerPortfolio();
      setPortfolio(data || []);
    } catch (err: any) {
      setLoadError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (tab === "MARKETPLACE") {
      loadMarketplace();
    } else {
      loadPortfolio();
    }
  }, [tab]);

  const handleAcquire = async (credit: any) => {
    Alert.alert(
      "Confirm Acquisition",
      `Acquire ${credit.carbon_quantity_tco2e} tCO2e for ₹${(credit.carbon_quantity_tco2e * credit.price_per_tco2e).toLocaleString("en-IN")}? (Prototype: no real payment is processed.)`,
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Acquire",
          onPress: async () => {
            setProcessingId(credit.id);
            try {
              await api.acquireCredit(credit.id);
              Alert.alert("Acquisition Successful", `Asset ${credit.id} acquired and transferred to your portfolio.`);
              loadMarketplace();
            } catch (err: any) {
              Alert.alert("Acquisition Failed", err.message);
            } finally {
              setProcessingId(null);
            }
          }
        }
      ]
    );
  };

  const handleRetire = async (credit: any) => {
    Alert.alert(
      "Irrevocable Retirement",
      `Permanently retire ${credit.carbon_quantity_tco2e} tCO2e for corporate ESG offset certificate? This cannot be undone.`,
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Retire Now",
          style: "destructive",
          onPress: async () => {
            setProcessingId(credit.id);
            try {
              const res = await api.retireCredit(credit.id);
              Alert.alert("Asset Retired", `Asset ${credit.id} retired. Blockchain: ${res?.blockchain_status === "CONFIRMED" ? `recorded on-chain (${res.blockchain_tx_hash})` : "not recorded on-chain (database only)"}.`);
              loadPortfolio();
            } catch (err: any) {
              Alert.alert("Retirement Failed", err.message);
            } finally {
              setProcessingId(null);
            }
          }
        }
      ]
    );
  };

  return (
    <View style={styles.container}>
      {/* Tabs */}
      <View style={styles.tabBar}>
        <TouchableOpacity
          style={[styles.tabBtn, tab === "MARKETPLACE" && styles.tabBtnActive]}
          onPress={() => setTab("MARKETPLACE")}
        >
          <Text style={[styles.tabText, tab === "MARKETPLACE" && styles.tabTextActive]}>
            Marketplace ({credits.length})
          </Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.tabBtn, tab === "PORTFOLIO" && styles.tabBtnActive]}
          onPress={() => setTab("PORTFOLIO")}
        >
          <Text style={[styles.tabText, tab === "PORTFOLIO" && styles.tabTextActive]}>
            ESG Portfolio ({portfolio.length})
          </Text>
        </TouchableOpacity>
      </View>

      <ScrollView contentContainerStyle={styles.content}>
        {loadError && <Text style={{ color: "#B91C1C", marginBottom: 10 }}>⚠️ {loadError}</Text>}
        {loading ? (
          <ActivityIndicator size="large" color="#1B3B2B" style={{ marginTop: 40 }} />
        ) : tab === "MARKETPLACE" ? (
          credits.length === 0 ? (
            <View style={styles.emptyBox}>
              <Text style={styles.emptyTitle}>No Credits Currently Listed</Text>
              <Text style={styles.emptySub}>Approved agroforestry carbon credits will appear here once verified.</Text>
            </View>
          ) : (
            credits.map((c) => (
              <View key={c.id} style={styles.card}>
                <View style={styles.cardHeader}>
                  <View>
                    <Text style={styles.cardId}>{c.id}</Text>
                    <Text style={styles.cardName}>{c.plantation_name || "—"}</Text>
                  </View>
                  <View style={styles.verifiedBadge}>
                    <Text style={styles.verifiedBadgeText}>VERIFIED</Text>
                  </View>
                </View>

                <View style={styles.metricsRow}>
                  <View style={styles.metricItem}>
                    <Text style={styles.metricLabel}>Volume</Text>
                    <Text style={styles.metricVal}>{c.carbon_quantity_tco2e} tCO2e</Text>
                  </View>
                  <View style={styles.metricItem}>
                    <Text style={styles.metricLabel}>Rate / tCO2e</Text>
                    <Text style={styles.metricVal}>₹{c.price_per_tco2e}</Text>
                  </View>
                  <View style={styles.metricItem}>
                    <Text style={styles.metricLabel}>Total Amount</Text>
                    <Text style={[styles.metricVal, { color: "#166534" }]}>₹{(c.carbon_quantity_tco2e * c.price_per_tco2e).toLocaleString("en-IN")}</Text>
                  </View>
                </View>

                <Text style={styles.provenanceText}>
                  Blockchain Provenance: {c.certificate_hash ? `${c.certificate_hash.slice(0, 18)}...` : "SHA-256 On-Chain"}
                </Text>

                <TouchableOpacity
                  style={[styles.actionBtn, processingId === c.id && styles.btnDisabled]}
                  onPress={() => handleAcquire(c)}
                  disabled={processingId === c.id}
                >
                  {processingId === c.id ? (
                    <ActivityIndicator color="#fff" size="small" />
                  ) : (
                    <Text style={styles.actionBtnText}>Acquire Carbon Credits</Text>
                  )}
                </TouchableOpacity>
              </View>
            ))
          )
        ) : (
          portfolio.length === 0 ? (
            <View style={styles.emptyBox}>
              <Text style={styles.emptyTitle}>No Holdings in Portfolio</Text>
              <Text style={styles.emptySub}>Acquired verified credits will appear here for ESG compliance.</Text>
            </View>
          ) : (
            portfolio.map((c) => (
              <View key={c.id} style={styles.card}>
                <View style={styles.cardHeader}>
                  <View>
                    <Text style={styles.cardId}>{c.id}</Text>
                    <Text style={styles.cardName}>{c.plantation_name || "—"}</Text>
                  </View>
                  <View style={[styles.verifiedBadge, c.status === "RETIRED" && styles.retiredBadge]}>
                    <Text style={[styles.verifiedBadgeText, c.status === "RETIRED" && styles.retiredBadgeText]}>
                      {c.status}
                    </Text>
                  </View>
                </View>

                <View style={styles.metricsRow}>
                  <View style={styles.metricItem}>
                    <Text style={styles.metricLabel}>Quantity</Text>
                    <Text style={styles.metricVal}>{c.carbon_quantity_tco2e} tCO2e</Text>
                  </View>
                  <View style={styles.metricItem}>
                    <Text style={styles.metricLabel}>Acquired On</Text>
                    <Text style={styles.metricVal}>2026</Text>
                  </View>
                </View>

                {c.status !== "RETIRED" && (
                  <TouchableOpacity
                    style={[styles.retireBtn, processingId === c.id && styles.btnDisabled]}
                    onPress={() => handleRetire(c)}
                    disabled={processingId === c.id}
                  >
                    {processingId === c.id ? (
                      <ActivityIndicator color="#fff" size="small" />
                    ) : (
                      <Text style={styles.retireBtnText}>Permanently Retire (Offset Certificate)</Text>
                    )}
                  </TouchableOpacity>
                )}
              </View>
            ))
          )
        )}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#F8FAFC" },
  tabBar: { flexDirection: "row", backgroundColor: "#FFFFFF", borderBottomWidth: 1, borderColor: "#E2E8F0" },
  tabBtn: { flex: 1, paddingVertical: 12, alignItems: "center" },
  tabBtnActive: { borderBottomWidth: 2, borderColor: "#1B3B2B" },
  tabText: { fontSize: 12, fontWeight: "700", color: "#64748B" },
  tabTextActive: { color: "#1B3B2B" },
  content: { padding: 16 },
  card: { backgroundColor: "#FFFFFF", borderRadius: 8, padding: 16, marginBottom: 12, borderWidth: 1, borderColor: "#E2E8F0" },
  cardHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 12 },
  cardId: { fontSize: 10, fontFamily: "monospace", color: "#64748B", fontWeight: "700" },
  cardName: { fontSize: 14, fontWeight: "800", color: "#0F172A", marginTop: 2 },
  verifiedBadge: { backgroundColor: "#DCFCE7", paddingHorizontal: 8, paddingVertical: 3, borderRadius: 4 },
  verifiedBadgeText: { fontSize: 9, fontWeight: "800", color: "#166534" },
  retiredBadge: { backgroundColor: "#F1F5F9" },
  retiredBadgeText: { color: "#475569" },
  metricsRow: { flexDirection: "row", justifyContent: "space-between", backgroundColor: "#F8FAFC", padding: 10, borderRadius: 6, marginVertical: 8 },
  metricItem: { alignItems: "center" },
  metricLabel: { fontSize: 9, color: "#64748B", fontWeight: "600" },
  metricVal: { fontSize: 13, fontWeight: "800", color: "#0F172A", marginTop: 2 },
  provenanceText: { fontSize: 9, color: "#64748B", fontFamily: "monospace", marginBottom: 10 },
  actionBtn: { backgroundColor: "#1B3B2B", paddingVertical: 10, borderRadius: 6, alignItems: "center" },
  actionBtnText: { color: "#FFFFFF", fontSize: 12, fontWeight: "800", textTransform: "uppercase" },
  retireBtn: { backgroundColor: "#0F172A", paddingVertical: 10, borderRadius: 6, alignItems: "center", marginTop: 6 },
  retireBtnText: { color: "#FFFFFF", fontSize: 11, fontWeight: "700" },
  btnDisabled: { opacity: 0.6 },
  emptyBox: { padding: 40, alignItems: "center" },
  emptyTitle: { fontSize: 14, fontWeight: "800", color: "#334155" },
  emptySub: { fontSize: 11, color: "#64748B", textAlign: "center", marginTop: 4 }
});
