import {
  Navigate,
  Outlet,
  Route,
  Routes,
  useLocation,
} from 'react-router-dom'
import ApplicationsPage from './pages/ApplicationsPage'
import EventDetailPage from './pages/EventDetailPage'
import EventsPage from './pages/EventsPage'
import SignupPage from './pages/SignupPage'
import LoginPage from './pages/LoginPage'
import JobDetailPage from './pages/JobDetailPage'
import JobsPage from './pages/JobsPage'
import RegistrationsPage from './pages/RegistrationsPage'
import StudentSidebar from './components/StudentSidebar'
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
  const { initializing } = useAuth()
  const location = useLocation()
  const isAuthPage =
    location.pathname === '/login' || location.pathname === '/signup'

  if (initializing) {
    return (
      <div className="session-loading" role="status">
        <span className="session-loading-mark" aria-hidden="true">H</span>
        <strong>Handshake</strong>
        <span>Restoring your student session...</span>
      </div>
    )
  }

  return (
    <div className="app-shell">
      {!isAuthPage && <StudentSidebar />}

      <main className={isAuthPage ? 'auth-main' : 'workspace-main'}>
        <Routes>
          <Route path="/" element={<Navigate to="/jobs" replace />} />
          <Route path="/jobs" element={<JobsPage />} />
          <Route path="/jobs/:jobId" element={<JobDetailPage />} />
          <Route path="/events" element={<EventsPage />} />
          <Route path="/events/:eventId" element={<EventDetailPage />} />
          <Route element={<ProtectedRoute />}>
            <Route path="/applications" element={<ApplicationsPage />} />
            <Route path="/registrations" element={<RegistrationsPage />} />
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
