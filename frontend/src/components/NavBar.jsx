import { NavLink, Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function NavBar() {
  const { logout } = useAuth();

  const navItems = [
    {
      label: "Jobs",
      path: "/company/dashboard",
      icon: "▣",
    },
    {
      label: "Events",
      path: "/company/events",
      icon: "□",
    },
    {
      label: "Students",
      path: "/company/students",
      icon: "♙",
    },
    {
      label: "Profile",
      path: "/company/profile",
      icon: "♢",
    },
    {
      label: "AI Assistant",
      path: "/company/assistant",
      icon: "✦",
    },
  ];

  return (
    <aside className="handshake-sidebar">
      <div className="sidebar-top">
        <Link
          to="/company/dashboard"
          className="sidebar-brand"
        >
          <div className="sidebar-brand-mark">
            H
          </div>

          <div className="sidebar-brand-text">
            <strong>Handshake</strong>
            <span>Recruiter</span>
          </div>
        </Link>

        <nav className="sidebar-navigation">
          <div className="sidebar-section-label">
            WORKSPACE
          </div>

          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                `sidebar-nav-item ${
                  isActive ? "active" : ""
                }`
              }
            >
              <span className="sidebar-nav-icon">
                {item.icon}
              </span>

              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>
      </div>

      <div className="sidebar-bottom">
        <div className="sidebar-company-card">
          <div className="sidebar-company-avatar">
            C
          </div>

          <div>
            <strong>Company Portal</strong>
            <span>Recruiter account</span>
          </div>
        </div>

        <button
          type="button"
          className="sidebar-logout"
          onClick={logout}
        >
          <span>↪</span>
          Log out
        </button>
      </div>
    </aside>
  );
}