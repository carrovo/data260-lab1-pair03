import axios from "axios";
import { getActiveRole, getToken, clearToken, clearActiveRole, loginPathForRole } from "./authStorage";

// Single shared Axios instance — all requests go through here so auth
// headers and error handling stay in one place. Relative "/api" paths are
// proxied to the FastAPI backend by vite.config.js in dev, and should be
// pointed at the real backend origin in a production build.
//
// Auth is role-aware (see authStorage.js) rather than hardcoded to the
// company persona, so this same instance can be reused once the
// student-side frontend merges in: each persona keeps its own token, and
// whichever one is "active" is the one attached to outgoing requests.
const api = axios.create({
  baseURL: "/api",
  headers: { "Content-Type": "application/json" },
});

api.interceptors.request.use((config) => {
  const role = getActiveRole();
  const token = getToken(role);
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      const role = getActiveRole();
      clearToken(role);
      clearActiveRole();
      const loginPath = loginPathForRole(role);
      if (window.location.pathname !== loginPath) {
        window.location.href = loginPath;
      }
    }
    return Promise.reject(error);
  }
);

export default api;
