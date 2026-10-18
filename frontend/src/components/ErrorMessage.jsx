export default function ErrorMessage({ error }) {
  if (!error) return null;
  const detail =
    error?.response?.data?.detail ||
    error?.message ||
    "Something went wrong. Please try again.";
  return <div className="state-message state-error">{detail}</div>;
}
