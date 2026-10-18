import { createContext, useContext, useState, useCallback } from "react";
import api from "../services/api";
import {
  getToken,
  setToken as storeToken,
  clearToken,
  setActiveRole,
  clearActiveRole,
} from "../services/authStorage";

// This provider is the company persona's auth context. The student-side
// equivalent (once merged) would be its own AuthProvider with ROLE =
// "student" and its own endpoints — authStorage.js keeps the two from
// colliding in localStorage.
const ROLE = "company";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => getToken(ROLE));

  const login = useCallback(async (email, password) => {
    const { data } = await api.post("/companies/auth/login", { email, password });
    storeToken(ROLE, data.access_token);
    setActiveRole(ROLE);
    setToken(data.access_token);
    return data;
  }, []);

  const signup = useCallback(async (payload) => {
    const { data } = await api.post("/companies/auth/signup", payload);
    storeToken(ROLE, data.access_token);
    setActiveRole(ROLE);
    setToken(data.access_token);
    return data;
  }, []);

  const logout = useCallback(() => {
    clearToken(ROLE);
    clearActiveRole();
    setToken(null);
  }, []);

  return (
    <AuthContext.Provider value={{ token, isAuthenticated: !!token, login, signup, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
