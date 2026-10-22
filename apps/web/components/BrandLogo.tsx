import React from "react";

interface BrandLogoProps {
  className?: string;
  iconOnly?: boolean;
  size?: "sm" | "md" | "lg";
}

export function BrandLogo({ className = "", iconOnly = false, size = "md" }: BrandLogoProps) {
  const sizeMap = {
    sm: "max-h-8",
    md: "max-h-20",
    lg: "max-h-14",
  };
  const sizeClass = sizeMap[size] ?? "max-h-8";



  return (
    <div className={`flex items-center gap-2.5 select-none ${className}`}>
      {/* Official Geometric P Mark with Integrated Checkmark */}
{/* eslint-disable @next/next/no-img-element */}
      <img
        src="/mint_proofmark_logo.png"
        alt="Proofmint logo"
        className={`${sizeClass} w-auto shrink-0 transition-transform duration-200 group-hover:scale-105`}
      />

      {/* Wordmark removed; logo PNG includes branding */}
    </div>
  );
}
