import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import api from "../../services/api";
import Loading from "../../components/Loading";
import ErrorMessage from "../../components/ErrorMessage";

export default function CompanyDashboard() {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [posting, setPosting] = useState(false);
  const [error, setError] = useState(null);
  const [showForm, setShowForm] = useState(false);

  const [form, setForm] = useState({
    title: "",
    description: "",
    category: "internship",
    city: "San Jose",
    location: "",
    is_remote: false,
    salary: "",
    skills: "",
    deadline: "",
  });

  const loadJobs = async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await api.get("/companies/jobs");
      setJobs(response.data || []);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadJobs();
  }, []);

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;

    setForm((prev) => ({
      ...prev,
      [name]: type === "checkbox" ? checked : value,
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    try {
      setPosting(true);
      setError(null);

      const deadline = form.deadline
        ? new Date(`${form.deadline}T23:59:59`).toISOString()
        : null;

      await api.post("/companies/jobs", {
        title: form.title.trim(),
        description: form.description.trim(),
        category: form.category,
        city: form.city,
        location: form.location.trim() || null,
        is_remote: form.is_remote,
        salary: form.salary ? Number(form.salary) : null,
        skills: form.skills.trim() || null,
        deadline,
      });

      setForm({
        title: "",
        description: "",
        category: "internship",
        city: "San Jose",
        location: "",
        is_remote: false,
        salary: "",
        skills: "",
        deadline: "",
      });

      setShowForm(false);
      await loadJobs();
    } catch (err) {
      setError(err);
    } finally {
      setPosting(false);
    }
  };

  if (loading) {
    return (
      <div className="dashboard-page">
        <Loading label="Loading job postings..." />
      </div>
    );
  }

  return (
    <div className="dashboard-page">
      <div className="page-header">
        <div className="page-header-main">
          <p className="page-eyebrow">RECRUITING</p>
          <h1>Job Postings</h1>
          <p>
            Create opportunities, manage active postings, and review
            applicants from one place.
          </p>
        </div>

        <button
          type="button"
          className="primary-action-button"
          onClick={() => setShowForm((prev) => !prev)}
        >
          {showForm ? "Cancel" : "+ Post a job"}
        </button>
      </div>

      <ErrorMessage error={error} />

      <div className="job-metric-grid">
        <div className="dashboard-card job-metric-card">
          <span>Active postings</span>
          <strong>{jobs.length}</strong>
        </div>

        <div className="dashboard-card job-metric-card">
          <span>Internships</span>
          <strong>
            {
              jobs.filter(
                (job) =>
                  String(job.category).toLowerCase() ===
                  "internship"
              ).length
            }
          </strong>
        </div>

        <div className="dashboard-card job-metric-card">
          <span>Hiring locations</span>
          <strong>
            {
              new Set(
                jobs.map((job) => job.city).filter(Boolean)
              ).size
            }
          </strong>
        </div>
      </div>

      {showForm && (
        <section className="dashboard-card job-create-card">
          <h2>Create a job posting</h2>

          <form className="job-create-form" onSubmit={handleSubmit}>
            <div className="form-two-column">
              <label>
                Job title
                <input
                  name="title"
                  value={form.title}
                  onChange={handleChange}
                  placeholder="e.g. Data Analyst Intern"
                  required
                />
              </label>

              <label>
                Category
                <select
                  name="category"
                  value={form.category}
                  onChange={handleChange}
                  required
                >
                  <option value="internship">Internship</option>
                  <option value="full_time">Full time</option>
                  <option value="part_time">Part time</option>
                  <option value="on_campus">On campus</option>
                </select>
              </label>
            </div>

            <label>
              Description
              <textarea
                name="description"
                value={form.description}
                onChange={handleChange}
                placeholder="Describe the role and responsibilities..."
                rows="5"
                required
              />
            </label>

            <div className="form-two-column">
              <label>
                City
                <select
                  name="city"
                  value={form.city}
                  onChange={handleChange}
                  required
                >
                  <option value="San Jose">San Jose</option>
                  <option value="Santa Clara">Santa Clara</option>
                  <option value="Fremont">Fremont</option>
                </select>
              </label>

              <label>
                Location detail
                <input
                  name="location"
                  value={form.location}
                  onChange={handleChange}
                  placeholder="e.g. Downtown San Jose"
                />
              </label>
            </div>

            <label>
              <input
                type="checkbox"
                name="is_remote"
                checked={form.is_remote}
                onChange={handleChange}
              />
              Remote position
            </label>

            <div className="form-three-column">
              <label>
                Salary
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  name="salary"
                  value={form.salary}
                  onChange={handleChange}
                />
              </label>

              <label>
                Skills
                <input
                  name="skills"
                  value={form.skills}
                  onChange={handleChange}
                  placeholder="Python, SQL, Tableau"
                />
              </label>

              <label>
                Application deadline
                <input
                  type="date"
                  name="deadline"
                  value={form.deadline}
                  onChange={handleChange}
                />
              </label>
            </div>

            <button
              type="submit"
              className="primary-action-button"
              disabled={posting}
            >
              {posting ? "Publishing..." : "Publish job"}
            </button>
          </form>
        </section>
      )}

      <section className="job-list-section">
        <h2>Your job postings</h2>

        {jobs.length === 0 ? (
          <div className="dashboard-card empty-state">
            <h3>No job postings yet</h3>
            <p>Publish your first opportunity to get started.</p>
          </div>
        ) : (
          <div className="job-card-grid">
            {jobs.map((job) => (
              <article
                key={job.id}
                className="dashboard-card"
              >
                <h3>{job.title}</h3>

                <p>{job.description}</p>

                <p>
                  <strong>Category:</strong>{" "}
                  {job.category || "Not specified"}
                </p>

                <p>
                  <strong>City:</strong>{" "}
                  {job.city || "Not specified"}
                </p>

                <p>
                  <strong>Location:</strong>{" "}
                  {job.location || "Not specified"}
                </p>

                <p>
                  <strong>Skills:</strong>{" "}
                  {job.skills || "Not specified"}
                </p>

                <Link
                  to={`/company/jobs/${job.id}/applicants`}
                  className="secondary-action-button"
                >
                  View applicants
                </Link>
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}