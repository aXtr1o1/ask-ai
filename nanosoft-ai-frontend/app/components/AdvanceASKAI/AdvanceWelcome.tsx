"use client";

import React from "react";

export default function AdvanceWelcome() {
  return (
    <div className="landing-card">
      <h1
        style={{
          fontSize: 32,
          fontWeight: 700,
          marginBottom: 16,
          background:
            "linear-gradient(180deg, #AE8625 0%, #F7EF8A 35%, #D2AC47 65%, #EDC967 100%)",
          backgroundSize: "200% 200%",
          WebkitBackgroundClip: "text",
          backgroundClip: "text",
          WebkitTextFillColor: "transparent",
          animation: "goldShine 3s ease-in-out infinite",
        }}
      >
        Welcome to Advance Ask AI
      </h1>
      <p className="landing-subtitle">
        Let's work together buddy
      </p>
    </div>
  );
}
