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
    <aside className="company-sidebar">
      <div className="company-sidebar-top">
        <Link className="company-sidebar-brand" to="/company/dashboard">
          <span className="company-sidebar-brand-mark" aria-hidden="true">
            H
          </span>
          <span className="company-sidebar-brand-text">
            <strong>Handshake</strong>
            <span>Company</span>
          </span>
        </Link>

        <nav className="company-sidebar-navigation" aria-label="Company portal">
          <span className="company-sidebar-section-label">RECRUITING</span>
          {companyNavigation.map((item) => (
            <NavLink
              className={({ isActive }) =>
                `company-sidebar-nav-item${isActive ? ' active' : ''}`
              }
              key={item.path}
              to={item.path}
            >
              <span className="company-sidebar-nav-icon" aria-hidden="true">
                {item.icon}
              </span>
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>
      </div>

      <div className="company-sidebar-bottom">
        <div className="company-sidebar-account">
          <span className="company-sidebar-avatar" aria-hidden="true">
            C
          </span>
          <span className="company-sidebar-details">
            <strong>Company workspace</strong>
            <span>Recruiter account</span>
          </span>
        </div>
        <button className="company-sidebar-logout" type="button" onClick={logout}>
          <span aria-hidden="true">↪</span>
          <span>Log out</span>
        </button>
      </div>
    </aside>
  )
}

export default CompanySidebar
