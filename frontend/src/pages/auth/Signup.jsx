import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../../api/client";
import { useAuth } from "../../hooks/AuthContext";
import AuthLayout from "../../components/auth/AuthLayout";
import {
  Divider,
  Field,
  FormError,
  OAuthButtons,
  PasswordStrength,
  SubmitButton,
} from "../../components/auth/AuthFormBits";

const MIN_PASSWORD_LENGTH = 8;

export default function Signup() {
  const { signup, isAuthenticated, initializing } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(searchParams.get("error") || "");
  const [fieldErrors, setFieldErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [config, setConfig] = useState(null);

  useEffect(() => {
    api.authConfig().then(setConfig).catch(() => setConfig({ oauth_providers: [], signup_enabled: true }));
  }, []);

  useEffect(() => {
    if (!initializing && isAuthenticated) navigate("/", { replace: true });
  }, [initializing, isAuthenticated, navigate]);

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");

    // Validate client-side first so an obviously short password doesn't cost a
    // round trip; the server enforces the same rule regardless.
    if (password.length < MIN_PASSWORD_LENGTH) {
      setFieldErrors({ password: `Use at least ${MIN_PASSWORD_LENGTH} characters` });
      return;
    }
    setFieldErrors({});
    setSubmitting(true);

    try {
      await signup(email, password, name);
      navigate("/", { replace: true });
    } catch (err) {
      setError(err.message);
      setSubmitting(false);
    }
  }

  if (config && config.signup_enabled === false) {
    return (
      <AuthLayout
        title="Signups are closed"
        subtitle="This Helix deployment isn't accepting new accounts right now."
        footer={
          <Link to="/login" className="text-accent hover:text-accent-strong font-medium">
            Back to sign in
          </Link>
        }
      >
        <div />
      </AuthLayout>
    );
  }

  return (
    <AuthLayout
      title="Create your account"
      subtitle="Track the people building AI × Biology — ranked for what you care about."
      footer={
        <>
          Already have an account?{" "}
          <Link to="/login" className="text-accent hover:text-accent-strong font-medium">
            Sign in
          </Link>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="flex flex-col gap-4" noValidate>
        <FormError>{error}</FormError>

        <Field
          label="Name"
          name="name"
          autoComplete="name"
          placeholder="Ada Lovelace"
          value={name}
          onChange={(e) => setName(e.target.value)}
          autoFocus
        />

        <Field
          label="Email"
          type="email"
          name="email"
          autoComplete="email"
          placeholder="you@lab.org"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />

        <div className="flex flex-col gap-2">
          <Field
            label="Password"
            type="password"
            name="password"
            autoComplete="new-password"
            placeholder="At least 8 characters"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            error={fieldErrors.password}
            required
          />
          <PasswordStrength value={password} />
        </div>

        <SubmitButton loading={submitting}>
          {submitting ? "Creating account…" : "Create account"}
        </SubmitButton>

        {config?.oauth_providers?.length > 0 && (
          <>
            <Divider />
            <OAuthButtons providers={config.oauth_providers} disabled={submitting} />
          </>
        )}

        <p className="text-[11.5px] text-faint leading-relaxed text-center">
          We'll send a confirmation link to your inbox. You can start using Helix immediately.
        </p>
      </form>
    </AuthLayout>
  );
}
