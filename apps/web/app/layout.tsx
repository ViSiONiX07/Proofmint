import type { Metadata } from "next";
import { Plus_Jakarta_Sans, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const jakarta = Plus_Jakarta_Sans({
  subsets: ["latin"],
  variable: "--font-jakarta",
  display: "swap",
});

const mono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Proofmint — Nothing Ships Unproven | AI Brand Verification Workspace",
  description:
    "Proofmint is an AI-powered brand verification workspace that checks marketing content against approved brand guidelines and verified claim evidence before publication.",
  keywords: [
    "Proofmint",
    "Brand Verification",
    "AI Governance",
    "Brand Guidelines",
    "Evidence Grounding",
    "FutureStack Round 2",
    "Regulatory Compliance",
  ],
  authors: [{ name: "Proofmint Team" }],
  viewport: "width=device-width, initial-scale=1",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark scroll-smooth">
      <head>
        <link rel="icon" href="/icon.svg" sizes="any" />
      </head>
      <body
        className={`${jakarta.variable} ${mono.variable} bg-graphite-base text-on-surface antialiased selection:bg-verification-mint selection:text-graphite-base`}
      >
        {children}
      </body>
    </html>
  );
}
