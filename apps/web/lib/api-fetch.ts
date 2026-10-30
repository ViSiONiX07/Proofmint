/** Same-origin-safe fetch wrapper for credentialed FastAPI requests and CSRF headers. */
let csrfToken = "";

export function setApiCsrfToken(value: string | null | undefined) {
  csrfToken = typeof value === "string" ? value : "";
}

export function apiFetch(input: RequestInfo | URL, init: RequestInit = {}) {
  const headers = new Headers(init.headers);
  if (typeof document !== "undefined") {
    const match = document.cookie.match(/(?:^|;\s*)proofmint_csrf=([^;]+)/);
    const token = match ? decodeURIComponent(match[1]) : csrfToken;
    if (token && !headers.has("X-CSRF-Token")) headers.set("X-CSRF-Token", token);
  }
  return fetch(input, { ...init, headers, credentials: "include" });
}
