import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import api from "../../services/api";
import {
  setActiveRole,
  setToken,
} from "../../services/authStorage";
import ErrorMessage from "../../components/ErrorMessage";
import Loading from "../../components/Loading";

const CITY_SET = [
  "San Jose",
  "Santa Clara",
  "Fremont",
];

export default function CompanySignup() {
  const navigate = useNavigate();

  const [form, setForm] = useState({
    name: "",
    email: "",
    password: "",
    city: CITY_SET[0],
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const response = await api.post(
        "/companies/auth/signup",
        form
      );

      setToken("company", response.data.access_token);
      setActiveRole("company");

      navigate("/company/dashboard");
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="company-signup-page">
      <h1>Create a Company Account</h1>

      <form
        onSubmit={handleSubmit}
        className="company-signup-form"
      >
        <label>
          Company name
          <input
            required
            value={form.name}
            onChange={(e) =>
              setForm({
                ...form,
                name: e.target.value,
              })
            }
          />
        </label>

        <label>
          Email
          <input
            type="email"
            required
            value={form.email}
            onChange={(e) =>
              setForm({
                ...form,
                email: e.target.value,
              })
            }
          />
        </label>

        <label>
          Password
          <input
            type="password"
            required
            minLength={8}
            value={form.password}
            onChange={(e) =>
              setForm({
                ...form,
                password: e.target.value,
              })
            }
          />
        </label>

        <label>
          City
          <select
            value={form.city}
            onChange={(e) =>
              setForm({
                ...form,
                city: e.target.value,
              })
            }
          >
            {CITY_SET.map((city) => (
              <option
                key={city}
                value={city}
              >
                {city}
              </option>
            ))}
          </select>
        </label>

        <ErrorMessage error={error} />

        {loading ? (
          <Loading label="Creating account..." />
        ) : (
          <button type="submit" className="company-signup-button">
            Sign up
          </button>
        )}
      </form>

      <p>
        Already have an account?{" "}
        <Link to="/company/login">
          Log in
        </Link>
      </p>
    </div>
  );
}
