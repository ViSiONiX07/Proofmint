import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        "graphite-base": "#171A1D",
        "charcoal-elevated": "#242A2D",
        "charcoal-subtle": "#2F363A",
        "verification-mint": "#A7F3D0",
        "verification-mint-dim": "rgba(167, 243, 208, 0.12)",
        "warning-copper": "#F2A65A",
        "warning-copper-dim": "rgba(242, 166, 90, 0.12)",
        "off-white": "#F5F5F0",
        "border-structural": "rgba(245, 245, 240, 0.08)",
        "border-focus": "rgba(167, 243, 208, 0.40)",
        "on-surface": "#e1e2e6",
        "on-surface-variant": "#bec9c2",
        "surface-container-lowest": "#0b0f11",
        "surface-container-low": "#191c1f",
        "surface-container": "#1d2023",
        "surface-container-high": "#272a2d",
        "surface-container-highest": "#323538",
        secondary: "#c1c7cb",
      },
      fontFamily: {
        sans: ["var(--font-jakarta)", "Plus Jakarta Sans", "Inter", "system-ui", "sans-serif"],
        display: ["var(--font-geist)", "Geist", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "JetBrains Mono", "SF Mono", "monospace"],
      },
      boxShadow: {
        "mint-glow": "0 0 20px rgba(167, 243, 208, 0.25)",
        "copper-glow": "0 0 20px rgba(242, 166, 90, 0.20)",
      },
    },
  },
  plugins: [],
};

export default config;
