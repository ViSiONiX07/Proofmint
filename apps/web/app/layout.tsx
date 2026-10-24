import type { Metadata, Viewport } from "next";
import "./globals.css";
import { Footer } from "@/components/Footer";
import { Navbar } from "@/components/Navbar";
import { WelcomeModal } from "@/components/WelcomeModal";
import { ScrollRevealObserver } from "@/components/ScrollRevealObserver";

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
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
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
        className="bg-graphite-base text-on-surface antialiased selection:bg-verification-mint selection:text-graphite-base"
      >
        <Navbar />
        <ScrollRevealObserver />
        {children}
        <Footer />
        <WelcomeModal />
      </body>
    </html>
  );
}
