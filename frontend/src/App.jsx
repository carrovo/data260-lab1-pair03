import {
  Navigate,
  Outlet,
  Route,
  Routes,
  useLocation,
} from 'react-router-dom'
import ApplicationsPage from './pages/ApplicationsPage'
import AssistantPage from './pages/AssistantPage'
import EventDetailPage from './pages/EventDetailPage'
import EventsPage from './pages/EventsPage'
import SignupPage from './pages/SignupPage'
import LoginPage from './pages/LoginPage'
import JobDetailPage from './pages/JobDetailPage'
import JobsPage from './pages/JobsPage'
import RegistrationsPage from './pages/RegistrationsPage'
import CompanyApplicants from './pages/company/Applicants'
import CompanyDashboard from './pages/company/Dashboard'
import CompanyEvents from './pages/company/Events'
import CompanyLogin from './pages/company/Login'
import CompanyProfile from './pages/company/Profile'
import CompanySignup from './pages/company/Signup'
import CompanyStudentProfile from './pages/company/StudentProfile'
import CompanyStudentsSearch from './pages/company/StudentsSearch'
import CompanySidebar from './components/CompanySidebar'
import StudentSidebar from './components/StudentSidebar'
import useAuth from './auth/useAuth'
import { getToken } from './services/authStorage'
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

function CompanyGuestOnlyRoute() {
  const location = useLocation()
  const returnLocation = location.state?.from
  const returnPath = returnLocation?.pathname?.startsWith('/company/')
    ? `${returnLocation.pathname}${returnLocation.search || ''}`
    : '/company/dashboard'

  return getToken('company') ? (
    <Navigate to={returnPath} replace />
  ) : (
    <Outlet />
  )
}

function CompanyProtectedRoute() {
  const location = useLocation()

  return getToken('company') ? (
    <Outlet />
  ) : (
    <Navigate to="/company/login" replace state={{ from: location }} />
  )
}

function App() {
  const { initializing } = useAuth()
  const location = useLocation()
  const isStudentAuthPage =
    location.pathname === '/login' || location.pathname === '/signup'
  const isCompanyPath =
    location.pathname === '/company' ||
    location.pathname.startsWith('/company/')
  const isCompanyAuthPage =
    location.pathname === '/company/login' ||
    location.pathname === '/company/signup'
  const isAuthPage = isStudentAuthPage || isCompanyAuthPage
  const showCompanySidebar =
    isCompanyPath && !isCompanyAuthPage && Boolean(getToken('company'))

  if (initializing && !isCompanyPath) {
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
      {!isCompanyPath && !isStudentAuthPage && <StudentSidebar />}
      {showCompanySidebar && <CompanySidebar />}

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
            <Route path="/assistant" element={<AssistantPage />} />
          </Route>
          <Route element={<GuestOnlyRoute />}>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/signup" element={<SignupPage />} />
          </Route>
          <Route
            path="/company"
            element={(
              <Navigate
                to={getToken('company')
                  ? '/company/dashboard'
                  : '/company/login'}
                replace
              />
            )}
          />
          <Route element={<CompanyGuestOnlyRoute />}>
            <Route path="/company/login" element={<CompanyLogin />} />
            <Route path="/company/signup" element={<CompanySignup />} />
          </Route>
          <Route element={<CompanyProtectedRoute />}>
            <Route
              path="/company/dashboard"
              element={<CompanyDashboard />}
            />
            <Route
              path="/company/jobs/:jobId/applicants"
              element={<CompanyApplicants />}
            />
            <Route path="/company/events" element={<CompanyEvents />} />
            <Route
              path="/company/students"
              element={<CompanyStudentsSearch />}
            />
            <Route
              path="/company/students/:studentId"
              element={<CompanyStudentProfile />}
            />
            <Route path="/company/profile" element={<CompanyProfile />} />
          </Route>
        </Routes>
      </main>
    </div>
  )
}

export default App
