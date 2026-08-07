import { useState } from "react";
import { Link } from "react-router-dom";
import { MailCheck } from "lucide-react";
import { api } from "../../api/client";
import AuthLayout from "../../components/auth/AuthLayout";
import { Field, FormError, SubmitButton } from "../../components/auth/AuthFormBits";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      await api.forgotPassword(email);
      // The API deliberately responds identically whether or not the address
      // is registered, and so does this screen — otherwise it becomes a way to
      // check which emails have accounts.
      setSent(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  if (sent) {
    return (
      <AuthLayout
        title="Check your inbox"
        subtitle={`If an account exists for ${email}, a reset link is on its way.`}
        footer={
          <Link to="/login" className="text-accent hover:text-accent-strong font-medium">
            Back to sign in
          </Link>
        }
      >
        <div className="flex flex-col gap-5">
          <div className="flex items-center gap-3 rounded-md border border-border glass-panel px-4 py-4">
            <span className="inline-flex items-center justify-center w-9 h-9 rounded-md bg-accent-soft text-accent shrink-0">
              <MailCheck size={17} />
            </span>
            <p className="text-[12.5px] text-dim leading-relaxed">
              The link expires in 24 hours and can be used once.
            </p>
          </div>
          <button
            type="button"
            onClick={() => setSent(false)}
            className="text-[12.5px] text-faint hover:text-accent transition-colors self-start"
          >
            Use a different email address
          </button>
        </div>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout
      title="Reset your password"
      subtitle="Enter the email you signed up with and we'll send you a reset link."
      footer={
        <Link to="/login" className="text-accent hover:text-accent-strong font-medium">
          Back to sign in
        </Link>
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
        <SubmitButton loading={submitting}>
          {submitting ? "Sending…" : "Send reset link"}
        </SubmitButton>
      </form>
    </AuthLayout>
  );
}
