import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";

import { AuthProvider } from "./context/AuthContext";
import NavBar from "./components/NavBar";
import ProtectedRoute from "./components/ProtectedRoute";

import CompanyLogin from "./pages/company/Login";
import CompanySignup from "./pages/company/Signup";
import CompanyDashboard from "./pages/company/Dashboard";
import CompanyProfile from "./pages/company/Profile";
import Applicants from "./pages/company/Applicants";
import StudentProfile from "./pages/company/StudentProfile";
import Events from "./pages/company/Events";
import StudentsSearch from "./pages/company/StudentsSearch";
import Assistant from "./pages/company/Assistant";


function AppLayout() {
  const location = useLocation();

  const hideNav =
    location.pathname === "/company/login" ||
    location.pathname === "/company/signup";

  return (
    <>
      {!hideNav && <NavBar />}

      <main>
        <Routes>
          <Route
            path="/"
            element={<Navigate to="/company/dashboard" replace />}
          />

          <Route
            path="/company/login"
            element={<CompanyLogin />}
          />

          <Route
            path="/company/signup"
            element={<CompanySignup />}
          />

          <Route
            path="/company/dashboard"
            element={
              <ProtectedRoute>
                <CompanyDashboard />
              </ProtectedRoute>
            }
          />

          <Route
            path="/company/jobs/:jobId/applicants"
            element={
              <ProtectedRoute>
                <Applicants />
              </ProtectedRoute>
            }
          />

          <Route
            path="/company/students/:studentId"
            element={
              <ProtectedRoute>
                <StudentProfile />
              </ProtectedRoute>
            }
          />

          <Route
            path="/company/events"
            element={
              <ProtectedRoute>
                <Events />
              </ProtectedRoute>
            }
          />

          <Route
            path="/company/students"
            element={
              <ProtectedRoute>
                <StudentsSearch />
              </ProtectedRoute>
            }
          />

          <Route
            path="/company/profile"
            element={
              <ProtectedRoute>
                <CompanyProfile />
              </ProtectedRoute>
            }
          />

          <Route
            path="/company/assistant"
            element={
              <ProtectedRoute>
                <Assistant />
              </ProtectedRoute>
            }
          />
        </Routes>
      </main>
    </>
  );
}


export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppLayout />
      </AuthProvider>
    </BrowserRouter>
  );
}