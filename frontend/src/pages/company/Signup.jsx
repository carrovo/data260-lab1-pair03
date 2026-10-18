import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import ErrorMessage from "../../components/ErrorMessage";
import Loading from "../../components/Loading";

const CITY_SET = ["San Jose", "Santa Clara", "Fremont"];

export default function CompanySignup() {
  const { signup } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ name: "", email: "", password: "", location: CITY_SET[0] });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await signup(form);
      navigate("/company/dashboard");
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <h1>Create a Company Account</h1>
      <form onSubmit={handleSubmit} className="form">
        <label>
          Company name
          <input
            required
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
          />
        </label>
        <label>
          Email
          <input
            type="email"
            required
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
          />
        </label>
        <label>
          Password
          <input
            type="password"
            required
            minLength={6}
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
          />
        </label>
        <label>
          Location
          <select
            value={form.location}
            onChange={(e) => setForm({ ...form, location: e.target.value })}
          >
            {CITY_SET.map((city) => (
              <option key={city} value={city}>{city}</option>
            ))}
          </select>
        </label>
        <ErrorMessage error={error} />
        {loading ? <Loading label="Creating account..." /> : <button type="submit">Sign up</button>}
      </form>
      <p>
        Already have an account? <Link to="/company/login">Log in</Link>
      </p>
    </div>
  );
}
