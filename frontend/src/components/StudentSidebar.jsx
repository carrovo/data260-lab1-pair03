import { Link, NavLink } from 'react-router-dom'
import useAuth from '../auth/useAuth'


const publicNavigation = [
  { label: 'Jobs', path: '/jobs', icon: '▣' },
  { label: 'Events', path: '/events', icon: '□' },
]

const studentNavigation = [
  { label: 'Applications', path: '/applications', icon: '≡' },
  { label: 'My Registrations', path: '/registrations', icon: '✓' },
]

function StudentSidebar() {
  const { isAuthenticated, logout, student } = useAuth()
  const navigation = isAuthenticated
    ? [...publicNavigation, ...studentNavigation]
    : publicNavigation
  const studentInitial = student?.full_name?.charAt(0).toUpperCase() || 'S'

  return (
    <aside
      className={`student-sidebar${isAuthenticated ? '' : ' sidebar-guest'}`}
    >
      <div className="sidebar-top">
        <Link className="sidebar-brand" to="/jobs">
          <span className="sidebar-brand-mark" aria-hidden="true">
            H
          </span>
          <span className="sidebar-brand-text">
            <strong>Handshake</strong>
            <span>Student</span>
          </span>
        </Link>

        <nav className="sidebar-navigation" aria-label="Student portal">
          <span className="sidebar-section-label">EXPLORE</span>
          {navigation.map((item) => (
            <NavLink
              className={({ isActive }) =>
                `sidebar-nav-item${isActive ? ' active' : ''}`
              }
              key={item.path}
              to={item.path}
            >
              <span className="sidebar-nav-icon" aria-hidden="true">
                {item.icon}
              </span>
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>
      </div>

      <div className="sidebar-bottom">
        {isAuthenticated ? (
          <>
            <div className="sidebar-student-card">
              <span className="sidebar-student-avatar" aria-hidden="true">
                {studentInitial}
              </span>
              <span className="sidebar-student-details">
                <strong>{student.full_name}</strong>
                <span>Student account</span>
              </span>
            </div>
            <button
              className="sidebar-logout"
              type="button"
              onClick={logout}
            >
              <span aria-hidden="true">↪</span>
              <span>Log out</span>
            </button>
          </>
        ) : (
          <div className="sidebar-guest-actions">
            <Link className="sidebar-login-link" to="/login">
              Log in
            </Link>
            <Link className="sidebar-signup-link" to="/signup">
              Create account
            </Link>
          </div>
        )}
      </div>
    </aside>
  )
}

export default StudentSidebar
