"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch, setApiCsrfToken } from "../../lib/api-fetch";
import { clearActiveWorkspace, saveActiveWorkspace } from "../../lib/workspace-session.mjs";
import { clearWorkflowSession } from "../../lib/workflow-session.mjs";
import { API_BASE } from "../../lib/api-base";

const GOOGLE_AUTH_ENABLED = process.env.NEXT_PUBLIC_GOOGLE_AUTH_ENABLED === "true";
type Mode = "choose" | "login" | "register";

function authError(response: Response, data: unknown) {
  if (data && typeof data === "object" && "detail" in data && typeof data.detail === "string") return `${data.detail} (HTTP ${response.status})`;
  if (response.status === 401) return "Email or password is incorrect. (HTTP 401)";
  if (response.status === 403) return "This authentication request was denied. (HTTP 403)";
  if (response.status >= 500) return `The authentication service returned HTTP ${response.status}.`;
  return `Authentication failed (HTTP ${response.status}).`;
}

function safeReturnTo(value: string | null) {
  return value && value.startsWith("/") && !value.startsWith("//") ? value : "/";
}

export default function AuthenticationPage() {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("choose");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [firstName, setFirstName] = useState("");
  const [surname, setSurname] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [returnTo, setReturnTo] = useState("/");

  useEffect(() => {
    const query = new URLSearchParams(window.location.search);
    const destination = safeReturnTo(query.get("returnTo"));
    setReturnTo(destination);
    if (query.get("google") === "success") router.replace(destination);
    const code = query.get("error");
    if (code) setError(code === "account_link_required" ? "An account already uses this email. Sign in using its original method; automatic account linking is disabled." : `Google sign-in could not complete (${code.replaceAll("_", " ")}).`);
  }, [router]);

  const clearOldWorkspace = () => { clearActiveWorkspace(window.sessionStorage); clearWorkflowSession(window.sessionStorage); };
  const submitCredentials = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault(); setBusy(true); setError("");
    try {
      const route = mode === "register" ? "register" : "login";
      const body = mode === "register" ? { first_name: firstName, surname, email, password, confirm_password: confirmPassword } : { email, password };
      const response = await apiFetch(`${API_BASE}/api/v1/auth/${route}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      const data = await response.json().catch(() => null);
      if (!response.ok) throw new Error(authError(response, data));
      setApiCsrfToken(data?.session?.csrf_token);
      clearOldWorkspace(); router.push(returnTo);
    } catch (reason) { setError(reason instanceof TypeError ? "The authentication API could not be reached. Check that FastAPI is running and NEXT_PUBLIC_API_URL matches it." : reason instanceof Error ? reason.message : "Authentication could not be completed."); }
    finally { setBusy(false); }
  };

  const startJudge = async () => {
    setBusy(true); setError("");
    try {
      const response = await apiFetch(`${API_BASE}/api/v1/auth/judge`, { method: "POST" });
      const data = await response.json().catch(() => null);
      if (!response.ok) throw new Error(authError(response, data));
      setApiCsrfToken(data?.session?.csrf_token);
      clearOldWorkspace(); saveActiveWorkspace(window.sessionStorage, data.workspace_id); router.push(returnTo === "/" ? "/studio" : returnTo);
    } catch (reason) { setError(reason instanceof TypeError ? "The authentication API could not be reached. Check that FastAPI is running and NEXT_PUBLIC_API_URL matches it." : reason instanceof Error ? reason.message : "Judge access could not be started."); }
    finally { setBusy(false); }
  };

  return <main className="min-h-screen px-4 pb-16 pt-28 sm:px-6 lg:px-12"><div className="mx-auto max-w-xl">
    <Link href="/" className="text-sm text-secondary underline underline-offset-4 hover:text-off-white">← Proofmint home</Link>
    <section className="mt-6 border border-border-structural bg-surface-container-low p-6 sm:p-9">
      <p className="font-mono text-xs uppercase tracking-[0.2em] text-verification-mint">Nothing ships unproven</p>
      <h1 className="mt-3 text-3xl font-semibold text-off-white">{mode === "register" ? "Create your account" : mode === "login" ? "Welcome back" : "Sign in to Proofmint"}</h1>
      <p className="mt-2 text-sm leading-relaxed text-secondary">Sign in to keep workspaces tied to your account. Judge access opens an isolated demonstration workspace.</p>
      {error && <p role="alert" className="mt-5 border border-warning-copper/40 p-3 text-sm text-warning-copper">{error}</p>}
      {mode === "choose" ? <div className="mt-7 space-y-3">
        {GOOGLE_AUTH_ENABLED ? <a href={`${API_BASE}/api/v1/auth/google/start?returnTo=${encodeURIComponent(returnTo)}`} className="block border border-border-structural px-4 py-3 text-center text-sm font-semibold text-off-white hover:border-verification-mint">Continue with Google</a> : <div aria-disabled="true" className="border border-border-structural/60 px-4 py-3 text-center text-sm font-semibold text-secondary"><span className="block">Continue with Google · Unavailable</span><span className="mt-1 block text-xs font-normal">Google sign-in is unavailable because this domain is not currently supported by Google authentication.</span></div>}
        <button type="button" onClick={() => setMode("login")} className="block w-full bg-verification-mint px-4 py-3 text-sm font-semibold text-graphite-base">Continue with Email</button>
        <div className="border-t border-border-structural pt-4"><p className="text-center text-xs uppercase tracking-wider text-secondary">Demonstration access</p><button type="button" disabled={busy} onClick={() => void startJudge()} className="mt-3 block w-full border border-warning-copper/50 px-4 py-3 text-sm font-semibold text-warning-copper disabled:opacity-50">{busy ? "Starting isolated demo…" : "Login as a Judge"}</button><p className="mt-2 text-center text-xs text-secondary">No personal email or password required.</p></div>
      </div> : <form className="mt-7 space-y-4" onSubmit={(event) => void submitCredentials(event)}>
        {mode === "register" && <><label className="block text-sm text-secondary">First name<input required maxLength={100} autoComplete="given-name" value={firstName} onChange={(event) => setFirstName(event.target.value)} className="mt-1 block w-full border border-border-structural bg-graphite-base px-3 py-3 text-off-white" /></label><label className="block text-sm text-secondary">Surname<input maxLength={100} autoComplete="family-name" value={surname} onChange={(event) => setSurname(event.target.value)} className="mt-1 block w-full border border-border-structural bg-graphite-base px-3 py-3 text-off-white" /></label></>}
        <label className="block text-sm text-secondary">Email address<input required type="email" maxLength={320} autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} className="mt-1 block w-full border border-border-structural bg-graphite-base px-3 py-3 text-off-white" /></label>
        <label className="block text-sm text-secondary">Password<input required type="password" minLength={12} maxLength={256} autoComplete={mode === "register" ? "new-password" : "current-password"} value={password} onChange={(event) => setPassword(event.target.value)} className="mt-1 block w-full border border-border-structural bg-graphite-base px-3 py-3 text-off-white" />{mode === "register" && <span className="mt-1 block text-xs">12+ characters, upper and lowercase, a number, and a symbol.</span>}</label>
        {mode === "register" && <label className="block text-sm text-secondary">Confirm password<input required type="password" maxLength={256} autoComplete="new-password" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} className="mt-1 block w-full border border-border-structural bg-graphite-base px-3 py-3 text-off-white" /></label>}
        <button disabled={busy} className="w-full bg-verification-mint px-4 py-3 text-sm font-semibold text-graphite-base disabled:opacity-50">{busy ? "Please wait…" : mode === "register" ? "Create account" : "Sign in"}</button>
        <div className="flex flex-wrap justify-between gap-3 text-sm"><button type="button" onClick={() => { setMode(mode === "register" ? "login" : "register"); setError(""); }} className="text-verification-mint underline underline-offset-4">{mode === "register" ? "Already have an account? Sign in" : "Create an account"}</button><button type="button" onClick={() => { setMode("choose"); setError(""); }} className="text-secondary underline underline-offset-4">Other sign-in options</button></div>
      </form>}
    </section>
  </div></main>;
}
