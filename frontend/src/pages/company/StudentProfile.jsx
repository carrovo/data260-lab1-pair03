import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import api from "../../services/api";
import Loading from "../../components/Loading";
import ErrorMessage from "../../components/ErrorMessage";

export default function StudentProfile() {
  const { studentId } = useParams();

  const [student, setStudent] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const loadStudent = async () => {
      try {
        setLoading(true);
        setError(null);

        const response = await api.get(
          `/companies/students/${studentId}/profile`
        );

        setStudent(response.data);
      } catch (err) {
        setError(err);
      } finally {
        setLoading(false);
      }
    };

    loadStudent();
  }, [studentId]);

  if (loading) {
    return (
      <Loading label="Loading student profile..." />
    );
  }

  return (
    <div className="dashboard-page">
      <Link to="/company/students">
        &larr; Back to students
      </Link>

      <ErrorMessage error={error} />

      {student && (
        <section className="dashboard-card">
          <h1>{student.full_name}</h1>

          <p>{student.email}</p>

          <p>
            <strong>College:</strong>{" "}
            {student.college_name || "—"}
          </p>

          <p>
            <strong>Major:</strong>{" "}
            {student.major || "—"}
          </p>

          <p>
            <strong>City:</strong>{" "}
            {student.city || "—"}
          </p>

          <p>
            <strong>State:</strong>{" "}
            {student.state || "—"}
          </p>

          <p>
            <strong>Skills:</strong>{" "}
            {student.skills || "—"}
          </p>
        </section>
      )}
    </div>
  );
}