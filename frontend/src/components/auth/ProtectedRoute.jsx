import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../../hooks/AuthContext";
import RouteFallback from "../RouteFallback";

/**
 * Gate for every signed-in route.
 *
 * The `initializing` check matters more than it looks: on a hard reload there
 * is no access token yet, and AuthContext is mid-way through exchanging the
 * refresh cookie for one. Redirecting during that window would bounce a
 * perfectly valid session to /login on every refresh.
 */
export default function ProtectedRoute() {
  const { isAuthenticated, initializing } = useAuth();
  const location = useLocation();

  // Uses the dependency-free fallback rather than the Lottie loader on
  // purpose: this component is on the critical path for every visitor,
  // including signed-out ones, and importing Lottie here would pull ~300KB of
  // animation runtime into the login page's initial payload.
  if (initializing) return <RouteFallback />;

  if (!isAuthenticated) {
    // Remember where they were going so sign-in can send them back there.
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <Outlet />;
}
