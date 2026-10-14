import { Link } from 'react-router-dom'


function AuthShell({
  alternateText,
  alternateLinkText,
  alternateTo,
  children,
  description,
  eyebrow,
  title,
}) {
  return (
    <div className="auth-page">
      <div className="auth-shell">
        <section className="auth-hero">
          <div>
            <span className="auth-hero-badge">Student Portal</span>
            <h1>Build your next chapter with the right opportunity.</h1>
            <p className="auth-hero-description">
              Discover roles, meet employers, and keep every application
              and event registration organized in one place.
            </p>

            <div className="auth-hero-features">
              <div><span>✓</span>Search jobs and internships</div>
              <div><span>✓</span>Apply with your PDF resume</div>
              <div><span>✓</span>Discover and register for events</div>
            </div>
          </div>
          <p className="auth-hero-footer">
            One workspace for your career journey.
          </p>
        </section>

        <section className="auth-panel">
          <Link className="auth-brand" to="/jobs">
            <span className="auth-brand-mark" aria-hidden="true">H</span>
            <span>
              <strong>Handshake</strong>
              <small>Student Portal</small>
            </span>
          </Link>

          <div className="auth-form-wrapper">
            <div className="auth-heading">
              <p className="page-eyebrow">{eyebrow}</p>
              <h2>{title}</h2>
              <p>{description}</p>
            </div>

            {children}

            <div className="auth-divider">
              <span>{alternateText}</span>
            </div>
            <Link className="auth-alternate-link" to={alternateTo}>
              {alternateLinkText}
            </Link>
          </div>
        </section>
      </div>
    </div>
  )
}

export default AuthShell
