import { useEffect, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { refreshAccessToken } from "../../api/client";
import { useAuth } from "../../hooks/AuthContext";
import AuthLayout from "../../components/auth/AuthLayout";

/**
 * Landing point after an OAuth provider redirect.
 *
 * The backend has already set the httpOnly refresh cookie, so there is no
 * token in the URL to pick up — this page simply exchanges that cookie for an
 * access token and continues. Keeping the token out of the URL means it never
 * reaches browser history, server logs, or a Referer header.
 */
export default function OAuthCallback() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { reloadAccount, isAuthenticated, initializing } = useAuth();
  const handled = useRef(false);

  const next = searchParams.get("next") || "/dashboard";

  useEffect(() => {
    if (handled.current) return;
    handled.current = true;

    (async () => {
      try {
        await refreshAccessToken();
        await reloadAccount();
        navigate(next, { replace: true });
      } catch {
        navigate("/login?error=Sign-in%20could%20not%20be%20completed", { replace: true });
      }
    })();
  }, [navigate, next, reloadAccount]);

  // If AuthContext's own bootstrap resolves first, don't wait on this effect.
  useEffect(() => {
    if (!initializing && isAuthenticated) navigate(next, { replace: true });
  }, [initializing, isAuthenticated, navigate, next]);

  return (
    <AuthLayout title="Signing you in" subtitle="Finishing up with your provider.">
      <div className="flex items-center gap-3 rounded-md border border-border glass-panel px-4 py-4">
        <Loader2 size={18} className="animate-spin text-accent shrink-0" />
        <span className="text-[12.5px] text-dim">Establishing your session…</span>
      </div>
    </AuthLayout>
  );
}
