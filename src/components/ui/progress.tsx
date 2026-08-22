import type * as React from "react";
import { Progress as ProgressPrimitive } from "radix-ui";
import { cn } from "../../lib/utils";

type ProgressProps = React.ComponentProps<typeof ProgressPrimitive.Root>;

export function Progress({ className, value, ...props }: ProgressProps) {
  return (
    <ProgressPrimitive.Root
      data-slot="progress"
      className={cn("progress-track", className)}
      value={value}
      {...props}
    >
      <ProgressPrimitive.Indicator
        data-slot="progress-indicator"
        className="progress-track-indicator"
        style={{ transform: `translateX(-${100 - (value ?? 0)}%)` }}
      />
    </ProgressPrimitive.Root>
  );
}
