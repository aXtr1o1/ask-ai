"use client";

import React, { useState } from "react";
import {
  IconSparkles,
  IconTable,
  IconList,
  IconListNumbers,
  IconInfoCircle,
  IconCopy,
  IconCheck,
  IconTerminal,
  IconReport,
  IconScale,
  IconFileText,
  IconChevronDown,
  IconChevronUp
} from "@tabler/icons-react";
import { useTheme } from "@/app/components/useTheme";
import { escapeRawNewlinesInJSON } from "./utils";
import AdvanceGraph from "./AdvanceGraph";

interface Envelope {
  response_type: string;
  layout: "PLAIN_TEXT" | "BULLET_LIST" | "NUMBERED_LIST" | "TABLE" | "JSON" | "MARKDOWN" | "GRAPH";
  format_reason?: string;
  formatted_answer: string;
}

function convertTableToBullets(text: string): string {
  const lines = text.split("\n").map(l => l.trim()).filter(Boolean);
  const tableLines = lines.filter(l => l.includes("|"));
  
  if (tableLines.length < 3) {
    return text; // Not a valid table or too short
  }

  const parseRow = (rowStr: string) => {
    let cells = rowStr.split("|").map(c => c.trim());
    if (rowStr.startsWith("|")) cells.shift();
    if (rowStr.endsWith("|")) cells.pop();
    return cells;
  };

  const headers = parseRow(tableLines[0]);
  
  // Skip separator line (tableLines[1])
  const rows: string[] = [];
  for (let i = 2; i < tableLines.length; i++) {
    const cells = parseRow(tableLines[i]);
    const rowParts: string[] = [];
    for (let j = 0; j < headers.length; j++) {
      const h = headers[j];
      const c = cells[j] || "";
      if (h && c) {
        rowParts.push(`**${h}**: ${c}`);
      }
    }
    if (rowParts.length > 0) {
      rows.push(`* ${rowParts.join(", ")}`);
    }
  }

  const firstIdx = lines.indexOf(tableLines[0]);
  const lastIdx = lines.indexOf(tableLines[tableLines.length - 1]);
  
  const nonTableBefore = lines.slice(0, firstIdx);
  const nonTableAfter = lines.slice(lastIdx + 1);

  const result: string[] = [];
  if (nonTableBefore.length > 0) {
    result.push(nonTableBefore.join("\n"));
  }
  result.push(rows.join("\n"));
  if (nonTableAfter.length > 0) {
    result.push(nonTableAfter.join("\n"));
  }

  return result.join("\n");
}

interface AdvanceAskAiRendererProps {
  text: string;
  isStreaming?: boolean;
  userQuery?: string;
}

export default function AdvanceAskAiRenderer({ text, isStreaming = false, userQuery = "" }: AdvanceAskAiRendererProps) {
  const { theme } = useTheme();
  const isDark = theme === "dark";
  const [copied, setCopied] = useState(false);
  const [showReason, setShowReason] = useState(false);

  // Defensive parsing of the formatting envelope
  const envelope = React.useMemo((): Envelope | null => {
    if (!text) return null;
    try {
      let raw = text.trim();
      
      // 1. If wrapped in WebSocket wrapper { session_id, response }
      if (raw.startsWith("{")) {
        const sanitizedRaw = escapeRawNewlinesInJSON(raw);
        const parsed = JSON.parse(sanitizedRaw);
        if (parsed.response !== undefined) {
          raw = String(parsed.response).trim();
        }
      }

      // 2. If it is the JSON envelope
      if (raw.startsWith("{")) {
        const sanitizedRaw = escapeRawNewlinesInJSON(raw);
        const parsedEnvelope = JSON.parse(sanitizedRaw);
        if (parsedEnvelope && parsedEnvelope.formatted_answer !== undefined) {
          let layout = parsedEnvelope.layout || "MARKDOWN";
          let formatted_answer = String(parsedEnvelope.formatted_answer);

          const query_lower = userQuery.toLowerCase();
          const hasTableInQuery = query_lower.includes("table");

          if (hasTableInQuery) {
            // User requested a table, force layout to TABLE if formatted_answer contains table data
            if (formatted_answer.includes("|")) {
              layout = "TABLE";
            }
          } else {
            // User did NOT request a table, convert to bullet list format if it is currently a table
            if (layout === "TABLE" || (formatted_answer.includes("|") && (formatted_answer.includes("\n|") || formatted_answer.includes("\r|")))) {
              formatted_answer = convertTableToBullets(formatted_answer);
              layout = "BULLET_LIST";
            }
          }

          return {
            response_type: parsedEnvelope.response_type || "general",
            layout: layout as any,
            format_reason: parsedEnvelope.format_reason,
            formatted_answer: formatted_answer,
          };
        }
      }
    } catch (e) {
      // JSON parsing failed — might be streaming or raw markdown
    }
    return null;
  }, [text, userQuery]);

  const handleCopy = (txt: string) => {
    navigator.clipboard.writeText(txt);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // If it's not a valid envelope (or is still streaming incomplete JSON), render as standard text/markdown
  if (!envelope) {
    // If it looks like JSON but couldn't be parsed yet (streaming), strip the JSON syntax keys to keep UI clean
    let cleanText = text;
    if (isStreaming) {
      // Regex to strip JSON properties if they are visible in partial stream
      cleanText = cleanText
        .replace(/^\{\s*"response_type":\s*"[^"]*",\s*"layout":\s*"[^"]*",\s*"format_reason":\s*"[^"]*",\s*"formatted_answer":\s*"/g, "")
        .replace(/^\{\s*"response_type":.*?,"formatted_answer":\s*"/g, "")
        .replace(/"\s*\}\s*$/g, "")
        .replace(/\\n/g, "\n")
        .replace(/\\"/g, '"');
    }
    
    return (
      <div style={{ display: "inline-block", width: "100%", position: "relative" }}>
        <StandardMarkdownRenderer text={cleanText} />
        {isStreaming && <span className="stream-cursor" />}
      </div>
    );
  }

  const { response_type, layout, format_reason, formatted_answer } = envelope;

  // Determine Icon for the response type
  const getTypeIcon = () => {
    const type = response_type.toLowerCase();
    if (type.includes("table")) return <IconTable size={18} />;
    if (type.includes("list") || type.includes("bullet")) return <IconList size={18} />;
    if (type.includes("count") || type.includes("ranking") || type.includes("breakdown")) return <IconListNumbers size={18} />;
    if (type.includes("comparison") || type.includes("versus")) return <IconScale size={18} />;
    if (type.includes("report") || type.includes("summary") || type.includes("analysis")) return <IconReport size={18} />;
    return <IconSparkles size={18} />;
  };

  // Capitalize word utility
  const formatTypeName = (name: string) => {
    return name
      .split(/[-_\s]+/)
      .map(w => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
      .join(" ");
  };

  return (
    <div
      className="advance-ask-ai-container"
      style={{
        width: "100%",
        display: "flex",
        flexDirection: "column",
        gap: "12px",
        padding: "16px",
        borderRadius: "12px",
        background: isDark
          ? "rgba(30, 41, 59, 0.45)"
          : "rgba(241, 245, 249, 0.7)",
        backdropFilter: "blur(12px)",
        border: isDark
          ? "1px solid rgba(255, 255, 255, 0.08)"
          : "1px solid rgba(15, 23, 42, 0.08)",
        boxShadow: isDark
          ? "0 4px 20px -2px rgba(0, 0, 0, 0.25)"
          : "0 4px 20px -2px rgba(0, 0, 0, 0.05)",
        fontFamily: "Outfit, Inter, sans-serif",
      }}
    >
      {/* Premium Header */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          borderBottom: isDark ? "1px solid rgba(255, 255, 255, 0.06)" : "1px solid rgba(15, 23, 42, 0.06)",
          paddingBottom: "10px",
          gap: "12px",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              width: "28px",
              height: "28px",
              borderRadius: "6px",
              background: "linear-gradient(135deg, #D4AF37 0%, #AA7C11 100%)",
              color: "#fff",
              boxShadow: "0 2px 8px rgba(212, 175, 55, 0.3)",
            }}
          >
            {getTypeIcon()}
          </div>
          <div>
            <h4
              style={{
                margin: 0,
                fontSize: "14px",
                fontWeight: 600,
                color: isDark ? "#f8fafc" : "#0f172a",
                letterSpacing: "0.2px",
              }}
            >
              {formatTypeName(response_type)}
            </h4>
            <span
              style={{
                fontSize: "11px",
                color: isDark ? "rgba(255,255,255,0.45)" : "rgba(15,23,42,0.5)",
              }}
            >
              Advance Ask-AI Engine
            </span>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          {/* Format Badge */}
          <span
            style={{
              fontSize: "10px",
              fontWeight: 600,
              padding: "3px 8px",
              borderRadius: "12px",
              background: isDark ? "rgba(212, 175, 55, 0.15)" : "rgba(212, 175, 55, 0.1)",
              color: isDark ? "#ffd700" : "#aa7c11",
              border: `1px solid ${isDark ? "rgba(212,175,55,0.3)" : "rgba(212,175,55,0.2)"}`,
              textTransform: "uppercase",
              letterSpacing: "0.5px",
            }}
          >
            {layout.replace("_", " ")}
          </span>

          {/* Copy Button */}
          <button
            onClick={() => handleCopy(formatted_answer)}
            title="Copy answer content"
            style={{
              background: "none",
              border: "none",
              padding: "4px",
              cursor: "pointer",
              color: isDark ? "rgba(255,255,255,0.55)" : "rgba(15,23,42,0.55)",
              borderRadius: "4px",
              transition: "background 0.2s",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
            onMouseEnter={(e) => (e.currentTarget.style.background = isDark ? "rgba(255,255,255,0.06)" : "rgba(0,0,0,0.04)")}
            onMouseLeave={(e) => (e.currentTarget.style.background = "none")}
          >
            {copied ? <IconCheck size={16} style={{ color: "#22c55e" }} /> : <IconCopy size={16} />}
          </button>
        </div>
      </div>

      {/* Structured Content Area */}
      <div style={{ overflowX: "auto", width: "100%" }}>
        {(() => {
          switch (layout) {
            case "TABLE":
              return <TableLayoutRenderer text={formatted_answer} isDark={isDark} />;
            case "BULLET_LIST":
              return <ListLayoutRenderer text={formatted_answer} isNumbered={false} isDark={isDark} />;
            case "NUMBERED_LIST":
              return <ListLayoutRenderer text={formatted_answer} isNumbered={true} isDark={isDark} />;
            case "JSON":
              return <JsonLayoutRenderer text={formatted_answer} isDark={isDark} onCopy={handleCopy} copied={copied} />;
            case "GRAPH":
              return <AdvanceGraph text={formatted_answer} isDark={isDark} onCopy={handleCopy} copied={copied} userQuery={userQuery} />;
            case "MARKDOWN":
              return <StandardMarkdownRenderer text={formatted_answer} />;
            case "PLAIN_TEXT":
            default:
              return (
                <div
                  style={{
                    fontSize: "14px",
                    lineHeight: "1.6",
                    color: isDark ? "#e2e8f0" : "#334155",
                    whiteSpace: "pre-wrap",
                  }}
                >
                  {formatted_answer}
                </div>
              );
          }
        })()}
      </div>

      {/* Format Reason Accordion */}
      {format_reason && (
        <div
          style={{
            marginTop: "6px",
            borderTop: isDark ? "1px solid rgba(255, 255, 255, 0.05)" : "1px solid rgba(15, 23, 42, 0.05)",
            paddingTop: "10px",
          }}
        >
          <button
            onClick={() => setShowReason(!showReason)}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "4px",
              background: "none",
              border: "none",
              cursor: "pointer",
              padding: 0,
              fontSize: "11px",
              fontWeight: 500,
              color: isDark ? "rgba(255,255,255,0.45)" : "rgba(15,23,42,0.5)",
              transition: "color 0.2s",
            }}
            onMouseEnter={(e) => (e.currentTarget.style.color = isDark ? "#ffd700" : "#aa7c11")}
            onMouseLeave={(e) => (e.currentTarget.style.color = isDark ? "rgba(255,255,255,0.45)" : "rgba(15,23,42,0.5)")}
          >
            <IconInfoCircle size={14} />
            <span>Why this format?</span>
            {showReason ? <IconChevronUp size={12} /> : <IconChevronDown size={12} />}
          </button>
          
          {showReason && (
            <div
              style={{
                marginTop: "6px",
                fontSize: "11.5px",
                lineHeight: "1.5",
                color: isDark ? "rgba(255,255,255,0.55)" : "rgba(15,23,42,0.6)",
                background: isDark ? "rgba(255,255,255,0.03)" : "rgba(0,0,0,0.02)",
                padding: "8px 12px",
                borderRadius: "6px",
                borderLeft: `2px solid ${isDark ? "rgba(212,175,55,0.5)" : "rgba(212,175,55,0.3)"}`,
              }}
            >
              {format_reason}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Sub-Renderer: Markdown Table ───────────────────────────────────────────
function TableLayoutRenderer({ text, isDark }: { text: string; isDark: boolean }) {
  const tableData = React.useMemo(() => {
    const lines = text.split("\n").map(l => l.trim()).filter(Boolean);
    const tableLines = lines.filter(l => l.includes("|"));
    if (tableLines.length < 2) return null;

    // Detect if second line is separator like ---|---|---
    const separatorLine = tableLines[1];
    if (!/^[|:\s-]+$/.test(separatorLine)) return null;

    const parseRow = (rowStr: string) => {
      let cells = rowStr.split("|").map(c => c.trim());
      if (rowStr.startsWith("|")) cells.shift();
      if (rowStr.endsWith("|")) cells.pop();
      return cells;
    };

    const headers = parseRow(tableLines[0]);
    const rows = tableLines.slice(2).map(parseRow);

    return { headers, rows };
  }, [text]);

  if (!tableData) {
    return <StandardMarkdownRenderer text={text} />;
  }

  const { headers, rows } = tableData;

  return (
    <div
      style={{
        overflowX: "auto",
        borderRadius: "8px",
        border: isDark ? "1px solid rgba(255,255,255,0.06)" : "1px solid rgba(15,23,42,0.06)",
        boxShadow: "0 2px 10px rgba(0,0,0,0.05)",
      }}
    >
      <table
        style={{
          width: "100%",
          borderCollapse: "collapse",
          textAlign: "left",
          fontSize: "13px",
        }}
      >
        <thead>
          <tr
            style={{
              background: isDark ? "rgba(255, 255, 255, 0.04)" : "rgba(0, 0, 0, 0.02)",
              borderBottom: isDark ? "1.5px solid rgba(255,255,255,0.12)" : "1.5px solid rgba(15,23,42,0.12)",
            }}
          >
            {headers.map((h, i) => (
              <th
                key={i}
                style={{
                  padding: "10px 14px",
                  fontWeight: 600,
                  color: isDark ? "#ffd700" : "#8a6508",
                  whiteSpace: "nowrap",
                }}
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rIdx) => (
            <tr
              key={rIdx}
              style={{
                borderBottom: rIdx < rows.length - 1
                  ? isDark ? "1px solid rgba(255,255,255,0.04)" : "1px solid rgba(15,23,42,0.04)"
                  : "none",
                background: rIdx % 2 === 1
                  ? isDark ? "rgba(255,255,255,0.015)" : "rgba(0,0,0,0.005)"
                  : "none",
                transition: "background 0.2s",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = isDark ? "rgba(212, 175, 55, 0.04)" : "rgba(212, 175, 55, 0.03)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = rIdx % 2 === 1
                  ? isDark ? "rgba(255,255,255,0.015)" : "rgba(0,0,0,0.005)"
                  : "none";
              }}
            >
              {row.map((cell, cIdx) => (
                <td
                  key={cIdx}
                  style={{
                    padding: "10px 14px",
                    color: isDark ? "#cbd5e1" : "#475569",
                  }}
                >
                  {cell.startsWith("**") && cell.endsWith("**") ? (
                    <strong>{cell.replace(/\*\*/g, "")}</strong>
                  ) : (
                    cell
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ListLayoutRenderer({ text, isNumbered, isDark }: { text: string; isNumbered: boolean; isDark: boolean }) {
  const items = React.useMemo(() => {
    const lines = text.split("\n").map(l => l.trim()).filter(l => l.length > 0);
    const parsedItems: string[] = [];
    for (const line of lines) {
      if (/^([\s]*(?:[-*•]|\d+[.)]))\s*/.test(line)) {
        const clean = line.replace(/^([\s]*(?:[-*•]|\d+[.)]))\s*/, "");
        parsedItems.push(clean);
      } else {
        if (parsedItems.length > 0) {
          parsedItems[parsedItems.length - 1] += "\n" + line;
        } else {
          parsedItems.push(line);
        }
      }
    }
    return parsedItems;
  }, [text]);

  if (items.length === 0) return <div style={{ fontSize: "14px" }}>{text}</div>;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "10px", paddingLeft: "4px" }}>
      {items.map((item, idx) => (
        <div key={idx} style={{ display: "flex", alignItems: "flex-start", gap: "10px" }}>
          {isNumbered ? (
            <div
              style={{
                flexShrink: 0,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                width: "22px",
                height: "22px",
                borderRadius: "50%",
                background: isDark ? "rgba(212, 175, 55, 0.15)" : "rgba(212, 175, 55, 0.1)",
                border: `1px solid ${isDark ? "rgba(212,175,55,0.3)" : "rgba(212,175,55,0.2)"}`,
                color: isDark ? "#ffd700" : "#8a6508",
                fontSize: "11px",
                fontWeight: 600,
                marginTop: "2px",
              }}
            >
              {idx + 1}
            </div>
          ) : (
            <div
              style={{
                flexShrink: 0,
                width: "6px",
                height: "6px",
                borderRadius: "50%",
                background: "linear-gradient(135deg, #D4AF37 0%, #AA7C11 100%)",
                marginTop: "10px",
                boxShadow: "0 0 6px rgba(212, 175, 55, 0.8)",
              }}
            />
          )}
          <div
            style={{
              fontSize: "13.5px",
              lineHeight: "1.6",
              color: isDark ? "#cbd5e1" : "#475569",
              flex: 1,
            }}
          >
            <StandardMarkdownRenderer text={item} />
          </div>
        </div>
      ))}
    </div>
  );
}

// ─── Sub-Renderer: Code/JSON Highlighted Blocks ─────────────────────────────
function JsonLayoutRenderer({
  text,
  isDark,
  onCopy,
  copied
}: {
  text: string;
  isDark: boolean;
  onCopy: (txt: string) => void;
  copied: boolean;
}) {
  const formattedJson = React.useMemo(() => {
    try {
      const obj = JSON.parse(text);
      return JSON.stringify(obj, null, 2);
    } catch {
      return text;
    }
  }, [text]);

  return (
    <div
      style={{
        position: "relative",
        background: isDark ? "rgba(15, 23, 42, 0.7)" : "#1e293b",
        color: "#f8fafc",
        fontFamily: "var(--font-mono, 'Courier New', monospace)",
        fontSize: "12.5px",
        padding: "14px",
        borderRadius: "8px",
        border: "1px solid rgba(255, 255, 255, 0.08)",
        boxShadow: "inset 0 2px 4px rgba(0,0,0,0.3)",
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          fontSize: "11px",
          color: "rgba(255,255,255,0.4)",
          marginBottom: "8px",
          borderBottom: "1px solid rgba(255,255,255,0.06)",
          paddingBottom: "6px",
        }}
      >
        <span style={{ display: "flex", alignItems: "center", gap: "4px" }}>
          <IconTerminal size={14} />
          JSON Output
        </span>
        <button
          onClick={() => onCopy(formattedJson)}
          style={{
            background: "none",
            border: "none",
            color: "rgba(255,255,255,0.5)",
            cursor: "pointer",
            fontSize: "11px",
            display: "flex",
            alignItems: "center",
            gap: "4px",
            padding: "2px 6px",
            borderRadius: "4px",
          }}
          onMouseEnter={(e) => (e.currentTarget.style.color = "#ffd700")}
          onMouseLeave={(e) => (e.currentTarget.style.color = "rgba(255,255,255,0.5)")}
        >
          {copied ? <IconCheck size={12} style={{ color: "#22c55e" }} /> : <IconCopy size={12} />}
          {copied ? "Copied!" : "Copy"}
        </button>
      </div>
      <pre style={{ margin: 0, overflowX: "auto", whiteSpace: "pre-wrap" }}>
        <code>{formattedJson}</code>
      </pre>
    </div>
  );
}

// Inline renderer for bold and code
function InlineMarkdownRenderer({ text }: { text: string }) {
  const parts = text.split(/(\*\*.*?\*\*|`.*?`)/g);
  return (
    <>
      {parts.map((part, idx) => {
        if (part.startsWith("**") && part.endsWith("**")) {
          return <strong key={idx} style={{ fontWeight: 600 }}>{part.slice(2, -2)}</strong>;
        }
        if (part.startsWith("`") && part.endsWith("`")) {
          return (
            <code
              key={idx}
              style={{
                fontFamily: "monospace",
                background: "rgba(212, 175, 55, 0.12)",
                color: "#ffc107",
                padding: "2px 5px",
                borderRadius: "4px",
                fontSize: "90%",
                margin: "0 2px",
                border: "1px solid rgba(212, 175, 55, 0.2)",
              }}
            >
              {part.slice(1, -1)}
            </code>
          );
        }
        return <span key={idx}>{part}</span>;
      })}
    </>
  );
}

// ─── Sub-Renderer: Basic Markdown parser (bold, inline code, links, headers, lists) ────────
function StandardMarkdownRenderer({ text }: { text: string }) {
  if (!text) return null;

  // Split by code blocks first
  const blocks = text.split(/(```[\s\S]*?```)/g);

  return (
    <div style={{ width: "100%", whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
      {blocks.map((block, bIdx) => {
        if (block.startsWith("```") && block.endsWith("```")) {
          const content = block.slice(3, -3);
          const lines = content.split("\n");
          let lang = "";
          let code = content;
          if (lines.length > 0 && lines[0].trim() && lines[0].trim().length < 15) {
            lang = lines[0].trim();
            code = lines.slice(1).join("\n");
          }
          return (
            <div
              key={bIdx}
              style={{
                background: "rgba(0,0,0,0.2)",
                padding: "10px 14px",
                borderRadius: "6px",
                margin: "8px 0",
                fontFamily: "monospace",
                fontSize: "12px",
                borderLeft: "3px solid #D4AF37",
                overflowX: "auto",
                color: "#cbd5e1"
              }}
            >
              {lang && (
                <div style={{ fontSize: "10px", color: "#ffd700", fontWeight: 600, textTransform: "uppercase", marginBottom: "4px" }}>
                  {lang}
                </div>
              )}
              <pre style={{ margin: 0, whiteSpace: "pre-wrap" }}>{code}</pre>
            </div>
          );
        }

        // Process non-code block text line by line to handle headings and lists dynamically
        const lines = block.split("\n");
        return (
          <span key={bIdx}>
            {lines.map((line, lIdx) => {
              const trimmed = line.trim();
              
              // Headings
              if (trimmed.startsWith("### ")) {
                return (
                  <h5 key={lIdx} style={{ margin: "12px 0 6px 0", fontWeight: 600, fontSize: "14px", borderLeft: "3.5px solid #D4AF37", paddingLeft: "8px", color: "#D4AF37" }}>
                    <InlineMarkdownRenderer text={trimmed.slice(4)} />
                  </h5>
                );
              }
              if (trimmed.startsWith("## ")) {
                return (
                  <h4 key={lIdx} style={{ margin: "16px 0 8px 0", fontWeight: 700, fontSize: "15px", borderLeft: "4px solid #D4AF37", paddingLeft: "8px", color: "#D4AF37" }}>
                    <InlineMarkdownRenderer text={trimmed.slice(3)} />
                  </h4>
                );
              }
              if (trimmed.startsWith("# ")) {
                return (
                  <h3 key={lIdx} style={{ margin: "20px 0 10px 0", fontWeight: 700, fontSize: "16px", borderLeft: "5px solid #D4AF37", paddingLeft: "8px", color: "#D4AF37" }}>
                    <InlineMarkdownRenderer text={trimmed.slice(2)} />
                  </h3>
                );
              }

              // List Items (Bullet lists)
              if (/^[-*•]\s+/.test(trimmed)) {
                return (
                  <div key={lIdx} style={{ display: "flex", alignItems: "flex-start", gap: "8px", margin: "4px 0 4px 12px" }}>
                    <span style={{ color: "#D4AF37", fontSize: "12px", marginTop: "2px" }}>•</span>
                    <span style={{ flex: 1 }}>
                      <InlineMarkdownRenderer text={trimmed.replace(/^[-*•]\s+/, "")} />
                    </span>
                  </div>
                );
              }

              // Numbered list items
              if (/^\d+[.)]\s+/.test(trimmed)) {
                const match = trimmed.match(/^(\d+)[.)]\s+/);
                const num = match ? match[1] : "1";
                return (
                  <div key={lIdx} style={{ display: "flex", alignItems: "flex-start", gap: "8px", margin: "4px 0 4px 12px" }}>
                    <span style={{ color: "#D4AF37", fontWeight: 600, fontSize: "12px", marginTop: "2px" }}>{num}.</span>
                    <span style={{ flex: 1 }}>
                      <InlineMarkdownRenderer text={trimmed.replace(/^\d+[.)]\s+/, "")} />
                    </span>
                  </div>
                );
              }

              // Normal text lines
              return (
                <span key={lIdx}>
                  <InlineMarkdownRenderer text={line} />
                  {lIdx < lines.length - 1 && <br />}
                </span>
              );
            })}
          </span>
        );
      })}
    </div>
  );
}
