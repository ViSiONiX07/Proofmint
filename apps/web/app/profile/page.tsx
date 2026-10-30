"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch, setApiCsrfToken } from "../../lib/api-fetch";
import { getProfileInitials } from "../../lib/profile-initials.mjs";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
type Profile = { first_name: string; surname: string; email: string };

export default function ProfilePage() {
  const router = useRouter();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { void apiFetch(`${API_BASE}/api/v1/auth/me`).then(async (response) => {
    const data = await response.json().catch(() => null);
    if (!response.ok || data?.role !== "user" || !data.profile) { router.replace("/auth"); return; }
    setApiCsrfToken(data.csrf_token); setProfile(data.profile);
  }).catch(() => setError("Profile information could not be loaded.")); }, [router]);
  if (error) return <main className="min-h-screen px-6 pt-28"><p role="alert" className="mx-auto max-w-2xl text-warning-copper">{error}</p></main>;
  return <main className="min-h-screen px-4 pb-16 pt-28 sm:px-6 lg:px-12"><section className="mx-auto max-w-2xl border border-border-structural bg-surface-container-low p-6 sm:p-9"><h1 className="text-2xl font-semibold text-off-white">Profile</h1>{profile ? <><div className="mt-6 flex items-center gap-4"><span aria-label={`${profile.first_name} ${profile.surname} initials`} className="flex h-14 w-14 items-center justify-center rounded-full border border-verification-mint text-lg font-semibold text-verification-mint">{getProfileInitials(profile.first_name, profile.surname)}</span><div><p className="font-semibold text-off-white">{`${profile.first_name} ${profile.surname}`.trim()}</p><p className="text-sm text-secondary">{profile.email}</p></div></div><p className="mt-6 text-sm text-secondary">Your profile details are tied to your authenticated account.</p></> : <p role="status" className="mt-4 text-sm text-secondary">Loading profile…</p>}<Link href="/account-settings" className="mt-6 inline-block bg-verification-mint px-4 py-2 text-sm font-semibold text-graphite-base">Account settings</Link></section></main>;
}
