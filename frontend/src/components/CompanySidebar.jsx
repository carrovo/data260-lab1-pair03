import { Link, NavLink, useNavigate } from 'react-router-dom'
import {
  clearActiveRole,
  clearToken,
  getActiveRole,
} from '../services/authStorage'


const companyNavigation = [
  { label: 'Dashboard', path: '/company/dashboard', icon: '▣' },
  { label: 'Events', path: '/company/events', icon: '□' },
  { label: 'Students', path: '/company/students', icon: '⌕' },
  { label: 'Profile', path: '/company/profile', icon: '○' },
]

function CompanySidebar() {
  const navigate = useNavigate()

  function logout() {
    clearToken('company')
    if (getActiveRole() === 'company') {
      clearActiveRole()
    }
    navigate('/company/login', { replace: true })
  }

  return (
    <aside className="student-sidebar company-sidebar">
      <div className="sidebar-top">
        <Link className="sidebar-brand" to="/company/dashboard">
          <span className="sidebar-brand-mark" aria-hidden="true">
            H
          </span>
          <span className="sidebar-brand-text">
            <strong>Handshake</strong>
            <span>Company</span>
          </span>
        </Link>

        <nav className="sidebar-navigation" aria-label="Company portal">
          <span className="sidebar-section-label">RECRUITING</span>
          {companyNavigation.map((item) => (
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
        <div className="sidebar-student-card">
          <span className="sidebar-student-avatar" aria-hidden="true">
            C
          </span>
          <span className="sidebar-student-details">
            <strong>Company workspace</strong>
            <span>Recruiter account</span>
          </span>
        </div>
        <button className="sidebar-logout" type="button" onClick={logout}>
          <span aria-hidden="true">↪</span>
          <span>Log out</span>
        </button>
      </div>
    </aside>
  )
}

export default CompanySidebar
