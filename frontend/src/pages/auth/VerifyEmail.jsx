import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { CheckCircle2, Loader2, XCircle } from "lucide-react";
import { api } from "../../api/client";
import { useAuth } from "../../hooks/AuthContext";
import AuthLayout from "../../components/auth/AuthLayout";

export default function VerifyEmail() {
  const [searchParams] = useSearchParams();
  const { isAuthenticated, reloadAccount } = useAuth();
  const token = searchParams.get("token") || "";

  const [state, setState] = useState(token ? "verifying" : "missing");
  const [error, setError] = useState("");
  // Verification burns a single-use token, so it must fire exactly once even
  // though React StrictMode double-invokes effects in development.
  const attempted = useRef(false);

  useEffect(() => {
    if (!token || attempted.current) return;
    attempted.current = true;

    api
      .verifyEmail(token)
      .then(async () => {
        setState("verified");
        if (isAuthenticated) {
          // Refresh the cached account so the "unverified" banner disappears
          // without needing a reload.
          try {
            await reloadAccount();
          } catch {
            /* non-fatal */
          }
        }
      })
      .catch((err) => {
        setError(err.message);
        setState("failed");
      });
  }, [token, isAuthenticated, reloadAccount]);

  const content = {
    verifying: {
      icon: <Loader2 size={20} className="animate-spin text-accent" />,
      title: "Confirming your email",
      subtitle: "One moment.",
      body: null,
    },
    verified: {
      icon: <CheckCircle2 size={20} className="text-success" />,
      title: "Email confirmed",
      subtitle: "Your account is fully activated.",
      body: (
        <Link
          to="/"
          className="inline-flex items-center justify-center w-full rounded-md bg-accent py-2.5 text-[13.5px] font-semibold text-[#04121f] hover:bg-accent-strong transition-colors"
        >
          Go to my dashboard
        </Link>
      ),
    },
    failed: {
      icon: <XCircle size={20} className="text-danger" />,
      title: "This link didn't work",
      subtitle: error || "The link may have expired or already been used.",
      body: (
        <Link
          to="/"
          className="inline-flex items-center justify-center w-full rounded-md border border-border bg-surface-2 py-2.5 text-[13.5px] font-semibold text-ink hover:bg-surface-3 transition-colors"
        >
          Continue to Helix
        </Link>
      ),
    },
    missing: {
      icon: <XCircle size={20} className="text-danger" />,
      title: "Nothing to verify",
      subtitle: "This link is missing its confirmation token.",
      body: (
        <Link
          to="/"
          className="inline-flex items-center justify-center w-full rounded-md border border-border bg-surface-2 py-2.5 text-[13.5px] font-semibold text-ink hover:bg-surface-3 transition-colors"
        >
          Continue to Helix
        </Link>
      ),
    },
  }[state];

  return (
    <AuthLayout
      title={content.title}
      subtitle={content.subtitle}
      footer={
        <Link to="/login" className="text-accent hover:text-accent-strong font-medium">
          Back to sign in
        </Link>
      }
    >
      <div className="flex flex-col gap-5">
        <div className="flex items-center gap-3 rounded-md border border-border glass-panel px-4 py-4">
          <span className="shrink-0">{content.icon}</span>
          <span className="text-[12.5px] text-dim">
            {state === "verifying" ? "Checking your confirmation link…" : content.subtitle}
          </span>
        </div>
        {content.body}
      </div>
    </AuthLayout>
  );
}
