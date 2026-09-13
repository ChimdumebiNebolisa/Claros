import { AlertCircle, CheckCircle, Info } from "lucide-react";
import type { ReactNode } from "react";
import { Button } from "@/v2/ui/Button";
import { cn } from "@/v2/ui/cn";

type NoticeTone = "info" | "success" | "warning" | "error";

type StatusNoticeProps = {
  title: string;
  children: ReactNode;
  tone?: NoticeTone;
  actionLabel?: string;
  onAction?: () => void;
  className?: string;
};

const toneStyles: Record<NoticeTone, string> = {
  info: "border-[var(--claros-blue-mist)] bg-[var(--claros-blue-soft)]",
  success: "border-[#b7e1ce] bg-[var(--claros-green-soft)]",
  warning: "border-[#f0d49c] bg-[var(--claros-amber-soft)]",
  error: "border-[#f0c4bf] bg-[#fff5f4]",
};

const toneIcons = {
  info: Info,
  success: CheckCircle,
  warning: AlertCircle,
  error: AlertCircle,
} as const;

const iconStyles: Record<NoticeTone, string> = {
  info: "bg-[var(--claros-blue-mist)] text-[var(--claros-blue-dark)]",
  success: "bg-[#d8f1e6] text-[var(--claros-green)]",
  warning: "bg-[#f7e8c9] text-[var(--claros-amber)]",
  error: "bg-[#f8dedb] text-[var(--claros-error)]",
};

export function StatusNotice({
  title,
  children,
  tone = "info",
  actionLabel,
  onAction,
  className,
}: StatusNoticeProps) {
  const Icon = toneIcons[tone];

  return (
    <div
      className={cn(
        "flex w-full items-start gap-3 rounded-xl border p-4 text-left",
        toneStyles[tone],
        className,
      )}
      role={tone === "error" ? "alert" : "status"}
      aria-live={tone === "error" ? "assertive" : "polite"}
    >
      <span
        className={cn(
          "grid size-9 shrink-0 place-items-center rounded-lg",
          iconStyles[tone],
        )}
        aria-hidden="true"
      >
        <Icon className="size-[18px]" />
      </span>
      <div className="min-w-0 flex-1">
        <p className="m-0 text-sm font-semibold text-[var(--claros-ink)]">
          {title}
        </p>
        <div className="mt-1 text-sm leading-6 text-[var(--claros-muted)]">
          {children}
        </div>
        {actionLabel && onAction ? (
          <Button
            color={tone === "error" ? "link-destructive" : "link-color"}
            size="sm"
            onPress={onAction}
            className="mt-2 min-h-11"
          >
            {actionLabel}
          </Button>
        ) : null}
      </div>
    </div>
  );
}
