"use client";

import { useEffect } from "react";

/**
 * Preconnect to the API origin so WebSocket (and fetch) connections open faster.
 * Run once on app load to warm DNS + TCP + TLS before the user starts a chat.
 */
export function ApiPreconnect() {
  useEffect(() => {
    const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
    if (!baseUrl || typeof document === "undefined") return;

    try {
      const url = new URL(baseUrl);
      const origin = url.origin; // e.g. "https://api.example.com"

      // Avoid duplicate links (e.g. React Strict Mode double mount)
      if (document.querySelector('link[data-api-preconnect]')) return;

      const dns = document.createElement("link");
      dns.rel = "dns-prefetch";
      dns.href = origin;
      dns.setAttribute("data-api-preconnect", "dns");
      document.head.appendChild(dns);

      const preconnect = document.createElement("link");
      preconnect.rel = "preconnect";
      preconnect.href = origin;
      preconnect.crossOrigin = "anonymous";
      preconnect.setAttribute("data-api-preconnect", "preconnect");
      document.head.appendChild(preconnect);
    } catch {
      // Invalid URL — ignore
    }
  }, []);

  return null;
}
