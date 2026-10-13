import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import api from "../../services/api";
import Loading from "../../components/Loading";
import ErrorMessage from "../../components/ErrorMessage";

export default function Applicants() {
  const { jobId } = useParams();

  const [applicants, setApplicants] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadApplicants = async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await api.get(
        `/companies/jobs/${jobId}/applicants`
      );

      setApplicants(response.data || []);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadApplicants();
  }, [jobId]);

  const updateStatus = async (applicationId, status) => {
    try {
      setError(null);

      await api.put(
        `/companies/applications/${applicationId}/status`,
        { status }
      );

      await loadApplicants();
    } catch (err) {
      setError(err);
    }
  };

  const previewResume = async (applicationId) => {
    try {
      setError(null);

      const response = await api.get(
        `/companies/applications/${applicationId}/resume`,
        {
          responseType: "blob",
        }
      );

      const fileURL = URL.createObjectURL(response.data);

      window.open(fileURL, "_blank", "noopener,noreferrer");

      setTimeout(() => {
        URL.revokeObjectURL(fileURL);
      }, 10000);
    } catch (err) {
      setError(err);
    }
  };

  if (loading) {
    return (
      <div className="dashboard-page">
        <Loading label="Loading applicants..." />
      </div>
    );
  }

  return (
    <div className="dashboard-page">
      <Link to="/company/dashboard" className="page-back-link">
        ← Back to job postings
      </Link>

      <div className="page-header">
        <div className="page-header-main">
          <h1>Applicants</h1>

          <p>
            Review students who applied to this position and manage their
            application status.
          </p>
        </div>
      </div>

      <ErrorMessage error={error} />

      <div className="metric-grid">
        <div className="dashboard-card metric-card">
          <div className="metric-label">Total applicants</div>
          <div className="metric-value">{applicants.length}</div>
        </div>

        <div className="dashboard-card metric-card">
          <div className="metric-label">Pending</div>
          <div className="metric-value">
            {
              applicants.filter(
                (applicant) =>
                  String(applicant.status).toLowerCase() === "pending"
              ).length
            }
          </div>
        </div>

        <div className="dashboard-card metric-card">
          <div className="metric-label">Reviewed</div>
          <div className="metric-value">
            {
              applicants.filter(
                (applicant) =>
                  String(applicant.status).toLowerCase() === "reviewed"
              ).length
            }
          </div>
        </div>
      </div>

      {applicants.length === 0 ? (
        <div className="dashboard-card empty-state">
          <div className="empty-state-inner">
            <div className="empty-state-icon">◎</div>

            <h2>No applicants yet</h2>

            <p>
              This job has not received any applications yet. Students who
              apply will appear here automatically.
            </p>
          </div>
        </div>
      ) : (
        <div className="dashboard-card data-table-wrapper">
          <table className="data-table">
            <thead>
              <tr>
                <th>Candidate</th>
                <th>College</th>
                <th>Status</th>
                <th>Applied</th>
                <th>Resume</th>
                <th>Actions</th>
              </tr>
            </thead>

            <tbody>
              {applicants.map((applicant) => (
                <tr key={applicant.application_id}>
                  <td>
                    <div className="table-primary-text">
                      {applicant.student_name}
                    </div>

                    <div className="table-secondary-text">
                      {applicant.student_email}
                    </div>
                  </td>

                  <td>
                    {applicant.college_name || "Not provided"}
                  </td>

                  <td>
                    <span className="status-badge">
                      {applicant.status}
                    </span>
                  </td>

                  <td>
                    {applicant.applied_at
                      ? new Date(
                          applicant.applied_at
                        ).toLocaleDateString()
                      : "—"}
                  </td>

                  <td>
                    <button
                      type="button"
                      className="secondary-action-button"
                      onClick={() =>
                        previewResume(applicant.application_id)
                      }
                    >
                      Preview resume
                    </button>
                  </td>

                  <td>
                    <div
                      style={{
                        display: "flex",
                        gap: "10px",
                        alignItems: "center",
                        flexWrap: "wrap",
                      }}
                    >
                      <Link
                        to={`/company/students/${applicant.student_id}`}
                        className="inline-action-link"
                      >
                        View profile
                      </Link>

                      <select
                        value={applicant.status}
                        onChange={(e) =>
                          updateStatus(
                            applicant.application_id,
                            e.target.value
                          )
                        }
                      >
                        <option value="Pending">Pending</option>
                        <option value="Reviewed">Reviewed</option>
                        <option value="Declined">Declined</option>
                      </select>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}