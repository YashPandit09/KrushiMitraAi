import { Link } from "react-router";
import { ApiError } from "../api";

export function Loading({ label = "Loading…" }: { label?: string }) {
  return (
    <p className="state-msg" role="status" aria-live="polite">
      {label}
    </p>
  );
}

export function ErrorNote({ error }: { error: Error }) {
  const notFound = error instanceof ApiError && error.status === 404;
  return (
    <div className="notice warn" role="alert" style={{ margin: "24px 0" }}>
      <strong>{notFound ? "Not found." : "Something went wrong."}</strong> {error.message}.{" "}
      {notFound ? <Link to="/">Back to the outlook</Link> : "Please try again in a moment."}
    </div>
  );
}

export function WarningIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" aria-hidden="true">
      <path fill="var(--serious)" d="M12 2 1 21h22L12 2Zm0 6 7.5 11h-15L12 8Z" />
      <path fill="var(--serious)" d="M11 11h2v4h-2zM11 16.5h2v2h-2z" />
    </svg>
  );
}
