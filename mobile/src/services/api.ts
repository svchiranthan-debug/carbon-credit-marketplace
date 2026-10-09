import Constants from "expo-constants";
import { Platform } from "react-native";

/**
 * Development API address resolution (first match wins):
 *  1. EXPO_PUBLIC_API_URL (set in mobile/.env), e.g. http://192.168.1.20:8000/api
 *  2. The IP of the computer running Metro (Expo Go on a physical phone reaches the
 *     backend on that same machine, port 8000)
 *  3. Emulator/simulator defaults: Android emulator -> 10.0.2.2, iOS simulator / web -> localhost
 * "localhost" is never used for a physical device, because it would point at the phone itself.
 */
function resolveApiBaseUrl(): string {
  const fromEnv = process.env.EXPO_PUBLIC_API_URL;
  if (fromEnv) {
    return fromEnv.replace(/\/+$/, "");
  }

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

  if (Platform.OS === "android") {
    return "http://10.0.2.2:8000/api";
  }
  return "http://localhost:8000/api";
}

function formatErrorDetail(detail: any, status: number): string {
  if (!detail) return `Request failed (HTTP ${status})`;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d) => {
        const field = Array.isArray(d.loc) ? d.loc.filter((p: string) => p !== "body").join(".") : "";
        const msg = String(d.msg || "").replace(/^Value error, /, "");
        return field ? `${field}: ${msg}` : msg;
      })
      .join("; ");
  }
  return JSON.stringify(detail);
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

    let res: Response;
    try {
      res = await fetch(`${API_BASE_URL}${endpoint}`, { ...options, headers });
    } catch {
      throw new Error(
        `Cannot reach the backend at ${API_BASE_URL}. Check that FastAPI is running with --host 0.0.0.0 ` +
          `and that the phone and computer are on the same network.`
      );
    }

    if (!res.ok) {
      let detail: any = null;
      try {
        detail = (await res.json()).detail;
      } catch {
        // non-JSON error body
      }
      throw new Error(formatErrorDetail(detail, res.status));
    }

    return res.json();
  }

  // Auth
  async login(email: string, password: string) {
    return this.request("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password })
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

  async listPhotos(plantationId: number) {
    return this.request(`/plantations/${plantationId}/photos`);
  }

  // Multi-Modal Verification
  async getVerification(plantationId: number) {
    return this.request(`/plantations/${plantationId}/verification`);
  }

  async runVerification(plantationId: number) {
    return this.request(`/plantations/${plantationId}/verify`, { method: "POST" });
  }

  // Carbon Assets & Marketplace
  async getFarmerCredits() {
    return this.request("/marketplace/my-credits");
  }

  async getMarketplaceCredits() {
    return this.request("/marketplace/credits");
  }

  async acquireCredit(creditId: string) {
    // Whole-lot purchase; prototype only, no payment is processed.
    return this.request(`/marketplace/credits/${creditId}/purchase`, { method: "POST", body: JSON.stringify({}) });
  }

  async getBuyerPortfolio() {
    return this.request("/marketplace/my-credits");
  }

  async retireCredit(creditId: string) {
    return this.request(`/marketplace/credits/${creditId}/retire`, { method: "POST" });
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
