"use client";

import React, { useState, useRef, useEffect } from "react";
import {
  IconCalendar,
  IconPlus,
  IconX,
  IconMessageReport,
} from "@tabler/icons-react";

const IconChat = ({ size = 16, stroke = 2, ...props }: { size?: number; stroke?: number | string; [key: string]: any }) => {
  const strokeWidth = typeof stroke === "number" ? stroke : 2;
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      {...props}
    >
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    </svg>
  );
};

interface SpaceBookingProps {
  children: React.ReactNode;

  // Space Booking state
  isSpaceBooking: boolean;
  setIsSpaceBooking: (val: boolean) => void;

  // Complaints state
  isComplaints: boolean;
  setIsComplaints: (val: boolean) => void;

  // Chat locking state
  isChatStarted?: boolean;
  onLockedClick?: () => void;
  onSwitchMode?: (newMode: "space_booking" | "complaints" | "ask_ai") => void;
}

export default function SpaceBooking({
  children,
  isSpaceBooking,
  setIsSpaceBooking,
  isComplaints,
  setIsComplaints,
  isChatStarted = false,
  onLockedClick,
  onSwitchMode,
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
                if (onSwitchMode) {
                  onSwitchMode("space_booking");
                } else {
                  if (isChatStarted) {
                    onLockedClick?.();
                    return;
                  }
                  const newVal = !isSpaceBooking;
                  setIsSpaceBooking(newVal);
                  if (newVal) {
                    setIsComplaints(false);
                  }
                }
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

            <button
              type="button"
              onClick={() => {
                if (onSwitchMode) {
                  onSwitchMode("ask_ai");
                } else {
                  if (isChatStarted) {
                    onLockedClick?.();
                    return;
                  }
                  setIsSpaceBooking(false);
                  setIsComplaints(false);
                }
                setIsOpen(false);
              }}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                width: "100%",
                padding: "12px 14px",
                background: (!isSpaceBooking && !isComplaints) ? "var(--color-primary-soft, rgba(212, 175, 55, 0.15))" : "transparent",
                border: "none",
                borderRadius: "10px",
                color: (!isSpaceBooking && !isComplaints) ? "var(--tile-label-color, #F7EF8A)" : "var(--color-text, #FFFFFF)",
                fontSize: "14px",
                fontWeight: 500,
                cursor: "pointer",
                textAlign: "left",
                transition: "all 0.15s ease",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = (!isSpaceBooking && !isComplaints)
                  ? "var(--color-primary-soft, rgba(212, 175, 55, 0.2))"
                  : "var(--color-primary-soft, rgba(255, 255, 255, 0.05))";
                e.currentTarget.style.color = "var(--tile-label-color, #F7EF8A)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = (!isSpaceBooking && !isComplaints)
                  ? "var(--color-primary-soft, rgba(212, 175, 55, 0.15))"
                  : "transparent";
                e.currentTarget.style.color = (!isSpaceBooking && !isComplaints)
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
                    color: (!isSpaceBooking && !isComplaints) ? "var(--tile-label-color, #F7EF8A)" : "var(--color-text-muted, rgba(255, 255, 255, 0.7))",
                    transition: "color 0.15s ease",
                  }}
                >
                  <IconChat size={18} stroke={1.5} />
                </span>
                <span>Ask AI</span>
              </div>
              {(!isSpaceBooking && !isComplaints) && (
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

            {/* Complaints menu item — hidden, preserved for future use */}
            <span style={{ display: 'none' }}>
            <button
              type="button"
              onClick={() => {
                if (onSwitchMode) {
                  onSwitchMode("complaints");
                } else {
                  if (isChatStarted) {
                    onLockedClick?.();
                    return;
                  }
                  const newVal = !isComplaints;
                  setIsComplaints(newVal);
                  if (newVal) {
                    setIsSpaceBooking(false);
                  }
                }
                setIsOpen(false);
              }}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                width: "100%",
                padding: "12px 14px",
                background: isComplaints ? "var(--color-primary-soft, rgba(212, 175, 55, 0.15))" : "transparent",
                border: "none",
                borderRadius: "10px",
                color: isComplaints ? "var(--tile-label-color, #F7EF8A)" : "var(--color-text, #FFFFFF)",
                fontSize: "14px",
                fontWeight: 500,
                cursor: "pointer",
                textAlign: "left",
                transition: "all 0.15s ease",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = isComplaints
                  ? "var(--color-primary-soft, rgba(212, 175, 55, 0.2))"
                  : "var(--color-primary-soft, rgba(255, 255, 255, 0.05))";
                e.currentTarget.style.color = "var(--tile-label-color, #F7EF8A)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = isComplaints
                  ? "var(--color-primary-soft, rgba(212, 175, 55, 0.15))"
                  : "transparent";
                e.currentTarget.style.color = isComplaints
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
                    color: isComplaints ? "var(--tile-label-color, #F7EF8A)" : "var(--color-text-muted, rgba(255, 255, 255, 0.7))",
                    transition: "color 0.15s ease",
                  }}
                >
                  <IconMessageReport size={18} stroke={1.5} />
                </span>
                <span>Complaints</span>
              </div>
              {isComplaints && (
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
            </span>
          </div>
        </div>
      )}

      {/* Active Feature Badges/Pills */}
      {isSpaceBooking && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            padding: "4px 8px 8px 8px",
            width: "100%",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              background: isChatStarted
                ? "rgba(255, 255, 255, 0.08)"
                : "var(--color-primary-soft, rgba(212, 175, 55, 0.15))",
              border: isChatStarted
                ? "1px solid rgba(255, 255, 255, 0.12)"
                : "1px solid var(--color-primary, rgba(212, 175, 55, 0.3))",
              borderRadius: "20px",
              padding: "4px 12px",
              fontSize: "12px",
              fontWeight: 500,
              color: isChatStarted
                ? "#a0a0a0"
                : "var(--tile-label-color, #F7EF8A)",
              cursor: "pointer",
            }}
            onClick={() => {
              if (isChatStarted) {
                onLockedClick?.();
              } else {
                setIsSpaceBooking(false);
              }
            }}
            title={isChatStarted ? "Mode is locked for this chat" : "Click to turn off Space Booking mode"}
          >
            <IconCalendar size={14} style={{ color: isChatStarted ? "#a0a0a0" : "var(--tile-label-color, #F7EF8A)" }} />
            <span>Space Booking</span>
            <span
              style={{
                width: "6px",
                height: "6px",
                borderRadius: "50%",
                backgroundColor: isChatStarted ? "#a0a0a0" : "var(--tile-label-color, #F7EF8A)",
                boxShadow: isChatStarted ? "none" : "0 0 8px var(--tile-label-color, #F7EF8A)",
                marginLeft: "2px",
              }}
            />
          </div>
        </div>
      )}

      {/* Complaints badge — hidden, preserved for future use */}
      {isComplaints && false && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            padding: "4px 8px 8px 8px",
            width: "100%",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              background: isChatStarted
                ? "rgba(255, 255, 255, 0.08)"
                : "var(--color-primary-soft, rgba(212, 175, 55, 0.15))",
              border: isChatStarted
                ? "1px solid rgba(255, 255, 255, 0.12)"
                : "1px solid var(--color-primary, rgba(212, 175, 55, 0.3))",
              borderRadius: "20px",
              padding: "4px 12px",
              fontSize: "12px",
              fontWeight: 500,
              color: isChatStarted
                ? "#a0a0a0"
                : "var(--tile-label-color, #F7EF8A)",
              cursor: "pointer",
            }}
            onClick={() => {
              if (isChatStarted) {
                onLockedClick?.();
              } else {
                setIsComplaints(false);
              }
            }}
            title={isChatStarted ? "Mode is locked for this chat" : "Click to turn off Complaints mode"}
          >
            <IconMessageReport size={14} style={{ color: isChatStarted ? "#a0a0a0" : "var(--tile-label-color, #F7EF8A)" }} />
            <span>Complaints</span>
            <span
              style={{
                width: "6px",
                height: "6px",
                borderRadius: "50%",
                backgroundColor: isChatStarted ? "#a0a0a0" : "var(--tile-label-color, #F7EF8A)",
                boxShadow: isChatStarted ? "none" : "0 0 8px var(--tile-label-color, #F7EF8A)",
                marginLeft: "2px",
              }}
            />
          </div>
        </div>
      )}

      {!isSpaceBooking && !isComplaints && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            padding: "4px 8px 8px 8px",
            width: "100%",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              background: isChatStarted
                ? "rgba(255, 255, 255, 0.08)"
                : "var(--color-primary-soft, rgba(212, 175, 55, 0.15))",
              border: isChatStarted
                ? "1px solid rgba(255, 255, 255, 0.12)"
                : "1px solid var(--color-primary, rgba(212, 175, 55, 0.3))",
              borderRadius: "20px",
              padding: "4px 12px",
              fontSize: "12px",
              fontWeight: 500,
              color: isChatStarted
                ? "#a0a0a0"
                : "var(--tile-label-color, #F7EF8A)",
              cursor: "pointer",
            }}
            onClick={() => {
              if (isChatStarted) {
                onLockedClick?.();
              }
            }}
            title={isChatStarted ? "Mode is locked for this chat" : "You are in Ask AI mode"}
          >
            <IconChat size={14} style={{ color: isChatStarted ? "#a0a0a0" : "var(--tile-label-color, #F7EF8A)" }} />
            <span>Ask AI</span>
            <span
              style={{
                width: "6px",
                height: "6px",
                borderRadius: "50%",
                backgroundColor: isChatStarted ? "#a0a0a0" : "var(--tile-label-color, #F7EF8A)",
                boxShadow: isChatStarted ? "none" : "0 0 8px var(--tile-label-color, #F7EF8A)",
                marginLeft: "2px",
              }}
            />
          </div>
        </div>
      )}

      {/* Input Row */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "8px",
          width: "100%",
          paddingLeft: "0px",
        }}
      >
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

