import React, { createContext, useContext, useState, useEffect } from "react";
import { api } from "../services/api";

export type UserRole = "FARMER" | "BUYER" | "AUDITOR";

interface User {
  id: number;
  full_name: string;
  email: string;
  role: UserRole;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  role: UserRole;
  login: (role: UserRole, email?: string) => Promise<void>;
  logout: () => void;
  setRole: (role: UserRole) => void;
  isLoading: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [role, setRoleState] = useState<UserRole>("FARMER");
  const [isLoading, setIsLoading] = useState<boolean>(false);

  const roleProfiles: Record<UserRole, { email: string; full_name: string }> = {
    FARMER: { email: "farmer@agrocarbon.demo", full_name: "Ramesh Gowda" },
    BUYER: { email: "buyer@ecocorp.demo", full_name: "Arun Mehta (EcoCorp ESG)" },
    AUDITOR: { email: "admin@agrocarbon.demo", full_name: "Bureau Veritas Audit Team" }
  };

  const login = async (selectedRole: UserRole, customEmail?: string) => {
    setIsLoading(true);
    const email = customEmail || roleProfiles[selectedRole].email;
    try {
      // Step 1: attempt login with existing account
      const res = await api.login(email, selectedRole);

      const jwt = res.access_token;
      api.setToken(jwt);
      setToken(jwt);
      setUser({
        id: res.user?.id || 1,
        full_name: res.user?.full_name || roleProfiles[selectedRole].full_name,
        email: res.user?.email || email,
        role: selectedRole
      });
      setRoleState(selectedRole);
    } catch (loginErr: any) {
      const msg: string = loginErr.message || "";

      // Only attempt auto-register if the backend says "user not found" (not a password/role error).
      // 401 = wrong password  |  400 with "role" = role mismatch  |  "already exists" = account exists
      // In all those cases the account IS there — registering again would just fail with 400.
      const isCredentialError =
        msg.toLowerCase().includes("incorrect") ||
        msg.toLowerCase().includes("password") ||
        msg.toLowerCase().includes("role") ||
        msg.toLowerCase().includes("already exists") ||
        msg.toLowerCase().includes("unauthorized");

      if (isCredentialError) {
        // Surface the real backend error — do NOT attempt registration
        setUser(null);
        setToken(null);
        api.setToken(null);
        console.warn("[Auth] Login rejected by backend:", msg);
        throw new Error(msg || "Login failed. Check your credentials and try again.");
      }

      // Step 2: login failed for an unknown reason (network / user not seeded yet) → try auto-register
      try {
        const prof = roleProfiles[selectedRole];
        await api.register(prof.full_name, prof.email, selectedRole);
        const res = await api.login(prof.email, selectedRole);
        const jwt = res.access_token;
        api.setToken(jwt);
        setToken(jwt);
        setUser({
          id: res.user?.id || 1,
          full_name: prof.full_name,
          email: prof.email,
          role: selectedRole
        });
        setRoleState(selectedRole);
      } catch (registerErr: any) {
        setUser(null);
        setToken(null);
        api.setToken(null);
        const regMsg = registerErr.message || "";
        console.warn("[Auth] Auto-register also failed:", regMsg);
        // Surface a clear, actionable message
        throw new Error(
          regMsg.toLowerCase().includes("already exists")
            ? `Account exists at ${email} but login failed. Verify backend seeding and password.`
            : `Cannot reach backend at ${api.constructor.name}. Ensure FastAPI is running and reachable over Wi-Fi.\n(${regMsg})`
        );
      }
    } finally {
      setIsLoading(false);
    }
  };

  const logout = () => {
    setUser(null);
    setToken(null);
    api.setToken(null);
  };

  const setRole = (newRole: UserRole) => {
    setRoleState(newRole);
    if (user) {
      setUser({
        ...user,
        role: newRole,
        full_name: roleProfiles[newRole].full_name,
        email: roleProfiles[newRole].email
      });
    }
  };

  return (
    <AuthContext.Provider value={{ user, token, role, login, logout, setRole, isLoading }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within an AuthProvider");
  return context;
};
