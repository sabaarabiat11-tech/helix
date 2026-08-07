import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  AlertTriangle, Bell, Check, Loader2, Lock, LogOut, Mail, Palette,
  Send, SlidersHorizontal, Trash2, User,
} from "lucide-react";
import { api } from "../api/client";
import { useAuth } from "../hooks/AuthContext";
import PageShell from "../components/PageShell";
import Card from "../components/ui/Card";
import Button from "../components/ui/Button";
import Badge from "../components/ui/Badge";
import TagInput from "../components/ui/TagInput";
import { Field, FormError, FormSuccess } from "../components/auth/AuthFormBits";
import { cn } from "../lib/cn";

const SENIORITY_OPTIONS = [
  { value: "any", label: "Any" },
  { value: "junior", label: "Junior" },
  { value: "mid", label: "Mid-level" },
  { value: "senior", label: "Senior" },
  { value: "leadership", label: "Leadership" },
];

const DIGEST_OPTIONS = [
  { value: "off", label: "Off", hint: "No scheduled emails" },
  { value: "instant", label: "Instant", hint: "As discoveries land" },
  { value: "daily", label: "Daily", hint: "One summary each morning" },
  { value: "weekly", label: "Weekly", hint: "Mondays — the default" },
];

const NOTIFICATION_TOGGLES = [
  { key: "notify_new_recommendations", label: "New recommendations", hint: "When people matching your interests are found" },
  { key: "notify_pipeline_complete", label: "Pipeline runs", hint: "When a discovery run finishes" },
  { key: "notify_new_companies", label: "New companies", hint: "When an organization enters the network" },
  { key: "notify_weekly_report", label: "Weekly reports", hint: "When a new report is generated" },
  { key: "notify_ai_insights", label: "AI insights", hint: "When fresh insights are available" },
];

function Section({ icon: Icon, title, description, children, className }) {
  return (
    <Card className={cn("p-6", className)}>
      <div className="flex items-start gap-3 mb-5">
        <span className="inline-flex items-center justify-center w-9 h-9 rounded-md bg-accent-soft text-accent shrink-0">
          <Icon size={17} />
        </span>
        <div className="min-w-0">
          <h2 className="font-display font-semibold text-[14.5px] text-ink">{title}</h2>
          {description && <p className="text-[12.5px] text-faint mt-0.5 leading-relaxed">{description}</p>}
        </div>
      </div>
      {children}
    </Card>
  );
}

function Toggle({ checked, onChange, label, hint, disabled }) {
  return (
    <label className={cn("flex items-start gap-3 py-2.5 cursor-pointer group", disabled && "opacity-50 cursor-not-allowed")}>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-label={label}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={cn(
          "relative mt-0.5 w-9 h-5 rounded-full shrink-0 transition-colors duration-150",
          "focus-visible:outline-2 focus-visible:outline-accent focus-visible:outline-offset-2",
          checked ? "bg-accent" : "bg-surface-3"
        )}
      >
        <span
          className={cn(
            "absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform duration-150",
            checked ? "translate-x-[18px]" : "translate-x-0.5"
          )}
        />
      </button>
      <div className="min-w-0">
        <div className="text-[13px] text-ink font-medium">{label}</div>
        {hint && <div className="text-[11.5px] text-faint mt-0.5">{hint}</div>}
      </div>
    </label>
  );
}

/** Saves are debounced-on-action rather than on a form submit, so each control
 * feels immediate; this reports the result without a modal. */
function SaveStatus({ state }) {
  if (state === "saving") {
    return <span className="text-[11.5px] text-faint inline-flex items-center gap-1.5"><Loader2 size={11} className="animate-spin" /> Saving…</span>;
  }
  if (state === "saved") {
    return <span className="text-[11.5px] text-success inline-flex items-center gap-1.5"><Check size={12} /> Saved</span>;
  }
  if (state) return <span className="text-[11.5px] text-danger">{state}</span>;
  return null;
}

export default function Settings() {
  const { user, preferences, linkedProviders, hasPassword, updateProfile, updatePreferences, setTheme, logout, reloadAccount } = useAuth();

  const [name, setName] = useState(user?.name || "");
  const [profileState, setProfileState] = useState("");
  const [prefState, setPrefState] = useState("");
  const [digestState, setDigestState] = useState("");
  const [passwordState, setPasswordState] = useState("");
  const [passwordError, setPasswordError] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [verifyState, setVerifyState] = useState("");
  const [deleting, setDeleting] = useState(false);

  useEffect(() => setName(user?.name || ""), [user?.name]);

  async function savePreferences(fields, setState = setPrefState) {
    setState("saving");
    try {
      await updatePreferences(fields);
      setState("saved");
      setTimeout(() => setState(""), 2000);
    } catch (err) {
      setState(err.message);
    }
  }

  async function saveProfile(event) {
    event.preventDefault();
    setProfileState("saving");
    try {
      await updateProfile({ name });
      setProfileState("saved");
      setTimeout(() => setProfileState(""), 2000);
    } catch (err) {
      setProfileState(err.message);
    }
  }

  async function changePassword(event) {
    event.preventDefault();
    setPasswordError("");
    setPasswordState("saving");
    try {
      await api.changePassword(currentPassword, newPassword);
      setPasswordState("saved");
      setCurrentPassword("");
      setNewPassword("");
      setTimeout(() => setPasswordState(""), 2500);
    } catch (err) {
      setPasswordError(err.message);
      setPasswordState("");
    }
  }

  async function sendTestDigest() {
    setDigestState("saving");
    try {
      const result = await api.sendTestDigest();
      setDigestState(`Sent to ${result.sent_to}`);
      setTimeout(() => setDigestState(""), 4000);
    } catch (err) {
      setDigestState(err.message);
    }
  }

  async function resendVerification() {
    setVerifyState("saving");
    try {
      await api.resendVerification();
      setVerifyState("Confirmation email sent");
      setTimeout(() => setVerifyState(""), 4000);
    } catch (err) {
      setVerifyState(err.message);
    }
  }

  async function deleteAccount() {
    const confirmed = window.confirm(
      "Delete your account permanently?\n\nYour watchlist, notes, preferences and notifications will be erased. This cannot be undone."
    );
    if (!confirmed) return;
    setDeleting(true);
    try {
      await api.deleteAccount();
      await logout();
    } catch (err) {
      window.alert(`Could not delete the account: ${err.message}`);
      setDeleting(false);
    }
  }

  if (!preferences || !user) {
    return (
      <PageShell title="Settings" subtitle="Your account and preferences">
        <div className="flex items-center gap-2 text-[13px] text-faint">
          <Loader2 size={14} className="animate-spin" /> Loading your settings…
        </div>
      </PageShell>
    );
  }

  return (
    <PageShell title="Settings" subtitle="Your account, preferences and email delivery">
      <div className="flex flex-col gap-4 max-w-3xl">

        {!user.email_verified && (
          <motion.div initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }}>
            <div className="flex flex-wrap items-center gap-3 rounded-lg border border-warning/30 bg-warning-soft px-4 py-3">
              <AlertTriangle size={16} className="text-warning shrink-0" />
              <p className="text-[12.5px] text-warning flex-1 min-w-[200px]">
                Your email isn't confirmed yet. Check your inbox for the link.
              </p>
              <Button size="sm" variant="secondary" onClick={resendVerification} disabled={verifyState === "saving"}>
                {verifyState === "saving" ? "Sending…" : "Resend"}
              </Button>
              {verifyState && verifyState !== "saving" && (
                <span className="text-[11.5px] text-success">{verifyState}</span>
              )}
            </div>
          </motion.div>
        )}

        {/* Profile */}
        <Section icon={User} title="Profile" description="How you appear inside Helix.">
          <form onSubmit={saveProfile} className="flex flex-col gap-4">
            <Field label="Name" value={name} onChange={(e) => setName(e.target.value)} required />
            <div className="flex flex-col gap-1.5">
              <span className="text-[12.5px] font-medium text-dim">Email</span>
              <div className="flex items-center gap-2.5 flex-wrap">
                <span className="text-[13.5px] text-ink font-mono">{user.email}</span>
                <Badge tone={user.email_verified ? "success" : "warning"}>
                  {user.email_verified ? "Verified" : "Unverified"}
                </Badge>
                {user.is_admin && <Badge tone="accent">Admin</Badge>}
              </div>
            </div>
            <div className="flex items-center gap-3">
              <Button type="submit" variant="primary" size="md" disabled={profileState === "saving" || name === user.name}>
                Save profile
              </Button>
              <SaveStatus state={profileState} />
            </div>
          </form>
        </Section>

        {/* Recommendation tuning */}
        <Section
          icon={SlidersHorizontal}
          title="What you care about"
          description="These re-rank your recommendations immediately. Every adjustment is shown as a reason on the profile it affects."
        >
          <div className="flex flex-col gap-5">
            <TagInput
              label="Focus areas"
              hint="Topics, methods or fields — e.g. protein folding, single-cell, drug discovery"
              placeholder="Add a focus area and press Enter"
              value={preferences.focus_areas}
              onChange={(focus_areas) => savePreferences({ focus_areas })}
            />
            <TagInput
              label="Target companies"
              hint="Organizations you want surfaced first"
              placeholder="Add a company and press Enter"
              value={preferences.preferred_companies}
              onChange={(preferred_companies) => savePreferences({ preferred_companies })}
            />
            <TagInput
              label="Locations"
              hint="Cities, regions or countries you're recruiting or collaborating in"
              placeholder="Add a location and press Enter"
              value={preferences.preferred_locations}
              onChange={(preferred_locations) => savePreferences({ preferred_locations })}
            />

            <div className="flex flex-col gap-2">
              <span className="text-[12.5px] font-medium text-dim">Seniority</span>
              <div className="flex flex-wrap gap-2">
                {SENIORITY_OPTIONS.map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => savePreferences({ seniority_preference: option.value })}
                    className={cn(
                      "px-3 py-1.5 rounded-md text-[12.5px] font-medium border transition-colors",
                      preferences.seniority_preference === option.value
                        ? "border-accent bg-accent-soft text-accent"
                        : "border-border text-dim hover:text-ink hover:border-accent/30"
                    )}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="flex flex-col gap-2">
              <div className="flex items-center justify-between">
                <span className="text-[12.5px] font-medium text-dim">Minimum score</span>
                <span className="font-mono text-[12.5px] text-accent">{preferences.min_score}</span>
              </div>
              <input
                type="range"
                min="0"
                max="100"
                step="5"
                value={preferences.min_score}
                onChange={(e) => savePreferences({ min_score: Number(e.target.value) })}
                aria-label="Minimum recommendation score"
                className="w-full accent-[var(--color-accent)]"
              />
              <p className="text-[11.5px] text-faint">
                Hide anyone scoring below this. Leave at 0 to see everything.
              </p>
            </div>

            <SaveStatus state={prefState} />
          </div>
        </Section>

        {/* Email */}
        <Section icon={Mail} title="Email digests" description="A summary of new discoveries, ranked for you.">
          <div className="flex flex-col gap-4">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {DIGEST_OPTIONS.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => savePreferences({ digest_frequency: option.value })}
                  className={cn(
                    "flex flex-col items-start gap-0.5 px-3 py-2.5 rounded-md border text-left transition-colors",
                    preferences.digest_frequency === option.value
                      ? "border-accent bg-accent-soft"
                      : "border-border hover:border-accent/30"
                  )}
                >
                  <span className={cn("text-[13px] font-semibold", preferences.digest_frequency === option.value ? "text-accent" : "text-ink")}>
                    {option.label}
                  </span>
                  <span className="text-[11px] text-faint leading-tight">{option.hint}</span>
                </button>
              ))}
            </div>

            <div className="flex items-center gap-3 flex-wrap">
              <Button variant="secondary" size="md" onClick={sendTestDigest} disabled={digestState === "saving"}>
                <Send size={13} />
                {digestState === "saving" ? "Sending…" : "Send me one now"}
              </Button>
              {digestState && digestState !== "saving" && (
                <span className="text-[11.5px] text-dim">{digestState}</span>
              )}
            </div>
          </div>
        </Section>

        {/* Notifications */}
        <Section icon={Bell} title="Notifications" description="Which events reach your in-app notification center.">
          <div className="flex flex-col divide-y divide-border">
            {NOTIFICATION_TOGGLES.map((toggle) => (
              <Toggle
                key={toggle.key}
                label={toggle.label}
                hint={toggle.hint}
                checked={preferences[toggle.key]}
                onChange={(value) => savePreferences({ [toggle.key]: value })}
              />
            ))}
          </div>
        </Section>

        {/* Appearance */}
        <Section icon={Palette} title="Appearance" description="Saved to your account, so it follows you across devices.">
          <div className="flex gap-2">
            {["dark", "light"].map((theme) => (
              <button
                key={theme}
                type="button"
                onClick={() => setTheme(theme)}
                className={cn(
                  "flex-1 px-4 py-3 rounded-md border text-[13px] font-medium capitalize transition-colors",
                  preferences.theme === theme
                    ? "border-accent bg-accent-soft text-accent"
                    : "border-border text-dim hover:text-ink hover:border-accent/30"
                )}
              >
                {theme}
              </button>
            ))}
          </div>
        </Section>

        {/* Security */}
        <Section icon={Lock} title="Security" description={hasPassword ? "Change your password or sign out everywhere." : "Set a password so you can sign in without a provider."}>
          <form onSubmit={changePassword} className="flex flex-col gap-4">
            <FormError>{passwordError}</FormError>
            {passwordState === "saved" && <FormSuccess>Password updated.</FormSuccess>}

            {hasPassword && (
              <Field
                label="Current password"
                type="password"
                autoComplete="current-password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                required
              />
            )}
            <Field
              label={hasPassword ? "New password" : "Create a password"}
              type="password"
              autoComplete="new-password"
              hint="At least 8 characters"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              required
            />
            <div className="flex items-center gap-3 flex-wrap">
              <Button type="submit" variant="primary" size="md" disabled={passwordState === "saving"}>
                {passwordState === "saving" ? "Updating…" : hasPassword ? "Change password" : "Set password"}
              </Button>
              <Button type="button" variant="secondary" size="md" onClick={() => api.logoutAll().then(() => logout())}>
                <LogOut size={13} /> Sign out everywhere
              </Button>
            </div>
          </form>

          {linkedProviders?.length > 0 && (
            <div className="mt-5 pt-5 border-t border-border">
              <div className="text-[12.5px] font-medium text-dim mb-2.5">Connected accounts</div>
              <div className="flex flex-wrap gap-2">
                {linkedProviders.map((provider) => (
                  <div key={provider} className="flex items-center gap-2 rounded-md border border-border px-3 py-1.5">
                    <span className="text-[12.5px] text-ink capitalize">{provider}</span>
                    <button
                      type="button"
                      onClick={() => api.unlinkOAuth(provider).then(reloadAccount)}
                      className="text-[11.5px] text-faint hover:text-danger transition-colors"
                    >
                      Unlink
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </Section>

        {/* Danger zone */}
        <Card className="p-6 border-danger/25">
          <div className="flex items-start gap-3 mb-4">
            <span className="inline-flex items-center justify-center w-9 h-9 rounded-md bg-danger-soft text-danger shrink-0">
              <Trash2 size={17} />
            </span>
            <div>
              <h2 className="font-display font-semibold text-[14.5px] text-ink">Delete account</h2>
              <p className="text-[12.5px] text-faint mt-0.5 leading-relaxed">
                Erases your watchlist, notes, preferences and notifications. The shared
                discovery database is unaffected. This cannot be undone.
              </p>
            </div>
          </div>
          <Button variant="danger" size="md" onClick={deleteAccount} disabled={deleting}>
            {deleting ? "Deleting…" : "Delete my account"}
          </Button>
        </Card>
      </div>
    </PageShell>
  );
}
