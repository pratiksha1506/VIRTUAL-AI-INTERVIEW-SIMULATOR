/**
 * api.js — Unified API Client for AI Mock Interview Simulator
 * Connects frontend to the secure FastAPI backend with automatic session management.
 */
const Api = (function () {
  const BASE_URL = ""; // Same-origin when served via FastAPI on port 8000
  const TOKEN_KEY = "ai_interview_token_v2";

  function getToken() {
    return localStorage.getItem(TOKEN_KEY) || sessionStorage.getItem(TOKEN_KEY);
  }

  function setToken(token) {
    if (token) {
      localStorage.setItem(TOKEN_KEY, token);
      sessionStorage.setItem(TOKEN_KEY, token);
    }
  }

  function clearToken() {
    localStorage.removeItem(TOKEN_KEY);
    sessionStorage.removeItem(TOKEN_KEY);
  }

  async function request(endpoint, options = {}) {
    options.credentials = "include";
    options.headers = options.headers || {};

    const token = getToken();
    if (token) {
      options.headers["Authorization"] = `Bearer ${token}`;
    }

    if (options.body && !(options.body instanceof FormData)) {
      options.headers["Content-Type"] = "application/json";
      if (typeof options.body !== "string") {
        options.body = JSON.stringify(options.body);
      }
    }

    let res;
    try {
      res = await fetch(BASE_URL + endpoint, options);
    } catch (netErr) {
      throw new Error("Unable to reach backend server. Please make sure the FastAPI server is running.");
    }

    const contentType = res.headers.get("content-type") || "";
    let data;
    if (contentType.includes("application/json")) {
      data = await res.json();
    } else {
      data = { text: await res.text() };
    }

    if (!res.ok) {
      const err = new Error(data.detail || data.error || "An unexpected server error occurred.");
      err.status = res.status;
      err.data = data;
      throw err;
    }
    return data;
  }

  return {
    getToken,
    setToken,
    clearToken,

    // Auth
    async register(name, email, password) {
      const res = await request("/api/auth/register", { method: "POST", body: { name, email, password } });
      if (res.token) setToken(res.token);
      return res;
    },
    async login(email, password) {
      const res = await request("/api/auth/login", { method: "POST", body: { email, password } });
      if (res.token) setToken(res.token);
      return res;
    },
    async adminLogin(email, password) {
      const res = await request("/api/auth/admin-login", { method: "POST", body: { email, password } });
      if (res.token) setToken(res.token);
      return res;
    },
    async getMe() {
      try {
        const res = await request("/api/auth/me", { method: "GET" });
        return res.user;
      } catch (e) {
        return null;
      }
    },
    async logout() {
      try {
        await request("/api/auth/logout", { method: "POST" });
      } catch (e) {}
      clearToken();
      window.location.href = "index.html";
    },
    async requireAuth(expectedRole = null) {
      const user = await this.getMe();
      if (!user) {
        window.location.href = expectedRole === "admin" ? "login-admin.html" : "login-candidate.html";
        return null;
      }
      if (expectedRole && user.role !== expectedRole) {
        window.location.href = user.role === "admin" ? "admin-dashboard.html" : "candidate-dashboard.html";
        return null;
      }
      return user;
    },

    // Candidate
    async getCandidateDashboard() {
      return request("/api/candidate/dashboard", { method: "GET" });
    },
    async getCandidateHistory() {
      return request("/api/candidate/history", { method: "GET" });
    },

    // Interviews
    async uploadResume(formData) {
      return request("/api/interviews/upload-resume", { method: "POST", body: formData });
    },
    async createInterview(payload) {
      return request("/api/interviews", { method: "POST", body: payload });
    },
    async startInterview(interviewId) {
      return request(`/api/interviews/${interviewId}/start`, { method: "POST" });
    },
    async getInterview(interviewId) {
      return request(`/api/interviews/${interviewId}`, { method: "GET" });
    },
    async submitResponse(interviewId, formData) {
      return request(`/api/interviews/${interviewId}/responses`, { method: "POST", body: formData });
    },
    async finishInterview(interviewId) {
      return request(`/api/interviews/${interviewId}/finish`, { method: "POST" });
    },
    async getReport(interviewId) {
      return request(`/api/interviews/${interviewId}/report`, { method: "GET" });
    },

    // Admin
    async getAdminDashboard() {
      return request("/api/admin/dashboard", { method: "GET" });
    },
    async getAdminCandidates() {
      return request("/api/admin/candidates", { method: "GET" });
    },
    async getAdminCandidate(candidateId) {
      return request(`/api/admin/candidate/${candidateId}`, { method: "GET" });
    },
    async getAdminHistory(params = {}) {
      const q = new URLSearchParams();
      if (params.status) q.append("status", params.status);
      if (params.search) q.append("search", params.search);
      if (params.candidate_id) q.append("candidate_id", params.candidate_id);
      const queryStr = q.toString() ? `?${q.toString()}` : "";
      return request(`/api/admin/history${queryStr}`, { method: "GET" });
    },
    async getAdminInterviewAudit(interviewId) {
      return request(`/api/admin/interview/${interviewId}`, { method: "GET" });
    },
    async clearAdminHistory() {
      return request("/api/admin/clear-history", { method: "POST" });
    },
    async scheduleInterview(payload) {
      return request("/api/admin/schedule", { method: "POST", body: payload });
    },
    async cancelInterview(interviewId) {
      return request(`/api/admin/cancel/${interviewId}`, { method: "POST" });
    },
    async getAdminSettings() {
      return request("/api/admin/settings", { method: "GET" });
    },
    async updateAdminSettings(payload) {
      return request("/api/admin/settings", { method: "POST", body: payload });
    },

    // System Health
    async getHealth() {
      return request("/api/health", { method: "GET" });
    }
  };
})();

window.Api = Api;
