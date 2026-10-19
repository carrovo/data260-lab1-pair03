import axios from "axios";
import {
  clearActiveRole,
  clearToken,
  getActiveRole,
  getToken,
} from "./authStorage";

// Single shared Axios instance — all requests go through here so auth
// headers and error handling stay in one place. Relative "/api" paths are
// proxied to the FastAPI backend by vite.config.js in dev, and should be
// pointed at the real backend origin in a production build.
//
// This instance is intentionally company-only. Student requests continue
// through the existing Fetch client, so each role always sends its own token
// even when both sessions exist in the same browser.
const api = axios.create({
  baseURL: "/api",
  headers: { "Content-Type": "application/json" },
});

api.interceptors.request.use((config) => {
  const token = getToken("company");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      clearToken("company");
      if (getActiveRole() === "company") {
        clearActiveRole();
      }
      if (window.location.pathname !== "/company/login") {
        window.location.href = "/company/login";
      }
    }
    return Promise.reject(error);
  }
);

export default api;
