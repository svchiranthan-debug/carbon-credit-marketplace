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
import { useAuth } from "../context/AuthContext";
import { API_BASE_URL } from "../services/api";

const DEMO_ACCOUNTS: { label: string; email: string }[] = [
  { label: "Farmer", email: "farmer@agrocarbon.demo" },
  { label: "Buyer", email: "buyer@ecocorp.demo" },
  { label: "Auditor", email: "auditor@agrocarbon.demo" },
];

export default function LoginScreen() {
  const { login, isLoading } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const handleSignIn = async () => {
    if (!email.trim() || !password) {
      Alert.alert("Missing details", "Enter your email and password.");
      return;
    }
    try {
      await login(email, password);
    } catch (err: any) {
      Alert.alert("Sign-in failed", err.message);
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
        <Text style={styles.label}>Email Address</Text>
        <TextInput
          style={styles.input}
          placeholder="you@example.com"
          placeholderTextColor="#94A3B8"
          value={email}
          onChangeText={setEmail}
          autoCapitalize="none"
          keyboardType="email-address"
        />

        <Text style={styles.label}>Password</Text>
        <TextInput
          style={styles.input}
          placeholder="Password"
          placeholderTextColor="#94A3B8"
          value={password}
          onChangeText={setPassword}
          secureTextEntry
        />

        <TouchableOpacity
          style={[styles.submitBtn, isLoading && styles.btnDisabled]}
          onPress={handleSignIn}
          disabled={isLoading}
        >
          {isLoading ? <ActivityIndicator color="#fff" /> : <Text style={styles.submitBtnText}>Sign in</Text>}
        </TouchableOpacity>

        <Text style={[styles.label, { marginTop: 16 }]}>Seeded demo accounts (fills the email only)</Text>
        <View style={styles.roleRow}>
          {DEMO_ACCOUNTS.map((a) => (
            <TouchableOpacity key={a.email} style={styles.roleBtn} onPress={() => setEmail(a.email)}>
              <Text style={styles.roleBtnText}>{a.label}</Text>
            </TouchableOpacity>
          ))}
        </View>
      </View>

      <View style={styles.footer}>
        <Text style={styles.footerText}>Backend: {API_BASE_URL}</Text>
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
