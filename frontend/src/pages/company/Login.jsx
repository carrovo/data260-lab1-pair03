import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import ErrorMessage from "../../components/ErrorMessage";
import Loading from "../../components/Loading";

export default function CompanyLogin() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ email: "", password: "" });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      await login(form.email, form.password);
      navigate("/company/dashboard");
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-shell">
        <section className="login-hero">
          <div>
            <span className="hero-badge">Recruiter Portal</span>

            <h1>
              Connect with the talent
              <br />
              shaping what comes next.
            </h1>

            <p className="hero-description">
              Discover students, publish opportunities, manage applicants,
              and organize recruiting events from one workspace.
            </p>

            <div className="hero-features">
              <div className="hero-feature">
                <span className="feature-icon">✓</span>
                <div>
                  <strong>Publish opportunities</strong>
                  <p>Create and manage job postings in one place.</p>
                </div>
              </div>

              <div className="hero-feature">
                <span className="feature-icon">✓</span>
                <div>
                  <strong>Review applicants</strong>
                  <p>Explore student profiles and manage applications.</p>
                </div>
              </div>

              <div className="hero-feature">
                <span className="feature-icon">✓</span>
                <div>
                  <strong>Build connections</strong>
                  <p>Host events and connect with emerging talent.</p>
                </div>
              </div>
            </div>
          </div>

          <p className="hero-footer">
            Recruiting tools designed for meaningful connections.
          </p>
        </section>

        <section className="login-panel">
          <div className="login-brand">
            <div className="brand-mark">H</div>
            <div>
              <div className="brand-name">Handshake</div>
              <div className="brand-subtitle">Recruiter Portal</div>
            </div>
          </div>

          <div className="login-form-wrapper">
            <div className="login-heading">
              <p className="login-eyebrow">WELCOME BACK</p>
              <h2>Sign in to your account</h2>
              <p>
                Manage opportunities, applicants, events, and student
                connections.
              </p>
            </div>

            <form onSubmit={handleSubmit} className="professional-login-form">
              <label>
                Work email
                <input
                  type="email"
                  placeholder="you@company.com"
                  required
                  autoComplete="email"
                  value={form.email}
                  onChange={(e) =>
                    setForm({ ...form, email: e.target.value })
                  }
                />
              </label>

              <label>
                Password
                <input
                  type="password"
                  placeholder="Enter your password"
                  required
                  autoComplete="current-password"
                  value={form.password}
                  onChange={(e) =>
                    setForm({ ...form, password: e.target.value })
                  }
                />
              </label>

              <ErrorMessage error={error} />

              {loading ? (
                <Loading label="Signing in..." />
              ) : (
                <button type="submit" className="login-primary-button">
                  Sign in
                </button>
              )}
            </form>

            <div className="login-divider">
              <span>New to Handshake?</span>
            </div>

            <Link to="/company/signup" className="create-account-button">
              Create a company account
            </Link>

            <p className="login-terms">
              By continuing, you agree to use the platform responsibly and
              protect student information.
            </p>
          </div>
        </section>
      </div>
    </div>
  );
}