import { Navigate } from "react-router-dom";
import { useAuth } from "../../hooks/AuthContext";
import RouteFallback from "../RouteFallback";

/**
 * Decides what `/` is.
 *
 * Signed out, it's the marketing landing page. Signed in, it's the dashboard —
 * reached by redirecting to `/dashboard` rather than rendering it here, so the
 * URL always matches what's on screen and a signed-in user can bookmark or
 * share the page they're actually looking at.
 *
 * The `initializing` guard matters on a hard reload: AuthContext is still
 * exchanging the refresh cookie for a token at that point, and rendering the
 * landing page in the meantime would flash marketing copy at someone who is
 * already logged in.
 */
export default function RootRoute({ landing }) {
  const { isAuthenticated, initializing } = useAuth();

  if (initializing) return <RouteFallback />;
  if (isAuthenticated) return <Navigate to="/dashboard" replace />;
  return landing;
}
