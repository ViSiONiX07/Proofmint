"use client";

import React, { useState, useRef, useEffect } from "react";
import { BrandLogo } from "./BrandLogo";
import { UserRound, X } from "lucide-react";

interface NavbarProps {
  onOpenWorkspace?: () => void;
  activeView?: "landing" | "workspace";
  setActiveView?: (view: "landing" | "workspace") => void;
}

export function Navbar({ onOpenWorkspace, activeView = "landing", setActiveView }: NavbarProps) {
  const [avatarOpen, setAvatarOpen] = useState(false);
  const avatarRef = useRef<HTMLDivElement>(null);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  // Track which page section is currently active for underline styling
  const [activeSection, setActiveSection] = useState<string>('overview');

  // Update activeSection on hash change or initial load
  React.useEffect(() => {
    const updateSection = () => {
      const hash = window.location.hash.replace('#', '') || 'overview';
      setActiveSection(hash);
    };
    updateSection();
    window.addEventListener('hashchange', updateSection);
    return () => window.removeEventListener('hashchange', updateSection);
  }, []);

  // Close avatar dropdown on outside click or Escape
  React.useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (avatarRef.current && !avatarRef.current.contains(e.target as Node)) {
        setAvatarOpen(false);
      }
    };
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setAvatarOpen(false);
    };
    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleKey);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleKey);
    };
  }, []);
  // Close mobile drawer on Escape or outside click
  useEffect(() => {
    if (!mobileMenuOpen) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setMobileMenuOpen(false);
    };
    const handleClickOutside = (e: MouseEvent) => {
      const target = e.target as Node;
      // close if click is outside the header element (which contains the drawer)
      if (mobileMenuOpen && !(target instanceof HTMLElement && target.closest('header'))) {
        setMobileMenuOpen(false);
      }
    };
    document.addEventListener('keydown', handleKey);
    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('keydown', handleKey);
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [mobileMenuOpen]);

  return (
    <header className="fixed top-0 left-0 right-0 w-full z-50 bg-[#171A1D]/90 backdrop-blur-md border-b border-border-structural transition-all duration-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-12 h-16 flex items-center justify-between gap-4">
        {/* Brand Lockup */}
        <div className="flex items-center gap-4 shrink-0">
          <a
            href="#overview"
            onClick={(e) => {
              if (setActiveView) {
                e.preventDefault();
                setActiveView("landing");
                window.scrollTo({ top: 0, behavior: "smooth" });
              }
            }}
            className="group flex items-center gap-2 flex-none focus:outline-none focus:ring-1 focus:ring-verification-mint rounded"
          >
            <BrandLogo size="md" />
          </a>
        </div>

        {/* Desktop Nav Links */}
        <nav className="hidden lg:flex items-center gap-6 text-sm text-secondary flex-shrink-0 whitespace-nowrap">
          <a href="#overview" className={`hover:text-off-white transition-colors py-1 ${activeSection === 'overview' ? 'text-off-white font-medium border-b border-verification-mint' : ''}`}>Overview & Telemetry</a>
          <a href="#workspace-hub" className={`hover:text-off-white transition-colors py-1 ${activeSection === 'workspace-hub' ? 'text-off-white font-medium border-b border-verification-mint' : ''}`}>Brand Workspace</a>
          <a href="#differentiators" onClick={() => { setActiveSection('differentiators'); }} className={`hover:text-off-white transition-colors py-1 ${activeSection === 'differentiators' ? 'text-off-white font-medium border-b border-verification-mint' : ''}`}>
            Differentiators
          </a>
          <a href="#pipeline" onClick={() => { setActiveSection('pipeline'); }} className={`hover:text-off-white transition-colors py-1 ${activeSection === 'pipeline' ? 'text-off-white font-medium border-b border-verification-mint' : ''}`}>
            Pipeline
          </a>
          <a href="#governance" onClick={() => { setActiveSection('governance'); }} className={`hover:text-off-white transition-colors py-1 ${activeSection === 'governance' ? 'text-off-white font-medium border-b border-verification-mint' : ''}`}>
            Sovereign Trust
          </a>
        </nav>

        {/* Action CTAs */}
        <div className="relative flex items-center gap-3">


          <a
            href="#workspace-hub"
            className="hidden xl:inline-flex items-center justify-center px-4 py-1.5 rounded text-xs font-semibold whitespace-nowrap text-graphite-base bg-verification-mint hover:brightness-105 hover:shadow-mint-glow transition-all mr-2"
          >
            Brand Workspace
          </a>
          <a
            href="#simulator"
            className="hidden xl:inline-flex items-center justify-center px-4 py-1.5 rounded text-xs font-semibold whitespace-nowrap text-graphite-base bg-verification-mint hover:brightness-105 hover:shadow-mint-glow transition-all"
          >
            Launch Studio
          </a>
          {/* Profile Avatar */}
          <button
            type="button"
            className="flex items-center justify-center w-9 h-9 rounded-full bg-charcoal-elevated border border-border-structural text-off-white hover:border-verification-mint/60 hover:text-verification-mint transition-all flex-shrink-0 mr-2"
            onClick={() => setAvatarOpen(!avatarOpen)}
            aria-label="Open profile menu"
          >
            <UserRound className="w-5 h-5" />


          </button>
          {avatarOpen && (
            <div
              ref={avatarRef}
              className="absolute right-0 mt-2 w-40 bg-[#171A1D] border border-border-structural rounded shadow-lg py-1"
            >
              <a href="#" className="block px-4 py-2 text-sm text-off-white hover:bg-charcoal-elevated">Profile</a>
              <a href="#" className="block px-4 py-2 text-sm text-off-white hover:bg-charcoal-elevated">Settings</a>
            </div>
          )}

          {/* Mobile Hamburger Button */}
          <button
            type="button"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="xl:hidden p-2 text-secondary hover:text-off-white rounded focus:outline-none"
            aria-label="Toggle Navigation Menu"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              {mobileMenuOpen ? (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
              ) : (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 6h16M4 12h16M4 18h16" />
              )}
            </svg>
          </button>
        </div>
      </div>

      {/* Mobile Drawer Menu */}
      {mobileMenuOpen && (
        <div className="xl:hidden fixed inset-0 bg-[#171A1D]/95 backdrop-blur-md overflow-y-auto p-6 animate-fade-in">
          <button type="button" onClick={() => setMobileMenuOpen(false)} className="absolute top-4 right-4 text-off-white hover:text-verification-mint" aria-label="Close navigation menu">
            <X className="w-6 h-6" />
          </button>
          <a
            href="#overview"
            onClick={() => {
              setActiveSection('overview');
              setMobileMenuOpen(false);
            }}
            className={`block py-2 text-sm ${activeSection === 'overview' ? 'text-off-white font-medium border-b border-verification-mint' : 'text-secondary'} hover:text-off-white`}
          >
            Overview & Telemetry
          </a>
          <a
            href="#workspace-hub"
            onClick={() => {
              setActiveSection('workspace-hub');
              setMobileMenuOpen(false);
              const el = document.getElementById('workspace-hub');
              el?.scrollIntoView({ behavior: 'smooth' });
            }}
            className={`block py-2 text-sm ${activeSection === 'workspace-hub' ? 'text-off-white font-medium border-b border-verification-mint' : 'text-secondary'} hover:text-off-white`}
          >
            Brand Workspace
          </a>
          <a
            href="#simulator"
            onClick={() => setMobileMenuOpen(false)}
            className="block py-2 text-sm text-secondary hover:text-off-white"
          >
            In-Flight Verification Studio
          </a>
          <a
            href="#differentiators"
            onClick={() => { setMobileMenuOpen(false); setActiveSection('differentiators'); }}
            className={`block py-2 text-sm ${activeSection === 'differentiators' ? 'text-off-white font-medium border-b border-verification-mint' : 'text-secondary'} hover:text-off-white`}
          >
            Core Differentiators
          </a>
          <a
            href="#pipeline"
            onClick={() => { setMobileMenuOpen(false); setActiveSection('pipeline'); }}
            className={`block py-2 text-sm ${activeSection === 'pipeline' ? 'text-off-white font-medium border-b border-verification-mint' : 'text-secondary'} hover:text-off-white`}
          >
            5-Step Pipeline
          </a>
          <a
            href="#governance"
            onClick={() => { setMobileMenuOpen(false); setActiveSection('governance'); }}
            className="block py-2 text-sm text-secondary hover:text-off-white"
          >
            Governance & Compliance
          </a>
          <a href="#simulator" onClick={() => setMobileMenuOpen(false)} className="block py-2 text-sm text-secondary hover:text-off-white">Launch Studio</a>
        </div>
      )}
    </header>
  );
}
