import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../../api/client";
import { useAuth } from "../../hooks/AuthContext";
import AuthLayout from "../../components/auth/AuthLayout";
import {
  Divider,
  Field,
  FormError,
  OAuthButtons,
  SubmitButton,
} from "../../components/auth/AuthFormBits";

export default function Login() {
  const { login, isAuthenticated, initializing } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(searchParams.get("error") || "");
  const [submitting, setSubmitting] = useState(false);
  const [config, setConfig] = useState(null);

  // Where to land after signing in — either where they were headed before the
  // redirect, or the dashboard.
  const next = location.state?.from?.pathname || searchParams.get("next") || "/";

  useEffect(() => {
    api.authConfig().then(setConfig).catch(() => setConfig({ oauth_providers: [], signup_enabled: true }));
  }, []);

  useEffect(() => {
    if (!initializing && isAuthenticated) navigate(next, { replace: true });
  }, [initializing, isAuthenticated, navigate, next]);

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      await login(email, password);
      navigate(next, { replace: true });
    } catch (err) {
      setError(err.message);
      setSubmitting(false);
    }
  }

  return (
    <AuthLayout
      title="Welcome back"
      subtitle="Sign in to your Helix intelligence dashboard."
      footer={
        config?.signup_enabled !== false && (
          <>
            New to Helix?{" "}
            <Link to="/signup" className="text-accent hover:text-accent-strong font-medium">
              Create an account
            </Link>
          </>
        )
      }
    >
      <form onSubmit={handleSubmit} className="flex flex-col gap-4" noValidate>
        <FormError>{error}</FormError>

        <Field
          label="Email"
          type="email"
          name="email"
          autoComplete="email"
          placeholder="you@lab.org"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          autoFocus
        />

        <div className="flex flex-col gap-1.5">
          <Field
            label="Password"
            type="password"
            name="password"
            autoComplete="current-password"
            placeholder="••••••••"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          <Link
            to="/forgot-password"
            className="self-end text-[12px] text-faint hover:text-accent transition-colors"
          >
            Forgot your password?
          </Link>
        </div>

        <SubmitButton loading={submitting}>
          {submitting ? "Signing in…" : "Sign in"}
        </SubmitButton>

        {config?.oauth_providers?.length > 0 && (
          <>
            <Divider />
            <OAuthButtons providers={config.oauth_providers} next={next} disabled={submitting} />
          </>
        )}
      </form>
    </AuthLayout>
  );
}
