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
    const { name, value } = e.target;

    setForm((prev) => ({
      ...prev,
      [name]: value,
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
        title: form.title,
        description: form.description || null,
        category: form.category,
        city: form.city,
        location: form.location || null,
        salary: form.salary ? Number(form.salary) : null,
        skills: form.skills || null,
        deadline,
      });

      setForm({
        title: "",
        description: "",
        category: "internship",
        city: "San Jose",
        location: "",
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

        <div className="page-header-actions">
          <button
            type="button"
            className={
              showForm
                ? "secondary-action-button"
                : "primary-action-button"
            }
            onClick={() => setShowForm((prev) => !prev)}
          >
            {showForm ? "Cancel" : "+ Post a job"}
          </button>
        </div>
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
          <div className="card-heading">
            <div className="card-heading-icon">＋</div>

            <div>
              <h2>Create a job posting</h2>

              <p>
                Add a new opportunity for students in your assigned
                recruiting cities.
              </p>
            </div>
          </div>

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
                </select>
              </label>
            </div>

            <label>
              Description
              <textarea
                name="description"
                value={form.description}
                onChange={handleChange}
                placeholder="Describe the role, responsibilities, and what the student will work on..."
                rows="5"
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
                  placeholder="e.g. San Jose, CA / Hybrid"
                />
              </label>
            </div>

            <div className="form-three-column">
              <label>
                Salary
                <input
                  type="number"
                  min="0"
                  name="salary"
                  value={form.salary}
                  onChange={handleChange}
                  placeholder="32"
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

            <div className="job-form-actions">
              <button
                type="submit"
                className="primary-action-button"
                disabled={posting}
              >
                {posting ? "Publishing..." : "Publish job"}
              </button>
            </div>
          </form>
        </section>
      )}

      <section className="job-list-section">
        <div className="section-title-row">
          <div>
            <h2>Your job postings</h2>

            <p>
              {jobs.length === 0
                ? "No jobs posted yet."
                : `${jobs.length} ${
                    jobs.length === 1 ? "opportunity" : "opportunities"
                  } currently listed.`}
            </p>
          </div>
        </div>

        {jobs.length === 0 ? (
          <div className="dashboard-card empty-state job-empty-state">
            <div className="empty-state-inner">
              <div className="empty-state-icon">＋</div>

              <h2>No job postings yet</h2>

              <p>
                Publish your first opportunity to start connecting with
                students.
              </p>
            </div>
          </div>
        ) : (
          <div className="job-card-grid">
            {jobs.map((job) => (
              <article
                className="dashboard-card recruiter-job-card"
                key={job.id}
              >
                <div className="job-card-header">
                  <div className="job-icon">
                    {job.category === "internship" ? "I" : "J"}
                  </div>

                  <div className="job-title-area">
                    <div className="job-title-top">
                      <h3>{job.title}</h3>

                      <span className="job-active-badge">
                        Active
                      </span>
                    </div>

                    <p>
                      {String(job.category || "")
                        .replaceAll("_", " ")
                        .replace(/\b\w/g, (letter) =>
                          letter.toUpperCase()
                        )}
                    </p>
                  </div>
                </div>

                {job.description && (
                  <p className="job-card-description">
                    {job.description}
                  </p>
                )}

                <div className="job-detail-grid">
                  <div>
                    <span>Location</span>
                    <strong>
                      {job.location || job.city || "Not specified"}
                    </strong>
                  </div>

                  <div>
                    <span>City</span>
                    <strong>{job.city || "Not specified"}</strong>
                  </div>

                  <div>
                    <span>Posted</span>
                    <strong>
                      {job.posting_date
                        ? new Date(
                            job.posting_date
                          ).toLocaleDateString()
                        : "—"}
                    </strong>
                  </div>

                  <div>
                    <span>Deadline</span>
                    <strong>
                      {job.deadline
                        ? new Date(
                            job.deadline
                          ).toLocaleDateString()
                        : "Open"}
                    </strong>
                  </div>
                </div>

                {job.skills && (
                  <div className="job-skills">
                    {job.skills
                      .split(",")
                      .map((skill) => skill.trim())
                      .filter(Boolean)
                      .map((skill) => (
                        <span
                          className="job-skill-tag"
                          key={`${job.id}-${skill}`}
                        >
                          {skill}
                        </span>
                      ))}
                  </div>
                )}

                <div className="job-card-footer">
                  <Link
                    to={`/company/jobs/${job.id}/applicants`}
                    className="primary-action-button"
                  >
                    View applicants
                  </Link>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}