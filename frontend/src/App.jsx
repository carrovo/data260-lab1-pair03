import {
  NavLink,
  Navigate,
  Outlet,
  Route,
  Routes,
  useLocation,
} from 'react-router-dom'
import ApplicationsPage from './pages/ApplicationsPage'
import SignupPage from './pages/SignupPage'
import LoginPage from './pages/LoginPage'
import JobDetailPage from './pages/JobDetailPage'
import JobsPage from './pages/JobsPage'
import useAuth from './auth/useAuth'
import './App.css'

function GuestOnlyRoute() {
  const { isAuthenticated } = useAuth()
  const location = useLocation()

  const returnLocation = location.state?.from
  const returnPath = returnLocation?.pathname
    ? `${returnLocation.pathname}${returnLocation.search || ''}`
    : '/jobs'

  return isAuthenticated ? <Navigate to={returnPath} replace /> : <Outlet />
}

function ProtectedRoute() {
  const { isAuthenticated } = useAuth()
  const location = useLocation()

  return isAuthenticated ? (
    <Outlet />
  ) : (
    <Navigate to="/login" replace state={{ from: location }} />
  )
}

function App() {
  const { initializing, isAuthenticated, logout, student } = useAuth()

  if (initializing) {
    return (
      <div className="session-loading" role="status">
        Restoring your session...
      </div>
    )
  }

  return (
    <div className="app-shell">
      <header className="site-header">
        <NavLink className="brand" to="/jobs">
          Career Portal
        </NavLink>

        <nav>
          <NavLink className="nav-link" to="/jobs">
            Jobs
          </NavLink>
          {isAuthenticated ? (
            <div className="auth-nav">
              <NavLink className="nav-link" to="/applications">
                Applications
              </NavLink>
              <span className="student-name">{student.full_name}</span>
              <button
                className="nav-button"
                type="button"
                onClick={logout}
              >
                Logout
              </button>
            </div>
          ) : (
            <>
              <NavLink className="nav-link" to="/login">
                Login
              </NavLink>
              <NavLink className="nav-link" to="/signup">
                Sign Up
              </NavLink>
            </>
          )}
        </nav>
      </header>

      <main className="main-content">
        <Routes>
          <Route path="/" element={<Navigate to="/jobs" replace />} />
          <Route path="/jobs" element={<JobsPage />} />
          <Route path="/jobs/:jobId" element={<JobDetailPage />} />
          <Route element={<ProtectedRoute />}>
            <Route path="/applications" element={<ApplicationsPage />} />
          </Route>
          <Route element={<GuestOnlyRoute />}>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/signup" element={<SignupPage />} />
          </Route>
        </Routes>
      </main>
    </div>
  )
}

export default App
