// Role-aware auth storage, shared by whichever persona's frontend uses it.
//
// Rationale: the company-side code used to hardcode a single localStorage
// key ("company_token"). That's fine in isolation, but once this merges
// with the student-side frontend, two different personas each need their
// own token without stepping on each other's key — and the shared Axios
// instance (api.js) needs to know *which* token to attach without being
// told explicitly on every call.
//
// The scheme: each role's token is stored under its own key
// ("auth_token_<role>"), and a separate "active role" key says which one
// is currently logged in. This assumes one active persona at a time (a
// user is logged in as a company OR a student, not both simultaneously),
// which matches how this app is used — reconcile with Xuanhua if the
// merged app ever needs simultaneous dual-login.

const ACTIVE_ROLE_KEY = "auth_active_role";
const LEGACY_COMPANY_TOKEN_KEY = "company_token"; // pre-this-file key

function tokenKey(role) {
  return `auth_token_${role}`;
}

export function getActiveRole() {
  return localStorage.getItem(ACTIVE_ROLE_KEY);
}

export function setActiveRole(role) {
  localStorage.setItem(ACTIVE_ROLE_KEY, role);
}

export function clearActiveRole() {
  localStorage.removeItem(ACTIVE_ROLE_KEY);
}

export function getToken(role) {
  if (!role) return null;
  return localStorage.getItem(tokenKey(role));
}

export function setToken(role, token) {
  localStorage.setItem(tokenKey(role), token);
}

export function clearToken(role) {
  if (!role) return;
  localStorage.removeItem(tokenKey(role));
}

// Where each role's frontend sends an unauthenticated user. Add an entry
// here when the student-side login route is known at merge time.
const LOGIN_PATH_BY_ROLE = {
  company: "/company/login",
};

export function loginPathForRole(role) {
  return LOGIN_PATH_BY_ROLE[role] || "/company/login";
}

// One-time migration so an already-logged-in company user (from before
// this file existed) isn't silently signed out when this change ships.
(function migrateLegacyCompanyToken() {
  const legacy = localStorage.getItem(LEGACY_COMPANY_TOKEN_KEY);
  if (legacy) {
    if (!getToken("company")) {
      setToken("company", legacy);
      setActiveRole("company");
    }
    localStorage.removeItem(LEGACY_COMPANY_TOKEN_KEY);
  }
})();
