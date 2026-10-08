import React, { useState } from "react";
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  ActivityIndicator,
  Alert,
  StyleSheet
} from "react-native";
import { useAuth, UserRole } from "../context/AuthContext";

export default function LoginScreen() {
  const { login, isLoading } = useAuth();
  const [selectedRole, setSelectedRole] = useState<UserRole>("FARMER");
  const [customEmail, setCustomEmail] = useState("");

  const handleSignIn = async () => {
    try {
      await login(selectedRole, customEmail || undefined);
    } catch (err: any) {
      Alert.alert("Authentication Failed", err.message || "Unable to connect to the backend server. Please verify your connection.");
    }
  };

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.badge}>MRV INFRASTRUCTURE • MOBILE CLIENT</Text>
        <Text style={styles.title}>CARBON CREDIT MARKETPLACE</Text>
        <Text style={styles.subtitle}>WITH MULTI-MODAL VERIFICATION</Text>
      </View>

      <View style={styles.card}>
        <Text style={styles.label}>Select Operational Role</Text>
        <View style={styles.roleRow}>
          {(["FARMER", "BUYER", "AUDITOR"] as UserRole[]).map((r) => (
            <TouchableOpacity
              key={r}
              style={[styles.roleBtn, selectedRole === r && styles.roleBtnActive]}
              onPress={() => setSelectedRole(r)}
            >
              <Text style={[styles.roleBtnText, selectedRole === r && styles.roleBtnTextActive]}>
                {r}
              </Text>
            </TouchableOpacity>
          ))}
        </View>

        <Text style={styles.roleDesc}>
          {selectedRole === "FARMER" && "Register agroforestry plantations, geotag coordinates via GPS, and submit camera evidence."}
          {selectedRole === "BUYER" && "Browse verified carbon assets, acquire credits via escrow, and retire certificates."}
          {selectedRole === "AUDITOR" && "Audit incoming plantations, inspect AI vision and satellite NDVI, and evaluate risk scores."}
        </Text>

        <Text style={styles.label}>Email Address</Text>
        <TextInput
          style={styles.input}
          placeholder={
            selectedRole === "FARMER" ? "farmer@agrocarbon.demo" :
            selectedRole === "BUYER" ? "buyer@agrocarbon.demo" : "auditor@agrocarbon.demo"
          }
          placeholderTextColor="#94A3B8"
          value={customEmail}
          onChangeText={setCustomEmail}
          autoCapitalize="none"
        />

        <TouchableOpacity
          style={[styles.submitBtn, isLoading && styles.btnDisabled]}
          onPress={handleSignIn}
          disabled={isLoading}
        >
          {isLoading ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <Text style={styles.submitBtnText}>Enter as {selectedRole}</Text>
          )}
        </TouchableOpacity>
      </View>

      <View style={styles.footer}>
        <Text style={styles.footerText}>
          Connected to FastAPI Backend on port 8000 • Shared unified database & blockchain registry.
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#F8FAFC", justifyContent: "center", padding: 20 },
  header: { alignItems: "center", marginBottom: 24 },
  badge: { fontSize: 9, fontWeight: "800", color: "#64748B", letterSpacing: 1, marginBottom: 4 },
  title: { fontSize: 16, fontWeight: "900", color: "#0F172A", textAlign: "center", letterSpacing: -0.3 },
  subtitle: { fontSize: 11, fontWeight: "700", color: "#1B3B2B", letterSpacing: 0.5, marginTop: 2 },
  card: { backgroundColor: "#FFFFFF", borderRadius: 10, padding: 20, borderWidth: 1, borderColor: "#E2E8F0", shadowColor: "#000", shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.05, shadowRadius: 3 },
  label: { fontSize: 11, fontWeight: "700", color: "#475569", marginBottom: 6 },
  roleRow: { flexDirection: "row", gap: 6, marginBottom: 12 },
  roleBtn: { flex: 1, paddingVertical: 10, alignItems: "center", borderRadius: 6, borderWidth: 1, borderColor: "#E2E8F0", backgroundColor: "#F8FAFC" },
  roleBtnActive: { backgroundColor: "#1B3B2B", borderColor: "#1B3B2B" },
  roleBtnText: { fontSize: 11, fontWeight: "800", color: "#64748B" },
  roleBtnTextActive: { color: "#FFFFFF" },
  roleDesc: { fontSize: 11, color: "#64748B", backgroundColor: "#F8FAFC", padding: 10, borderRadius: 6, marginBottom: 14, borderLeftWidth: 3, borderLeftColor: "#1B3B2B" },
  input: { borderWidth: 1, borderColor: "#CBD5E1", borderRadius: 6, paddingHorizontal: 12, paddingVertical: 10, fontSize: 13, backgroundColor: "#FFFFFF", marginBottom: 16, color: "#0F172A" },
  submitBtn: { backgroundColor: "#1B3B2B", paddingVertical: 12, borderRadius: 6, alignItems: "center" },
  submitBtnText: { color: "#FFFFFF", fontSize: 12, fontWeight: "800", textTransform: "uppercase", letterSpacing: 0.5 },
  btnDisabled: { opacity: 0.6 },
  footer: { marginTop: 24, alignItems: "center" },
  footerText: { fontSize: 10, color: "#94A3B8", textAlign: "center" }
});
