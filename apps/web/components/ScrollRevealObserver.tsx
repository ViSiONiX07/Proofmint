"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";

export function ScrollRevealObserver() {
  const pathname = usePathname();

  useEffect(() => {
    const elements = document.querySelectorAll<HTMLElement>(".reveal-on-scroll");
    const mediaQuery = window.matchMedia("(prefers-reduced-motion: reduce)");

    if (mediaQuery.matches || !("IntersectionObserver" in window)) {
      elements.forEach((element) => element.classList.add("is-visible"));
      return;
    }

    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        }
      });
    }, { rootMargin: "0px 0px -60px 0px", threshold: 0.1 });

    elements.forEach((element) => {
      if (!element.classList.contains("is-visible")) observer.observe(element);
    });

    return () => observer.disconnect();
  }, [pathname]);

  return null;
}
