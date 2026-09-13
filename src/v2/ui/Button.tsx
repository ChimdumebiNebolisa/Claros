import { LoaderCircle, type LucideIcon } from "lucide-react";
import type { ButtonHTMLAttributes, ComponentType, SVGProps } from "react";
import { cn } from "./cn";

type IconComponent = LucideIcon | ComponentType<SVGProps<SVGSVGElement>>;

type ButtonColor =
  | "primary"
  | "secondary"
  | "tertiary"
  | "link-gray"
  | "link-color"
  | "link-destructive";

type ButtonSize = "sm" | "md" | "lg";

export type ButtonProps = Omit<
  ButtonHTMLAttributes<HTMLButtonElement>,
  "color" | "disabled"
> & {
  color?: ButtonColor;
  size?: ButtonSize;
  iconLeading?: IconComponent;
  iconTrailing?: IconComponent;
  isDisabled?: boolean;
  isLoading?: boolean;
  showTextWhileLoading?: boolean;
  onPress?: () => void;
};

const colors: Record<ButtonColor, string> = {
  primary:
    "border-transparent bg-[var(--claros-blue)] text-white shadow-[0_1px_2px_rgba(17,32,51,.14)] hover:bg-[var(--claros-blue-dark)]",
  secondary:
    "border-[var(--claros-line-strong)] bg-white text-[var(--claros-ink)] shadow-[0_1px_2px_rgba(17,32,51,.06)] hover:border-[#9aa8bd] hover:bg-[var(--claros-soft)]",
  tertiary:
    "border-transparent bg-transparent text-[var(--claros-ink)] hover:bg-[var(--claros-soft)]",
  "link-gray":
    "border-transparent bg-transparent px-1 text-[var(--claros-muted)] hover:text-[var(--claros-ink)]",
  "link-color":
    "border-transparent bg-transparent px-1 text-[var(--claros-blue-dark)] hover:text-[var(--claros-blue)]",
  "link-destructive":
    "border-transparent bg-transparent px-1 text-[var(--claros-error)] hover:text-[#8c1c16]",
};

const sizes: Record<ButtonSize, string> = {
  sm: "min-h-10 gap-2 rounded-lg px-3 text-sm",
  md: "min-h-11 gap-2 rounded-lg px-4 text-sm",
  lg: "min-h-12 gap-2.5 rounded-[10px] px-5 text-[15px]",
};

export function Button({
  color = "primary",
  size = "md",
  iconLeading: IconLeading,
  iconTrailing: IconTrailing,
  isDisabled,
  isLoading,
  showTextWhileLoading,
  onPress,
  onClick,
  className,
  children,
  type = "button",
  ...props
}: ButtonProps) {
  return (
    <button
      type={type}
      disabled={isDisabled || isLoading}
      onClick={(event) => {
        onClick?.(event);
        if (!event.defaultPrevented) onPress?.();
      }}
      className={cn(
        "inline-flex shrink-0 items-center justify-center border font-semibold outline-none transition-[color,background-color,border-color,box-shadow,transform] duration-150 focus-visible:ring-2 focus-visible:ring-[var(--claros-blue)] focus-visible:ring-offset-2 active:translate-y-px disabled:pointer-events-none disabled:opacity-45",
        colors[color],
        sizes[size],
        className,
      )}
      {...props}
    >
      {isLoading ? (
        <LoaderCircle className="size-4 animate-spin" aria-hidden="true" />
      ) : IconLeading ? (
        <IconLeading className="size-4" aria-hidden="true" />
      ) : null}
      {!isLoading || showTextWhileLoading ? (
        children
      ) : (
        <span className="sr-only">{children}</span>
      )}
      {!isLoading && IconTrailing ? (
        <IconTrailing className="size-4" aria-hidden="true" />
      ) : null}
    </button>
  );
}
