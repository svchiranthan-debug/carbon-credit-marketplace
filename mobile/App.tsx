import React from "react";
import { SafeAreaView, View, Text, TouchableOpacity, StyleSheet, StatusBar } from "react-native";
import { AuthProvider, useAuth, UserRole } from "./src/context/AuthContext";
import LoginScreen from "./src/screens/LoginScreen";
import FarmerScreen from "./src/screens/FarmerScreen";
import BuyerScreen from "./src/screens/BuyerScreen";
import AuditorScreen from "./src/screens/AuditorScreen";

function MainApp() {
  const { user, role, setRole, logout } = useAuth();

  if (!user) {
    return <LoginScreen />;
  }

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar barStyle="dark-content" backgroundColor="#FFFFFF" />
      
      {/* Top Professional Navigation Header */}
      <View style={styles.navBar}>
        <View>
          <Text style={styles.navTitle}>CARBON MARKETPLACE</Text>
          <Text style={styles.navSub}>
            {user.full_name} • <Text style={{ fontWeight: "800", color: "#1B3B2B" }}>{role}</Text>
          </Text>
        </View>

        <TouchableOpacity onPress={logout} style={styles.logoutBtn}>
          <Text style={styles.logoutBtnText}>Exit</Text>
        </TouchableOpacity>
      </View>

      {/* Role Navigation Bar */}
      <View style={styles.roleBar}>
        {(["FARMER", "BUYER", "AUDITOR"] as UserRole[]).map((r) => (
          <TouchableOpacity
            key={r}
            style={[styles.roleTab, role === r && styles.roleTabActive]}
            onPress={() => setRole(r)}
          >
            <Text style={[styles.roleTabText, role === r && styles.roleTabTextActive]}>
              {r === "FARMER" ? "🌾 Farmer" : r === "BUYER" ? "💼 Buyer" : "🛡️ Auditor"}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Screen Body */}
      <View style={styles.body}>
        {role === "FARMER" && <FarmerScreen />}
        {role === "BUYER" && <BuyerScreen />}
        {role === "AUDITOR" && <AuditorScreen />}
      </View>
    </SafeAreaView>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <MainApp />
    </AuthProvider>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: "#FFFFFF" },
  navBar: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderColor: "#E2E8F0",
    backgroundColor: "#FFFFFF"
  },
  navTitle: { fontSize: 11, fontWeight: "900", color: "#0F172A", letterSpacing: 0.5 },
  navSub: { fontSize: 10, color: "#64748B", marginTop: 1 },
  logoutBtn: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 4, backgroundColor: "#F1F5F9" },
  logoutBtnText: { fontSize: 10, fontWeight: "700", color: "#475569" },
  roleBar: {
    flexDirection: "row",
    backgroundColor: "#F8FAFC",
    borderBottomWidth: 1,
    borderColor: "#E2E8F0"
  },
  roleTab: { flex: 1, paddingVertical: 9, alignItems: "center" },
  roleTabActive: { backgroundColor: "#FFFFFF", borderBottomWidth: 2, borderColor: "#1B3B2B" },
  roleTabText: { fontSize: 11, fontWeight: "700", color: "#64748B" },
  roleTabTextActive: { color: "#1B3B2B", fontWeight: "800" },
  body: { flex: 1, backgroundColor: "#F8FAFC" }
});
