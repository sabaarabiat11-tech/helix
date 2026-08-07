import { forwardRef } from "react";
import { cva } from "class-variance-authority";
import { cn } from "../../lib/cn";

const button = cva(
  "inline-flex items-center justify-center gap-2 rounded-md font-semibold transition-all duration-150 disabled:opacity-40 disabled:pointer-events-none focus-visible:outline-2 focus-visible:outline-accent focus-visible:outline-offset-2 active:scale-[0.97]",
  {
    variants: {
      variant: {
        primary: "bg-accent text-[#04121f] hover:bg-accent-strong shadow-[0_0_20px_-4px_rgba(0,212,255,0.6),0_1px_0_0_rgba(255,255,255,0.15)_inset]",
        secondary: "bg-surface-2 text-ink border border-border hover:bg-surface-3",
        ghost: "text-dim hover:text-ink hover:bg-surface-2",
        danger: "bg-danger-soft text-danger hover:bg-danger/20",
        outline: "border border-border text-ink hover:bg-surface-2",
      },
      size: {
        sm: "text-[12px] px-2.5 py-1.5",
        md: "text-[13px] px-3.5 py-2",
        lg: "text-[14px] px-5 py-2.5",
        icon: "p-2",
      },
    },
    defaultVariants: { variant: "secondary", size: "md" },
  }
);

const Button = forwardRef(({ className, variant, size, ...props }, ref) => (
  <button ref={ref} className={cn(button({ variant, size }), className)} {...props} />
));
Button.displayName = "Button";

export default Button;
