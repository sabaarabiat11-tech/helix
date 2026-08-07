import { forwardRef, useId, useState } from "react";
import { AlertCircle, CheckCircle2, Eye, EyeOff, Loader2 } from "lucide-react";
import { api } from "../../api/client";
import { cn } from "../../lib/cn";

/** Labelled field with an accessible error association. */
export const Field = forwardRef(function Field(
  { label, type = "text", error, hint, className, ...props },
  ref
) {
  const id = useId();
  const errorId = `${id}-error`;
  const hintId = `${id}-hint`;
  const [revealed, setRevealed] = useState(false);
  const isPassword = type === "password";

  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      <label htmlFor={id} className="text-[12.5px] font-medium text-dim">
        {label}
      </label>
      <div className="relative">
        <input
          ref={ref}
          id={id}
          type={isPassword && revealed ? "text" : type}
          aria-invalid={error ? "true" : undefined}
          aria-describedby={cn(error && errorId, hint && hintId) || undefined}
          className={cn(
            "w-full rounded-md border bg-surface px-3 py-2.5 text-[13.5px] text-ink placeholder:text-faint",
            "focus:outline-none focus:ring-2 focus:ring-accent/40 transition-colors",
            isPassword && "pr-10",
            error ? "border-danger focus:border-danger" : "border-border focus:border-accent"
          )}
          {...props}
        />
        {isPassword && (
          <button
            type="button"
            onClick={() => setRevealed((v) => !v)}
            className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 rounded text-faint hover:text-ink transition-colors"
            aria-label={revealed ? "Hide password" : "Show password"}
            tabIndex={-1}
          >
            {revealed ? <EyeOff size={15} /> : <Eye size={15} />}
          </button>
        )}
      </div>
      {hint && !error && (
        <p id={hintId} className="text-[11.5px] text-faint">{hint}</p>
      )}
      {error && (
        <p id={errorId} className="text-[11.5px] text-danger flex items-center gap-1.5">
          <AlertCircle size={12} className="shrink-0" />
          {error}
        </p>
      )}
    </div>
  );
});

export function FormError({ children }) {
  if (!children) return null;
  return (
    <div
      role="alert"
      className="flex items-start gap-2 rounded-md border border-danger/30 bg-danger-soft px-3.5 py-2.5 text-[12.5px] text-danger"
    >
      <AlertCircle size={14} className="shrink-0 mt-[1px]" />
      <span>{children}</span>
    </div>
  );
}

export function FormSuccess({ children }) {
  if (!children) return null;
  return (
    <div
      role="status"
      className="flex items-start gap-2 rounded-md border border-success/30 bg-success-soft px-3.5 py-2.5 text-[12.5px] text-success"
    >
      <CheckCircle2 size={14} className="shrink-0 mt-[1px]" />
      <span>{children}</span>
    </div>
  );
}

export function SubmitButton({ loading, children, ...props }) {
  return (
    <button
      type="submit"
      disabled={loading}
      className={cn(
        "w-full inline-flex items-center justify-center gap-2 rounded-md py-2.5 text-[13.5px] font-semibold",
        "bg-accent text-[#04121f] transition-all duration-150",
        "shadow-[0_0_20px_-4px_rgba(0,212,255,0.6),0_1px_0_0_rgba(255,255,255,0.15)_inset]",
        "hover:bg-accent-strong active:scale-[0.99]",
        "disabled:opacity-50 disabled:pointer-events-none",
        "focus-visible:outline-2 focus-visible:outline-accent focus-visible:outline-offset-2"
      )}
      {...props}
    >
      {loading && <Loader2 size={14} className="animate-spin" />}
      {children}
    </button>
  );
}

/** Brand marks are inline SVG so the CSP-safe build has no external requests. */
const PROVIDER_ICONS = {
  google: (
    <svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true">
      <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.76h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
      <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.76c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84A11 11 0 0 0 12 23z" />
      <path fill="#FBBC05" d="M5.84 14.11a6.6 6.6 0 0 1 0-4.22V7.05H2.18a11 11 0 0 0 0 9.9l3.66-2.84z" />
      <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.05l3.66 2.84C6.71 7.31 9.14 5.38 12 5.38z" />
    </svg>
  ),
  github: (
    <svg viewBox="0 0 24 24" width="15" height="15" fill="currentColor" aria-hidden="true">
      <path d="M12 .5C5.37.5 0 5.87 0 12.5c0 5.3 3.44 9.8 8.21 11.39.6.11.82-.26.82-.58v-2.03c-3.34.73-4.04-1.61-4.04-1.61-.55-1.39-1.34-1.76-1.34-1.76-1.09-.75.08-.73.08-.73 1.2.08 1.84 1.24 1.84 1.24 1.07 1.834 2.81 1.304 3.5.997.11-.776.42-1.305.76-1.605-2.67-.3-5.47-1.335-5.47-5.94 0-1.31.47-2.38 1.24-3.22-.13-.3-.54-1.523.1-3.176 0 0 1.01-.323 3.3 1.23a11.5 11.5 0 0 1 6.01 0c2.29-1.553 3.3-1.23 3.3-1.23.64 1.653.24 2.876.12 3.176.77.84 1.23 1.91 1.23 3.22 0 4.617-2.8 5.635-5.48 5.93.43.372.82 1.102.82 2.222v3.293c0 .32.21.694.83.576A12.01 12.01 0 0 0 24 12.5C24 5.87 18.63.5 12 .5z" />
    </svg>
  ),
  linkedin: (
    <svg viewBox="0 0 24 24" width="15" height="15" fill="#0A66C2" aria-hidden="true">
      <path d="M20.45 20.45h-3.56v-5.57c0-1.33-.03-3.04-1.85-3.04-1.85 0-2.14 1.45-2.14 2.94v5.67H9.35V9h3.41v1.56h.05c.48-.9 1.63-1.85 3.36-1.85 3.6 0 4.27 2.37 4.27 5.45v6.29zM5.34 7.43a2.06 2.06 0 1 1 0-4.13 2.06 2.06 0 0 1 0 4.13zM7.12 20.45H3.55V9h3.57v11.45zM22.22 0H1.77C.79 0 0 .77 0 1.72v20.56C0 23.23.79 24 1.77 24h20.45c.98 0 1.78-.77 1.78-1.72V1.72C24 .77 23.2 0 22.22 0z" />
    </svg>
  ),
};

export function OAuthButtons({ providers, next = "/", disabled }) {
  if (!providers?.length) return null;
  return (
    <div className="flex flex-col gap-2">
      {providers.map((provider) => (
        <a
          key={provider.id}
          // A full-page navigation to the backend, so it must be the absolute
          // API origin in production — a relative path would hit Vercel.
          href={disabled ? undefined : api.oauthStartUrl(provider.id, next)}
          aria-disabled={disabled || undefined}
          className={cn(
            "inline-flex items-center justify-center gap-2.5 rounded-md border border-border bg-surface-2",
            "py-2.5 text-[13px] font-medium text-ink transition-colors",
            "hover:bg-surface-3 hover:border-accent/30",
            "focus-visible:outline-2 focus-visible:outline-accent focus-visible:outline-offset-2",
            disabled && "opacity-50 pointer-events-none"
          )}
        >
          {PROVIDER_ICONS[provider.id]}
          Continue with {provider.label}
        </a>
      ))}
    </div>
  );
}

export function Divider({ children = "or" }) {
  return (
    <div className="flex items-center gap-3" role="separator">
      <span className="flex-1 h-px bg-border" />
      <span className="text-[11px] uppercase tracking-wider text-faint">{children}</span>
      <span className="flex-1 h-px bg-border" />
    </div>
  );
}

/**
 * Password strength as a simple, honest signal: length plus character-class
 * variety. Not a security control — the server enforces the real minimum —
 * just feedback while typing.
 */
export function PasswordStrength({ value }) {
  if (!value) return null;

  const checks = [
    value.length >= 8,
    value.length >= 12,
    /[a-z]/.test(value) && /[A-Z]/.test(value),
    /\d/.test(value) || /[^A-Za-z0-9]/.test(value),
  ];
  const score = checks.filter(Boolean).length;
  const labels = ["Too short", "Weak", "Fair", "Good", "Strong"];
  const colors = ["bg-danger", "bg-danger", "bg-warning", "bg-accent", "bg-success"];

  return (
    <div className="flex items-center gap-2.5 -mt-0.5">
      <div className="flex-1 flex gap-1" aria-hidden="true">
        {[0, 1, 2, 3].map((i) => (
          <span
            key={i}
            className={cn("h-[3px] flex-1 rounded-full transition-colors", i < score ? colors[score] : "bg-surface-3")}
          />
        ))}
      </div>
      <span className="text-[11px] text-faint w-16 text-right">{labels[score]}</span>
    </div>
  );
}
