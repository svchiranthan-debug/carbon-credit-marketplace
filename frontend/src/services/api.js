// Backend origin. Override with VITE_API_BASE_URL in frontend/.env (e.g. http://192.168.1.20:8000).
export const API_ORIGIN = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/+$/, "");
const API_BASE = `${API_ORIGIN}/api`;

/** Turns FastAPI error bodies (string or 422 validation list) into one readable message. */
function formatErrorDetail(detail, status) {
  if (!detail) return `Request failed (HTTP ${status})`;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d) => {
        const field = Array.isArray(d.loc) ? d.loc.filter((p) => p !== "body").join(".") : "";
        const msg = (d.msg || "").replace(/^Value error, /, "");
        return field ? `${field}: ${msg}` : msg;
      })
      .join("; ");
  }
  return JSON.stringify(detail);
}

export class ApiError extends Error {
  constructor(message, status, isNetworkError = false) {
    super(message);
    this.status = status;
    this.isNetworkError = isNetworkError;
  }
}

class ApiService {
  getToken() {
    return localStorage.getItem("agrocarbon_token");
  }

  setToken(token) {
    if (token) {
      localStorage.setItem("agrocarbon_token", token);
    } else {
      localStorage.removeItem("agrocarbon_token");
    }
  }

  async request(endpoint, options = {}) {
    const token = this.getToken();
    const headers = {
      ...options.headers,
    };

    if (!(options.body instanceof FormData)) {
      headers["Content-Type"] = "application/json";
    }

    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    let res;
    try {
      res = await fetch(`${API_BASE}${endpoint}`, { ...options, headers });
    } catch {
      throw new ApiError(
        `Cannot reach the backend at ${API_ORIGIN}. Make sure the FastAPI server is running.`,
        0,
        true
      );
    }

    if (res.status === 401) {
      this.setToken(null);
    }

    if (!res.ok) {
      let detail = null;
      try {
        detail = (await res.json()).detail;
      } catch {
        // non-JSON error body
      }
      throw new ApiError(formatErrorDetail(detail, res.status), res.status);
    }

    if (res.status === 204) return null;
    return await res.json();
  }

  // --- AUTH ---
  async login(email, password, role = null) {
    const data = await this.request("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password, role }),
    });
    this.setToken(data.access_token);
    return data;
  }

  async register(userData) {
    const data = await this.request("/auth/register", {
      method: "POST",
      body: JSON.stringify(userData),
    });
    this.setToken(data.access_token);
    return data;
  }

  async getMe() {
    return await this.request("/auth/me");
  }

  logout() {
    this.setToken(null);
  }

  // --- PLANTATIONS ---
  async listPlantations() {
    return await this.request("/plantations");
  }

  async getPlantation(id) {
    return await this.request(`/plantations/${id}`);
  }

  async createPlantation(plantationData) {
    return await this.request("/plantations", {
      method: "POST",
      body: JSON.stringify(plantationData),
    });
  }

  async uploadImage(file) {
    const formData = new FormData();
    formData.append("file", file);
    return await this.request("/plantations/upload-image", {
      method: "POST",
      body: formData,
    });
  }

  async updatePlantationEvidence(plantationId, evidenceData) {
    return await this.request(`/plantations/${plantationId}/evidence`, {
      method: "PUT",
      body: JSON.stringify(evidenceData),
    });
  }

  // --- VERIFICATION ENGINE ---
  async runVerification(plantationId) {
    return await this.request(`/plantations/${plantationId}/verify`, {
      method: "POST",
    });
  }

  async getPlantationVerification(plantationId) {
    return await this.request(`/plantations/${plantationId}/verification`);
  }

  async getVerificationHistory(plantationId) {
    return await this.request(`/plantations/${plantationId}/verifications`);
  }

  async getVerificationById(verificationId) {
    return await this.request(`/verifications/${verificationId}`);
  }

  // --- CARBON ENGINE ---
  async estimateCarbon(plantationId) {
    return await this.request(`/plantations/${plantationId}/carbon-estimate`, {
      method: "POST",
    });
  }

  async generateCredits(plantationId, pricePerTco2e = null) {
    return await this.request(`/plantations/${plantationId}/generate-credits`, {
      method: "POST",
      body: JSON.stringify(pricePerTco2e ? { price_per_tco2e: pricePerTco2e } : {}),
    });
  }

  // --- MARKETPLACE ---
  async listMarketplaceCredits(params = {}) {
    const query = new URLSearchParams();
    if (params.location) query.append("location", params.location);
    if (params.min_score) query.append("min_score", params.min_score);
    if (params.min_price) query.append("min_price", params.min_price);
    if (params.max_price) query.append("max_price", params.max_price);
    if (params.status) query.append("status_filter", params.status);

    const qs = query.toString();
    return await this.request(`/marketplace/credits${qs ? `?${qs}` : ""}`);
  }

  async getCreditDetail(creditId) {
    return await this.request(`/marketplace/credits/${creditId}`);
  }

  async getCredit(creditId) {
    return await this.getCreditDetail(creditId);
  }

  async getMyCredits() {
    return await this.request("/marketplace/my-credits");
  }

  // --- TRANSACTIONS & BLOCKCHAIN ---
  async purchaseCredit(creditId, quantity = null) {
    return await this.request(`/marketplace/credits/${creditId}/purchase`, {
      method: "POST",
      body: JSON.stringify(quantity ? { quantity_tco2e: quantity } : {}),
    });
  }

  async retireCredit(creditId) {
    return await this.request(`/marketplace/credits/${creditId}/retire`, {
      method: "POST",
    });
  }

  async getBlockchainRecord(creditId) {
    return await this.request(`/marketplace/credits/${creditId}/blockchain-record`);
  }

  async getBlockchainStatus() {
    return await this.request("/blockchain/status");
  }

  async listTransactions() {
    return await this.request("/transactions");
  }

  // --- ADMIN & AUDITOR ---
  async getAdminMetrics() {
    return await this.request("/admin/metrics");
  }

  async listAdminVerifications() {
    return await this.request("/admin/verifications");
  }

  async getVerificationQueue() {
    return await this.listAdminVerifications();
  }

  async updateAdminDecision(verificationId, decision, notes = "") {
    return await this.request(`/admin/verifications/${verificationId}/decision`, {
      method: "POST",
      body: JSON.stringify({ decision, notes }),
    });
  }

  async reviewVerification(verificationId, { decision, notes }) {
    return await this.updateAdminDecision(verificationId, decision, notes);
  }

  async getAuditLogs() {
    return await this.request("/admin/audit-logs");
  }
}

export function getImageUrl(path) {
  if (!path) return null;
  if (path.startsWith("http://") || path.startsWith("https://") || path.startsWith("blob:") || path.startsWith("data:")) {
    return path;
  }
  const cleanPath = path.startsWith("/") ? path : `/${path}`;
  return `${API_ORIGIN}${cleanPath}`;
}

export const api = new ApiService();
export default api;
