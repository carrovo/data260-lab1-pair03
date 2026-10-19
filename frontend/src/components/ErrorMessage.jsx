export default function ErrorMessage({ error }) {
  if (!error) return null;
  const responseDetail = error?.response?.data?.detail;
  const validationDetail = Array.isArray(responseDetail)
    ? responseDetail
        .map((item) => item?.msg)
        .filter(Boolean)
        .join(" ")
    : null;
  const detail = typeof responseDetail === "string"
    ? responseDetail
    : validationDetail ||
      error?.message ||
      "Something went wrong. Please try again.";

  return <div className="state-message state-error">{detail}</div>;
}
