const productionApiUrl = "https://proofmint-q9ss.onrender.com";
const developmentApiUrl = "http://127.0.0.1:8000";

/** Resolve the public API without silently sending production traffic to localhost. */
export const API_BASE = process.env.NEXT_PUBLIC_API_URL || (
  process.env.NODE_ENV === "production" ? productionApiUrl : developmentApiUrl
);
