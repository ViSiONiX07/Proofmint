"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch, setApiCsrfToken } from "../../lib/api-fetch";
import { API_BASE } from "../../lib/api-base";

type Profile = { first_name: string; surname: string; email: string };

export default function AccountSettingsPage() {
  const router = useRouter();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  useEffect(() => { void apiFetch(`${API_BASE}/api/v1/auth/me`).then(async (response) => { const data = await response.json().catch(() => null); if (!response.ok || data?.role !== "user" || !data.profile) { router.replace("/auth"); return; } setApiCsrfToken(data.csrf_token); setProfile(data.profile); }).catch(() => setError("Account settings could not be loaded.")); }, [router]);
  const saveProfile = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault(); if (!profile) return; setSaving(true); setError(""); setNotice("");
    try { const response = await apiFetch(`${API_BASE}/api/v1/auth/profile`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ first_name: profile.first_name, surname: profile.surname }) }); const data = await response.json().catch(() => null); if (!response.ok) throw new Error(data?.detail || "Profile could not be saved."); setProfile(data.profile); setNotice("Profile updated."); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Profile could not be saved."); } finally { setSaving(false); }
  };
  const changePassword = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault(); setSaving(true); setError(""); setNotice("");
    try { const response = await apiFetch(`${API_BASE}/api/v1/auth/password`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ current_password: currentPassword, new_password: newPassword, confirm_password: confirmPassword }) }); const data = await response.json().catch(() => null); if (!response.ok) throw new Error(data?.detail || "Password could not be changed."); setCurrentPassword(""); setNewPassword(""); setConfirmPassword(""); setNotice("Password updated. Other active sessions were signed out."); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Password could not be changed."); } finally { setSaving(false); }
  };
  return <main className="min-h-screen px-4 pb-16 pt-28 sm:px-6 lg:px-12"><div className="mx-auto max-w-2xl"><Link href="/profile" className="text-sm text-secondary underline underline-offset-4">← Profile</Link><section className="mt-5 border border-border-structural bg-surface-container-low p-6 sm:p-9"><h1 className="text-2xl font-semibold text-off-white">Account settings</h1>{error && <p role="alert" className="mt-4 border border-warning-copper/40 p-3 text-sm text-warning-copper">{error}</p>}{notice && <p role="status" className="mt-4 text-sm text-verification-mint">{notice}</p>}{profile ? <>
    <form onSubmit={(event) => void saveProfile(event)} className="mt-6 space-y-4"><h2 className="font-semibold text-off-white">Profile information</h2><label className="block text-sm text-secondary">First name<input required maxLength={100} value={profile.first_name} onChange={(event) => setProfile({ ...profile, first_name: event.target.value })} className="mt-1 block w-full border border-border-structural bg-graphite-base p-3 text-off-white" /></label><label className="block text-sm text-secondary">Surname<input maxLength={100} value={profile.surname} onChange={(event) => setProfile({ ...profile, surname: event.target.value })} className="mt-1 block w-full border border-border-structural bg-graphite-base p-3 text-off-white" /></label><p className="text-sm text-secondary">Email · {profile.email}</p><button disabled={saving} className="bg-verification-mint px-4 py-2 text-sm font-semibold text-graphite-base disabled:opacity-50">Save profile</button></form>
    <form onSubmit={(event) => void changePassword(event)} className="mt-8 space-y-4 border-t border-border-structural pt-6"><h2 className="font-semibold text-off-white">Change password</h2><label className="block text-sm text-secondary">Current password<input required type="password" autoComplete="current-password" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} className="mt-1 block w-full border border-border-structural bg-graphite-base p-3 text-off-white" /></label><label className="block text-sm text-secondary">New password<input required type="password" minLength={12} maxLength={256} autoComplete="new-password" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} className="mt-1 block w-full border border-border-structural bg-graphite-base p-3 text-off-white" /></label><label className="block text-sm text-secondary">Confirm new password<input required type="password" maxLength={256} autoComplete="new-password" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} className="mt-1 block w-full border border-border-structural bg-graphite-base p-3 text-off-white" /></label><button disabled={saving} className="border border-border-structural px-4 py-2 text-sm text-off-white disabled:opacity-50">Change password</button></form>
  </> : <p role="status" className="mt-4 text-sm text-secondary">Loading account settings…</p>}</section></div></main>;
}
