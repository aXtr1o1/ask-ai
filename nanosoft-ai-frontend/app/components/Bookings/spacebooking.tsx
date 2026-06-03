"use client";

import React, { useState, useRef, useEffect } from "react";
import {
  IconCalendar,
  IconPlus,
  IconX,
} from "@tabler/icons-react";

interface SpaceBookingProps {
  children: React.ReactNode;

  // Space Booking state
  isSpaceBooking: boolean;
  setIsSpaceBooking: (val: boolean) => void;
}

export default function SpaceBooking({
  children,
  isSpaceBooking,
  setIsSpaceBooking,
}: SpaceBookingProps) {
  const [isOpen, setIsOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);

  // Close when clicking outside
  useEffect(() => {
    if (!isOpen) return;

    function handleClickOutside(event: MouseEvent) {
      if (
        menuRef.current &&
        !menuRef.current.contains(event.target as Node) &&
        buttonRef.current &&
        !buttonRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
      }
    }

    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isOpen]);

  return (
    <div style={{ display: "flex", flexDirection: "column", width: "100%", gap: "4px" }}>
      {/* Dropdown Action Menu */}
      {isOpen && (
        <div
          ref={menuRef}
          className="space-booking-dropdown"
          style={{
            position: "absolute",
            bottom: "calc(100% + 12px)",
            left: "0",
            width: "250px",
            background: "var(--glass-bg, rgba(38, 38, 38, 0.95))",
            backdropFilter: "blur(20px)",
            WebkitBackdropFilter: "blur(20px)",
            border: "var(--glass-border, 1px solid rgba(255, 255, 255, 0.08))",
            borderRadius: "16px",
            boxShadow: "0 10px 30px rgba(0, 0, 0, 0.15), inset 0 1px 0 rgba(255, 255, 255, 0.05)",
            padding: "8px",
            zIndex: 10000,
            animation: "dropdownOpen 0.2s cubic-bezier(0.16, 1, 0.3, 1) forwards",
            transformOrigin: "bottom left",
          }}
        >
          <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
            <button
              type="button"
              onClick={() => {
                setIsSpaceBooking(!isSpaceBooking);
                setIsOpen(false);
              }}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                width: "100%",
                padding: "12px 14px",
                background: isSpaceBooking ? "var(--color-primary-soft, rgba(212, 175, 55, 0.15))" : "transparent",
                border: "none",
                borderRadius: "10px",
                color: isSpaceBooking ? "var(--tile-label-color, #F7EF8A)" : "var(--color-text, #FFFFFF)",
                fontSize: "14px",
                fontWeight: 500,
                cursor: "pointer",
                textAlign: "left",
                transition: "all 0.15s ease",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = isSpaceBooking
                  ? "var(--color-primary-soft, rgba(212, 175, 55, 0.2))"
                  : "var(--color-primary-soft, rgba(255, 255, 255, 0.05))";
                e.currentTarget.style.color = "var(--tile-label-color, #F7EF8A)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = isSpaceBooking
                  ? "var(--color-primary-soft, rgba(212, 175, 55, 0.15))"
                  : "transparent";
                e.currentTarget.style.color = isSpaceBooking
                  ? "var(--tile-label-color, #F7EF8A)"
                  : "var(--color-text, #FFFFFF)";
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                <span
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: isSpaceBooking ? "var(--tile-label-color, #F7EF8A)" : "var(--color-text-muted, rgba(255, 255, 255, 0.7))",
                    transition: "color 0.15s ease",
                  }}
                >
                  <IconCalendar size={18} stroke={1.5} />
                </span>
                <span>Space Booking</span>
              </div>
              {isSpaceBooking && (
                <span
                  style={{
                    width: "6px",
                    height: "6px",
                    borderRadius: "50%",
                    backgroundColor: "var(--tile-label-color, #F7EF8A)",
                    boxShadow: "0 0 8px var(--tile-label-color, #F7EF8A)",
                  }}
                />
              )}
            </button>
          </div>
        </div>
      )}

      {/* Active Feature Badges/Pills */}
      {isSpaceBooking && (
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: "8px",
            padding: "4px 8px 8px 8px",
            width: "100%",
            borderBottom: "1px solid var(--color-border, rgba(255, 255, 255, 0.05))",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              background: "var(--color-primary-soft, rgba(212, 175, 55, 0.15))",
              border: "1px solid var(--color-primary, rgba(212, 175, 55, 0.3))",
              borderRadius: "20px",
              padding: "4px 10px",
              fontSize: "12px",
              color: "var(--tile-label-color, #F7EF8A)",
            }}
          >
            <IconCalendar size={14} />
            <span>Space Booking Mode</span>
            <button
              type="button"
              onClick={() => setIsSpaceBooking(false)}
              style={{
                background: "transparent",
                border: "none",
                color: "var(--tile-label-color, #F7EF8A)",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                padding: 0,
              }}
            >
              <IconX size={12} />
            </button>
          </div>
        </div>
      )}

      {/* Input Row */}
      <div style={{ display: "flex", alignItems: "center", gap: "8px", width: "100%" }}>
        {/* Plus Button */}
        <button
          ref={buttonRef}
          type="button"
          onClick={() => setIsOpen(!isOpen)}
          title="Actions"
          style={{
            background: "transparent",
            border: "none",
            color: isOpen ? "var(--color-primary)" : "var(--color-text-muted, rgba(255, 255, 255, 0.5))",
            cursor: "pointer",
            padding: "8px",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            flexShrink: 0,
          }}
        >
          <IconPlus size={20} />
        </button>

        {children}
      </div>
    </div>
  );
}

