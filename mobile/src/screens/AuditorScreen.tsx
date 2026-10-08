import React, { useState, useEffect } from "react";
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  ScrollView,
  ActivityIndicator,
  Alert,
  StyleSheet
} from "react-native";
import { api } from "../services/api";

export default function AuditorScreen() {
  const [queue, setQueue] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [actingId, setActingId] = useState<string | null>(null);
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [loadError, setLoadError] = useState<string | null>(null);

  const loadQueue = async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const data = await api.getAuditorQueue();
      setQueue(data || []);
    } catch (err: any) {
      setLoadError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadQueue();
  }, []);

  const handleDecision = async (item: any, decision: "APPROVED" | "REJECTED") => {
    Alert.alert(
      `Confirm ${decision}`,
      `Are you sure you want to mark verification ${item.id} as ${decision}?`,
      [
        { text: "Cancel", style: "cancel" },
        {
          text: decision,
          style: decision === "REJECTED" ? "destructive" : "default",
          onPress: async () => {
            setActingId(item.id);
            try {
              // Only the auditor's own notes are sent; the backend requires them for overrides.
              await api.submitAuditorDecision(item.id, decision, (notes[item.id] || "").trim());
              Alert.alert("Decision Recorded", `Status updated to ${decision}.`);
              loadQueue();
            } catch (err: any) {
              Alert.alert("Error", err.message);
            } finally {
              setActingId(null);
            }
          }
        }
      ]
    );
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.header}>
        <Text style={styles.subtitle}>INDEPENDENT MRV REGISTRY AUDIT</Text>
        <Text style={styles.title}>Auditor Verification Queue</Text>
      </View>

      {loadError && <Text style={{ color: "#B91C1C", marginBottom: 10 }}>⚠️ {loadError}</Text>}
      {loading ? (
        <ActivityIndicator size="large" color="#1B3B2B" style={{ marginTop: 40 }} />
      ) : queue.length === 0 ? (
        <View style={styles.emptyBox}>
          <Text style={styles.emptyTitle}>Queue Clean</Text>
          <Text style={styles.emptySub}>No pending verification assessments requiring auditor intervention.</Text>
        </View>
      ) : (
        queue.map((item) => {
          const isHighRisk = item.risk_level === "HIGH";
          const ndviSource = item.ndvi_provenance === "SENTINEL2_COMPUTED" ? "Sentinel-2" : item.ndvi_provenance === "REPORTED" ? "Reported" : "Unavailable";
          const scored = item.overall_score !== null && item.overall_score !== undefined;
          const decidable = Boolean(item.id);

          return (
            <View key={item.id || `preview-${item.plantation_id}`} style={[styles.card, isHighRisk && styles.cardHighRisk]}>
              <View style={styles.cardHeader}>
                <View>
                  <Text style={styles.cardId}>{item.id || "Not yet verified"}</Text>
                  <Text style={styles.cardPlot}>Plot #{item.plantation_id} • {item.plantation_name || "—"}</Text>
                  <Text style={styles.farmerText}>Farmer: {item.farmer_name || "—"} • Score: {scored ? item.overall_score : "—"}</Text>
                </View>
                <View style={[
                  styles.statusBadge,
                  item.decision === "APPROVED" ? styles.badgeApproved :
                  item.decision === "REVIEW" ? styles.badgeReview : styles.badgePending
                ]}>
                  <Text style={styles.statusBadgeText}>{item.decision}</Text>
                </View>
              </View>

              {/* Multi-Modal Evidence Breakdown */}
              <View style={styles.metricsGrid}>
                <View style={styles.metricCard}>
                  <Text style={styles.metricLabel}>SATELLITE NDVI</Text>
                  <Text style={styles.metricVal}>{item.ndvi_score != null ? `${item.ndvi_score}` : "—"}</Text>
                  <Text style={[styles.metricTag, item.ndvi_provenance === "SENTINEL2_COMPUTED" ? styles.tagReal : styles.tagSim]}>
                    {ndviSource}
                  </Text>
                </View>

                <View style={styles.metricCard}>
                  <Text style={styles.metricLabel}>AI VISION</Text>
                  <Text style={styles.metricVal}>{item.cv_score != null ? `${item.cv_score}` : "—"}</Text>
                  <Text style={styles.metricTag}>
                    {item.ai_confidence_pct != null ? `${item.ai_confidence_pct}% Conf` : "—"}
                  </Text>
                </View>

                <View style={styles.metricCard}>
                  <Text style={styles.metricLabel}>SOIL SOC</Text>
                  <Text style={styles.metricVal}>{item.soc_score != null ? `${item.soc_score}` : "—"}</Text>
                  <Text style={styles.metricTag}>{item.soc_pct != null ? `${item.soc_pct}%` : "—"}</Text>
                </View>
              </View>

              {/* Risk Engine Indicators */}
              {item.risk_level ? <View style={[
                styles.riskBanner,
                isHighRisk ? styles.riskHigh : item.risk_level === "MEDIUM" ? styles.riskMed : styles.riskLow
              ]}>
                <Text style={styles.riskBannerTitle}>
                  Risk Score: {item.risk_score}/100 • {item.risk_level} RISK
                </Text>
                {item.risk_factors && item.risk_factors.length > 0 ? (
                  <Text style={styles.riskFactorText}>⚠️ {item.risk_factors[0]}</Text>
                ) : (
                  <Text style={styles.riskFactorText}>No risk factors triggered.</Text>
                )}
              </View> : (
                <Text style={styles.riskFactorText}>
                  Risk not assessed{item.missing_evidence?.length ? ` — missing: ${item.missing_evidence.join(", ")}` : ""}
                </Text>
              )}

              {decidable && (
                <TextInput
                  style={styles.notesInput}
                  placeholder="Auditor notes (required when overriding the engine)"
                  placeholderTextColor="#94A3B8"
                  value={notes[item.id] || ""}
                  onChangeText={(t) => setNotes({ ...notes, [item.id]: t })}
                />
              )}

              {/* Auditor Action Buttons */}
              <View style={styles.actionRow}>
                <TouchableOpacity
                  style={[styles.btn, styles.rejectBtn, (!decidable || actingId === item.id) && styles.btnDisabled]}
                  onPress={() => handleDecision(item, "REJECTED")}
                  disabled={!decidable || actingId === item.id}
                >
                  <Text style={styles.rejectBtnText}>Reject</Text>
                </TouchableOpacity>

                <TouchableOpacity
                  style={[styles.btn, styles.approveBtn, (!scored || !decidable || actingId === item.id) && styles.btnDisabled]}
                  onPress={() => handleDecision(item, "APPROVED")}
                  disabled={!scored || !decidable || actingId === item.id}
                >
                  <Text style={styles.approveBtnText}>Approve Verification</Text>
                </TouchableOpacity>
              </View>
            </View>
          );
        })
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#F8FAFC" },
  content: { padding: 16, paddingBottom: 40 },
  header: { marginBottom: 14 },
  subtitle: { fontSize: 10, fontWeight: "700", color: "#64748B", letterSpacing: 0.8 },
  title: { fontSize: 18, fontWeight: "800", color: "#0F172A" },
  card: { backgroundColor: "#FFFFFF", borderRadius: 8, padding: 16, marginBottom: 14, borderWidth: 1, borderColor: "#E2E8F0" },
  cardHighRisk: { borderColor: "#FECACA", borderWidth: 1.5 },
  cardHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 10 },
  cardId: { fontSize: 10, fontFamily: "monospace", color: "#64748B", fontWeight: "700" },
  cardPlot: { fontSize: 13, fontWeight: "800", color: "#0F172A", marginTop: 2 },
  farmerText: { fontSize: 11, color: "#64748B", marginTop: 1 },
  statusBadge: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 4 },
  badgeApproved: { backgroundColor: "#DCFCE7" },
  badgeReview: { backgroundColor: "#FEF3C7" },
  badgePending: { backgroundColor: "#F1F5F9" },
  statusBadgeText: { fontSize: 9, fontWeight: "800", color: "#166534" },
  metricsGrid: { flexDirection: "row", gap: 8, marginVertical: 8 },
  metricCard: { flex: 1, backgroundColor: "#F8FAFC", borderRadius: 6, padding: 8, alignItems: "center", borderWidth: 1, borderColor: "#E2E8F0" },
  metricLabel: { fontSize: 8, fontWeight: "800", color: "#64748B" },
  metricVal: { fontSize: 14, fontWeight: "800", color: "#0F172A", marginVertical: 2, fontFamily: "monospace" },
  metricTag: { fontSize: 8, color: "#64748B" },
  tagReal: { color: "#166534", fontWeight: "700" },
  tagSim: { color: "#854D0E" },
  riskBanner: { padding: 10, borderRadius: 6, marginVertical: 8 },
  riskLow: { backgroundColor: "#F0FDF4", borderColor: "#BBF7D0", borderWidth: 1 },
  riskMed: { backgroundColor: "#FFFBEB", borderColor: "#FDE68A", borderWidth: 1 },
  riskHigh: { backgroundColor: "#FEF2F2", borderColor: "#FECACA", borderWidth: 1 },
  riskBannerTitle: { fontSize: 11, fontWeight: "800", color: "#0F172A" },
  riskFactorText: { fontSize: 10, color: "#475569", marginTop: 2 },
  actionRow: { flexDirection: "row", gap: 8, marginTop: 10 },
  btn: { flex: 1, paddingVertical: 9, borderRadius: 6, alignItems: "center" },
  approveBtn: { backgroundColor: "#1B3B2B" },
  approveBtnText: { color: "#FFFFFF", fontSize: 11, fontWeight: "800" },
  rejectBtn: { backgroundColor: "#FFFFFF", borderWidth: 1, borderColor: "#E2E8F0" },
  rejectBtnText: { color: "#DC2626", fontSize: 11, fontWeight: "700" },
  btnDisabled: { opacity: 0.5 },
  notesInput: { borderWidth: 1, borderColor: "#E2E8F0", borderRadius: 6, padding: 8, fontSize: 11, color: "#0F172A", marginTop: 6 },
  emptyBox: { padding: 40, alignItems: "center" },
  emptyTitle: { fontSize: 14, fontWeight: "800", color: "#334155" },
  emptySub: { fontSize: 11, color: "#64748B", textAlign: "center", marginTop: 4 }
});
