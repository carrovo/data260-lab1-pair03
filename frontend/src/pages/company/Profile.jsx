import { useEffect, useState } from "react";

import api from "../../services/api";
import Loading from "../../components/Loading";
import ErrorMessage from "../../components/ErrorMessage";

export default function CompanyProfile() {
  const [profile, setProfile] = useState({
    name: "",
    location: "San Jose",
    description: "",
    contact_info: "",
    profile_picture: null,
  });

  const [profileImageUrl, setProfileImageUrl] = useState(null);

  const [imageFile, setImageFile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);

  const [error, setError] = useState(null);
  const [success, setSuccess] = useState("");

  /*
    Load the actual image through Axios.

    This is important because the picture endpoint is protected
    and Axios already sends our authentication token.
  */
  const loadProfilePicture = async () => {
    try {
      const response = await api.get(
        "/companies/me/picture",
        {
          responseType: "blob",
        }
      );

      const objectUrl = URL.createObjectURL(response.data);

      setProfileImageUrl((oldUrl) => {
        if (oldUrl) {
          URL.revokeObjectURL(oldUrl);
        }

        return objectUrl;
      });
    } catch (err) {
      /*
        A missing image is not a fatal profile error.
        We simply display the initials instead.
      */
      setProfileImageUrl(null);
    }
  };

  const loadProfile = async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await api.get("/companies/me");

      const profileData = {
        name: response.data.name || "",
        location: response.data.location || "San Jose",
        description: response.data.description || "",
        contact_info: response.data.contact_info || "",
        profile_picture:
          response.data.profile_picture || null,
      };

      setProfile(profileData);

      /*
        Only request the image if the backend says
        that a profile picture exists.
      */
      if (profileData.profile_picture) {
        await loadProfilePicture();
      } else {
        setProfileImageUrl(null);
      }
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadProfile();

    return () => {
      if (profileImageUrl) {
        URL.revokeObjectURL(profileImageUrl);
      }
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
        name: profile.name,
        location: profile.location,
        description: profile.description,
        contact_info: profile.contact_info,
      });

      setSuccess("Profile updated successfully.");

      await loadProfile();
    } catch (err) {
      setError(err);
    } finally {
      setSaving(false);
    }
  };

  const handleUpload = async () => {
    if (!imageFile) return;

    try {
      setUploading(true);
      setError(null);
      setSuccess("");

      const formData = new FormData();

      formData.append("file", imageFile);

      await api.post(
        "/companies/me/picture",
        formData,
        {
          headers: {
            "Content-Type": "multipart/form-data",
          },
        }
      );

      setSuccess(
        "Profile picture updated successfully."
      );

      setImageFile(null);

      /*
        Reload both the profile information and
        the newly uploaded image.
      */
      await loadProfile();
    } catch (err) {
      setError(err);
    } finally {
      setUploading(false);
    }
  };

  if (loading) {
    return (
      <div className="dashboard-page">
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
      profile.location,
      profile.description,
      profile.contact_info,
      profile.profile_picture,
    ].filter(Boolean).length * 20;

  return (
    <div className="dashboard-page">
      <div className="page-header">
        <div className="page-header-main">
          <p className="page-eyebrow">
            COMPANY SETTINGS
          </p>

          <h1>Company Profile</h1>

          <p>
            Manage the information students see when
            they discover your company and
            opportunities.
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
        {/* LEFT SUMMARY */}

        <aside className="dashboard-card company-profile-summary">
          <div className="company-avatar-section">
            {profileImageUrl ? (
              <img
                src={profileImageUrl}
                alt={profile.name}
                className="company-profile-image"
              />
            ) : (
              <div className="company-avatar-placeholder">
                {initials}
              </div>
            )}

            <h2>
              {profile.name || "Your company"}
            </h2>

            <p>
              {profile.location ||
                "Location not added"}
            </p>
          </div>

          <div className="profile-summary-divider" />

          <div className="profile-upload-section">
            <span className="profile-section-label">
              Company logo
            </span>

            <p>
              Upload a JPG or PNG image to represent
              your company.
            </p>

            <label className="profile-file-picker">
              <span>
                {imageFile
                  ? imageFile.name
                  : "Choose image"}
              </span>

              <input
                type="file"
                accept="image/png,image/jpeg"
                onChange={(e) =>
                  setImageFile(
                    e.target.files?.[0] || null
                  )
                }
              />
            </label>

            <button
              type="button"
              className="secondary-action-button profile-upload-button"
              onClick={handleUpload}
              disabled={!imageFile || uploading}
            >
              {uploading
                ? "Uploading..."
                : "Upload logo"}
            </button>
          </div>

          <div className="profile-summary-divider" />

          <div className="profile-completion">
            <div className="profile-completion-top">
              <span>
                Profile completion
              </span>

              <strong>
                {profileCompletion}%
              </strong>
            </div>

            <div className="profile-progress-track">
              <div
                className="profile-progress-fill"
                style={{
                  width: `${profileCompletion}%`,
                }}
              />
            </div>
          </div>
        </aside>

        {/* RIGHT FORM */}

        <section className="dashboard-card company-profile-form-card">
          <div className="card-heading">
            <div className="card-heading-icon">
              ✎
            </div>

            <div>
              <h2>Company information</h2>

              <p>
                Keep your company details accurate
                and up to date.
              </p>
            </div>
          </div>

          <form
            className="company-profile-form"
            onSubmit={handleSave}
          >
            <div className="form-two-column">
              <label>
                Company name

                <input
                  name="name"
                  value={profile.name}
                  onChange={handleChange}
                  placeholder="Company name"
                  required
                />
              </label>

              <label>
                Location

                <select
                  name="location"
                  value={profile.location}
                  onChange={handleChange}
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
            </div>

            <label>
              Company description

              <textarea
                name="description"
                value={profile.description}
                onChange={handleChange}
                placeholder="Tell students about your company, mission, teams, and opportunities..."
                rows="6"
              />
            </label>

            <label>
              Contact information

              <input
                name="contact_info"
                value={profile.contact_info}
                onChange={handleChange}
                placeholder="e.g. recruiting@company.com"
              />
            </label>

            <div className="profile-form-actions">
              <button
                type="submit"
                className="primary-action-button"
                disabled={saving}
              >
                {saving
                  ? "Saving..."
                  : "Save changes"}
              </button>
            </div>
          </form>
        </section>
      </div>
    </div>
  );
}