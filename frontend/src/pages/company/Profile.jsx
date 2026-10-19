import { useEffect, useState } from "react";

import api from "../../services/api";
import Loading from "../../components/Loading";
import ErrorMessage from "../../components/ErrorMessage";

export default function CompanyProfile() {
  const [profile, setProfile] = useState({
    name: "",
    city: "San Jose",
    description: "",
    contact_info: "",
  });

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState("");

  const loadProfile = async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await api.get("/companies/me");

      setProfile({
        name: response.data.name || "",
        city: response.data.city || "San Jose",
        description: response.data.description || "",
        contact_info: response.data.contact_info || "",
      });
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let active = true;

    async function loadInitialProfile() {
      try {
        const response = await api.get("/companies/me");

        if (active) {
          setProfile({
            name: response.data.name || "",
            city: response.data.city || "San Jose",
            description: response.data.description || "",
            contact_info: response.data.contact_info || "",
          });
        }
      } catch (err) {
        if (active) {
          setError(err);
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    loadInitialProfile();

    return () => {
      active = false;
    };
  }, []);

  const handleChange = (e) => {
    const { name, value } = e.target;

    setProfile((prev) => ({
      ...prev,
      [name]: value,
    }));
  };

  const handleSave = async (e) => {
    e.preventDefault();

    try {
      setSaving(true);
      setError(null);
      setSuccess("");

      await api.put("/companies/me", {
        name: profile.name.trim(),
        city: profile.city,
        description: profile.description.trim() || null,
        contact_info: profile.contact_info.trim() || null,
      });

      setSuccess("Profile updated successfully.");

      await loadProfile();
    } catch (err) {
      setError(err);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="company-dashboard-page">
        <Loading label="Loading company profile..." />
      </div>
    );
  }

  const initials = profile.name
    ? profile.name
        .split(" ")
        .map((word) => word[0])
        .join("")
        .slice(0, 2)
        .toUpperCase()
    : "C";

  const profileCompletion =
    [
      profile.name,
      profile.city,
      profile.description,
      profile.contact_info,
    ].filter(Boolean).length * 25;

  return (
    <div className="company-dashboard-page">
      <div className="company-page-header">
        <div className="company-page-header-main">
          <p className="company-page-eyebrow">
            COMPANY SETTINGS
          </p>

          <h1>Company Profile</h1>

          <p>
            Manage the information students see about
            your company.
          </p>
        </div>
      </div>

      <ErrorMessage error={error} />

      {success && (
        <div className="profile-success-message">
          {success}
        </div>
      )}

      <div className="profile-layout">
        <aside className="dashboard-card company-profile-summary">
          <div className="company-avatar-section">
            <div className="company-avatar-placeholder">
              {initials}
            </div>

            <h2>{profile.name || "Your company"}</h2>

            <p>
              {profile.city || "City not added"}
            </p>
          </div>

          <div className="profile-completion">
            <span>Profile completion</span>
            <strong>{profileCompletion}%</strong>
          </div>
        </aside>

        <section className="dashboard-card company-profile-form-card">
          <h2>Company information</h2>

          <form className="company-profile-form" onSubmit={handleSave}>
            <label>
              Company name
              <input
                name="name"
                value={profile.name}
                onChange={handleChange}
                required
              />
            </label>

            <label>
              City
              <select
                name="city"
                value={profile.city}
                onChange={handleChange}
                required
              >
                <option value="San Jose">
                  San Jose
                </option>
                <option value="Santa Clara">
                  Santa Clara
                </option>
                <option value="Fremont">
                  Fremont
                </option>
              </select>
            </label>

            <label>
              Description
              <textarea
                name="description"
                value={profile.description}
                onChange={handleChange}
                rows="5"
              />
            </label>

            <label>
              Contact information
              <input
                name="contact_info"
                value={profile.contact_info}
                onChange={handleChange}
                placeholder="recruiting@company.com"
              />
            </label>

            <button
              type="submit"
              className="primary-action-button"
              disabled={saving}
            >
              {saving ? "Saving..." : "Save profile"}
            </button>
          </form>
        </section>
      </div>
    </div>
  );
}
