export default function Loading({ label = "Loading..." }) {
  return <div className="state-message state-loading">{label}</div>;
}
