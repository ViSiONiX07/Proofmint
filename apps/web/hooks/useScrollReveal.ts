"use client";

import { useEffect } from "react";

/**
 * Reusable Intersection Observer hook that applies the 'is-visible' class
 * to all elements with the '.reveal-on-scroll' class when they enter the viewport.
 * Honors prefers-reduced-motion automatically.
 */
export function useScrollReveal() {
  useEffect(() => {
    if (typeof window === "undefined") return;

    // Check if user prefers reduced motion
    const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (prefersReducedMotion) {
      document.querySelectorAll(".reveal-on-scroll").forEach((el) => {
        el.classList.add("is-visible");
      });
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            // Unobserve once revealed to save CPU resources
            observer.unobserve(entry.target);
          }
        });
      },
      {
        root: null,
        rootMargin: "0px 0px -60px 0px",
        threshold: 0.1,
      }
    );

    const elements = document.querySelectorAll(".reveal-on-scroll");
    elements.forEach((el) => observer.observe(el));

    return () => {
      observer.disconnect();
    };
  }, []);
}
