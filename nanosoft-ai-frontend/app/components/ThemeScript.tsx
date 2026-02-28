"use client";

import { useEffect } from "react";

export function ThemeScript() {
  useEffect(() => {
    // Sync theme on mount
    const stored = localStorage.getItem("theme");
    if (stored && (stored === "light" || stored === "dark")) {
      document.documentElement.setAttribute("data-theme", stored);
    } else {
      const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
      const theme = prefersDark ? "dark" : "light";
      document.documentElement.setAttribute("data-theme", theme);
      localStorage.setItem("theme", theme);
    }
  }, []);

  return null;
}

