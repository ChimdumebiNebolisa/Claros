import { cn } from "./cn";

export function LoadingState({
  label,
  className,
}: {
  label: string;
  className?: string;
}) {
  return (
    <div
      className={cn("grid justify-items-center gap-4 text-center", className)}
      role="status"
      aria-live="polite"
    >
      <span className="claros-loader" aria-hidden="true">
        <span />
        <span />
        <span />
        <span />
      </span>
      <span className="text-sm font-medium text-[var(--claros-muted)]">
        {label}
      </span>
    </div>
  );
}
