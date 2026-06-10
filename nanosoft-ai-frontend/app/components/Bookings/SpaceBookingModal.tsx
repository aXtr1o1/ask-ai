"use client";

import React, { useState, useEffect, useRef } from "react";
import {
  IconCalendar,
  IconX,
  IconMessageCircle,
  IconCheck,
  IconClock,
} from "@tabler/icons-react";

// Helper to parse "13:45" to { hour: "01", minute: "45", period: "PM" }
const parse24hTime = (timeStr: string) => {
  if (!timeStr) return { hour: "12", minute: "00", period: "AM" };
  const parts = timeStr.split(":");
  if (parts.length < 2) return { hour: "12", minute: "00", period: "AM" };
  const hStr = parts[0];
  const mStr = parts[1];
  let h = parseInt(hStr, 10);
  const m = mStr || "00";
  let period = "AM";
  if (h >= 12) {
    period = "PM";
    if (h > 12) h -= 12;
  }
  if (h === 0) h = 12;
  const hour = String(h).padStart(2, "0");
  return { hour, minute: m, period };
};

// Helper to format { hour: "01", minute: "45", period: "PM" } to "13:45"
const format24hTime = (hour: string, minute: string, period: string) => {
  let h = parseInt(hour, 10);
  if (period === "PM" && h < 12) h += 12;
  if (period === "AM" && h === 12) h = 0;
  const hStr = String(h).padStart(2, "0");
  return `${hStr}:${minute}`;
};

interface CustomTimePickerProps {
  label: string;
  value: string;
  onChange: (val: string) => void;
  popoverPosition?: "left" | "right" | "top";
  selectedDate?: string;
  existingBookings?: Array<{ start_time: string; end_time: string }>;
}

function CustomTimePicker({
  label,
  value,
  onChange,
  popoverPosition = "top",
  selectedDate,
  existingBookings = [],
}: CustomTimePickerProps) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const { hour, minute, period } = parse24hTime(value);

  useEffect(() => {
    if (!isOpen) return;
    function handleClick(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [isOpen]);

  const hoursList = ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12"];
  const minutesList = ["00", "15", "30", "45"];
  const periodsList = ["AM", "PM"];

  const todayStr = new Date().toISOString().split("T")[0];
  const isToday = selectedDate === todayStr;

  const isDateTimeBooked = (dateStr: string, timeStr24: string) => {
    if (!existingBookings || existingBookings.length === 0) return false;
    const targetTime = new Date(`${dateStr}T${timeStr24}:00`).getTime();
    if (isNaN(targetTime)) return false;

    return existingBookings.some((b) => {
      const bStartStr = b.start_time.includes(" ") ? b.start_time.replace(" ", "T") : b.start_time;
      const bEndStr = b.end_time.includes(" ") ? b.end_time.replace(" ", "T") : b.end_time;
      const bStart = new Date(bStartStr).getTime();
      const bEnd = new Date(bEndStr).getTime();
      if (isNaN(bStart) || isNaN(bEnd)) return false;
      return targetTime >= bStart && targetTime < bEnd;
    });
  };

  const isHourDisabled = (h: string) => {
    if (isToday) {
      const now = new Date();
      const currentHour24 = now.getHours();
      let h24 = parseInt(h, 10);
      if (period === "PM" && h24 < 12) h24 += 12;
      if (period === "AM" && h24 === 12) h24 = 0;
      if (h24 < currentHour24) return true;
    }

    if (selectedDate && existingBookings && existingBookings.length > 0) {
      return minutesList.every((m) => {
        let h24 = parseInt(h, 10);
        if (period === "PM" && h24 < 12) h24 += 12;
        if (period === "AM" && h24 === 12) h24 = 0;
        const time24 = `${String(h24).padStart(2, "0")}:${m}`;
        return isDateTimeBooked(selectedDate, time24);
      });
    }
    return false;
  };

  const isMinuteDisabled = (m: string) => {
    if (isToday) {
      const now = new Date();
      const currentHour24 = now.getHours();
      const currentMin = now.getMinutes();
      let selectedH24 = parseInt(hour, 10);
      if (period === "PM" && selectedH24 < 12) selectedH24 += 12;
      if (period === "AM" && selectedH24 === 12) selectedH24 = 0;
      if (selectedH24 < currentHour24) return true;
      if (selectedH24 === currentHour24 && parseInt(m, 10) < currentMin) return true;
    }

    if (selectedDate && existingBookings && existingBookings.length > 0) {
      let selectedH24 = parseInt(hour, 10);
      if (period === "PM" && selectedH24 < 12) selectedH24 += 12;
      if (period === "AM" && selectedH24 === 12) selectedH24 = 0;
      const time24 = `${String(selectedH24).padStart(2, "0")}:${m}`;
      return isDateTimeBooked(selectedDate, time24);
    }
    return false;
  };

  const isPeriodDisabled = (p: string) => {
    if (isToday) {
      const now = new Date();
      const currentHour24 = now.getHours();
      let selectedH24 = parseInt(hour, 10);
      if (p === "PM" && selectedH24 < 12) selectedH24 += 12;
      if (p === "AM" && selectedH24 === 12) selectedH24 = 0;
      if (selectedH24 < currentHour24) return true;
    }

    if (selectedDate && existingBookings && existingBookings.length > 0) {
      return hoursList.every((h) => {
        return minutesList.every((m) => {
          let h24 = parseInt(h, 10);
          if (p === "PM" && h24 < 12) h24 += 12;
          if (p === "AM" && h24 === 12) h24 = 0;
          const time24 = `${String(h24).padStart(2, "0")}:${m}`;
          return isDateTimeBooked(selectedDate, time24);
        });
      });
    }
    return false;
  };

  const selectHour = (newHour: string) => {
    onChange(format24hTime(newHour, minute, period));
  };
  const selectMinute = (newMinute: string) => {
    onChange(format24hTime(hour, newMinute, period));
  };
  const selectPeriod = (newPeriod: string) => {
    onChange(format24hTime(hour, minute, newPeriod));
  };

  const isLeft = popoverPosition === "left";
  const isRight = popoverPosition === "right";

  return (
    <div ref={dropdownRef} style={{ display: "flex", flexDirection: "column", gap: "6px", position: "relative", zIndex: isOpen ? 1001 : 1 }}>
      <label style={{ fontSize: "13px", fontWeight: 600, color: "var(--tile-label-color, #F7EF8A)" }}>
        {label}
      </label>

      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        style={{
          background: "rgba(255, 255, 255, 0.05)",
          border: isOpen ? "1px solid var(--color-primary, #d4af37)" : "1px solid var(--color-border, rgba(255, 255, 255, 0.1))",
          color: "var(--color-text, #ffffff)",
          borderRadius: "8px",
          padding: "10px 12px",
          fontSize: "14px",
          textAlign: "left",
          outline: "none",
          width: "100%",
          cursor: "pointer",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          boxShadow: isOpen ? "0 0 8px rgba(212, 175, 55, 0.25)" : "none",
          transition: "border-color 0.2s, box-shadow 0.2s",
        }}
      >
        <span>{`${hour}:${minute} ${period}`}</span>
        <IconClock size={16} style={{ color: "rgba(255, 255, 255, 0.4)" }} />
      </button>

      {isOpen && (
        <div
          style={{
            position: "absolute",
            bottom: (isLeft || isRight) ? 0 : "100%",
            left: isRight ? "100%" : "auto",
            right: isLeft ? "100%" : (isRight ? "auto" : 0),
            zIndex: 1000,
            marginRight: isLeft ? "10px" : 0,
            marginLeft: isRight ? "10px" : 0,
            marginBottom: (isLeft || isRight) ? 0 : "6px",
            width: "max-content",
            background: "#181818",
            border: "1px solid rgba(255, 255, 255, 0.12)",
            borderRadius: "10px",
            boxShadow: "0 10px 30px rgba(0, 0, 0, 0.5)",
            padding: "12px",
            display: "flex",
            gap: "12px",
            animation: isLeft ? "fadeInLeft 0.15s ease-out" : (isRight ? "fadeInRight 0.15s ease-out" : "fadeInTop 0.15s ease-out"),
          }}
        >
          <style>{`
            @keyframes fadeInLeft {
              from { opacity: 0; transform: translateX(5px); }
              to { opacity: 1; transform: translateX(0); }
            }
            @keyframes fadeInRight {
              from { opacity: 0; transform: translateX(-5px); }
              to { opacity: 1; transform: translateX(0); }
            }
            @keyframes fadeInTop {
              from { opacity: 0; transform: translateY(5px); }
              to { opacity: 1; transform: translateY(0); }
            }
            .time-column {
              display: flex;
              flex-direction: column;
              gap: 2px;
              max-height: 160px;
              overflow-y: auto;
              padding-right: 4px;
              min-width: 40px;
            }
            .time-column::-webkit-scrollbar {
              width: 4px;
            }
            .time-column::-webkit-scrollbar-thumb {
              background: rgba(255, 255, 255, 0.15);
              border-radius: 2px;
            }
            .time-item {
              background: transparent;
              border: none;
              color: rgba(255, 255, 255, 0.7);
              padding: 6px 10px;
              font-size: 13px;
              font-weight: 500;
              border-radius: 4px;
              cursor: pointer;
              transition: all 0.1s ease;
              text-align: center;
              min-width: 40px;
              white-space: nowrap;
            }
            .time-item:hover {
              background: rgba(255, 255, 255, 0.08);
              color: #ffffff;
            }
            .time-item.active {
              background: var(--color-primary, #d4af37);
              color: #000000;
              font-weight: 700;
            }
          `}</style>

          <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
            <span style={{ fontSize: "10px", fontWeight: 700, color: "rgba(255,255,255,0.4)", textAlign: "center", textTransform: "uppercase" }}>Hr</span>
            <div className="time-column">
              {hoursList.map(h => {
                const disabled = isHourDisabled(h);
                return (
                  <button
                    key={h}
                    type="button"
                    disabled={disabled}
                    className={`time-item ${hour === h ? "active" : ""}`}
                    onClick={() => selectHour(h)}
                    style={{
                      opacity: disabled ? 0.3 : 1,
                      cursor: disabled ? "not-allowed" : "pointer"
                    }}
                  >
                    {h}
                  </button>
                );
              })}
            </div>
          </div>

          <div style={{ width: "1px", background: "rgba(255, 255, 255, 0.08)", alignSelf: "stretch" }} />

          <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
            <span style={{ fontSize: "10px", fontWeight: 700, color: "rgba(255,255,255,0.4)", textAlign: "center", textTransform: "uppercase" }}>Min</span>
            <div className="time-column">
              {minutesList.map(m => {
                const disabled = isMinuteDisabled(m);
                return (
                  <button
                    key={m}
                    type="button"
                    disabled={disabled}
                    className={`time-item ${minute === m ? "active" : ""}`}
                    onClick={() => selectMinute(m)}
                    style={{
                      opacity: disabled ? 0.3 : 1,
                      cursor: disabled ? "not-allowed" : "pointer"
                    }}
                  >
                    {m}
                  </button>
                );
              })}
            </div>
          </div>

          <div style={{ width: "1px", background: "rgba(255, 255, 255, 0.08)", alignSelf: "stretch" }} />

          <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
            <span style={{ fontSize: "10px", fontWeight: 700, color: "rgba(255,255,255,0.4)", textAlign: "center", textTransform: "uppercase" }}>Per</span>
            <div className="time-column" style={{ justifyContent: "center" }}>
              {periodsList.map(p => {
                const disabled = isPeriodDisabled(p);
                return (
                  <button
                    key={p}
                    type="button"
                    disabled={disabled}
                    className={`time-item ${period === p ? "active" : ""}`}
                    onClick={() => selectPeriod(p)}
                    style={{
                      opacity: disabled ? 0.3 : 1,
                      cursor: disabled ? "not-allowed" : "pointer"
                    }}
                  >
                    {p}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

interface SpaceBookingModalProps {
  onClose: () => void;
  bookingFrom?: string;
  bookingTo?: string;
  onSave?: (from: string, to: string) => void;
  isInline?: boolean;
  spotCode?: string;
}

export default function SpaceBookingModal({
  onClose,
  bookingFrom = "",
  bookingTo = "",
  onSave,
  isInline = false,
  spotCode,
}: SpaceBookingModalProps) {
  const [startDate, setStartDate] = useState<string>("");
  const [endDate, setEndDate] = useState<string>("");
  const [startTime, setStartTime] = useState<string>("");
  const [endTime, setEndTime] = useState<string>("");
  const [viewDate, setViewDate] = useState<Date>(() => new Date());
  const [error, setError] = useState<string>("");
  const [mounted, setMounted] = useState<boolean>(false);
  const [existingBookings, setExistingBookings] = useState<Array<{ start_time: string; end_time: string }>>([]);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!spotCode) return;
    const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || "";
    fetch(`${baseUrl}/api/bookings/${spotCode}`)
      .then((res) => res.json())
      .then((data) => {
        if (data.status === "ok" && Array.isArray(data.bookings)) {
          setExistingBookings(data.bookings);
        }
      })
      .catch((err) => console.error("Failed to fetch bookings for spot", err));
  }, [spotCode]);

  const isDateFullyBooked = (dateStr: string) => {
    if (!existingBookings || existingBookings.length === 0) return false;
    const slots = [];
    for (let h = 0; h < 24; h++) {
      for (const m of ["00", "15", "30", "45"]) {
        slots.push(`${String(h).padStart(2, "0")}:${m}`);
      }
    }
    return slots.every((time24) => {
      const targetTime = new Date(`${dateStr}T${time24}:00`).getTime();
      if (isNaN(targetTime)) return false;
      return existingBookings.some((b) => {
        const bStartStr = b.start_time.includes(" ") ? b.start_time.replace(" ", "T") : b.start_time;
        const bEndStr = b.end_time.includes(" ") ? b.end_time.replace(" ", "T") : b.end_time;
        const bStart = new Date(bStartStr).getTime();
        const bEnd = new Date(bEndStr).getTime();
        if (isNaN(bStart) || isNaN(bEnd)) return false;
        return targetTime >= bStart && targetTime < bEnd;
      });
    });
  };

  const hasAnyBooking = (dateStr: string) => {
    if (!existingBookings || existingBookings.length === 0) return false;
    const dayStart = new Date(`${dateStr}T00:00:00`).getTime();
    const dayEnd = new Date(`${dateStr}T23:59:59`).getTime();
    if (isNaN(dayStart) || isNaN(dayEnd)) return false;
    return existingBookings.some((b) => {
      const bStartStr = b.start_time.includes(" ") ? b.start_time.replace(" ", "T") : b.start_time;
      const bEndStr = b.end_time.includes(" ") ? b.end_time.replace(" ", "T") : b.end_time;
      const bStart = new Date(bStartStr).getTime();
      const bEnd = new Date(bEndStr).getTime();
      if (isNaN(bStart) || isNaN(bEnd)) return false;
      return bStart <= dayEnd && bEnd >= dayStart;
    });
  };

  useEffect(() => {
    setError("");
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

    const parsedDate = new Date(initialStartDate);
    if (!isNaN(parsedDate.getTime())) {
      setViewDate(parsedDate);
    }

    console.log("📅 [SpaceBookingModal] Ingested parameters -> from:", bookingFrom, "to:", bookingTo, "parsed:", { initialStartDate, initialEndDate, initialStart, initialEnd });
  }, [bookingFrom, bookingTo]);

  const handleConfirm = () => {
    setError("");
    const finalEndDate = endDate || startDate;
    const fromStr = `${startDate} ${startTime}`;
    const toStr = `${finalEndDate} ${endTime}`;
    console.log("📅 [SpaceBookingModal] Confirming date/time:", { fromStr, toStr });

    const now = new Date();
    const startDateTime = new Date(`${startDate}T${startTime}`);
    const endDateTime = new Date(`${finalEndDate}T${endTime}`);

    if (isNaN(startDateTime.getTime())) {
      setError("Please select a valid start date and time.");
      return;
    }

    if (startDateTime < now) {
      setError("Bookings for past dates or times are not permitted. Please select a current or future time.");
      return;
    }

    if (!isNaN(endDateTime.getTime()) && endDateTime.getTime() === startDateTime.getTime()) {
      setError("The start and end times cannot be the same. Please select a valid time range.");
      return;
    }

    if (!isNaN(endDateTime.getTime()) && endDateTime < startDateTime) {
      setError("The end time cannot be before the start time. Please select a valid time range.");
      return;
    }

    if (onSave) {
      onSave(fromStr, toStr);
    }
    onClose();
  };

  if (isInline) {
    const weekDays = ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"];
    const monthNames = [
      "January", "February", "March", "April", "May", "June",
      "July", "August", "September", "October", "November", "December"
    ];

    const currentYear = viewDate.getFullYear();
    const currentMonth = viewDate.getMonth();
    const monthLabel = `${monthNames[currentMonth]} ${currentYear}`;

    const daysInMonth = new Date(currentYear, currentMonth + 1, 0).getDate();
    const firstDayIndex = new Date(currentYear, currentMonth, 1).getDay();

    const handlePrevMonth = () => {
      setViewDate(prev => new Date(prev.getFullYear(), prev.getMonth() - 1, 1));
    };
    const handleNextMonth = () => {
      setViewDate(prev => new Date(prev.getFullYear(), prev.getMonth() + 1, 1));
    };


    const handleDateClick = (dateStr: string) => {
      setError("");
      if (!startDate || (startDate && endDate)) {
        setStartDate(dateStr);
        setEndDate("");
      } else {
        if (dateStr < startDate) {
          setStartDate(dateStr);
        } else {
          setEndDate(dateStr);
        }
      }
    };

    const gridCells = [];
    for (let i = 0; i < firstDayIndex; i++) {
      gridCells.push(<div key={`empty-${i}`} />);
    }
    for (let day = 1; day <= daysInMonth; day++) {
      const yyyy = currentYear;
      const mm = String(currentMonth + 1).padStart(2, '0');
      const dd = String(day).padStart(2, '0');
      const dateStr = `${yyyy}-${mm}-${dd}`;

      const todayStr = mounted ? new Date().toISOString().split("T")[0] : "";
      const isPastDate = mounted && dateStr < todayStr;
      const isFullyBooked = mounted && isDateFullyBooked(dateStr);
      const isDisabled = isPastDate || isFullyBooked;

      const isSelectedStart = startDate === dateStr;
      const isSelectedEnd = endDate === dateStr;
      const isInRange = endDate && dateStr > startDate && dateStr < endDate;
      const isHighlighted = isSelectedStart || isSelectedEnd;

      gridCells.push(
        <button
          key={day}
          type="button"
          disabled={isDisabled}
          onClick={() => handleDateClick(dateStr)}
          style={{
            background: isHighlighted
              ? "var(--color-primary, #d4af37)"
              : isInRange
                ? "rgba(212, 175, 55, 0.2)"
                : "transparent",
            color: isDisabled
              ? "rgba(255, 255, 255, 0.2)"
              : isHighlighted
                ? "#000000"
                : "var(--color-text, #ffffff)",
            border: "none",
            borderRadius: isSelectedStart && !endDate
              ? "6px"
              : isSelectedStart
                ? "6px 0 0 6px"
                : isSelectedEnd
                  ? "0 6px 6px 0"
                  : isInRange
                    ? "0"
                    : "6px",
            height: "30px",
            width: "100%",
            padding: 0,
            fontSize: "13px",
            fontWeight: isHighlighted || isInRange ? 700 : 500,
            cursor: isDisabled ? "not-allowed" : "pointer",
            opacity: isDisabled ? 0.5 : 1,
            transition: "all 0.15s ease",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
          onMouseEnter={(e) => {
            if (!isHighlighted && !isInRange && !isDisabled) e.currentTarget.style.background = "rgba(255, 255, 255, 0.08)";
          }}
          onMouseLeave={(e) => {
            if (!isHighlighted && !isInRange && !isDisabled) e.currentTarget.style.background = "transparent";
          }}
        >
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", position: "relative" }}>
            <span style={{ transform: hasAnyBooking(dateStr) && !isFullyBooked ? "translateY(-1px)" : "none" }}>{day}</span>
            {hasAnyBooking(dateStr) && !isFullyBooked && (
              <div style={{
                width: "4px",
                height: "4px",
                borderRadius: "50%",
                background: isHighlighted ? "#000000" : "var(--color-primary, #d4af37)",
                position: "absolute",
                bottom: "-6px"
              }} />
            )}
          </div>
        </button>
      );
    }

    return (
      <div
        className="inline-booking-picker"
        style={{
          width: "100%",
          maxWidth: "560px",
          background: "rgba(255, 255, 255, 0.03)",
          border: "1px solid rgba(255, 255, 255, 0.08)",
          borderRadius: "14px",
          display: "flex",
          flexDirection: "column",
          color: "var(--color-text, #ffffff)",
          padding: "20px",
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
        `}</style>

        {/* Title */}
        <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "16px" }}>
          <div
            style={{
              width: "32px",
              height: "32px",
              borderRadius: "6px",
              background: "rgba(212, 175, 55, 0.15)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "var(--color-primary, #d4af37)",
            }}
          >
            <IconCalendar size={20} />
          </div>
          <span style={{ fontSize: "16px", fontWeight: 600 }}>Specify Booking Details</span>
        </div>

        {/* Flex Layout: Left Side (Mini Calendar) & Right Side (Time Selectors) */}
        <div style={{ display: "flex", gap: "20px", flexWrap: "wrap", marginBottom: "16px" }}>
          {/* Left Side: Mini Calendar */}
          <div style={{ flex: "1.3 1 240px", display: "flex", flexDirection: "column", gap: "8px", background: "rgba(255, 255, 255, 0.02)", border: "1px solid rgba(255, 255, 255, 0.06)", borderRadius: "10px", padding: "14px" }}>
            {/* Calendar Header */}
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "6px" }}>
              <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
                <span style={{ fontSize: "14px", fontWeight: 700, color: "var(--color-text, #ffffff)" }}>
                  {monthLabel}
                </span>
              </div>
              <div style={{ display: "flex", gap: "4px" }}>
                <button
                  type="button"
                  onClick={handlePrevMonth}
                  style={{ background: "transparent", border: "none", color: "var(--color-text-muted, #a0aec0)", cursor: "pointer", padding: "2px 8px", fontSize: "14px", fontWeight: "bold" }}
                >
                  &lt;
                </button>
                <button
                  type="button"
                  onClick={handleNextMonth}
                  style={{ background: "transparent", border: "none", color: "var(--color-text-muted, #a0aec0)", cursor: "pointer", padding: "2px 8px", fontSize: "14px", fontWeight: "bold" }}
                >
                  &gt;
                </button>
              </div>
            </div>

            {/* Calendar Weekday Names */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", gap: "4px", textAlign: "center", fontSize: "12px", fontWeight: 600, color: "var(--color-text-muted, rgba(255,255,255,0.4))", marginBottom: "4px" }}>
              {weekDays.map(d => <div key={d}>{d}</div>)}
            </div>
            {/* Calendar Day Grid */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", gap: "4px" }}>
              {gridCells}
            </div>
          </div>

          {/* Right Side: Time Selectors */}
          <div style={{ flex: "1 1 180px", display: "flex", flexDirection: "column", gap: "12px", justifyContent: "center" }}>
            <CustomTimePicker
              label="Start Time"
              value={startTime}
              onChange={setStartTime}
              selectedDate={startDate}
              existingBookings={existingBookings}
            />
            <CustomTimePicker
              label="End Time"
              value={endTime}
              onChange={setEndTime}
              selectedDate={endDate || startDate}
              existingBookings={existingBookings}
            />
          </div>
        </div>

        {error && (
          <div style={{
            background: "rgba(239, 68, 68, 0.15)",
            border: "1px solid rgba(239, 68, 68, 0.3)",
            color: "#ef4444",
            padding: "10px 14px",
            borderRadius: "8px",
            fontSize: "13px",
            fontWeight: 500,
            marginBottom: "16px",
            textAlign: "center"
          }}>
            {error}
          </div>
        )}

        {/* Actions */}
        <div style={{ display: "flex", gap: "10px", marginTop: "8px" }}>
          <button
            onClick={onClose}
            style={{
              flex: 1,
              background: "rgba(255, 255, 255, 0.05)",
              color: "var(--color-text, #ffffff)",
              border: "1px solid rgba(255, 255, 255, 0.08)",
              borderRadius: "8px",
              padding: "10px 16px",
              fontWeight: 600,
              fontSize: "14px",
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
              padding: "10px 16px",
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

        {error && (
          <div style={{
            background: "rgba(239, 68, 68, 0.15)",
            border: "1px solid rgba(239, 68, 68, 0.3)",
            color: "#ef4444",
            padding: "10px 14px",
            borderRadius: "8px",
            fontSize: "13px",
            fontWeight: 500,
            marginTop: "16px",
            textAlign: "center"
          }}>
            {error}
          </div>
        )}

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
                min={mounted ? new Date().toISOString().split("T")[0] : undefined}
                onChange={(e) => {
                  setError("");
                  setStartDate(e.target.value);
                }}
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
                min={startDate || (mounted ? new Date().toISOString().split("T")[0] : undefined)}
                onChange={(e) => {
                  setError("");
                  setEndDate(e.target.value);
                }}
              />
            </div>
          </div>

          <div style={{ display: "flex", gap: "16px" }}>
            <div style={{ flex: 1 }}>
              <CustomTimePicker
                label="Start Time"
                value={startTime}
                onChange={setStartTime}
                selectedDate={startDate}
                existingBookings={existingBookings}
              />
            </div>
            <div style={{ flex: 1 }}>
              <CustomTimePicker
                label="End Time"
                value={endTime}
                onChange={setEndTime}
                selectedDate={endDate || startDate}
                existingBookings={existingBookings}
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
