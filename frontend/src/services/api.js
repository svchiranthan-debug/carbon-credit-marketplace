const API_BASE = "http://localhost:8000/api";

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

    try {
      const res = await fetch(`${API_BASE}${endpoint}`, {
        ...options,
        headers,
      });

      if (res.status === 401) {
        // Clear token on 401
        this.setToken(null);
      }

      if (!res.ok) {
        let errorMsg = `HTTP Error ${res.status}`;
        try {
          const errData = await res.json();
          errorMsg = errData.detail || errorMsg;
        } catch {
          // Ignore JSON parse error on non-json response
        }
        throw new Error(errorMsg);
      }

      return await res.json();
    } catch (err) {
      console.error(`API Error on [${options.method || 'GET'} ${endpoint}]:`, err.message);
      throw err;
    }
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

  async getVerificationById(verificationId) {
    return await this.request(`/verifications/${verificationId}`);
  }

  // --- CARBON ENGINE ---
  async estimateCarbon(plantationId) {
    return await this.request(`/plantations/${plantationId}/carbon-estimate`, {
      method: "POST",
    });
  }

  async generateCredits(plantationId, pricePerTco2e = 1500) {
    return await this.request(`/plantations/${plantationId}/generate-credits`, {
      method: "POST",
      body: JSON.stringify({ price_per_tco2e: pricePerTco2e }),
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
      body: JSON.stringify({ quantity_tco2e: quantity }),
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
  return `http://localhost:8000${cleanPath}`;
}

export const api = new ApiService();
export default api;
