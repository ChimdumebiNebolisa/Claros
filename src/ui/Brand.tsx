import { Link } from "react-router-dom";

type WordmarkProps = {
  linked?: boolean;
};

export function Wordmark({ linked = true }: WordmarkProps) {
  const content = (
    <>
      <span className="wordmark-mark">C</span>
      <span>claros</span>
    </>
  );

  if (!linked) return <span className="wordmark">{content}</span>;

  return (
    <Link className="wordmark" to="/" aria-label="Claros home">
      {content}
    </Link>
  );
}
