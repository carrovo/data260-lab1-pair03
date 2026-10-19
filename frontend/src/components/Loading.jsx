export default function Loading({ label = "Loading..." }) {
  return (
    <div className="company-state-message company-state-loading" role="status">
      {label}
    </div>
  );
}
