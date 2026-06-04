"use client";

import React, { useState, useEffect } from "react";
import {
  IconCalendar,
  IconX,
  IconMessageCircle,
  IconCheck,
  IconClock,
} from "@tabler/icons-react";

interface SpaceBookingModalProps {
  onClose: () => void;
  bookingFrom?: string;
  bookingTo?: string;
  onSave?: (from: string, to: string) => void;
  isInline?: boolean;
}

export default function SpaceBookingModal({
  onClose,
  bookingFrom = "",
  bookingTo = "",
  onSave,
  isInline = false,
}: SpaceBookingModalProps) {
  const [startDate, setStartDate] = useState<string>("");
  const [endDate, setEndDate] = useState<string>("");
  const [startTime, setStartTime] = useState<string>("");
  const [endTime, setEndTime] = useState<string>("");

  useEffect(() => {
    // Determine defaults
    let initialStartDate = new Date().toISOString().split("T")[0];
    let initialEndDate = new Date().toISOString().split("T")[0];
    let initialStart = "10:00";
    let initialEnd = "11:00";

    // Try to parse bookingFrom: e.g. "2026-06-04 10:00"
    if (bookingFrom) {
      const parts = bookingFrom.trim().split(/\s+/);
      if (parts[0] && /^\d{4}-\d{2}-\d{2}$/.test(parts[0])) {
        initialStartDate = parts[0];
      }
      if (parts[1]) {
        initialStart = parts[1];
      } else if (/^\d{2}:\d{2}$/.test(parts[0])) {
        initialStart = parts[0];
      }
    }

    // Try to parse bookingTo: e.g. "2026-06-04 11:00"
    if (bookingTo) {
      const parts = bookingTo.trim().split(/\s+/);
      if (parts[0] && /^\d{4}-\d{2}-\d{2}$/.test(parts[0])) {
        initialEndDate = parts[0];
      } else {
        initialEndDate = initialStartDate;
      }
      if (parts[1]) {
        initialEnd = parts[1];
      } else if (/^\d{2}:\d{2}$/.test(parts[0])) {
        initialEnd = parts[0];
      }
    } else {
      initialEndDate = initialStartDate;
    }

    setStartDate(initialStartDate);
    setEndDate(initialEndDate);
    setStartTime(initialStart);
    setEndTime(initialEnd);
    console.log("📅 [SpaceBookingModal] Ingested parameters -> from:", bookingFrom, "to:", bookingTo, "parsed:", { initialStartDate, initialEndDate, initialStart, initialEnd });
  }, [bookingFrom, bookingTo]);

  const handleConfirm = () => {
    const fromStr = `${startDate} ${startTime}`;
    const toStr = `${endDate} ${endTime}`;
    console.log("📅 [SpaceBookingModal] Confirming date/time:", { fromStr, toStr });
    if (onSave) {
      onSave(fromStr, toStr);
    }
    onClose();
  };

  if (isInline) {
    return (
      <div
        className="inline-booking-picker"
        style={{
          width: "100%",
          maxWidth: "400px",
          background: "rgba(255, 255, 255, 0.03)",
          border: "1px solid rgba(255, 255, 255, 0.08)",
          borderRadius: "14px",
          display: "flex",
          flexDirection: "column",
          color: "var(--color-text, #ffffff)",
          padding: "16px",
          marginTop: "12px",
          boxShadow: "0 4px 20px rgba(0, 0, 0, 0.15)",
        }}
      >
        <style>{`
          .modal-input-field {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--color-border, rgba(255, 255, 255, 0.1));
            color: var(--color-text, #ffffff);
            border-radius: 8px;
            padding: 10px 12px;
            font-size: 14px;
            outline: none;
            width: 100%;
            transition: border-color 0.2s, box-shadow 0.2s;
          }
          .modal-input-field:focus {
            border-color: var(--color-primary, #d4af37);
            box-shadow: 0 0 8px rgba(212, 175, 55, 0.25);
          }
          .theme-dark-date-picker::-webkit-calendar-picker-indicator {
            filter: invert(1);
            cursor: pointer;
          }
        `}</style>

        {/* Title */}
        <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "12px" }}>
          <div
            style={{
              width: "28px",
              height: "28px",
              borderRadius: "6px",
              background: "rgba(212, 175, 55, 0.15)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "var(--color-primary, #d4af37)",
            }}
          >
            <IconCalendar size={18} />
          </div>
          <span style={{ fontSize: "14px", fontWeight: 600 }}>Specify Booking Details</span>
        </div>

        {/* Date & Time Selectors */}
        <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
          <div style={{ display: "flex", gap: "10px" }}>
            <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: "4px" }}>
              <label style={{ fontSize: "12px", fontWeight: 600, color: "var(--tile-label-color, #F7EF8A)" }}>
                Start Date
              </label>
              <input
                type="date"
                className="modal-input-field theme-dark-date-picker"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
              />
            </div>
            <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: "4px" }}>
              <label style={{ fontSize: "12px", fontWeight: 600, color: "var(--tile-label-color, #F7EF8A)" }}>
                End Date
              </label>
              <input
                type="date"
                className="modal-input-field theme-dark-date-picker"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
              />
            </div>
          </div>

          <div style={{ display: "flex", gap: "10px" }}>
            <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: "4px" }}>
              <label style={{ fontSize: "12px", fontWeight: 600, color: "var(--tile-label-color, #F7EF8A)" }}>
                Start Time
              </label>
              <input
                type="time"
                className="modal-input-field"
                value={startTime}
                onChange={(e) => setStartTime(e.target.value)}
              />
            </div>
            <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: "4px" }}>
              <label style={{ fontSize: "12px", fontWeight: 600, color: "var(--tile-label-color, #F7EF8A)" }}>
                End Time
              </label>
              <input
                type="time"
                className="modal-input-field"
                value={endTime}
                onChange={(e) => setEndTime(e.target.value)}
              />
            </div>
          </div>
        </div>

        {/* Actions */}
        <div style={{ display: "flex", gap: "8px", marginTop: "14px" }}>
          <button
            onClick={onClose}
            style={{
              flex: 1,
              background: "rgba(255, 255, 255, 0.05)",
              color: "var(--color-text, #ffffff)",
              border: "1px solid rgba(255, 255, 255, 0.08)",
              borderRadius: "8px",
              padding: "8px 12px",
              fontWeight: 600,
              fontSize: "13px",
              cursor: "pointer",
              transition: "background 0.2s",
            }}
            onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(255, 255, 255, 0.1)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = "rgba(255, 255, 255, 0.05)"; }}
          >
            Cancel
          </button>
          <button
            onClick={handleConfirm}
            style={{
              flex: 2,
              background: "var(--color-primary, #d4af37)",
              color: "#000000",
              border: "none",
              borderRadius: "8px",
              padding: "8px 12px",
              fontWeight: 700,
              fontSize: "13px",
              cursor: "pointer",
              transition: "opacity 0.2s",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "6px",
            }}
            onMouseEnter={(e) => { e.currentTarget.style.opacity = "0.9"; }}
            onMouseLeave={(e) => { e.currentTarget.style.opacity = "1"; }}
          >
            <IconCheck size={16} />
            Confirm
          </button>
        </div>
      </div>
    );
  }

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        backgroundColor: "rgba(0, 0, 0, 0.65)",
        backdropFilter: "blur(12px)",
        WebkitBackdropFilter: "blur(12px)",
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
        .modal-input-field {
          background: rgba(255, 255, 255, 0.05);
          border: 1px solid var(--color-border, rgba(255, 255, 255, 0.1));
          color: var(--color-text, #ffffff);
          border-radius: 8px;
          padding: 10px 12px;
          font-size: 14px;
          outline: none;
          width: 100%;
          transition: border-color 0.2s, box-shadow 0.2s;
        }
        .modal-input-field:focus {
          border-color: var(--color-primary, #d4af37);
          box-shadow: 0 0 8px rgba(212, 175, 55, 0.25);
        }
        .theme-dark-date-picker::-webkit-calendar-picker-indicator {
          filter: invert(1);
          cursor: pointer;
        }
      `}</style>
      <div
        style={{
          width: "100%",
          maxWidth: "480px",
          background: "var(--glass-bg, #111111)",
          border: "var(--glass-border, 1px solid var(--color-border))",
          borderRadius: "20px",
          boxShadow: "0 20px 50px rgba(0, 0, 0, 0.5)",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
          animation: "modalScaleIn 0.25s cubic-bezier(0.16, 1, 0.3, 1) forwards",
          color: "var(--color-text, #ffffff)",
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
            color: "var(--color-text-muted, #a0aec0)",
            cursor: "pointer",
            padding: "4px",
            display: "flex",
            alignItems: "center",
            borderRadius: "50%",
            transition: "background 0.2s",
          }}
          onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(255, 255, 255, 0.1)"; }}
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
              Confirm Booking Details
            </h3>
            <p style={{ margin: 0, fontSize: "14px", color: "var(--color-text-muted, #a0aec0)" }}>
              Specify the date and time window for the reservation.
            </p>
          </div>
        </div>

        {/* Date & Time Selectors */}
        <div style={{ display: "flex", flexDirection: "column", gap: "16px", margin: "24px 0" }}>
          <div style={{ display: "flex", gap: "16px" }}>
            <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: "6px" }}>
              <label style={{ fontSize: "13px", fontWeight: 600, color: "var(--tile-label-color, #F7EF8A)" }}>
                Start Date
              </label>
              <input
                type="date"
                className="modal-input-field theme-dark-date-picker"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
              />
            </div>
            <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: "6px" }}>
              <label style={{ fontSize: "13px", fontWeight: 600, color: "var(--tile-label-color, #F7EF8A)" }}>
                End Date
              </label>
              <input
                type="date"
                className="modal-input-field theme-dark-date-picker"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
              />
            </div>
          </div>

          <div style={{ display: "flex", gap: "16px" }}>
            <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: "6px" }}>
              <label style={{ fontSize: "13px", fontWeight: 600, color: "var(--tile-label-color, #F7EF8A)" }}>
                Start Time
              </label>
              <input
                type="time"
                className="modal-input-field"
                value={startTime}
                onChange={(e) => setStartTime(e.target.value)}
              />
            </div>
            <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: "6px" }}>
              <label style={{ fontSize: "13px", fontWeight: 600, color: "var(--tile-label-color, #F7EF8A)" }}>
                End Time
              </label>
              <input
                type="time"
                className="modal-input-field"
                value={endTime}
                onChange={(e) => setEndTime(e.target.value)}
              />
            </div>
          </div>
        </div>

        {/* Actions */}
        <div style={{ display: "flex", gap: "12px", marginTop: "8px" }}>
          <button
            onClick={onClose}
            style={{
              flex: 1,
              background: "rgba(255, 255, 255, 0.08)",
              color: "var(--color-text, #ffffff)",
              border: "1px solid var(--color-border, rgba(255, 255, 255, 0.1))",
              borderRadius: "10px",
              padding: "12px",
              fontWeight: 600,
              fontSize: "14px",
              cursor: "pointer",
              transition: "background 0.2s",
            }}
            onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(255, 255, 255, 0.12)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = "rgba(255, 255, 255, 0.08)"; }}
          >
            Cancel
          </button>
          <button
            onClick={handleConfirm}
            style={{
              flex: 2,
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
            Confirm Booking
          </button>
        </div>
      </div>
    </div>
  );
}
