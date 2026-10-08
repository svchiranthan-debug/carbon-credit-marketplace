import Constants from "expo-constants";
import { Platform } from "react-native";

// Mac LAN IP verified via network configuration for physical device testing
export const MAC_LAN_IP = "172.20.10.3";

function resolveApiBaseUrl(): string {
  // 1. Explicit env override if set
  if (process.env.EXPO_PUBLIC_API_URL) {
    return process.env.EXPO_PUBLIC_API_URL;
  }

  // 2. Extract host from Expo Metro debugger host (auto-detects Mac LAN IP when iPhone connects to Metro)
  const hostUri =
    Constants.expoConfig?.hostUri ||
    (Constants as any).manifest?.debuggerHost ||
    (Constants as any).manifest2?.extra?.expoGo?.debuggerHost;

  if (hostUri) {
    const ip = hostUri.split(":")[0];
    if (ip && ip !== "localhost" && ip !== "127.0.0.1") {
      return `http://${ip}:8000/api`;
    }
  }

  // 3. Physical iPhone / real device or iOS simulator connecting to local network
  if (Platform.OS === "android") {
    return `http://${MAC_LAN_IP}:8000/api`;
  }

  return `http://${MAC_LAN_IP}:8000/api`;
}

export const API_BASE_URL = resolveApiBaseUrl();

class MobileApiClient {
  private token: string | null = null;

  setToken(token: string | null) {
    this.token = token;
  }

  getToken() {
    return this.token;
  }

  private async request(endpoint: string, options: RequestInit = {}) {
    const headers: Record<string, string> = {
      ...(options.headers as Record<string, string> || {})
    };

    if (this.token) {
      headers["Authorization"] = `Bearer ${this.token}`;
    }

    if (!headers["Content-Type"] && !(options.body instanceof FormData)) {
      headers["Content-Type"] = "application/json";
    }

    const method = options.method || "GET";
    console.log(`[Mobile API] -> ${method} ${API_BASE_URL}${endpoint}`);

    const res = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      headers
    });

    if (!res.ok) {
      let msg = "Network error";
      try {
        const errJson = await res.json();
        msg = errJson.detail || JSON.stringify(errJson);
      } catch {
        msg = `HTTP ${res.status}: ${res.statusText}`;
      }
      console.error(`[Mobile API] Error on ${endpoint}: HTTP ${res.status} - ${msg}`);
      throw new Error(msg);
    }

    return res.json();
  }

  // Auth
  async login(email: string, role: string) {
    return this.request("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password: "Demo@123", role })
    });
  }

  async register(full_name: string, email: string, role: string) {
    return this.request("/auth/register", {
      method: "POST",
      body: JSON.stringify({
        full_name,
        email,
        password: "Demo@123",
        role
      })
    });
  }

  // Plantations
  async getPlantations() {
    return this.request("/plantations");
  }

  async createPlantation(data: any) {
    return this.request("/plantations", {
      method: "POST",
      body: JSON.stringify(data)
    });
  }

  async uploadPlantationImage(plantationId: number, imageUri: string) {
    const formData = new FormData();
    let filename = imageUri.split("/").pop() || `evidence_${Date.now()}.jpg`;
    if (!filename.includes(".")) {
      filename = `${filename}.jpg`;
    }
    const match = /\.(\w+)$/.exec(filename);
    const type = match ? `image/${match[1].toLowerCase()}` : `image/jpeg`;

    formData.append("file", {
      uri: imageUri,
      name: filename,
      type
    } as any);

    return this.request(`/plantations/${plantationId}/evidence`, {
      method: "POST",
      body: formData
    });
  }

  // Multi-Modal Verification
  async getVerification(plantationId: number) {
    return this.request(`/plantations/${plantationId}/verification`);
  }

  async runVerification(plantationId: number, groundImagePath?: string, socSamplePct?: number) {
    if (groundImagePath !== undefined || socSamplePct !== undefined) {
      return this.request(`/verification/run`, {
        method: "POST",
        body: JSON.stringify({
          plantation_id: plantationId,
          ground_image_path: groundImagePath,
          soc_sample_pct: socSamplePct
        })
      });
    }
    return this.request(`/plantations/${plantationId}/verify`, {
      method: "POST"
    });
  }

  // Carbon Assets & Marketplace
  async getFarmerCredits() {
    return this.request("/marketplace/my-credits");
  }

  async getMarketplaceCredits() {
    return this.request("/marketplace/credits");
  }

  async acquireCredit(creditId: string) {
    return this.request(`/marketplace/credits/${creditId}/purchase`, {
      method: "POST",
      body: JSON.stringify({ payment_method: "ESCROW_INR" })
    });
  }

  async getBuyerPortfolio() {
    return this.request("/marketplace/my-credits");
  }

  async retireCredit(creditId: string, reason: string) {
    return this.request(`/marketplace/credits/${creditId}/retire`, {
      method: "POST",
      body: JSON.stringify({ retirement_beneficiary: reason })
    });
  }

  // Auditor Queue
  async getAuditorQueue() {
    return this.request("/admin/verifications");
  }

  async submitAuditorDecision(verificationId: string, decision: string, notes: string) {
    return this.request(`/admin/verifications/${verificationId}/decision`, {
      method: "POST",
      body: JSON.stringify({ decision, notes })
    });
  }
}

export const api = new MobileApiClient();
