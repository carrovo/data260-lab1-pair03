import { useState } from "react";
import { Link } from "react-router-dom";

import api from "../../services/api";
import Loading from "../../components/Loading";
import ErrorMessage from "../../components/ErrorMessage";

export default function StudentsSearch() {
  const [filters, setFilters] = useState({
    name: "",
    college: "",
    skill: "",
  });

  const [students, setStudents] = useState([]);
  const [searched, setSearched] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleChange = (e) => {
    const { name, value } = e.target;

    setFilters((prev) => ({
      ...prev,
      [name]: value,
    }));
  };

  const handleSearch = async (e) => {
    e.preventDefault();

    try {
      setLoading(true);
      setError(null);

      const params = {};

      if (filters.name.trim()) {
        params.name = filters.name.trim();
      }

      if (filters.college.trim()) {
        params.college = filters.college.trim();
      }

      if (filters.skill.trim()) {
        params.skill = filters.skill.trim();
      }

      const response = await api.get("/companies/students", {
        params,
      });

      setStudents(response.data || []);
      setSearched(true);
    } catch (err) {
      setError(err);
      setStudents([]);
      setSearched(true);
    } finally {
      setLoading(false);
    }
  };

  const clearFilters = () => {
    setFilters({
      name: "",
      college: "",
      skill: "",
    });

    setStudents([]);
    setSearched(false);
    setError(null);
  };

  return (
    <div className="dashboard-page">
      <div className="page-header">
        <div className="page-header-main">
          <p className="page-eyebrow">TALENT DISCOVERY</p>

          <h1>Student Directory</h1>

          <p>
            Search students by name, college, or skillset and explore
            profiles that match your recruiting needs.
          </p>
        </div>
      </div>

      <ErrorMessage error={error} />

      <section className="dashboard-card student-search-card">
        <div className="card-heading">
          <div className="card-heading-icon">⌕</div>

          <div>
            <h2>Find students</h2>
            <p>Use one or more filters to narrow the directory.</p>
          </div>
        </div>

        <form className="student-search-form" onSubmit={handleSearch}>
          <div className="student-filter-grid">
            <label>
              Student name
              <input
                type="text"
                name="name"
                value={filters.name}
                onChange={handleChange}
                placeholder="e.g. Priya Sharma"
              />
            </label>

            <label>
              College
              <input
                type="text"
                name="college"
                value={filters.college}
                onChange={handleChange}
                placeholder="e.g. San Jose State University"
              />
            </label>

            <label>
              Skill
              <input
                type="text"
                name="skill"
                value={filters.skill}
                onChange={handleChange}
                placeholder="e.g. Python, SQL, Tableau"
              />
            </label>
          </div>

          <div className="student-search-actions">
            <button
              type="submit"
              className="primary-action-button"
              disabled={loading}
            >
              {loading ? "Searching..." : "Search students"}
            </button>

            <button
              type="button"
              className="secondary-action-button"
              onClick={clearFilters}
            >
              Clear
            </button>
          </div>
        </form>
      </section>

      <section className="student-results-section">
        <div className="section-title-row">
          <div>
            <h2>Search results</h2>

            <p>
              {searched
                ? `${students.length} ${
                    students.length === 1 ? "student" : "students"
                  } found`
                : "Search the directory to discover students."}
            </p>
          </div>
        </div>

        {loading ? (
          <div className="dashboard-card student-results-loading">
            <Loading label="Searching students..." />
          </div>
        ) : !searched ? (
          <div className="dashboard-card empty-state student-empty-state">
            <div className="empty-state-inner">
              <div className="empty-state-icon">⌕</div>

              <h2>Start your search</h2>

              <p>
                Use the filters above to find students by name, college,
                or skillset.
              </p>
            </div>
          </div>
        ) : students.length === 0 ? (
          <div className="dashboard-card empty-state student-empty-state">
            <div className="empty-state-inner">
              <div className="empty-state-icon">◎</div>

              <h2>No matching students</h2>

              <p>
                Try broadening your search or removing one of the
                filters.
              </p>
            </div>
          </div>
        ) : (
          <div className="student-card-grid">
            {students.map((student) => (
              <article
                className="dashboard-card student-directory-card"
                key={student.id}
              >
                <div className="student-directory-top">
                  <div className="student-directory-avatar">
                    {student.name
                      ? student.name.charAt(0).toUpperCase()
                      : "S"}
                  </div>

                  <div className="student-directory-title">
                    <h3>{student.name}</h3>
                    <p>{student.email}</p>
                  </div>
                </div>

                <div className="student-profile-details">
                  <div>
                    <span>College</span>
                    <strong>
                      {student.college_name || "Not provided"}
                    </strong>
                  </div>

                  <div>
                    <span>Major</span>
                    <strong>{student.major || "Not provided"}</strong>
                  </div>

                  <div>
                    <span>City</span>
                    <strong>{student.city || "Not provided"}</strong>
                  </div>
                </div>

                <div className="student-skills-section">
                  <span className="student-section-label">Skills</span>

                  {student.skills ? (
                    <div className="student-skill-tags">
                      {student.skills
                        .split(",")
                        .map((skill) => skill.trim())
                        .filter(Boolean)
                        .map((skill) => (
                          <span
                            key={`${student.id}-${skill}`}
                            className="student-skill-tag"
                          >
                            {skill}
                          </span>
                        ))}
                    </div>
                  ) : (
                    <p className="student-no-skills">
                      No skills listed yet.
                    </p>
                  )}
                </div>

                <div className="student-card-footer">
                  <Link
                    to={`/company/students/${student.id}`}
                    className="secondary-action-button"
                  >
                    View profile
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