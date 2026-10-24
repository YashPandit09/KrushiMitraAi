import { Link } from "react-router";

export default function NotFound() {
  return (
    <div className="page-head">
      <div className="eyebrow">404</div>
      <h1>Page not found</h1>
      <p>
        That page doesn't exist. <Link to="/">Go to the outlook</Link>.
      </p>
    </div>
  );
}
