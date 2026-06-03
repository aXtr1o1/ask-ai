"use client";

import React from "react";
import {
  IconCalendar,
  IconX,
  IconMessageCircle,
  IconCheck,
} from "@tabler/icons-react";

interface SpaceBookingModalProps {
  onClose: () => void;
}

export default function SpaceBookingModal({ onClose }: SpaceBookingModalProps) {
  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        backgroundColor: "rgba(0, 0, 0, 0.55)",
        backdropFilter: "blur(8px)",
        WebkitBackdropFilter: "blur(8px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 20000,
        padding: "16px",
      }}
    >
      <style>{`
        @keyframes modalScaleIn {
          from {
            opacity: 0;
            transform: scale(0.95) translateY(10px);
          }
          to {
            opacity: 1;
            transform: scale(1) translateY(0);
          }
        }
      `}</style>
      <div
        style={{
          width: "100%",
          maxWidth: "480px",
          background: "var(--glass-bg, #ffffff)",
          border: "var(--glass-border, 1px solid var(--color-border))",
          borderRadius: "20px",
          boxShadow: "0 20px 50px rgba(0, 0, 0, 0.3)",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
          animation: "modalScaleIn 0.25s cubic-bezier(0.16, 1, 0.3, 1) forwards",
          color: "var(--color-text, #1f2937)",
          padding: "24px",
          position: "relative",
        }}
      >
        {/* Close Button */}
        <button
          onClick={onClose}
          style={{
            position: "absolute",
            top: "16px",
            right: "16px",
            background: "transparent",
            border: "none",
            color: "var(--color-text-muted, #718096)",
            cursor: "pointer",
            padding: "4px",
            display: "flex",
            alignItems: "center",
            borderRadius: "50%",
            transition: "background 0.2s",
          }}
          onMouseEnter={(e) => { e.currentTarget.style.background = "var(--color-primary-soft)"; }}
          onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
        >
          <IconX size={20} />
        </button>

        {/* Icon & Title */}
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", textAlign: "center", marginTop: "8px", gap: "12px" }}>
          <div
            style={{
              width: "48px",
              height: "48px",
              borderRadius: "12px",
              background: "var(--color-primary-soft, rgba(212, 175, 55, 0.15))",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "var(--color-primary, #d4af37)",
            }}
          >
            <IconCalendar size={28} />
          </div>
          <div>
            <h3 style={{ margin: "0 0 4px 0", fontSize: "20px", fontWeight: 700, letterSpacing: "-0.02em" }}>
              Space Booking via AI
            </h3>
            <p style={{ margin: 0, fontSize: "14px", color: "var(--color-text-muted)" }}>
              Ask the assistant to book rooms or desks for you.
            </p>
          </div>
        </div>

        {/* Guide Steps */}
        <div style={{ display: "flex", flexDirection: "column", gap: "16px", margin: "24px 0" }}>
          <div style={{ fontSize: "13px", fontWeight: 600, color: "var(--tile-label-color, #F7EF8A)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
            Example Prompts:
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            {[
              "Book boardroom alpha today at 3 PM",
              "Find an available hot desk in Zone A",
              "Show my current bookings",
              "Cancel my meeting room reservation",
            ].map((promptText) => (
              <div
                key={promptText}
                style={{
                  display: "flex",
                  alignItems: "flex-start",
                  gap: "10px",
                  padding: "12px 14px",
                  background: "var(--tile-card-bg, rgba(255, 255, 255, 0.03))",
                  border: "var(--tile-card-border, 1px solid rgba(0, 0, 0, 0.15))",
                  borderRadius: "10px",
                  fontSize: "13px",
                  lineHeight: "1.4",
                }}
              >
                <IconMessageCircle size={16} style={{ color: "var(--color-primary)", marginTop: "2px", flexShrink: 0 }} />
                <span style={{ color: "var(--color-text)", fontWeight: 500 }}>"{promptText}"</span>
              </div>
            ))}
          </div>
        </div>

        {/* Action Button */}
        <button
          onClick={onClose}
          style={{
            width: "100%",
            background: "var(--color-primary, #d4af37)",
            color: "#000000",
            border: "none",
            borderRadius: "10px",
            padding: "12px",
            fontWeight: 700,
            fontSize: "14px",
            cursor: "pointer",
            transition: "opacity 0.2s",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: "8px",
          }}
          onMouseEnter={(e) => { e.currentTarget.style.opacity = "0.9"; }}
          onMouseLeave={(e) => { e.currentTarget.style.opacity = "1"; }}
        >
          <IconCheck size={18} />
          Got it, let's book!
        </button>
      </div>
    </div>
  );
}
