"use client";

import React, { useState, useRef, useEffect } from "react";
import {
  IconMessageChatbot,
  IconPlus,
  IconMessageCircle,
} from "@tabler/icons-react";

interface AdvanceChatProps {
  children: React.ReactNode;
  
  // Advance AI state
  isAdvanceAskAI: boolean;
  setIsAdvanceAskAI: (val: boolean) => void;

  // Chat locking state
  isChatStarted?: boolean;
  onLockedClick?: () => void;
}

export default function AdvanceChatUI({
  children,
  isAdvanceAskAI,
  setIsAdvanceAskAI,
  isChatStarted = false,
  onLockedClick,
}: AdvanceChatProps) {
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
          className="advance-ai-dropdown"
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
                if (isChatStarted) {
                  onLockedClick?.();
                  return;
                }
                setIsAdvanceAskAI(true);
                setIsOpen(false);
              }}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                width: "100%",
                padding: "12px 14px",
                background: isAdvanceAskAI ? "var(--color-primary-soft, rgba(212, 175, 55, 0.15))" : "transparent",
                border: "none",
                borderRadius: "10px",
                color: isAdvanceAskAI ? "var(--tile-label-color, #F7EF8A)" : "var(--color-text, #FFFFFF)",
                fontSize: "14px",
                fontWeight: 500,
                cursor: "pointer",
                textAlign: "left",
                transition: "all 0.15s ease",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = isAdvanceAskAI
                  ? "var(--color-primary-soft, rgba(212, 175, 55, 0.2))"
                  : "var(--color-primary-soft, rgba(255, 255, 255, 0.05))";
                e.currentTarget.style.color = "var(--tile-label-color, #F7EF8A)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = isAdvanceAskAI
                  ? "var(--color-primary-soft, rgba(212, 175, 55, 0.15))"
                  : "transparent";
                e.currentTarget.style.color = isAdvanceAskAI
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
                    color: isAdvanceAskAI ? "var(--tile-label-color, #F7EF8A)" : "var(--color-text-muted, rgba(255, 255, 255, 0.7))",
                    transition: "color 0.15s ease",
                  }}
                >
                  <IconMessageChatbot size={18} stroke={1.5} />
                </span>
                <span>Advance AI</span>
              </div>
              {isAdvanceAskAI && (
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
                if (isChatStarted) {
                  onLockedClick?.();
                  return;
                }
                setIsAdvanceAskAI(false);
                setIsOpen(false);
              }}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                width: "100%",
                padding: "12px 14px",
                background: !isAdvanceAskAI ? "var(--color-primary-soft, rgba(212, 175, 55, 0.15))" : "transparent",
                border: "none",
                borderRadius: "10px",
                color: !isAdvanceAskAI ? "var(--tile-label-color, #F7EF8A)" : "var(--color-text, #FFFFFF)",
                fontSize: "14px",
                fontWeight: 500,
                cursor: "pointer",
                textAlign: "left",
                transition: "all 0.15s ease",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = !isAdvanceAskAI
                  ? "var(--color-primary-soft, rgba(212, 175, 55, 0.2))"
                  : "var(--color-primary-soft, rgba(255, 255, 255, 0.05))";
                e.currentTarget.style.color = "var(--tile-label-color, #F7EF8A)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = !isAdvanceAskAI
                  ? "var(--color-primary-soft, rgba(212, 175, 55, 0.15))"
                  : "transparent";
                e.currentTarget.style.color = !isAdvanceAskAI
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
                    color: !isAdvanceAskAI ? "var(--tile-label-color, #F7EF8A)" : "var(--color-text-muted, rgba(255, 255, 255, 0.7))",
                    transition: "color 0.15s ease",
                  }}
                >
                  <IconMessageCircle size={18} stroke={1.5} />
                </span>
                <span>Standard AI</span>
              </div>
              {!isAdvanceAskAI && (
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
              setIsOpen(true);
            }
          }}
          title={isChatStarted ? "Mode is locked for this chat" : "Click to switch AI mode"}
        >
          {isAdvanceAskAI ? (
             <IconMessageChatbot size={14} style={{ color: isChatStarted ? "#a0a0a0" : "var(--tile-label-color, #F7EF8A)" }} />
          ) : (
             <IconMessageCircle size={14} style={{ color: isChatStarted ? "#a0a0a0" : "var(--tile-label-color, #F7EF8A)" }} />
          )}
          <span>{isAdvanceAskAI ? "Advance AI" : "Standard AI"}</span>
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

// ─── Formatting Tools ────────────────────────────────────────────────────────
export function renderTableLayout(text: string, isDark: boolean) {
  let headers: string[] = [];
  let rows: string[][] = [];

  try {
    const obj = JSON.parse(text);
    let data = obj;
    if (!Array.isArray(data)) {
      if (obj.records) data = obj.records;
      else if (obj.sorted_data) data = obj.sorted_data;
      else if (obj.unique_values) data = obj.unique_values;
      else if (obj.groups) data = obj.groups;
    }
    if (Array.isArray(data) && data.length > 0) {
      const flatData = data.flat(Infinity);
      if (flatData.length > 0 && typeof flatData[0] === "object" && flatData[0] !== null) {
        headers = Object.keys(flatData[0]);
        rows = flatData.map((item: any) => headers.map(h => (item[h] !== undefined && item[h] !== null) ? String(item[h]) : ""));
      } else {
         return renderMarkdownLayout(text);
      }
    } else {
      return renderMarkdownLayout(text);
    }
  } catch (e) {
    const lines = text.split("\n").map(l => l.trim()).filter(Boolean);
    const tableLines = lines.filter(l => l.includes("|"));
    if (tableLines.length < 2) return renderMarkdownLayout(text);

    const parseRow = (rowStr: string) => {
      let cells = rowStr.split("|").map(c => c.trim());
      if (rowStr.startsWith("|")) cells.shift();
      if (rowStr.endsWith("|")) cells.pop();
      return cells;
    };
    headers = parseRow(tableLines[0]);
    rows = tableLines.slice(2).map(parseRow);
  }

  let tableRowsHtml = rows.map((row, rIdx) => {
    let cellsHtml = row.map((cell) => {
      let cellContent = cell;
      if (cell.startsWith("**") && cell.endsWith("**")) {
        cellContent = `<strong>${cell.replace(/\*\*/g, "")}</strong>`;
      }
      return `<td style="padding: 10px 14px; color: ${isDark ? "#cbd5e1" : "#475569"};">${cellContent}</td>`;
    }).join("");
    
    const rowBg = rIdx % 2 === 1 ? (isDark ? "rgba(255,255,255,0.015)" : "rgba(0,0,0,0.005)") : "transparent";
    return `
      <tr style="
        border-bottom: ${rIdx < rows.length - 1 ? (isDark ? "1px solid rgba(255,255,255,0.04)" : "1px solid rgba(15,23,42,0.04)") : "none"};
        background: ${rowBg};
        transition: background 0.2s;
      " onmouseenter="this.style.background='${isDark ? "rgba(212, 175, 55, 0.04)" : "rgba(212, 175, 55, 0.03)"}'" onmouseleave="this.style.background='${rowBg}'">
        ${cellsHtml}
      </tr>
    `;
  }).join("");

  return `
    <div style="
      overflow-x: auto;
      border-radius: 8px;
      border: 1px solid ${isDark ? "rgba(255,255,255,0.06)" : "rgba(15,23,42,0.06)"};
      box-shadow: 0 2px 10px rgba(0,0,0,0.05);
    ">
      <table style="width: 100%; border-collapse: collapse; text-align: left; font-size: 13px;">
        <thead>
          <tr style="
            background: ${isDark ? "rgba(255, 255, 255, 0.04)" : "rgba(0, 0, 0, 0.02)"};
            border-bottom: 1.5px solid ${isDark ? "rgba(255,255,255,0.12)" : "1.5px solid rgba(15,23,42,0.12)"};
          ">
            ${headers.map(h => `<th style="padding: 10px 14px; font-weight: 600; color: ${isDark ? "#ffd700" : "#8a6508"}; white-space: nowrap;">${h}</th>`).join("")}
          </tr>
        </thead>
        <tbody>
          ${tableRowsHtml}
        </tbody>
      </table>
    </div>
  `;
}

export function renderListLayout(text: string, isNumbered: boolean, isDark: boolean) {
  let parsedItems: string[] = [];
  let itemsAreHtml = false;

  try {
    const obj = JSON.parse(text);
    let data = obj;
    if (!Array.isArray(data)) {
      if (obj.records) data = obj.records;
      else if (obj.sorted_data) data = obj.sorted_data;
      else if (obj.unique_values) data = obj.unique_values;
      else if (obj.groups) data = obj.groups;
    }
    
    if (Array.isArray(data) && data.length > 0) {
      const flatData = data.flat(Infinity);
      itemsAreHtml = true;
      parsedItems = flatData
        .map((item: any) => {
          if (typeof item === "object" && item !== null) {
            const filtered = Object.entries(item).filter(([_, value]) => {
              const v = (value === null || value === undefined) ? "" : String(value).trim();
              return v !== "" && v !== "null" && v !== "undefined";
            });
            if (filtered.length === 0) return null;
            return filtered
              .map(([key, value]) => `<span style="opacity:0.75; font-size:12px;">${escapeHtml(key)}:</span> <b>${escapeHtml(String(value))}</b>`)
              .join(" <span style='opacity:0.3; margin:0 4px;'>|</span> ");
          }
          const strVal = String(item).trim();
          if (strVal === "" || strVal === "null") return null;
          return escapeHtml(strVal);
        })
        .filter((item): item is string => item !== null);
    } else {
      throw new Error("Not an array");
    }
  } catch (e) {
    const lines = text.split("\\n").map(l => l.trim()).filter(l => l.length > 0);
    for (const line of lines) {
      if (/^([\\s]*(?:[-*•]|\\d+[.)]))\\s*/.test(line)) {
        const clean = line.replace(/^([\\s]*(?:[-*•]|\\d+[.)]))\\s*/, "");
        parsedItems.push(clean);
      } else {
        if (parsedItems.length > 0) {
          parsedItems[parsedItems.length - 1] += "\\n" + line;
        } else {
          parsedItems.push(line);
        }
      }
    }
  }

  if (parsedItems.length === 0) {
    return `<div style="font-size: 14px;">${text}</div>`;
  }

  let itemsHtml = parsedItems.map((item, idx) => {
    let markerHtml = "";
    if (isNumbered) {
      markerHtml = `
        <div style="
          flex-shrink: 0; display: flex; align-items: center; justify-content: center;
          width: 22px; height: 22px; border-radius: 50%;
          background: ${isDark ? "rgba(212, 175, 55, 0.15)" : "rgba(212, 175, 55, 0.1)"};
          border: 1px solid ${isDark ? "rgba(212,175,55,0.3)" : "rgba(212,175,55,0.2)"};
          color: ${isDark ? "#ffd700" : "#8a6508"}; font-size: 11px; font-weight: 600; margin-top: 2px;
        ">${idx + 1}</div>
      `;
    } else {
      markerHtml = `
        <div style="
          flex-shrink: 0; width: 6px; height: 6px; border-radius: 50%;
          background: linear-gradient(135deg, #D4AF37 0%, #AA7C11 100%);
          margin-top: 10px; box-shadow: 0 0 6px rgba(212, 175, 55, 0.8);
        "></div>
      `;
    }

    const contentHtml = itemsAreHtml ? item : parseMarkdownTokens(item);
    return `
      <div style="display: flex; align-items: flex-start; gap: 10px;">
        ${markerHtml}
        <div style="font-size: 13.5px; line-height: 1.6; color: ${isDark ? "#cbd5e1" : "#475569"}; flex: 1;">
          ${contentHtml}
        </div>
      </div>
    `;
  }).join("");

  return `<div style="display: flex; flex-direction: column; gap: 10px; padding-left: 4px;">${itemsHtml}</div>`;
}

export function renderJsonLayout(text: string, isDark: boolean) {
  let formattedJson = text;
  try {
    const obj = JSON.parse(text);
    formattedJson = JSON.stringify(obj, null, 2);
  } catch (e) {}

  return `
    <div style="
      position: relative; background: ${isDark ? "rgba(15, 23, 42, 0.7)" : "#1e293b"};
      color: #f8fafc; font-family: var(--font-mono); font-size: 12.5px;
      padding: 14px; border-radius: 8px; border: 1px solid rgba(255, 255, 255, 0.08);
      box-shadow: inset 0 2px 4px rgba(0,0,0,0.3);
    ">
      <div style="
        display: flex; justify-content: space-between; align-items: center;
        font-size: 11px; color: rgba(255,255,255,0.4); margin-bottom: 8px;
        border-bottom: 1px solid rgba(255,255,255,0.06); padding-bottom: 6px;
      ">
        <span style="display: flex; align-items: center; gap: 4px;">JSON Output</span>
      </div>
      <pre style="margin: 0; overflow-x: auto; white-space: pre-wrap;"><code>${escapeHtml(formattedJson)}</code></pre>
    </div>
  `;
}

export function renderGraphLayout(text: string, isDark: boolean) {
  let data: any[] = [];
  try {
    const obj = JSON.parse(text);
    let raw = obj;
    if (!Array.isArray(raw)) {
      if (obj.groups) raw = obj.groups;
      else if (obj.sorted_data) raw = obj.sorted_data;
    }
    if (Array.isArray(raw) && raw.length > 0) data = raw;
    else return `<div style="font-size:14px; white-space:pre-wrap; color:var(--text-secondary);">${escapeHtml(text)}</div>`;
  } catch (e) {
    return `<div style="font-size:14px; white-space:pre-wrap; color:var(--text-secondary);">${escapeHtml(text)}</div>`;
  }

  const firstItem = data[0];
  const keys = Object.keys(firstItem);
  const valueKey = keys.find(k => k === "count" || k === "value") || keys[keys.length - 1];
  const labelKey = keys.find(k => k !== valueKey) || keys[0];

  const values = data.map(d => Number(d[valueKey]) || 0);
  const maxVal = Math.max(...values, 1);
  const barColor = isDark ? "#D4AF37" : "#AA7C11";
  const textColor = isDark ? "#cbd5e1" : "#475569";
  const labelColor = isDark ? "#94a3b8" : "#64748b";
  const bgBar = isDark ? "rgba(255,255,255,0.04)" : "rgba(0,0,0,0.04)";

  const barsHtml = data.map((item) => {
    const label = String(item[labelKey] ?? "");
    const val = Number(item[valueKey]) || 0;
    const pct = Math.max((val / maxVal) * 100, 0).toFixed(1);
    return `
      <div style="display:flex; align-items:center; gap:10px; margin-bottom:8px;">
        <div style="width:130px; flex-shrink:0; font-size:12px; color:${labelColor}; text-align:right; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title='${escapeHtml(label)}'>${escapeHtml(label)}</div>
        <div style="flex:1; background:${bgBar}; border-radius:4px; height:22px; position:relative; overflow:hidden;">
          <div style="width:${pct}%; height:100%; background:linear-gradient(90deg, ${barColor} 0%, ${isDark ? '#AA7C11' : '#D4AF37'} 100%); border-radius:4px; transition: width 0.4s ease; min-width:2px;"></div>
        </div>
        <div style="width:48px; flex-shrink:0; font-size:12px; font-weight:600; color:${textColor}; text-align:left;">${val.toLocaleString()}</div>
      </div>
    `;
  }).join("");

  return `
    <div style="padding:4px 0;">
      <div style="font-size:11px; color:${labelColor}; text-transform:uppercase; letter-spacing:0.05em; margin-bottom:12px; display:flex; justify-content:space-between;">
        <span>${escapeHtml(labelKey)}</span>
        <span>${escapeHtml(valueKey)}</span>
      </div>
      ${barsHtml}
      <div style="margin-top:10px; font-size:11px; color:${labelColor}; text-align:right;">${data.length} group${data.length !== 1 ? 's' : ''}</div>
    </div>
  `;
}

export function renderMarkdownLayout(text: string) {
  try {
    const obj = JSON.parse(text);
    if (typeof obj === "object" && obj !== null) {
      if (obj.formatted_answer !== undefined || obj.response_type !== undefined) {
        return renderChatResponseHtml(obj);
      }
      if (!Array.isArray(obj) && Object.keys(obj).length === 1) {
        const key = Object.keys(obj)[0];
        return `<div style="font-weight: 600; color: #ffd700; font-size: 16px;">${key}: ${obj[key]}</div>`;
      }
      return renderJsonLayout(text, true); // default to dark
    } else if (typeof obj === "number" || typeof obj === "string") {
        return `<div style="font-weight: 600; color: #ffd700; font-size: 16px;">${obj}</div>`;
    }
  } catch (e) {}

  return `<div style="width: 100%; word-break: break-word; line-height: 1.6;">${parseMarkdownBlocks(text)}</div>`;
}

function parseMarkdownBlocks(text: string) {
  if (!text) return "";
  const blocks = text.split(/(```[\\s\\S]*?```)/g);
  return blocks.map(block => {
    if (block.startsWith("\`\`\`") && block.endsWith("\`\`\`")) {
      const content = block.slice(3, -3);
      const lines = content.split("\\n");
      let lang = "";
      let code = content;
      if (lines.length > 0 && lines[0].trim() && lines[0].trim().length < 15) {
        lang = lines[0].trim();
        code = lines.slice(1).join("\\n");
      }
      return `
        <div style="background: rgba(0,0,0,0.2); padding: 10px 14px; border-radius: 6px; margin: 8px 0; font-family: var(--font-mono); font-size: 12px; border-left: 3px solid #D4AF37; overflow-x: auto; color: #cbd5e1;">
          ${lang ? `<div style="font-size: 10px; color: #ffd700; font-weight: 600; text-transform: uppercase; margin-bottom: 4px;">${lang}</div>` : ""}
          <pre style="margin: 0; white-space: pre-wrap;">${escapeHtml(code)}</pre>
        </div>
      `;
    }

    const lines = block.split("\\n");
    return lines.map((line, lIdx) => {
      const trimmed = line.trim();
      if (trimmed.startsWith("### ")) return `<h5 style="margin: 12px 0 6px 0; font-weight: 600; font-size: 14px; border-left: 3.5px solid #D4AF37; padding-left: 8px; color: #D4AF37;">${parseMarkdownTokens(trimmed.slice(4))}</h5>`;
      if (trimmed.startsWith("## ")) return `<h4 style="margin: 16px 0 8px 0; font-weight: 700; font-size: 15px; border-left: 4px solid #D4AF37; padding-left: 8px; color: #D4AF37;">${parseMarkdownTokens(trimmed.slice(3))}</h4>`;
      if (trimmed.startsWith("# ")) return `<h3 style="margin: 20px 0 10px 0; font-weight: 700; font-size: 16px; border-left: 5px solid #D4AF37; padding-left: 8px; color: #D4AF37;">${parseMarkdownTokens(trimmed.slice(2))}</h3>`;
      if (/^[-*•]\\s+/.test(trimmed)) return `<div style="display: flex; align-items: flex-start; gap: 8px; margin: 4px 0 4px 12px;"><span style="color: #D4AF37; font-size: 12px; margin-top: 2px;">•</span><span style="flex: 1;">${parseMarkdownTokens(trimmed.replace(/^[-*•]\\s+/, ""))}</span></div>`;
      if (/^\\d+[.)]\\s+/.test(trimmed)) {
        const match = trimmed.match(/^(\\d+)[.)]\\s+/);
        const num = match ? match[1] : "1";
        return `<div style="display: flex; align-items: flex-start; gap: 8px; margin: 4px 0 4px 12px;"><span style="color: #D4AF37; font-weight: 600; font-size: 12px; margin-top: 2px;">${num}.</span><span style="flex: 1;">${parseMarkdownTokens(trimmed.replace(/^\\d+[.)]\\s+/, ""))}</span></div>`;
      }
      return `<span>${parseMarkdownTokens(line)}${lIdx < lines.length - 1 ? "<br />" : ""}</span>`;
    }).join("");
  }).join("");
}

function parseMarkdownTokens(text: string) {
  text = text.replace(/\\$\\$/g, '').replace(/\\\\text\\{([^}]+)\\}/g, '$1');
  const parts = text.split(/(\\*\\*.*?\\*\\*|\`.*?\`)/g);
  return parts.map(part => {
    if (part.startsWith("**") && part.endsWith("**")) return `<strong style="font-weight: 600;">${part.slice(2, -2)}</strong>`;
    if (part.startsWith("\`") && part.endsWith("\`")) return `<code style="font-family: var(--font-mono); background: rgba(212, 175, 55, 0.12); color: #ffd700; padding: 2px 5px; border-radius: 4px; font-size: 90%; margin: 0 2px; border: 1px solid rgba(212, 175, 55, 0.2);">${part.slice(1, -1)}</code>`;
    return escapeHtml(part);
  }).join("");
}

function escapeHtml(unsafe: string) {
  return unsafe
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function renderChatResponseHtml(responseObj: any) {
  const isDark = true;
  const response_type = responseObj.response_type || "general";
  const layout = responseObj.layout || "PLAIN_TEXT";
  const explanationText = responseObj.explanation || "";
  const formatted_answer = responseObj.formatted_answer || "";

  const formatTypeName = (name: string) => {
    return name
      .split(/[-_\s]+/)
      .map(w => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
      .join(" ");
  };
  
  const headerText = responseObj.header || formatTypeName(response_type);

  // Determine Icon
  let typeIconHtml = `<svg class="btn-svg" viewBox="0 0 24 24" style="width:16px; height:16px; fill:none; stroke:currentColor; stroke-width:2; stroke-linecap:round; stroke-linejoin:round;"><path d="M12 3l1.912 5.886h6.188l-5.006 3.637 1.912 5.886-5.006-3.637-5.006 3.637 1.912-5.886-5.006-3.637h6.188z"/></svg>`;
  const typeLower = response_type.toLowerCase();
  if (typeLower.includes("table")) {
    typeIconHtml = `<svg class="btn-svg" viewBox="0 0 24 24" style="width:16px; height:16px; fill:none; stroke:currentColor; stroke-width:2; stroke-linecap:round; stroke-linejoin:round;"><path d="M3 3h18v18H3zM3 9h18M3 15h18M9 3v18M15 3v18"/></svg>`;
  } else if (typeLower.includes("list") || typeLower.includes("bullet")) {
    typeIconHtml = `<svg class="btn-svg" viewBox="0 0 24 24" style="width:16px; height:16px; fill:none; stroke:currentColor; stroke-width:2; stroke-linecap:round; stroke-linejoin:round;"><path d="M9 6h11M9 12h11M9 18h11M5 6v.01M5 12v.01M5 18v.01"/></svg>`;
  } else if (typeLower.includes("count") || typeLower.includes("ranking") || typeLower.includes("breakdown")) {
    typeIconHtml = `<svg class="btn-svg" viewBox="0 0 24 24" style="width:16px; height:16px; fill:none; stroke:currentColor; stroke-width:2; stroke-linecap:round; stroke-linejoin:round;"><path d="M10 6h10M10 12h10M10 18h10M4 6h2v6H4M4 18h2M6 18H4"/></svg>`;
  } else if (typeLower.includes("comparison") || typeLower.includes("versus")) {
    typeIconHtml = `<svg class="btn-svg" viewBox="0 0 24 24" style="width:16px; height:16px; fill:none; stroke:currentColor; stroke-width:2; stroke-linecap:round; stroke-linejoin:round;"><path d="M3 6h18M3 18h18M12 3v18"/></svg>`;
  } else if (typeLower.includes("report") || typeLower.includes("summary") || typeLower.includes("analysis")) {
    typeIconHtml = `<svg class="btn-svg" viewBox="0 0 24 24" style="width:16px; height:16px; fill:none; stroke:currentColor; stroke-width:2; stroke-linecap:round; stroke-linejoin:round;"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6M16 13H8M16 17H8M10 9H8"/></svg>`;
  }

  let finalLayout = layout || "PLAIN_TEXT";
  let finalAnswer = formatted_answer || "";

  // Smart JSON layout detection override
  try {
    const obj = JSON.parse(finalAnswer);
    let data = obj;
    if (!Array.isArray(data)) {
      if (obj.records) data = obj.records;
      else if (obj.sorted_data) data = obj.sorted_data;
      else if (obj.unique_values) data = obj.unique_values;
      else if (obj.groups) data = obj.groups;
    }

    if (Array.isArray(data) && finalLayout !== "TABLE" && finalLayout !== "BULLET_LIST" && finalLayout !== "NUMBERED_LIST") {
       if (data.length > 0 && typeof data[0] === "object" && data[0] !== null && !Array.isArray(data[0])) {
           finalLayout = "TABLE";
       } else {
           finalLayout = "BULLET_LIST";
       }
    }
  } catch(e) {}

  // Generate layout specific renderer HTML
  let renderedContentHtml = "";
  switch (finalLayout) {
    case "TABLE":
      renderedContentHtml = renderTableLayout(finalAnswer, isDark);
      break;
    case "BULLET_LIST":
      renderedContentHtml = renderListLayout(finalAnswer, false, isDark);
      break;
    case "NUMBERED_LIST":
      renderedContentHtml = renderListLayout(finalAnswer, true, isDark);
      break;
    case "GRAPH":
      renderedContentHtml = renderGraphLayout(finalAnswer, isDark);
      break;
    case "PLAIN_TEXT":
    case "MARKDOWN":
    default:
      renderedContentHtml = renderMarkdownLayout(finalAnswer);
      break;
  }

  let explanationHtml = "";
  if (explanationText) {
    explanationHtml = `
      <div style="
        font-size: 13px;
        color: ${isDark ? "rgba(255,255,255,0.7)" : "rgba(15,23,42,0.8)"};
        margin-bottom: 8px;
        font-family: var(--font-sans, 'Inter', sans-serif);
        line-height: 1.5;
      ">
        ${escapeHtml(explanationText)}
      </div>
    `;
  }

  return `
    <div class="advance-ask-ai-container" style="
      width: 100%;
      display: flex;
      flex-direction: column;
      gap: 12px;
      padding: 16px;
      border-radius: 12px;
      background: ${isDark ? "rgba(30, 41, 59, 0.45)" : "rgba(241, 245, 249, 0.7)"};
      backdrop-filter: blur(12px);
      border: 1px solid ${isDark ? "rgba(255, 255, 255, 0.08)" : "rgba(15, 23, 42, 0.08)"};
      box-shadow: ${isDark ? "0 4px 20px -2px rgba(0, 0, 0, 0.25)" : "0 4px 20px -2px rgba(0, 0, 0, 0.05)"};
      font-family: var(--font-heading, 'Outfit', sans-serif);
    ">
      <!-- Premium Header -->
      <div style="
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-bottom: 1px solid ${isDark ? "rgba(255, 255, 255, 0.06)" : "rgba(15, 23, 42, 0.06)"};
        padding-bottom: 10px;
        gap: 12px;
      ">
        <div style="display: flex; align-items: center; gap: 8px;">
          <div style="
            display: flex;
            align-items: center;
            justify-content: center;
            width: 28px;
            height: 28px;
            border-radius: 6px;
            background: linear-gradient(135deg, #D4AF37 0%, #AA7C11 100%);
            color: #fff;
            box-shadow: 0 2px 8px rgba(212, 175, 55, 0.3);
          ">
            ${typeIconHtml}
          </div>
          <div>
            <h4 style="
              margin: 0;
              font-size: 14px;
              font-weight: 600;
              color: ${isDark ? "#f8fafc" : "#0f172a"};
              letter-spacing: 0.2px;
            ">
              ${escapeHtml(headerText)}
            </h4>
            <span style="
              font-size: 11px;
              color: ${isDark ? "rgba(255,255,255,0.45)" : "rgba(15,23,42,0.5)"};
            ">
              Advance Ask-AI Engine
            </span>
          </div>
        </div>
      </div>
      
      ${explanationHtml}

      <!-- Structured Content Area -->
      <div style="overflow-x: auto; width: 100%; font-family: var(--font-sans, 'Inter', sans-serif);">
        ${renderedContentHtml}
      </div>
    </div>
  `;
}

export async function sendAdvanceQuery(
  text: string,
  baseUrl: string,
  onStart: (stage: string) => void,
  onChunk: (word: string) => void,
  onEnd: (stage: string) => void,
  onComplete: (result: any) => void,
  onError: (error: any) => void,
  ws?: WebSocket | null,
  sessionId?: string
) {
  try {
    const CHAR_INTERVAL_MS = 22;
    let charQueue: string[] = [];
    let drainTimer: any = null;
    let streamDone = false;
    let pendingResult: any = null;
    let fadePending = false;
    let fadePendingStage = "";

    function startDrain() {
      if (drainTimer) return;
      drainTimer = setInterval(() => {
        if (charQueue.length > 0) {
          const charToDrain = charQueue.shift();
          if (charToDrain) onChunk(charToDrain);
        } else if (fadePending) {
          fadePending = false;
          const stage = fadePendingStage;
          onEnd(stage);
        } else if (streamDone) {
          clearInterval(drainTimer);
          drainTimer = null;
          if (ws && ws.readyState === WebSocket.OPEN) {
            ws.removeEventListener("message", handleWsMessage);
          }
          onComplete(pendingResult);
        }
      }, CHAR_INTERVAL_MS);
    }

    function handleWsMessage(event: MessageEvent) {
      try {
        const raw = typeof event.data === "string" ? event.data : "";
        if (raw.trim() === "pong") return;
        const line = raw.startsWith("data: ") ? raw.slice(6).trim() : raw.trim();
        if (line === "[DONE]" || line === "__END__") {
          if (!streamDone) {
            streamDone = true;
            startDrain();
          }
          return;
        }

        const data = JSON.parse(line);
        if (data.status === "running_start") {
          onStart(data.stage);
        } else if (data.status === "running_chunk") {
          if (data.word) {
            for (const ch of data.word) {
              charQueue.push(ch);
            }
            startDrain();
          }
        } else if (data.status === "running_end") {
          fadePending = true;
          fadePendingStage = data.stage;
          startDrain();
        } else if (data.status === "complete") {
          pendingResult = data.result;
          streamDone = true;
          // Clear the thought char queue immediately — don't wait for 22ms/char drain.
          // The final answer should appear as soon as the backend finishes, not seconds later.
          charQueue.length = 0;
          fadePending = false;
          if (drainTimer) {
            clearInterval(drainTimer);
            drainTimer = null;
          }
          if (ws && ws.readyState === WebSocket.OPEN) {
            ws.removeEventListener("message", handleWsMessage);
          }
          onComplete(pendingResult);

        }
      } catch (e) {
        // Ignored
      }
    }

    // ── 100% WebSocket Streaming Only ────────────────────────────
    if (ws && ws.readyState === WebSocket.OPEN) {
      console.log("🔌 Routing Advance AI query 100% over WebSocket...");
      ws.addEventListener("message", handleWsMessage);
      ws.send(JSON.stringify({
        query: text,
        isAdvanceStream: true,
        sessionId: sessionId || "default"
      }));
      return;
    }

    throw new Error("WebSocket is not connected. Advance AI strictly requires WebSocket connection.");
  } catch (err) {
    onError(err);
  }
}

export function renderCharToDom(ch: string) {
  const sc = document.getElementById("active-stream-container");
  if (!sc) return;

  let line = sc.querySelector(".active-stream-line:last-child") as HTMLElement | null;
  if (!line) {
    line = document.createElement("span");
    line.className = "active-stream-line";
    line.style.cssText = "font-family:var(--font-mono, 'Fira Code', monospace);font-size:12px;color:#94a3b8;line-height:1.6;white-space:pre-wrap;display:block;";
    sc.appendChild(line);
  }

  // Line wrap: break at space when line is getting long (~80 chars)
  if (ch === ' ' && line.textContent && line.textContent.length >= 80) {
    const newLine = document.createElement("span");
    newLine.className = "active-stream-line";
    newLine.style.cssText = "font-family:var(--font-mono, 'Fira Code', monospace);font-size:12px;color:#94a3b8;line-height:1.6;white-space:pre-wrap;transition:opacity 0.4s ease;display:block;";
    sc.appendChild(newLine);

    // Keep only 2 lines visible, fade older ones out
    const lines = sc.querySelectorAll(".active-stream-line");
    const total = lines.length;
    lines.forEach((ln, i) => {
      const age = total - 1 - i;
      const el = ln as HTMLElement;
      if (age === 0) el.style.opacity = "1";
      else if (age === 1) el.style.opacity = "0.4";
      else {
        el.style.opacity = "0";
        el.style.maxHeight = "0";
        el.style.overflow = "hidden";
      }
    });
    line = newLine;
    return; // skip space at start of line
  }

  line.textContent = (line.textContent || "") + ch;

  // Auto-scroll terminal container & parent chat window (100% matching index.html line 1767)
  sc.scrollTop = sc.scrollHeight;
  let curr: HTMLElement | null = sc.parentElement;
  while (curr) {
    if (curr.scrollHeight > curr.clientHeight && (getComputedStyle(curr).overflowY === 'auto' || getComputedStyle(curr).overflowY === 'scroll' || curr.classList.contains('overflow-y-auto'))) {
      curr.scrollTop = curr.scrollHeight;
      break;
    }
    curr = curr.parentElement;
  }
}

export function AdvanceStreamMessage({ msg, isDark = true }: { msg: any; isDark?: boolean }) {
  const [isThinkingOpen, setIsThinkingOpen] = useState(true);

  // Close accordion automatically when done
  useEffect(() => {
    if (!msg.streaming && msg.advanceResult) {
      setIsThinkingOpen(false);
    }
  }, [msg.streaming, msg.advanceResult]);

  return (
    <div style={{ width: "100%", display: "flex", flexDirection: "column", gap: "12px" }}>
      {/* Thought Process / Active Streaming Container */}
      {msg.streaming && (
        <div style={{ display: "flex", flexDirection: "column", gap: "6px", width: "100%" }}>
          {/* Initial Thinking Button (Only before any agent stage starts) */}
          {!msg.stage ? (
            <button 
              style={{ 
                display: "flex", alignItems: "center", gap: "8px", background: "rgba(212,175,55,0.1)", 
                border: "1px solid rgba(212,175,55,0.2)", borderRadius: "8px", padding: "8px 12px", 
                color: "#D4AF37", fontFamily: "inherit", fontSize: "13px", 
                textAlign: "left", outline: "none", width: "fit-content"
              }}
            >
              <svg 
                className="thinking-icon" 
                viewBox="0 0 24 24" 
                style={{ width: "16px", height: "16px", stroke: "currentColor", strokeWidth: 2, fill: "none", strokeLinecap: "round", strokeLinejoin: "round", animation: "spin 2s linear infinite" }}
              >
                <path d="M12 2v4m0 12v4M4.93 4.93l2.83 2.83m8.48 8.48l2.83 2.83M2 12h4m12 0h4M4.93 19.07l2.83-2.83m8.48-8.48l2.83-2.83"/>
              </svg>
              <span style={{ fontWeight: 500, letterSpacing: "0.3px" }}>Thinking...</span>
            </button>
          ) : (
            /* Active Agent Terminal Stream (Replaces Thinking... button when stage starts) */
            <div style={{ display: "flex", flexDirection: "column", gap: "6px", paddingLeft: "12px", borderLeft: "2px solid rgba(212,175,55,0.2)", marginLeft: "4px" }}>
              {/* Stage Header */}
              <div style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "11px", fontWeight: 600, letterSpacing: "0.05em", textTransform: "uppercase", color: "#D4AF37", padding: "2px 0" }}>
                <svg viewBox="0 0 24 24" style={{ width: "12px", height: "12px", stroke: "#D4AF37", fill: "none", strokeWidth: 2, strokeLinecap: "round", strokeLinejoin: "round", animation: "spin 2s linear infinite" }}>
                  <path d="M12 2v4m0 12v4M4.93 4.93l2.83 2.83m8.48 8.48l2.83 2.83M2 12h4m12 0h4M4.93 19.07l2.83-2.83m8.48-8.48l2.83-2.83"/>
                </svg>
                <span>{msg.stage}</span>
              </div>

              {/* Terminal Output Container matching index.html 100% */}
              <div 
                id="active-stream-container"
                style={{
                  background: "rgba(0,0,0,0.2)",
                  border: "1px solid rgba(212,175,55,0.15)",
                  borderRadius: "6px",
                  padding: "10px 12px",
                  minHeight: "120px",
                  maxHeight: "180px",
                  overflowY: "auto",
                  display: "flex",
                  flexDirection: "column"
                }}
              >
                <span 
                  className="active-stream-line"
                  style={{
                    fontFamily: "var(--font-mono, 'Fira Code', monospace)",
                    fontSize: "12px",
                    color: "#94a3b8",
                    lineHeight: "1.6",
                    whiteSpace: "pre-wrap",
                    display: "block"
                  }}
                ></span>
              </div>

              {/* Retrieval gap indicator */}
              {msg.isRetrieving && (
                <div 
                  className="retrieval-indicator"
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                    fontSize: "12px",
                    color: "#D4AF37",
                    fontStyle: "italic",
                    padding: "4px 0"
                  }}
                >
                  <svg viewBox="0 0 24 24" style={{ width: "16px", height: "16px", stroke: "#D4AF37", fill: "none", strokeWidth: 2, strokeLinecap: "round", strokeLinejoin: "round", animation: "spin 2s linear infinite" }}>
                    <ellipse cx="12" cy="5" rx="9" ry="3"/>
                    <path d="M3 5v14c0 1.657 4.03 3 9 3s9-1.343 9-3V5"/>
                    <path d="M3 12c0 1.657 4.03 3 9 3s9-1.343 9-3"/>
                  </svg>
                  <span>Retrieving data from database...</span>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Final Envelope Result */}
      {!msg.streaming && msg.advanceResult && (
        <div dangerouslySetInnerHTML={{ __html: renderChatResponseHtml(msg.advanceResult) }} />
      )}
    </div>
  );
}


