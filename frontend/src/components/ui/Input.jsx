import { forwardRef } from "react";
import { cn } from "../../lib/cn";

const Input = forwardRef(({ className, ...props }, ref) => (
  <input
    ref={ref}
    className={cn(
      "w-full rounded-md border border-border bg-surface px-3 py-2 text-[13.5px] text-ink placeholder:text-faint",
      "focus:border-accent focus:outline-none transition-colors",
      className
    )}
    {...props}
  />
));
Input.displayName = "Input";

export default Input;
