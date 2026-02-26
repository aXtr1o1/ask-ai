"use client";

import React from "react";

/* Gold palette: #d4af37 (212,175,55), #f5c249, #AE8625, #F7EF8A */
const GOLD = "212, 175, 55";
const GOLD_LIGHT = "245, 208, 96";
const GOLD_DARK = "174, 134, 37";

const BackgroundLayer = ({ theme = "dark" }: { theme?: "light" | "dark" }) => {
  const isDark = theme === "dark";

  /* Dark theme: blue radial gradient background */
  if (isDark) {
    return (
      <div
        className="fixed inset-0 z-0 overflow-hidden"
        style={{
          background: `
            radial-gradient(ellipse at top left, rgba(59, 130, 246, 0.3) 0%, transparent 50%),
            radial-gradient(ellipse at top right, rgba(14, 165, 233, 0.3) 0%, transparent 50%),
            radial-gradient(ellipse at bottom left, rgba(37, 99, 235, 0.2) 0%, transparent 50%),
            radial-gradient(ellipse at bottom right, rgba(56, 189, 248, 0.2) 0%, transparent 50%),
            linear-gradient(135deg, #0A0A0A 0%, #111111 50%, #0A0A0A 100%)
          `,
        }}
      />
    );
  }

  return (
    <div
      className="fixed inset-0 z-0 overflow-hidden"
      style={{
        background: `
          radial-gradient(ellipse at top left, rgba(${GOLD}, 0.12) 0%, transparent 50%),
          radial-gradient(ellipse at top right, rgba(${GOLD_LIGHT}, 0.1) 0%, transparent 50%),
          radial-gradient(ellipse at bottom left, rgba(${GOLD}, 0.08) 0%, transparent 50%),
          radial-gradient(ellipse at bottom right, rgba(${GOLD_DARK}, 0.08) 0%, transparent 50%),
          linear-gradient(135deg, #FAFAFA 0%, #f7f5f0 50%, #FFFFFF 100%)
        `,
      }}
    >
      <div
        className="absolute inset-0"
        style={{
          background: `
            radial-gradient(circle at 20% 30%, rgba(${GOLD}, 0.06) 0%, transparent 40%),
            radial-gradient(circle at 80% 70%, rgba(${GOLD_LIGHT}, 0.05) 0%, transparent 40%),
            radial-gradient(circle at 50% 50%, rgba(${GOLD}, 0.04) 0%, transparent 60%)
          `,
          filter: "blur(80px)",
          opacity: 0.9,
        }}
      />
      <div
        className="absolute inset-0"
        style={{
          background: `
            linear-gradient(180deg, transparent 0%, rgba(${GOLD}, 0.025) 40%, rgba(${GOLD_LIGHT}, 0.025) 60%, transparent 100%)
          `,
          filter: "blur(50px)",
        }}
      />
      <div
        className="absolute inset-0"
        style={{
          background: `
            radial-gradient(ellipse at 30% 20%, rgba(255, 255, 255, 0.4) 0%, transparent 50%),
            radial-gradient(ellipse at 70% 80%, rgba(255, 255, 255, 0.3) 0%, transparent 50%)
          `,
          filter: "blur(100px)",
          opacity: 0.6,
        }}
      />
    </div>
  );
};

export default BackgroundLayer;
