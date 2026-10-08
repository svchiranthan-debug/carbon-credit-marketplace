import React, { createContext, useContext, useState, useEffect } from "react";
import api from "../services/api";

const AuthContext = createContext(null);

export const DEMO_ACCOUNTS = {
  FARMER: {
    email: "farmer@agrocarbon.demo",
    password: "Demo@123",
    role: "FARMER",
    name: "Ramesh Kumar",
    org: "Kaveri Smallholder Farmers Cooperative"
  },
  FARMER_2: {
    email: "farmer2@agrocarbon.demo",
    password: "Demo@123",
    role: "FARMER",
    name: "Lakshmi Devi",
    org: "Coorg Sustainable Growers Alliance"
  },
  BUYER: {
    email: "buyer@ecocorp.demo",
    password: "Demo@123",
    role: "BUYER",
    name: "Arun Mehta",
    org: "EcoCorp Solutions (ESG Portfolio)"
  },
  ADMIN: {
    email: "admin@agrocarbon.demo",
    password: "Demo@123",
    role: "ADMIN",
    name: "Dr. Sunita Rao",
    org: "Carbon Verification Authority"
  }
};

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    async function loadUser() {
      const token = api.getToken();
      if (token) {
        try {
          const userData = await api.getMe();
          setUser(userData);
        } catch (err) {
          console.warn("Session expired or invalid token:", err.message);
          api.setToken(null);
          setUser(null);
        }
      }
      setLoading(false);
    }
    loadUser();
  }, []);

  const login = async (email, password, role = null) => {
    setError(null);
    try {
      const res = await api.login(email, password, role);
      setUser(res.user);
      return res.user;
    } catch (err) {
      setError(err.message);
      throw err;
    }
  };

  const register = async (userData) => {
    setError(null);
    try {
      const res = await api.register(userData);
      // Section 8: Registration successful -> Continue to Login
      api.setToken(null);
      setUser(null);
      return res.user;
    } catch (err) {
      setError(err.message);
      throw err;
    }
  };

  const logout = () => {
    api.logout();
    setUser(null);
  };

  const loginDemoAccount = async (roleKey) => {
    const creds = DEMO_ACCOUNTS[roleKey];
    if (!creds) return;
    return await login(creds.email, creds.password, creds.role);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        role: user?.role || null,
        loading,
        error,
        login,
        register,
        logout,
        loginDemoAccount,
        DEMO_ACCOUNTS
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
