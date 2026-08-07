import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../../api/client";
import AuthLayout from "../../components/auth/AuthLayout";
import {
  Field,
  FormError,
  FormSuccess,
  PasswordStrength,
  SubmitButton,
} from "../../components/auth/AuthFormBits";

const MIN_PASSWORD_LENGTH = 8;

export default function ResetPassword() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get("token") || "";

  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [fieldErrors, setFieldErrors] = useState({});
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");

    const errors = {};
    if (password.length < MIN_PASSWORD_LENGTH) {
      errors.password = `Use at least ${MIN_PASSWORD_LENGTH} characters`;
    }
    if (password !== confirm) {
      errors.confirm = "Passwords don't match";
    }
    if (Object.keys(errors).length) {
      setFieldErrors(errors);
      return;
    }

    setFieldErrors({});
    setSubmitting(true);
    try {
      await api.resetPassword(token, password);
      setDone(true);
      // Give the confirmation a beat to register before moving on.
      setTimeout(() => navigate("/login", { replace: true }), 2200);
    } catch (err) {
      setError(err.message);
      setSubmitting(false);
    }
  }

  if (!token) {
    return (
      <AuthLayout
        title="This link is incomplete"
        subtitle="The reset link is missing its token. Request a new one and try again."
        footer={
          <Link to="/login" className="text-accent hover:text-accent-strong font-medium">
            Back to sign in
          </Link>
        }
      >
        <Link
          to="/forgot-password"
          className="inline-flex items-center justify-center w-full rounded-md bg-accent py-2.5 text-[13.5px] font-semibold text-[#04121f] hover:bg-accent-strong transition-colors"
        >
          Request a new link
        </Link>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout
      title="Choose a new password"
      subtitle="Setting a new password signs you out of every other device."
      footer={
        <Link to="/login" className="text-accent hover:text-accent-strong font-medium">
          Back to sign in
        </Link>
      }
    >
      <form onSubmit={handleSubmit} className="flex flex-col gap-4" noValidate>
        <FormError>{error}</FormError>
        {done && <FormSuccess>Password updated. Taking you to sign in…</FormSuccess>}

        <div className="flex flex-col gap-2">
          <Field
            label="New password"
            type="password"
            autoComplete="new-password"
            placeholder="At least 8 characters"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            error={fieldErrors.password}
            disabled={done}
            required
            autoFocus
          />
          <PasswordStrength value={password} />
        </div>

        <Field
          label="Confirm new password"
          type="password"
          autoComplete="new-password"
          placeholder="Type it again"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          error={fieldErrors.confirm}
          disabled={done}
          required
        />

        <SubmitButton loading={submitting} disabled={done || submitting}>
          {done ? "Password updated" : submitting ? "Updating…" : "Update password"}
        </SubmitButton>
      </form>
    </AuthLayout>
  );
}
