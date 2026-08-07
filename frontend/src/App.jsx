import { lazy, Suspense } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "./hooks/AuthContext";
import { RunProvider } from "./hooks/RunContext";
import { WatchlistProvider } from "./hooks/WatchlistContext";
import { NotificationsProvider } from "./hooks/NotificationsContext";
import { TooltipProvider } from "./components/ui/Tooltip";
import ProtectedRoute from "./components/auth/ProtectedRoute";
import RootRoute from "./components/auth/RootRoute";
import RouteFallback from "./components/RouteFallback";

// The landing page and login are the two entry points a signed-out visitor
// can arrive at directly, so both are bundled eagerly — making the very first
// screen wait on a second network round trip is the one place code splitting
// costs more than it saves.
import Landing from "./pages/Landing";
import Login from "./pages/auth/Login";

// Everything else is split per route. The heavy dependencies (three.js,
// recharts, lottie) are only pulled in by the routes that actually use them,
// so signing in no longer downloads the 3D renderer or the charting library.
// Layout carries the sidebar, command palette, log drawer and cinematic
// intro — none of which a signed-out visitor needs, and which between them
// pull in the Lottie runtime. Lazy so the login page doesn't pay for it.
const Layout = lazy(() => import("./components/Layout"));

const Signup = lazy(() => import("./pages/auth/Signup"));
const ForgotPassword = lazy(() => import("./pages/auth/ForgotPassword"));
const ResetPassword = lazy(() => import("./pages/auth/ResetPassword"));
const VerifyEmail = lazy(() => import("./pages/auth/VerifyEmail"));
const OAuthCallback = lazy(() => import("./pages/auth/OAuthCallback"));

const Dashboard = lazy(() => import("./pages/Dashboard"));
const Discoveries = lazy(() => import("./pages/Discoveries"));
const Companies = lazy(() => import("./pages/Companies"));
const CompanyDetail = lazy(() => import("./pages/CompanyDetail"));
const Recommendations = lazy(() => import("./pages/Recommendations"));
const Insights = lazy(() => import("./pages/Insights"));
const Watchlist = lazy(() => import("./pages/Watchlist"));
const Timeline = lazy(() => import("./pages/Timeline"));
const Analytics = lazy(() => import("./pages/Analytics"));
const Reports = lazy(() => import("./pages/Reports"));
const Settings = lazy(() => import("./pages/Settings"));

export default function App() {
  return (
    <BrowserRouter>
      {/* AuthProvider sits inside the router because its pages navigate, and
          outside the data providers because they all need the session. */}
      <AuthProvider>
        <TooltipProvider>
          <Suspense fallback={<RouteFallback />}>
            <Routes>
              {/* Public marketing surface at "/", dashboard for signed-in users */}
              <Route path="/" element={<RootRoute landing={<Landing />} />} />

              {/* Public */}
              <Route path="/login" element={<Login />} />
              <Route path="/signup" element={<Signup />} />
              <Route path="/forgot-password" element={<ForgotPassword />} />
              <Route path="/reset-password" element={<ResetPassword />} />
              <Route path="/verify-email" element={<VerifyEmail />} />
              <Route path="/auth/callback" element={<OAuthCallback />} />

              {/* Everything below requires a session */}
              <Route element={<ProtectedRoute />}>
                <Route
                  element={
                    <NotificationsProvider>
                      <WatchlistProvider>
                        <RunProvider>
                          <Layout />
                        </RunProvider>
                      </WatchlistProvider>
                    </NotificationsProvider>
                  }
                >
                  <Route path="dashboard" element={<Dashboard />} />
                  <Route path="discoveries" element={<Discoveries />} />
                  <Route path="recommendations" element={<Recommendations />} />
                  <Route path="watchlist" element={<Watchlist />} />
                  <Route path="timeline" element={<Timeline />} />
                  <Route path="companies" element={<Companies />} />
                  <Route path="companies/:name" element={<CompanyDetail />} />
                  <Route path="insights" element={<Insights />} />
                  <Route path="analytics" element={<Analytics />} />
                  <Route path="reports" element={<Reports />} />
                  <Route path="settings" element={<Settings />} />
                </Route>
              </Route>
            </Routes>
          </Suspense>
        </TooltipProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}
