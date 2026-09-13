import { Link } from "react-router-dom";

export function Brand({ to = "/" }: { to?: string }) {
  return (
    <Link className="claros-brand" to={to} aria-label="Claros home">
      <img className="claros-brand-mark" src="/favicon.svg?v=2" alt="" />
      <span>Claros</span>
    </Link>
  );
}
