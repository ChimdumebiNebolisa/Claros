import { forwardRef, type TextareaHTMLAttributes, type Ref } from "react";
import { cn } from "./cn";

type TextareaProps = Omit<
  TextareaHTMLAttributes<HTMLTextAreaElement>,
  "onChange"
> & {
  onChange?: (value: string) => void;
  textAreaRef?: Ref<HTMLTextAreaElement>;
  textAreaClassName?: string;
};

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  function Textarea(
    { className, textAreaClassName, textAreaRef, onChange, ...props },
    forwardedRef,
  ) {
    return (
      <textarea
        ref={textAreaRef ?? forwardedRef}
        onChange={(event) => onChange?.(event.currentTarget.value)}
        className={cn(
          "block w-full resize-y rounded-[10px] border border-[var(--claros-line-strong)] bg-white px-4 py-3 text-base leading-6 text-[var(--claros-ink)] outline-none transition-[border-color,box-shadow] placeholder:text-[var(--claros-quiet)] focus:border-[var(--claros-blue)] focus:ring-4 focus:ring-[color-mix(in_srgb,var(--claros-blue)_14%,transparent)] disabled:cursor-not-allowed disabled:bg-[var(--claros-soft)] disabled:opacity-60",
          className,
          textAreaClassName,
        )}
        {...props}
      />
    );
  },
);
