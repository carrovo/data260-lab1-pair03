import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import api from "../../services/api";
import Loading from "../../components/Loading";
import ErrorMessage from "../../components/ErrorMessage";

export default function StudentProfile() {
  const { studentId } = useParams();
  const [student, setStudent] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    api
      .get(`/companies/students/${studentId}/profile`)
      .then(({ data }) => setStudent(data))
      .catch((err) => setError(err))
      .finally(() => setLoading(false));
  }, [studentId]);

  if (loading) return <Loading label="Loading student profile..." />;

  return (
    <div className="page">
      <Link to="/company/dashboard">&larr; Back</Link>
      <ErrorMessage error={error} />
      {student && (
        <div className="card">
          <h1>{student.name}</h1>
          <p>{student.email}</p>
          <p><strong>College:</strong> {student.college_name || "—"}</p>
          <p><strong>Major:</strong> {student.major || "—"}</p>
          <p><strong>City:</strong> {student.city || "—"}</p>
          <p><strong>Skills:</strong> {student.skills || "—"}</p>
        </div>
      )}
    </div>
  );
}
