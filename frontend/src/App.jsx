import {
  NavLink,
  Navigate,
  Outlet,
  Route,
  Routes,
} from 'react-router-dom'
import SignupPage from './pages/SignupPage'
import LoginPage from './pages/LoginPage'
import JobsPage from './pages/JobsPage'
import useAuth from './auth/useAuth'
import './App.css'

function GuestOnlyRoute() {
  const { isAuthenticated } = useAuth()

  return isAuthenticated ? <Navigate to="/jobs" replace /> : <Outlet />
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
