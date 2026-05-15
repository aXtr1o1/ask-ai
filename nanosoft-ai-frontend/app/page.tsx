"use client";

import { useState, useRef, useEffect, useLayoutEffect } from "react";
import { createPortal } from "react-dom";
/* changes done by megnathan: Cleaned up unused imports */
import { useRouter } from "next/navigation";
import Image from "next/image";
import { ThemeToggle } from "./components/ThemeToggle";
import { useResponsive, getResponsivePieChartSize } from "./hooks/useResponsive";
import BackgroundLayer from "./components/BackgroundLayer";
import { useTheme } from "./components/useTheme";

import { useVoiceRecorder, RecordingInterface, VoicePreviewBar, VoiceMicButton } from "./components/VoiceRecorder";
import { parseGraphData, BarChartRenderer, HorizontalBarChartRenderer, LineChartRenderer, PieChartRenderer, ChartType } from "./components/GraphRenderer";
import TableWithTile, { TableWithTileRow } from "./components/TableWithTile";
import UpgradePlan from "./components/UpgradePlan";
import ManageAccount from "./components/ManageAccount/ManageAccount";
import WalkthroughPopup from "./components/WalkthroughPopup";
import LandingSuggestedQueries from "./components/LandingSuggestedQueries";
import GroupsChat from "./components/GroupsChat";
/* changes done by megnathan: Added imports for the new Ghost Completion feature */
import { useGhostInputCompletion } from "./hooks/useGhostInputCompletion";
import { recordPromptForGhostHistory, ghostPromptHistoryStorageKey } from "./lib/ghostInputCompletion";
/* changes done by megnathan: Cleaned up icon imports to avoid conflicts with local definitions */
import {
  IconUser, IconMicrophone, IconPlayerPlay, IconPlayerPause,
  IconTrash, IconArrowUp, IconChartBar, IconList,
  IconLayoutGrid, IconMenu2, IconX, IconCrown,
  IconDotsVertical, IconCopy, IconCheck, IconBulb, IconFolder
} from "@tabler/icons-react";
// ─── Types ───────────────────────────────────────────────────────────────────
interface Message {
  role: "user" | "ai" | "error";
  text: string;
  streaming?: boolean;
  isLargeDataset?: boolean;
  isAudio?: boolean;
  audioDuration?: number;
  audioUrl?: string;
  sendStatus?: "sent" | "failed" | "sending";
  isGraphResponse?: boolean;  // ← Set to true if response is type="graph"
  chartType?: ChartType;      // ← chart type per message
  originalText?: string;      // ← Store original raw response before HTML processing
  tableData?: TableWithTileRow[];  // ← Store table rows for TableWithTile component
  tableTitle?: string;        // ← Title for the table
  tableViewMode?: 'table' | 'tile';  // ← Toggle between table and tile views
}
interface ChatSession { id: string; title: string; createdAt: number; updatedAt?: number; isPinned?: boolean; isArchived?: boolean; group_name?: string; }
interface Group {
  id: string;
  name: string;
  description: string;
  chatCount: number;
  updatedAt: string;
}

// ─── Extract text from any backend response shape ─────────────────────────────
// Improved: handles JSON strings without spaces, array join, and reply/content/text fields
function extractText(raw: any, depth = 0): string {
  if (depth > 10 || raw == null) return "";
  if (typeof raw === "string") {
    const trimmed = raw.trim();
    // If it looks like JSON (starts with { or [), attempt to parse it.
    // Relaxed rule: JSONB or stringified JSON from backend often contains spaces
    // so try parsing whenever it appears JSON-like. Fall back to the raw string on error.
    if (trimmed.startsWith("{") || trimmed.startsWith("[")) {
      try {
        const parsedOnce = JSON.parse(trimmed);
        // If parsing returns a string containing JSON (double-encoded), try again
        if (typeof parsedOnce === 'string') {
          try { return extractText(JSON.parse(parsedOnce), depth + 1); } catch { /* ignore */ }
        }
        return extractText(parsedOnce, depth + 1);
      } catch {
        // not valid JSON — continue and return raw below
      }
    }
    return raw;
  }
  if (Array.isArray(raw))
    return raw.map(item => extractText(item, depth + 1)).filter(t => t.trim()).join("");
  if (typeof raw === "object") {
    // Priority order: response → content → text → reply
    if (raw.response) return extractText(raw.response, depth + 1);
    if (raw.content) return extractText(raw.content, depth + 1);
    if (raw.text) return extractText(raw.text, depth + 1);
    if (raw.reply) return extractText(raw.reply, depth + 1);
    return "";
  }
  return String(raw);
}

// ═══════════════════════════════════════════════════════════════════════════════
//  DYNAMIC UNIVERSAL FORMATTER  v3
//
//  ONE RULE:
//    Any KV data with ≥3 fields  → TABLE  (even 1 record)
//    Any KV data with <3 fields  → BULLET LIST
//    Plain bullets (no KV)       → BULLET LIST
//    Pipe table (|col|col|)      → TABLE  always
//
//  Handles ALL backend output shapes:
//  ┌──────────────────────────────────────────────────────────────────────────┐
//  │ A  Pipe table    "| Col | Col |\n|---|\n| V | V |"    → TABLE always    │
//  │ B  Horiz KV     "• Key: V, Key: V, Key: V"           → TABLE if ≥3 KV  │
//  │ C  Vert bullet  "• Key: V\n• Key: V\n• Key: V..."    → TABLE if ≥3 KV  │
//  │ D  Plain block  "Key: V\nKey: V\n\nKey: V\n..."       → TABLE if ≥3 KV  │
//  │ E  Plain prose  "• text\n• text"                      → BULLET LIST      │
//  └──────────────────────────────────────────────────────────────────────────┘
// ═══════════════════════════════════════════════════════════════════════════════

// ── HTML escape ───────────────────────────────────────────────────────────────
function esc(s: string): string {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

// ── Inline markdown: **bold**, *italic*, `code` ───────────────────────────────
function md(text: string): string {
  text = esc(text);
  text = text.replace(/`([^`]+)`/g,
    '<code style="background:rgba(0,0,0,0.07);padding:1px 5px;border-radius:3px;font-family:monospace;font-size:12px">$1</code>');
  text = text.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  text = text.replace(/\*(.+?)\*/g, "<em>$1</em>");
  return text;
}

// ── Strip bullet/number prefix + strip **bold** and *italic* from a line ──────
function cleanLine(raw: string): string {
  let s = raw.replace(/^[\s]*(?:[-*•]|\d+[.)]):?\s?/, "").trim();
  s = s.replace(/\*\*(.+?)\*\*/g, "$1").replace(/\*(.+?)\*/g, "$1");
  return s;
}

// ── Detect if HTML contains a <table> tag ────────────────────────────────────
function hasTableTag(html: string): boolean {
  return /<table[^>]*>/i.test(html);
}

// ── Extract table rows from HTML table ─────────────────────────────────────────
function extractTableRows(html: string): TableWithTileRow[] {
  const rows: TableWithTileRow[] = [];
  try {
    const parser = new DOMParser();
    const doc = parser.parseFromString(html, "text/html");
    const table = doc.querySelector("table");
    if (!table) return rows;

    // Get column headers
    const headers: string[] = [];
    const ths = table.querySelectorAll("thead th");
    ths.forEach(th => {
      const text = th.textContent?.trim() || "";
      if (text) headers.push(text);
    });

    // Get table rows
    const trs = table.querySelectorAll("tbody tr");
    trs.forEach(tr => {
      const tds = tr.querySelectorAll("td");
      const row: TableWithTileRow = {};
      tds.forEach((td, idx) => {
        const header = headers[idx];
        if (header) {
          row[header] = td.textContent?.trim() || "—";
        }
      });
      if (Object.keys(row).length > 0) {
        rows.push(row);
      }
    });
  } catch (err) {
    console.warn("Failed to parse table HTML:", err);
  }
  return rows;
}

// ── Regex: matches "Key: value" or "**Key**: value" (key 2–30 alpha chars) ────
const KV_LINE_RE = /^\*{0,2}([A-Za-z][A-Za-z ]{1,28})\*{0,2}:[ \t]+(.+)$/;
// Multi-KV on one line: "Key: Val, Key: Val"
const KV_BOUND_SRC = String.raw`(?:^|(?:,\s+))([A-Za-z][A-Za-z ]{0,25}?):\s*`;

// ── Columns to hide from large dataset display (sensitive data) ──
const HIDDEN_COLUMNS = new Set([
  'id',
  'user_id',
  'userid',
  'user_name',
  'username',
  'createdat',
  'created_at',
  'updatedat',
  'updated_at',
]);

function isHiddenColumn(col: string): boolean {
  return HIDDEN_COLUMNS.has(col.toLowerCase().replace(/[\s_]/g, ""));
}

// ── Status badge renderer ─────────────────────────────────────────────────────
function badge(val: string): string {
  const v = val.toLowerCase();
  const cls = ["online", "open", "good", "active", "operational", "serviceable", "completed"].includes(v)
    ? "status-online"
    : ["offline", "closed", "inactive", "fault", "immobilized", "cancelled"].includes(v)
      ? "status-offline"
      : "status-neutral";
  return `<span class="status-badge ${cls}">${esc(val)}</span>`;
}

const BADGE_COLS = new Set(["status", "condition", "state", "wostatus", "ppstatus", "ppmstatus"]);
function isBadgeCol(col: string): boolean {
  return BADGE_COLS.has(col.toLowerCase().replace(/[\s_]/g, ""));
}

// ── Extract table HTML from larger HTML block ────────────────────────────────
function extractTableHtml(html: string): string | null {
  const tableMatch = html.match(/<table[^>]*>[\s\S]*?<\/table>/i);
  return tableMatch ? tableMatch[0] : null;
}

// ── Build HTML <table> from rows ──────────────────────────────────────────────
// ── Build HTML <table> from rows - SMALL DATA TABLES ──
// ── Build HTML <table> from rows - SMALL DATA TABLES ──
function buildTable(rows: Record<string, string>[], cols?: string[]): string {
  if (!rows.length) return "";

  // Collect column order preserving insertion order
  const allCols: string[] = cols ?? (() => {
    const seen: string[] = [];
    rows.forEach(r => Object.keys(r).forEach(k => { if (!seen.includes(k)) seen.push(k); }));
    return seen;
  })();

  const thead = `<thead><tr>${allCols.map(c => `<th>${esc(c)}</th>`).join("")}</tr></thead>`;

  const tbody = `<tbody>${rows.map(row =>
    `<tr>${allCols.map(col => {
      const val = row[col] ?? "—";
      const cell = isBadgeCol(col) ? badge(val) : esc(val);
      return `<td>${cell}</td>`;
    }).join("")}</tr>`
  ).join("")}</tbody>`;

  const tfoot = `<tfoot><tr><td colspan="${allCols.length}" style="text-align:left;padding-left:12px;padding-right:12px;display:flex;justify-content:space-between;align-items:center;gap:20px"><span>Columns: ${allCols.length}</span><span>Total: ${rows.length} records</span></td></tr></tfoot>`;

  return `<div class="table-wrapper"><table class="ai-table">${thead}${tbody}${tfoot}</table></div>`;
}

// ══════════════════════════════════════════════════════════════════════════════
//  EXTRACT RESPONSE CONTENT (Remove session_id wrapper)
// ══════════════════════════════════════════════════════════════════════════════

function extractResponseContent(text: string): string {
  try {
    const parsed = JSON.parse(text);

    // If wrapper has session_id + response, extract just the response
    if (parsed.session_id && parsed.response) {
      return String(parsed.response);
    }

    // If it has a response field, use it
    if (parsed.response) {
      return String(parsed.response);
    }

    // Otherwise return original text
    return text;
  } catch {
    // Not JSON, return as-is
    return text;
  }
}

// ══════════════════════════════════════════════════════════════════════════════
//  LARGE DATASET HANDLER (SEPARATE FUNCTION)
//  Handles >100 records: Converts to table + displays context summary
// ══════════════════════════════════════════════════════════════════════════════

function renderLargeDataset(text: string): string | null {
  // ─────────────────────────────────────────
  // Hidden columns
  // ─────────────────────────────────────────
  const HIDDEN_COLUMNS = new Set([
    "id",
    "user_id",
    "userid",
    "user_name",
    "username",
    "createdat",
    "created_at",
    "updatedat",
    "updated_at",
  ]);

  function isHiddenColumn(col: string) {
    return HIDDEN_COLUMNS.has(col.toLowerCase().replace(/[\s_]/g, ""));
  }

  // ─────────────────────────────────────────
  // Status badge columns
  // ─────────────────────────────────────────
  const BADGE_COLS = new Set([
    "status",
    "condition",
    "state",
    "wostatus",
    "ppstatus",
    "ppmstatus",
  ]);

  function isBadgeCol(col: string) {
    return BADGE_COLS.has(col.toLowerCase().replace(/[\s_]/g, ""));
  }

  function badge(val: string) {
    const v = val.toLowerCase();
    const cls =
      ["online", "open", "good", "active", "operational", "serviceable", "completed"].includes(v)
        ? "status-online"
        : ["offline", "closed", "inactive", "fault", "immobilized", "cancelled"].includes(v)
          ? "status-offline"
          : "status-neutral";
    return `<span class="status-badge ${cls}">${escapeHTML(val)}</span>`;
  }

  // ─────────────────────────────────────────
  // Escape HTML
  // ─────────────────────────────────────────
  function escapeHTML(s: string) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  // ─────────────────────────────────────────
  // Parse response JSON
  // ─────────────────────────────────────────
  let parsed: any;

  try {
    parsed = JSON.parse(text);
    if (parsed.response && typeof parsed.response === "string") {
      parsed = JSON.parse(parsed.response);
    }
  } catch {
    return null;
  }

  // ─────────────────────────────────────────
  // Detect data (ANY size - no limits)
  // ─────────────────────────────────────────
  let records = [];

  // Accept ANY array, regardless of size
  if (parsed.type === "large_dataset" && Array.isArray(parsed.records)) {
    records = parsed.records;
  } else if (Array.isArray(parsed.records)) {
    records = parsed.records;
  } else if (Array.isArray(parsed.p_list)) {
    records = parsed.p_list;
  } else if (Array.isArray(parsed.data)) {
    records = parsed.data;
  } else {
    return null;
  }

  // Return null only if no records found
  if (!records || records.length === 0) {
    return null;
  }

  const context = parsed.context_summary || `Dataset contains ${records.length} records`;

  if (!records.length) {
    return `<div class="large-dataset-context">${escapeHTML(context)}</div>`;
  }

  // ─────────────────────────────────────────
  // Collect columns dynamically
  // ─────────────────────────────────────────
  const columns = new Set<string>();

  records.forEach((r: any) => {
    if (!r || typeof r !== "object") return;
    Object.keys(r).forEach(k => {
      if (!isHiddenColumn(k)) columns.add(k);
    });
  });

  const cols = Array.from(columns);

  // ─────────────────────────────────────────
  // Build table header
  // ─────────────────────────────────────────
  let head = "<thead><tr>";
  cols.forEach(c => {
    head += `<th>${escapeHTML(c)}</th>`;
  });
  head += "</tr></thead>";

  // ─────────────────────────────────────────
  // Build rows
  // ─────────────────────────────────────────
  let body = "<tbody>";

  records.forEach((record: any) => {
    body += "<tr>";
    cols.forEach(col => {
      const val = record[col];
      let cell = "—";

      if (val === null || val === undefined) {
        cell = "—";
      } else if (typeof val === "boolean") {
        cell = `<span style="font-weight:600;color:${val ? "#22c55e" : "#ef44440"}">
                ${val ? "✓" : "✗"}
                </span>`;
      } else if (typeof val === "object") {
        const str = JSON.stringify(val);
        cell = escapeHTML(str.length > 50 ? str.slice(0, 50) + "…" : str);
      } else {
        const str = String(val);
        const display = str.length > 100 ? str.slice(0, 100) + "…" : str;

        if (isBadgeCol(col)) {
          cell = badge(str);
        } else {
          cell = escapeHTML(display);
        }
      }

      body += `<td>${cell}</td>`;
    });
    body += "</tr>";
  });

  body += "</tbody>";

  // ─────────────────────────────────────────
  // Footer summary
  // ─────────────────────────────────────────
  const footer = `
  <tfoot>
    <tr>
      <td colspan="${cols.length}" style="text-align:left;padding-left:12px;padding-right:12px;display:flex;justify-content:space-between;align-items:center;gap:20px">
        <span>Columns: ${cols.length}</span>
        <span>Total: ${records.length} records</span>
      </td>
    </tr>
  </tfoot>
  `;

  // ─────────────────────────────────────────
  // Final HTML
  // ─────────────────────────────────────────
  const table = `
  <div class="large-dataset-context">
    ${escapeHTML(context)}
  </div>
  <div class="large-dataset-wrapper">
    <table class="large-dataset-table">
      ${head}
      ${body}
      ${footer}
    </table>
  </div>
  `;

  return table;
}

function formatLargeDatasetTable(largeDataData: any): string {
  let records = largeDataData.records || [];
  const context = largeDataData.context_summary || "";

  // Handle case where records might not be an array
  if (!Array.isArray(records)) {
    console.warn("⚠️ Large dataset records is not an array:", typeof records);
    records = [];
  }


  if (records.length === 0) {
    return `<div class="large-dataset-context"><strong>Summary:</strong> ${esc(context)}</div>`;
  }


  console.log(`✅ Formatting large dataset: ${records.length} records, context length: ${context.length}`);


  // ═══════════════════════════════════════════════════════════════════
  // DYNAMICALLY COLLECT ALL COLUMNS FROM RECORDS (EXCLUDING HIDDEN)
  // ═══════════════════════════════════════════════════════════════════


  const allKeys = new Set<string>();
  records.forEach((r: any) => {
    if (r && typeof r === 'object') {
      Object.keys(r).forEach(k => {
        // Skip hidden/sensitive columns
        if (!isHiddenColumn(k)) {
          allKeys.add(k);
        }
      });
    }
  });


  // Convert Set to array while preserving order
  const colsToShow: string[] = Array.from(allKeys);


  console.log(`📊 Dynamic columns detected: ${colsToShow.length} columns (hidden: ${records[0] ? Object.keys(records[0]).filter(k => isHiddenColumn(k)).length : 0}):`, colsToShow.slice(0, 10));


  // ═══════════════════════════════════════════════════════════════════
  // BUILD HTML TABLE STRUCTURE DYNAMICALLY - USING CSS CLASSES
  // ═══════════════════════════════════════════════════════════════════


  // 1. Create table header with ALL columns (excluding hidden)
  let tableHeadHTML = "<thead><tr>";
  colsToShow.forEach(col => {
    tableHeadHTML += `<th>${esc(col)}</th>`;
  });
  tableHeadHTML += "</tr></thead>";


  // 2. Create table body rows dynamically
  let tableBodyHTML = "<tbody>";
  records.forEach((record: any, rowIndex: number) => {
    if (!record || typeof record !== 'object') return;


    tableBodyHTML += `<tr>`;


    // Populate visible columns for each row (skip hidden columns)
    colsToShow.forEach(col => {
      const val = record[col];
      let cellContent = "—";


      if (val === null || val === undefined) {
        cellContent = "—";
      } else if (typeof val === "boolean") {
        cellContent = `<span style="font-weight:600;color:${val ? '#22c55e' : '#ef4444'};">${val ? '✓' : '✗'}</span>`;
      } else if (typeof val === "object") {
        const str = JSON.stringify(val);
        cellContent = esc(str.length > 50 ? str.substring(0, 50) + "…" : str);
      } else {
        const strVal = String(val);
        const displayVal = strVal.length > 100 ? strVal.substring(0, 100) + "…" : strVal;


        // Apply status badge styling for status-like columns
        if (isBadgeCol(col) && val) {
          cellContent = badge(strVal);
        } else {
          cellContent = esc(displayVal);
        }
      }


      tableBodyHTML += `<td>${cellContent}</td>`;
    });


    tableBodyHTML += "</tr>";
  });
  tableBodyHTML += "</tbody>";


  // 3. Create table footer with summary - ALIGN RIGHT
  const tfoot = `<tfoot><tr><td colspan="${colsToShow.length}" style="text-align: right; padding-right: 14px;">Total: ${records.length} record${records.length !== 1 ? "s" : ""} | ${colsToShow.length} column${colsToShow.length !== 1 ? "s" : ""}</td></tr></tfoot>`;


  // 4. Complete table HTML with CSS classes for styling
  const tableHTML = `<div class="large-dataset-wrapper">
    <table class="large-dataset-table">
      ${tableHeadHTML}
      ${tableBodyHTML}
      ${tfoot}
    </table>
  </div>`;


  // 5. Add context summary above table - JUST THE CONTEXT ONLY
  // const contextHTML = context 
  //   ? `<div class="large-dataset-context">${esc(context)}</div>` 
  const contextHTML = context
    ? `<div class="large-dataset-context">${esc(context)}</div>`
    : "";


  const fullHTML = contextHTML + tableHTML;
  console.log(` HTML generated - length: ${fullHTML.length}, has table-wrapper: ${fullHTML.includes('large-dataset-wrapper')}`);
  return fullHTML;
}

// ── Render plain bullet list ──────────────────────────────────────────────────
function renderBullets(lines: string[]): string {
  let html = '<ul style="margin:8px 0 8px 20px;padding:0;list-style:disc">';
  lines.forEach(l => {
    html += `<li style="margin:4px 0;line-height:1.6;color:#F3F4F6">${md(cleanLine(l))}</li>`;
  });
  return html + "</ul>";
}

// ── Render single KV record as a 2-col vertical table (Key | Value) ───────────
function renderKVVertical(pairs: { key: string; val: string }[]): string {
  const rows = pairs.map(({ key, val }) => {
    const cell = isBadgeCol(key) ? badge(val) : esc(val);
    return `<tr><th style="width:35%;text-align:left">${esc(key)}</th><td>${cell}</td></tr>`;
  });
  return `<div class="table-wrapper"><table class="ai-table"><tbody>${rows.join("")}</tbody></table></div>`;
}

// ── Parse one line as horizontal multi-KV: "Key: V, Key: V" → {K:V, K:V} ─────
function parseHorizKV(raw: string): Record<string, string> | null {
  const line = cleanLine(raw);
  if (!line) return null;
  const re = new RegExp(KV_BOUND_SRC, "g");
  const hits: { key: string; vs: number; rs: number }[] = [];
  let m: RegExpExecArray | null;
  while ((m = re.exec(line)) !== null) {
    const key = m[1].trim();
    if (!key || /\d/.test(key) || key.length < 2 || key.length > 30) continue;
    hits.push({ key, vs: m.index + m[0].length, rs: m.index });
  }
  if (hits.length < 2) return null;
  const result: Record<string, string> = {};
  for (let i = 0; i < hits.length; i++) {
    const end = i + 1 < hits.length ? hits[i + 1].rs : line.length;
    result[hits[i].key] = line.slice(hits[i].vs, end).replace(/,\s*$/, "").trim() || "—";
  }
  return Object.keys(result).length >= 2 ? result : null;
}

// ── Parse one line as single KV: "Key: value" → {key, val} ───────────────────
function parseSingleKV(raw: string): { key: string; val: string } | null {
  const line = cleanLine(raw);
  const m = KV_LINE_RE.exec(line);
  if (!m) return null;
  return { key: m[1].trim(), val: m[2].trim() };
}

// ── Parse plain KV blocks (blank-line-separated records) ─────────────────────
//    "Key: V\nKey: V\n\nKey: V\nKey: V" → [{K:V,K:V},{K:V,K:V}]
function parsePlainKVBlocks(lines: string[]): Record<string, string>[] | null {
  const records: Record<string, string>[] = [];
  let cur: Record<string, string> = {};

  const flush = () => {
    if (Object.keys(cur).length >= 1) { records.push(cur); cur = {}; }
  };

  for (const raw of lines) {
    const t = raw.trim();
    if (t === "") { flush(); continue; }
    const m = KV_LINE_RE.exec(cleanLine(t));
    // also try with bullet prefix stripped already applied by cleanLine
    const m2 = m ?? KV_LINE_RE.exec(t);
    if (m2) {
      cur[m2[1].trim()] = m2[2].trim();
    } else {
      return null; // non-KV line → abort, not a KV block
    }
  }
  flush();
  return records.length >= 1 ? records : null;
}

// ── Parse pipe table (with or without separator row) ─────────────────────────
function parsePipeTable(lines: string[]): { cols: string[]; rows: Record<string, string>[] } | null {
  const tl = lines.filter(l => /^\|.+\|$/.test(l.trim()));
  if (tl.length < 2) return null;

  const split = (l: string) =>
    l.split("|").map(c => c.trim()).filter((_, i, a) => i > 0 && i < a.length - 1);
  const isSep = (l: string) =>
    /^\|[\s\-:|]+\|$/.test(l.trim()) && split(l).every(c => /^[\-:\s]+$/.test(c));

  const hasSep = tl.length > 1 && isSep(tl[1]);
  const cols = split(tl[0]);
  const dataRows = (hasSep ? tl.slice(2) : tl.slice(1)).filter(l => !isSep(l));
  if (!dataRows.length) return null;

  const rows = dataRows.map(l => {
    const cells = split(l);
    const row: Record<string, string> = {};
    cols.forEach((c, idx) => { row[c] = cells[idx] ?? "—"; });
    return row;
  });
  return { cols, rows };
}

// ══════════════════════════════════════════════════════════════════════════════
//  MASTER formatOutput()
//
//  Decision logic:
//    Pipe table            → TABLE always
//    Horiz KV bullets      → TABLE (multi-row, 1 record per bullet line)
//    Vert KV bullets       → TABLE if ≥3 fields, else 2-col KV table
//    Plain KV blocks       → TABLE (multi-record), 2-col if 1 record < 3 keys
//    Pure bullets (no KV)  → BULLET LIST
//    Numbered list         → ORDERED LIST
//    Prose                 → paragraph
// ══════════════════════════════════════════════════════════════════════════════

// Remove emoji from text (especially from "Found X records..." message)
function removeEmoji(text: string): string {
  // Only remove emoji from the FIRST line (Found X records message)
  const lines = text.split("\n");
  if (lines.length > 0) {
    // Remove emoji from first line only
    const firstLine = lines[0].replace(/[\u{1F300}-\u{1F9FF}]|[\u{2600}-\u{27BF}]|[\u{1F600}-\u{1F64F}]|[\u{1F680}-\u{1F6FF}]/gu, '').trim();
    lines[0] = firstLine;
  }
  return lines.join("\n");
}

function formatOutput(text: string): string {
  if (!text.trim()) return "";

  // Remove emojis from the first line only (Found X records message)
  text = removeEmoji(text);


  const allLines = text.split("\n");
  let html = "";

  let i = 0;

  while (i < allLines.length) {
    const line = allLines[i];
    const trimmed = line.trim();

    // ── Blank line ─────────────────────────────────────────────────────────
    if (trimmed === "") {
      html += '<div style="height:6px"></div>';
      i++; continue;
    }

    // ── A: Pipe table | col | col | ────────────────────────────────────────
    // Also match col | col | col (without leading/trailing pipes) → convert to markdown table
    if (/^\|.+\|$/.test(trimmed) || /^[^|]*\|[^|]*\|/.test(trimmed)) {
      const block: string[] = [];
      while (i < allLines.length) {
        const t = allLines[i].trim();
        if (/^\|.+\|$/.test(t) || /^[^|]*\|[^|]*\|/.test(t)) {
          // Convert "col | col | col" to "| col | col | col |" format
          const normalized = t.startsWith('|') ? t : '| ' + t.split('|').map(c => c.trim()).join(' | ') + ' |';
          block.push(normalized);
          i++;
        } else {
          break;
        }
      }
      const parsed = parsePipeTable(block);
      html += parsed
        ? buildTable(parsed.rows, parsed.cols)
        : block.map(l => `<div>${md(l)}</div>`).join("");
      continue;
    }

    // ── B / C: Bullet or numbered block ────────────────────────────────────
    if (/^[\s]*(?:[-*•]|\d+[.)]) /.test(line)) {
      const block: string[] = [];
      while (
        i < allLines.length &&
        allLines[i].trim() !== "" &&
        /^[\s]*(?:[-*•]|\d+[.)]) /.test(allLines[i])
      ) { block.push(allLines[i]); i++; }

      // B: Horizontal KV per line: "• Key: V, Key: V" → each line = 1 table row
      const hRows = block.map(parseHorizKV).filter(Boolean) as Record<string, string>[];
      if (hRows.length > 0 && hRows.length >= Math.ceil(block.length * 0.5)) {
        html += buildTable(hRows);
        continue;
      }

      // C: Vertical KV: "• Key: V" lines together = fields of one record
      //    BUT if repeated keys found → multiple records
      const vPairs = block.map(parseSingleKV).filter(Boolean) as { key: string; val: string }[];
      const kvRatio = vPairs.length / block.length;

      if (vPairs.length >= 1 && kvRatio >= 0.6) {
        // Check if keys repeat → multiple records
        const keysSeen = new Set<string>();
        const multiRecords: Record<string, string>[] = [];
        let cur: Record<string, string> = {};
        for (const { key, val } of vPairs) {
          if (keysSeen.has(key)) {
            // Key repeated → flush current record, start new
            if (Object.keys(cur).length) multiRecords.push(cur);
            cur = {}; keysSeen.clear();
          }
          cur[key] = val;
          keysSeen.add(key);
        }
        if (Object.keys(cur).length) multiRecords.push(cur);

        if (multiRecords.length > 1) {
          // Multiple records → wide table
          html += buildTable(multiRecords);
        } else {
          // Single record: ≥3 fields → wide table; <3 → 2-col KV table
          const fields = Object.keys(multiRecords[0] ?? {}).length;
          html += fields >= 3
            ? buildTable(multiRecords)
            : renderKVVertical(vPairs);
        }
        continue;
      }

      // E: Pure bullet list (no KV)
      html += renderBullets(block);
      continue;
    }

    // ── D: Plain KV block (no bullet prefix) ───────────────────────────────
    //    "Asset Tag: X\nType: Fixed\n\nAsset Tag: Y\n..."
    if (KV_LINE_RE.test(cleanLine(trimmed))) {
      // Collect all lines until we hit something that is not KV and not blank
      const block: string[] = [];
      let j = i;
      while (j < allLines.length) {
        const t = allLines[j].trim();
        if (t === "") { block.push(allLines[j]); j++; continue; }
        if (KV_LINE_RE.test(cleanLine(t))) { block.push(allLines[j]); j++; continue; }
        break;
      }
      // Strip trailing blanks
      while (block.length && block[block.length - 1].trim() === "") block.pop();

      if (block.length >= 1) {
        const records = parsePlainKVBlocks(block);
        if (records && records.length >= 1) {
          if (records.length > 1) {
            // Multiple records → wide multi-row table
            html += buildTable(records);
          } else {
            // Single record: ≥3 keys → wide table, else 2-col KV table
            const keys = Object.keys(records[0]);
            html += keys.length >= 3
              ? buildTable(records)
              : renderKVVertical(keys.map(k => ({ key: k, val: records![0][k] })));
          }
          i = j; continue;
        }
      }
    }

    // ── Ordered list ───────────────────────────────────────────────────────
    if (/^\d+[.)]\s/.test(trimmed)) {
      let listHtml = '<ol style="margin:8px 0 8px 20px;padding:0;list-style:decimal">';
      while (i < allLines.length) {
        const oM = allLines[i].trim().match(/^\d+[.)]\s+(.*)/);
        if (!oM) break;
        listHtml += `<li style="margin:4px 0;line-height:1.6">${md(oM[1])}</li>`;
        i++;
      }
      html += listHtml + "</ol>"; continue;
    }

    // ── Heading # ## ### ───────────────────────────────────────────────────
    const headM = trimmed.match(/^(#{1,3})\s+(.*)/);
    if (headM) {
      const sz = ["20px", "17px", "15px"][headM[1].length - 1];
      const fw = headM[1].length === 1 ? "700" : "600";
      html += `<div style="font-size:${sz};font-weight:${fw};margin:12px 0 5px;background:linear-gradient(180deg, #AE8625 0%, #F7EF8A 35%, #D2AC47 65%, #EDC967 100%);background-size:200% 200%;-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent">${md(headM[2])}</div>`;
      i++; continue;
    }

    // ── Regular prose ──────────────────────────────────────────────────────
    html += `<div style="line-height:1.75;margin:2px 0;color:#F3F4F6">${md(trimmed)}</div>`;
    i++;
  }

  return html;
}

function decodeEntities(text: string): string {
  if (!text) return "";
  return text
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'");
}


// ─── Session ID ───────────────────────────────────────────────────────────────
function generateSessionId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function")
    return crypto.randomUUID();
  const b = new Uint8Array(16);
  crypto.getRandomValues(b);
  b[6] = (b[6]! & 0x0f) | 0x40;
  b[8] = (b[8]! & 0x3f) | 0x80;
  const h = [...b].map(x => x.toString(16).padStart(2, "0")).join("");
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
}

// ─── Static Data ─────────────────────────────────────────────────────────────
// Chat history will be implemented later

// ─── Icons ────────────────────────────────────────────────────────────────────

const IconPlus = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
    <path d="M12 5v14M5 12h14" />
  </svg>
);
const IconSearch = ({ style }: { style?: React.CSSProperties }) => (
  <svg
    width="14"
    height="14"
    viewBox="0 0 24 24"
    fill="none"
    stroke="#9CA3AF"
    strokeWidth="1.7"
    strokeLinecap="round"
    strokeLinejoin="round"
    style={style}
  >
    <circle cx="11" cy="11" r="5.5" />
    <line x1="15" y1="15" x2="20" y2="20" />
  </svg>
);
const IconHamburger = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
    <line x1="3" y1="6" x2="21" y2="6" />
    <line x1="3" y1="12" x2="21" y2="12" />
    <line x1="3" y1="18" x2="21" y2="18" />
  </svg>
);
const IconLogout = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
    <polyline points="16 17 21 12 16 7" /><line x1="21" y1="12" x2="9" y2="12" />
  </svg>
);
const IconUser1 = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" /><circle cx="12" cy="7" r="4" />
  </svg>
);
const IconChat = ({ width = 16, height = 16, style }: { width?: number; height?: number; style?: React.CSSProperties }) => (
  <svg width={width} height={height} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={style}>
    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
  </svg>
);
const IconArchive = ({ width = 16, height = 16, style }: { width?: number; height?: number; style?: React.CSSProperties }) => (
  <svg width={width} height={height} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={style}>
    <rect x="3" y="4" width="18" height="4" rx="1" /><path d="M5 8v10a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8" /><line x1="10" y1="12" x2="14" y2="12" />
  </svg>
);
const IconLibrary = ({ width = 16, height = 16, style }: { width?: number; height?: number; style?: React.CSSProperties }) => (
  <svg width={width} height={height} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={style}>
    <line x1="3" y1="6" x2="21" y2="6" /><line x1="3" y1="12" x2="21" y2="12" /><line x1="3" y1="18" x2="21" y2="18" />
  </svg>
);
const IconShare = ({ width = 16, height = 16, style }: { width?: number; height?: number; style?: React.CSSProperties }) => (
  <svg width={width} height={height} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={style}>
    <circle cx="18" cy="5" r="3" /><circle cx="6" cy="12" r="3" /><circle cx="18" cy="19" r="3" /><line x1="8.59" y1="13.51" x2="15.41" y2="17.49" /><line x1="15.41" y1="6.51" x2="8.59" y2="10.49" />
  </svg>
);

const IconPin = ({ size = 16, style }: { size?: number; style?: React.CSSProperties }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={style}>
    <path d="M12 17v5M9 17h6M15 13V4H9v9l-2 4h10l-2-4z" />
  </svg>
);

const IconCheckbox = ({ width = 16, height = 16, style }: { width?: number; height?: number; style?: React.CSSProperties }) => (
  <svg width={width} height={height} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={style}>
    <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
  </svg>
);
const IconWarning = ({ width = 14, height = 14, style }: { width?: number; height?: number; style?: React.CSSProperties }) => (
  <svg width={width} height={height} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={style}>
    <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z" /><line x1="12" y1="9" x2="12" y2="13" /><line x1="12" y1="17" x2="12.01" y2="17" />
  </svg>
);
const IconTheme = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 3v2M12 19v2M5.64 5.64l1.41 1.41M16.95 16.95l1.41 1.41M3 12h2M19 12h2M5.64 18.36l1.41-1.41M16.95 7.05l1.41-1.41" />
    <circle cx="12" cy="12" r="4" />
  </svg>
);
const IconAI = () => (
  <svg width="22" height="22" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <linearGradient id="aiGrad" x1="0" y1="0" x2="32" y2="32" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#f5c249" />
        <stop offset="50%" stopColor="#d4af37" />
        <stop offset="100%" stopColor="#b8941f" />
      </linearGradient>
      <radialGradient id="goldGlow" cx="50%" cy="50%">
        <stop offset="0%" stopColor="#f5c249" stopOpacity="0.8" />
        <stop offset="100%" stopColor="#d4af37" stopOpacity="0.3" />
      </radialGradient>
      <filter id="glow">
        <feGaussianBlur stdDeviation="2.5" result="coloredBlur" />
        <feMerge>
          <feMergeNode in="coloredBlur" />
          <feMergeNode in="SourceGraphic" />
        </feMerge>
      </filter>
    </defs>
    {/* Premium golden circle with glow */}
    <circle cx="16" cy="16" r="15" fill="url(#goldGlow)" opacity="0.4" />
    <circle cx="16" cy="16" r="14" fill="url(#aiGrad)" filter="url(#glow)" />
    {/* Plus icon filling the circle */}
    <line x1="16" y1="6" x2="16" y2="26" stroke="#FFFFFF" strokeWidth="3" strokeLinecap="round" />
    <line x1="6" y1="16" x2="26" y2="16" stroke="#FFFFFF" strokeWidth="3" strokeLinecap="round" />
  </svg>
);

// ─── Main Component ───────────────────────────────────────────────────────────
export const dynamic = "force-dynamic";

export default function Home() {
  const router = useRouter();
  // const searchParams  = useSearchParams();
  const responsive = useResponsive();  // Auto-detect screen size
  const [userIdFromUrl, setUserIdFromUrl] = useState<string | null>(null); // display name
  const [createGroupTrigger, setCreateGroupTrigger] = useState(0);
  const [userIdInt, setUserIdInt] = useState<number | null>(null); // integer user_id for filtering
  const [clientNameFromUrl, setClientNameFromUrl] = useState<string | null>(null); // backend username
  // `input` is the debounced value (used for heavier work).
  const [input, setInput] = useState<string>("");
  // Use a ref for immediate typing to avoid re-renders on each keystroke
  const rawInputRef = useRef<string>("");
  const inputDebounceRef = useRef<number | null>(null);
  const DEBOUNCE_MS = 400; // 300-500ms recommended
  const [messages, setMessages] = useState<Message[]>([]);
  const [activeMessageIdx, setActiveMessageIdx] = useState<number | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [sessionId, setSessionId] = useState<string>(() => generateSessionId());
  const [searchVal, setSearchVal] = useState("");
  const [isRecording, setIsRecording] = useState<boolean>(false);
  const [recordingTime, setRecordingTime] = useState(0);
  const [isLocked, setIsLocked] = useState(false);
  const [recordedAudioBlob, setRecordedAudioBlob] = useState<Blob | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackTime, setPlaybackTime] = useState(0);
  const [slideGestureActive, setSlideGestureActive] = useState(false);
  const [loggedInUser, setLoggedInUser] = useState<string | null>(null); // backend username (client_name)
  const [authChecked, setAuthChecked] = useState<boolean>(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [showUpgradePlan, setShowUpgradePlan] = useState(false);
  const [showManageAccount, setShowManageAccount] = useState(false);
  const [isManageAccountMenuOpen, setIsManageAccountMenuOpen] = useState(false);
  const [currentPlan, setCurrentPlan] = useState<string>("Free"); // Track active plan
  const [sidebarOpen, setSidebarOpen] = useState(true);  // Will be auto-closed by useEffect if mobile is detected
  const [wsConnectionState, setWsConnectionState] = useState<'connecting' | 'connected' | 'failed'>('connecting');
  const [isGraphMode, setIsGraphMode] = useState<boolean>(false);
  const [chartType, setChartType] = useState<ChartType>('vertical-bar');
  const [activeFeature, setActiveFeature] = useState<'chat' | 'archived' | 'library'>('chat');
  const [showFeaturePlaceholder, setShowFeaturePlaceholder] = useState<boolean>(false);
  const [chatSessions, setChatSessions] = useState<ChatSession[]>([]);
  const [searchTerm, setSearchTerm] = useState("");
  const [shareModalOpen, setShareModalOpen] = useState(false);
  const [shareLinkCopied, setShareLinkCopied] = useState(false);
  /* changes done by megnathan: Added share code states */
  const [shareCode, setShareCode] = useState<string | null>(null);
  const [isGeneratingCode, setIsGeneratingCode] = useState(false);
  const [importModalOpen, setImportModalOpen] = useState(false);
  const [inputShareCode, setInputShareCode] = useState("");
  const [isImporting, setIsImporting] = useState(false);
  /* changes done by megnathan: Track which session is actually being shared */
  const [sessionToShare, setSessionToShare] = useState<string | null>(null);
  /* changes done by megnathan: Added share code copy feedback state */
  const [shareCodeCopied, setShareCodeCopied] = useState(false);
  const [shareLink, setShareLink] = useState("");
  const [sessionMenuOpen, setSessionMenuOpen] = useState<string | null>(null);
  const [sessionMenuPos, setSessionMenuPos] = useState<{ top: number; left: number; placement?: 'above' | 'below'; buttonRectTop?: number; buttonRectBottom?: number } | null>(null);
  const sessionMenuRef = useRef<HTMLDivElement | null>(null);
  const [sessionMenuVisible, setSessionMenuVisible] = useState<boolean>(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [audioPlayingIndex, setAudioPlayingIndex] = useState<number | null>(null);

  // Inline edit state for renaming sessions
  const [editingSessionId, setEditingSessionId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState<string>("");
  const editingInputRef = useRef<HTMLInputElement | null>(null);
  const [groups, setGroups] = useState<Group[]>([]);
  const [selectedGroupName, setSelectedGroupName] = useState<string | null>(null);
  const [expandedGroups, setExpandedGroups] = useState<string[]>([]);
  const [groupActiveType, setGroupActiveType] = useState<'folder' | 'chat'>('folder');

  const handleCreateGroup = (name: string) => {
    const newGroup: Group = {
      id: Math.random().toString(36).substr(2, 9),
      name,
      description: "Custom group",
      chatCount: 0,
      updatedAt: new Date().toLocaleDateString()
    };
    setGroups(prev => [...prev, newGroup]);
    setSelectedGroupName(name);
    setMessages([]); // Clear messages for new group chat
    setSessionId(generateSessionId()); // New session for the group
  };
  // Archived sessions (store only id/title client-side)
  const [archivedSessions, setArchivedSessions] = useState<ChatSession[]>([]);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deleteSessionId, setDeleteSessionId] = useState<string | null>(null);
  const [deleteSessionTitle, setDeleteSessionTitle] = useState<string>("");
  const [isCreateGroupModalOpen, setIsCreateGroupModalOpen] = useState(false);
  const [newGroupName, setNewGroupName] = useState("");

  // Helper to toggle a global body class used for applying a full-page blur fallback
  const setGlobalBackdropBlur = (enable: boolean) => {
    if (typeof document === "undefined") return;
    try {
      if (enable) document.body.classList.add("modal-open-blur");
      else document.body.classList.remove("modal-open-blur");
    } catch (e) { /* ignore */ }
  };

  // Keep body class in sync with modal visibility (works across devices)
  useEffect(() => {
    setGlobalBackdropBlur(showDeleteModal);
    return () => { setGlobalBackdropBlur(false); };
  }, [showDeleteModal]);

  useEffect(() => {
    if (!showManageAccount) {
      setIsManageAccountMenuOpen(false);
    }
  }, [showManageAccount]);

  // Derive groups from chatSessions so they persist on refresh
  useEffect(() => {
    const uniqueGroupNames = Array.from(new Set(chatSessions.map(s => s.group_name).filter(Boolean)));

    setGroups(prev => {
      const merged = [...prev];
      uniqueGroupNames.forEach(name => {
        if (!merged.some(g => g.name === name)) {
          merged.push({
            id: name as string,
            name: name as string,
            description: "Custom group",
            chatCount: chatSessions.filter(s => s.group_name === name).length,
            updatedAt: new Date().toLocaleDateString()
          });
        }
      });
      return merged;
    });
  }, [chatSessions]);

  // Load archived sessions from localStorage on mount
  // useEffect(() => {
  //   try {
  //     const raw = localStorage.getItem('archivedSessions');
  //     if (raw) {
  //       const parsed = JSON.parse(raw) as ChatSession[];
  //       if (Array.isArray(parsed)) setArchivedSessions(parsed);
  //     }
  //   } catch (e) { /* ignore */ }
  // }, []);
  const [audioProgressMap, setAudioProgressMap] = useState<Record<number, number>>({});
  const [audioDurationMap, setAudioDurationMap] = useState<Record<number, number>>({});
  const audioDurationMapRef = useRef<Record<number, number>>({});
  const [loginPageClientLogoPath, setLoginPageClientLogoPath] = useState<string | null>(null);
  const [loginFooterLogoPath, setLoginFooterLogoPath] = useState<string | null>(null);

  // ─── Refs (declare early for use in hooks) ────────────────────────────────
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const {
    ghostUserSpanRef,
    ghostSuffixSpanRef,
    ghostSuffixStrRef,
    isComposingRef,
    clearGhostCompletion,
    syncGhostUserMirror,
    applyGhostSuffixFromInput,
  } = useGhostInputCompletion(
    messages,
    loggedInUser,
    rawInputRef,
    inputRef,
    isLoading,
    wsConnectionState,
  );
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const sessionIdRef = useRef<string>(sessionId);
  const wsConnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectDelayRef = useRef(2000);
  const sessionMessagesRef = useRef<Map<string, Message[]>>(new Map());
  const streamRef = useRef<MediaStream | null>(null);
  const recordingTimerRef = useRef<NodeJS.Timeout | null>(null);
  const audioPlaybackRef = useRef<HTMLAudioElement | null>(null);
  const recordingStartTimeRef = useRef<number>(0);
  const touchStartYRef = useRef<number>(0);
  const touchStartXRef = useRef<number>(0);
  const audioPlayersRef = useRef<Record<number, HTMLAudioElement>>({});
  const accRef = useRef<string>("");
  const pingRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const userActiveRef = useRef<boolean>(true);
  const idleTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ─── Voice Recorder Hook ──────────────────────────────────────────────────
  const voiceRecorder = useVoiceRecorder(
    isLoading,
    wsConnectionState,
    loggedInUser || "anonymous",
    userIdFromUrl ?? "",
    sessionId,
    wsRef,
    (duration: number, audioUrl: string) => {
      setIsGraphMode(false);
      setMessages(prev => {
        const updated = [...prev, {
          role: "user" as const,
          text: "Voice message",
          isAudio: true,
          audioDuration: duration,
          audioUrl: audioUrl
        }];
        sessionMessagesRef.current.set(sessionId, updated);
        return updated;
      });
      setIsLoading(true);
      accRef.current = "";
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  );

  // Sync sidebarOpen with responsive.isMobile - ensures sidebar closes on mobile detection
  useEffect(() => {
    if (responsive.isMobile) {
      setSidebarOpen(false);
    }
  }, [responsive.isMobile]);

  // Read userName and branding logos from URL (e.g. from autologin redirect); persist logos to localStorage
  useEffect(() => {
    if (typeof window !== "undefined") {
      const params = new URLSearchParams(window.location.search);
      // Legacy params removed — now using JWT token + cl/fl params

      // Read JWT token + plain logo params from URL
      const jwtToken = params.get("data");

      if (jwtToken) {
        const verifyJwt = async () => {
          try {
            console.log("[auth] verifying token");
            // Verify JWT via API route (keeps JWT_SECRET server-side only; not under /api/ so nginx can proxy /api to Python)
            const res = await fetch("/verify-token", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ token: jwtToken }),
            });

            const rawBody = await res.text();
            let parsed: Record<string, unknown> = {};
            try {
              parsed = JSON.parse(rawBody) as Record<string, unknown>;
            } catch {
              parsed = {};
            }
            if (!res.ok) {
              console.error("[home] JWT verify HTTP error", {
                status: res.status,
                statusText: res.statusText,
                body: rawBody.slice(0, 500),
              });
              throw new Error("Token verification failed");
            }

            const { userName, clientName, userId, cl, fl } = parsed as {
              userName?: string;
              clientName?: string;
              userId?: string;
              cl?: string;
              fl?: string;
            };

            console.log("[auth] token verified");

            if (userName) {
              setUserIdFromUrl(userName);
              localStorage.setItem("userName", userName);

            }
            if (clientName) {
              setClientNameFromUrl(clientName);
              localStorage.setItem("clientName", clientName);
              localStorage.setItem("loggedInUser", clientName);

            }
            if (userId) {
              setUserIdInt(parseInt(userId, 10));
              localStorage.setItem("userId", userId);

            }
            if (cl) {
              setLoginPageClientLogoPath(cl);
              localStorage.setItem("loginPageClientLogoPath", cl);

            }
            if (fl) {
              setLoginFooterLogoPath(fl);
              localStorage.setItem("loginFooterLogoPath", fl);

            }

            setTokenVerified(true); // ← ADD THIS LINE

          } catch (err) {
            console.error("[auth] verification failed — checking URL params or stored session");
            const urlUserName = params.get("userName");
            const urlClientName = params.get("clientName");
            const urlUserId = params.get("userId");

            const storedUserName = urlUserName || localStorage.getItem("userName");
            const storedClientName = urlClientName || localStorage.getItem("clientName") || localStorage.getItem("loggedInUser");
            const storedUserId = urlUserId || localStorage.getItem("userId");

            const storedLogoPath = localStorage.getItem("loginPageClientLogoPath");
            const storedFooterLogoPath = localStorage.getItem("loginFooterLogoPath");

            if (storedUserName) {
              setUserIdFromUrl(storedUserName);
              localStorage.setItem("userName", storedUserName);
            }
            if (storedClientName) {
              setClientNameFromUrl(storedClientName);
              localStorage.setItem("clientName", storedClientName);
              localStorage.setItem("loggedInUser", storedClientName);
              setLoggedInUser(storedClientName);
            }
            if (storedUserId) {
              setUserIdInt(parseInt(storedUserId, 10));
              localStorage.setItem("userId", storedUserId);
            }
            if (storedLogoPath) setLoginPageClientLogoPath(storedLogoPath);
            if (storedFooterLogoPath) setLoginFooterLogoPath(storedFooterLogoPath);

            setTokenVerified(true);
          }
        };
        verifyJwt();

      } else {
        // No token — Check for direct URL params first, then fallback to localStorage
        console.log("[auth] checking URL params or stored session");
        const urlUserName = params.get("userName");
        const urlClientName = params.get("clientName");
        const urlUserId = params.get("userId");

        const storedUserName = urlUserName || localStorage.getItem("userName");
        const storedClientName = urlClientName || localStorage.getItem("clientName") || localStorage.getItem("loggedInUser");
        const storedUserId = urlUserId || localStorage.getItem("userId");

        const storedLogoPath = localStorage.getItem("loginPageClientLogoPath");
        const storedFooterLogoPath = localStorage.getItem("loginFooterLogoPath");

        if (storedUserName) {
          setUserIdFromUrl(storedUserName);
          localStorage.setItem("userName", storedUserName);
        }
        if (storedClientName) {
          setClientNameFromUrl(storedClientName);
          localStorage.setItem("clientName", storedClientName);
          localStorage.setItem("loggedInUser", storedClientName);
          setLoggedInUser(storedClientName); // Ensure state is updated immediately
        }
        if (storedUserId) {
          setUserIdInt(parseInt(storedUserId, 10));
          localStorage.setItem("userId", storedUserId);
        }
        if (storedLogoPath) setLoginPageClientLogoPath(storedLogoPath);
        if (storedFooterLogoPath) setLoginFooterLogoPath(storedFooterLogoPath);

        setAuthChecked(true); // Signal that auth check is done
      }
    }
  }, [setLoggedInUser, setAuthChecked]);

  // Mobile viewport height fix (handles dynamic browser chrome on iOS/Android)
  useEffect(() => {
    const setVh = () => {
      document.documentElement.style.setProperty("--vh", `${window.innerHeight * 0.01}px`);
    };
    if (typeof window !== "undefined") {
      setVh();
      window.addEventListener("resize", setVh);
    }
    return () => window.removeEventListener("resize", setVh);
  }, []);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  // Update sidebar visibility based on screen size
  useEffect(() => {
    // Don't change sidebar if a modal is open
    if (showManageAccount || showUpgradePlan) {
      return;
    }

    if (responsive.isDesktop) {
      // Always show sidebar on desktop
      setSidebarOpen(true);
    } else if (responsive.isMobile) {
      // Close sidebar on mobile (user can open with menu button)
      setSidebarOpen(false);
    }
  }, [responsive.isDesktop, responsive.isMobile, showManageAccount, showUpgradePlan]);

  // Add this state at top of component with other states:
  const [tokenVerified, setTokenVerified] = useState(false);

  // Auth guard
  useEffect(() => {
    if (typeof window === "undefined") return;

    const params = new URLSearchParams(window.location.search);
    const hasToken = !!params.get("data");

    // Wait for JWT verification to finish before checking auth
    if (hasToken && !tokenVerified) return;

    // 1. Check for shared session FIRST
    const sharedSid = params.get("sharedSessionId");
    const owner = params.get("owner");
    if (sharedSid) {
      const fetchShared = async () => {
        try {
          const url = `${baseUrl}/api/share/history?sessionId=${sharedSid}${owner ? `&owner=${owner}` : ""}`;
          const res = await fetch(url);
          const data = await res.json();
          if (data.status === "ok") {
            // Map DB fields (query/assistant) to UI fields (role/text)
            const mappedHistory = (data.history || []).flatMap((m: any) => [
              { role: "user", text: m.query || "" },
              {
                role: "ai", text: typeof m.assistant === "string" && m.assistant.startsWith("{")
                  ? JSON.parse(m.assistant).response || m.assistant
                  : m.assistant || ""
              }
            ]);
            setSessionId(sharedSid);
            setMessages(processLoadedMessages(mappedHistory));
            console.log("[share] shared chat loaded and mapped");
            setAuthChecked(true);
          }
        } catch (e) {
          console.error("Failed to load shared session:", e);
        }
      };
      fetchShared();
      return; // Stop here if it's a shared session link
    }

    const backendUserName = clientNameFromUrl || localStorage.getItem("clientName") || localStorage.getItem("loggedInUser");

    if (backendUserName) {
      localStorage.setItem("loggedInUser", backendUserName);
      setLoggedInUser(backendUserName);
      setAuthChecked(true);

      if (window.location.search) {
        router.replace("/");
      }
      return;
    }

    const stored = localStorage.getItem("loggedInUser");
    setLoggedInUser(stored);
    setAuthChecked(true);
  }, [router, clientNameFromUrl, tokenVerified]);

  // Keep sessionIdRef in sync with state
  useEffect(() => {
    sessionIdRef.current = sessionId;
  }, [sessionId]);

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, isLoading]);

  // Handle body overflow when upgrade plan modal opens/closes
  useEffect(() => {
    if (showUpgradePlan) {
      document.body.classList.add('upgrade-plan-open');
      // Close sidebar on mobile/tablet when modal opens
      if (responsive.isMobile || responsive.isTablet) {
        setSidebarOpen(false);
      }
    } else {
      document.body.classList.remove('upgrade-plan-open');
    }
    return () => {
      document.body.classList.remove('upgrade-plan-open');
    };
  }, [showUpgradePlan, responsive.isMobile, responsive.isTablet]);

  // Handle sidebar close when manage account modal opens
  useEffect(() => {
    if (showManageAccount) {
      setSidebarOpen(false);
    }
  }, [showManageAccount]);

  // Handle body overflow when manage account modal opens/closes
  useEffect(() => {
    if (showManageAccount) {
      document.body.classList.add('manage-account-open');
      // Close sidebar when manage account modal opens
      setSidebarOpen(false);
    } else {
      document.body.classList.remove('manage-account-open');
    }
    return () => {
      document.body.classList.remove('manage-account-open');
    };
  }, [showManageAccount]);

  // Auto-resize textarea
  const resizeTA = () => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "0px";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
    el.style.overflowY = el.scrollHeight > 160 ? "auto" : "hidden";
  };
  // Auto-resize is called from the onChange handler (direct DOM measurement)

  // ── Persistent WebSocket: connect once on mount, stay open all session ───────
  const IDLE_TIMEOUT = 2 * 60 * 1000;  // 2 minutes
  const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;

  if (!baseUrl) {
    throw new Error("NEXT_PUBLIC_API_BASE_URL is not defined");
  }

  const getWsUrl = () => {
    const wsBase = baseUrl
      .replace(/^http:/, "ws:")
      .replace(/^https:/, "wss:") + "/api/chat";
    const params = new URLSearchParams(window.location.search);
    const owner = params.get("owner");
    // Priority: URL userName > URL owner > Logged In User > anonymous
    const user = userIdFromUrl ?? owner ?? loggedInUser ?? "anonymous";
    return `${wsBase}?sessionId=${sessionId}&userName=${user}`;
  };
  // const getWsUrl = () =>
  //   process.env.NEXT_PUBLIC_API_BASE_URL
  //     .replace(/^http:/,  "ws:")
  //     .replace(/^https:/, "wss:") + "/api/chat";

  // ── Start pinging only the ACTIVE session socket ──────────────────────────
  const connectWSRef = useRef<() => void>(() => { });  // forward ref for connectWS

  const startPing = () => {
    // Clear any previous ping interval
    if (pingRef.current) { clearInterval(pingRef.current); pingRef.current = null; }

    pingRef.current = setInterval(() => {
      const ws = wsRef.current;
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send("ping");
      }
    }, 30_000);
  };
  const stripHtml = (html: string) => {
    const temp = document.createElement("div");
    temp.innerHTML = html;
    return temp.textContent || "";
  };

  // ── Convert base64 audio to blob URL for immediate use ─────────────────────
  const base64ToAudioUrl = (base64String: string): string => {
    try {
      if (!base64String || !base64String.startsWith("data:audio/")) {
        return base64String;
      }
      // Extract base64 data part
      const base64Data = base64String.split(",")[1];
      if (!base64Data) return base64String;

      // Convert to binary and create blob
      const binaryString = atob(base64Data);
      const bytes = new Uint8Array(binaryString.length);
      for (let i = 0; i < binaryString.length; i++) {
        bytes[i] = binaryString.charCodeAt(i);
      }
      const blob = new Blob([bytes], { type: "audio/ogg" });
      return URL.createObjectURL(blob);
    } catch (error) {
      console.warn("Failed to convert base64 to audio URL:", error);
      return base64String;
    }
  };

  // ── Save chat history to backend (PostgreSQL) ───────────────────────────────
  const saveChatHistory = async (sid: string, msgs: Message[]) => {
    const valid = msgs.filter(m => m.role !== "error");
    if (valid.length === 0) return;
    try {
      await fetch(`${baseUrl}/api/session`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          userName: userIdFromUrl ?? loggedInUser,
          sessionId: sid,
          group_name: selectedGroupName,
          chatHistory: valid.map(m => ({
            role: m.role,
            text: m.isAudio
              ? (m.audioUrl || m.text)
              : m.role === "ai"
                ? (m.originalText || stripHtml(m.text))  // ← Use original raw response if available, fallback to stripHtml
                : m.text,
            isAudio: m.isAudio ?? false,
          })),
        }),
      });
    } catch (err) {
      console.warn("Failed to save chat history:", err);
    }
  };

  const saveChatHistoryRef = useRef(saveChatHistory);
  useEffect(() => { saveChatHistoryRef.current = saveChatHistory; });

  // Start inline rename flow for a session (shows input in-place)
  const handleRenameSession = async (sid: string) => {
    const existing = chatSessions.find(s => s.id === sid);
    const currentTitle = existing?.title ?? "";
    setEditingSessionId(sid);
    setEditingTitle(currentTitle);
    setSessionMenuOpen(null);
    setSessionMenuPos(null);
    // focus will be set via effect when input is rendered
  };

  // Compute smart menu position so the popup appears inside viewport and chooses above/below placement
  const computeSessionMenuPos = (btn: HTMLElement, menuMinWidth = 140) => {
    const rect = btn.getBoundingClientRect();
    const viewportW = window.innerWidth;
    const viewportH = window.innerHeight;
    const spaceBelow = viewportH - rect.bottom;
    const spaceAbove = rect.top;
    // prefer below unless not enough space and above has more room
    const placement: 'above' | 'below' = (spaceBelow < 220 && spaceAbove > spaceBelow) ? 'above' : 'below';
    // keep left inside viewport, leave 12px padding
    const left = Math.max(8, Math.min(rect.left, viewportW - menuMinWidth - 12));
    const top = rect.bottom + 6; // initial top is below; we'll flip to above after measuring menu height if needed
    return { top, left, placement, buttonRectTop: rect.top, buttonRectBottom: rect.bottom };
  };

  // After menu mounts, measure its height and flip placement if it would overflow.
  useLayoutEffect(() => {
    if (!sessionMenuOpen || !sessionMenuPos || !sessionMenuRef.current) return;
    const menuEl = sessionMenuRef.current;
    const menuH = menuEl.offsetHeight;
    const viewportH = window.innerHeight;
    const btnBottom = sessionMenuPos.buttonRectBottom ?? (sessionMenuPos.top || 0);
    const btnTop = sessionMenuPos.buttonRectTop ?? (sessionMenuPos.top || 0);

    // If not enough space below and more space above, flip
    if (sessionMenuPos.placement !== 'above' && (btnBottom + menuH) > viewportH && btnTop > (viewportH - btnBottom)) {
      // place above
      setSessionMenuPos(pos => pos ? { ...pos, placement: 'above', top: (pos.buttonRectTop ?? btnTop) - 6 } : pos);
      return;
    }

    // If placement was above but now not enough space above, ensure below
    if (sessionMenuPos.placement === 'above' && ((btnTop - menuH) < 0)) {
      setSessionMenuPos(pos => pos ? { ...pos, placement: 'below', top: (pos.buttonRectBottom ?? btnBottom) + 6 } : pos);
      return;
    }
  }, [sessionMenuOpen, sessionMenuPos]);

  // When placement is finalized, reveal the menu (avoid flicker)
  useEffect(() => {
    if (!sessionMenuOpen) {
      setSessionMenuVisible(false);
      return;
    }
    // Small async tick to ensure layout effect ran and sessionMenuPos updated
    const t = setTimeout(() => setSessionMenuVisible(true), 0);
    return () => clearTimeout(t);
  }, [sessionMenuOpen, sessionMenuPos]);

  // Close session menu when clicking/tapping outside or pressing Escape
  useEffect(() => {
    if (!sessionMenuOpen) return;
    const onOutside = (e: Event) => {
      const tgt = e.target as Node;
      if (sessionMenuRef.current && sessionMenuRef.current.contains(tgt)) return;
      // clicked outside menu -> close
      setSessionMenuOpen(null);
      setSessionMenuPos(null);
      setSessionMenuVisible(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setSessionMenuOpen(null);
        setSessionMenuPos(null);
        setSessionMenuVisible(false);
      }
    };
    document.addEventListener('mousedown', onOutside);
    document.addEventListener('touchstart', onOutside);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onOutside);
      document.removeEventListener('touchstart', onOutside);
      document.removeEventListener('keydown', onKey);
    };
  }, [sessionMenuOpen]);

  // Archive a session title (client-side only). Do NOT move chat history in DB.
  // const handleArchiveSession = (sid: string) => {
  //   const existing = chatSessions.find(s => s.id === sid);
  //   if (!existing) return;
  //   // Add minimal record to archivedSessions
  //   setArchivedSessions(prev => {
  //     const next = [...prev.filter(a => a.id !== sid), { id: existing.id, title: existing.title, createdAt: existing.createdAt }];
  //     try { localStorage.setItem('archivedSessions', JSON.stringify(next)); } catch (e) { /* ignore */ }
  //     return next;
  //   });
  //   // Remove from visible active list (history), but do not delete messages in DB
  //   setChatSessions(prev => prev.filter(s => s.id !== sid));
  //   setSessionMenuOpen(null);
  //   setSessionMenuPos(null);
  // };

  // Commit inline rename (optimistic update + backend request)
  const commitRename = async (sid: string) => {
    const trimmed = editingTitle.trim();
    if (!trimmed) {
      setEditingSessionId(null);
      setEditingTitle("");
      return;
    }
    // optimistic UI update
    setChatSessions(prev => prev.map(s => s.id === sid ? { ...s, title: trimmed } : s));
    setEditingSessionId(null);
    try {
      await fetch(`${baseUrl}/api/session/rename`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ userName: userIdFromUrl ?? loggedInUser, sessionId: sid, title: trimmed }),
      });
    } catch (err) {
      console.warn("Failed to update session title on server:", err);
    } finally {
      setEditingTitle("");
    }
  };

  // Open delete confirmation modal for a session
  const handleDeleteSession = async (sid: string) => {
    const existing = chatSessions.find(s => s.id === sid);
    setDeleteSessionId(sid);
    setDeleteSessionTitle(existing?.title ?? "Chat");
    setSessionMenuOpen(null);
    setSessionMenuPos(null);
    setShowDeleteModal(true);
  };

  // Perform deletion after confirmation (optimistic + backend)
  const performDeleteSession = async () => {
    const sid = deleteSessionId;
    if (!sid) {
      setShowDeleteModal(false);
      return;
    }
    // optimistic UI update
    setChatSessions(prev => prev.filter(s => s.id !== sid));
    sessionMessagesRef.current.delete(sid);
    // If we're viewing the deleted session, switch to a new chat
    if (sessionIdRef.current === sid) {
      const newSid = generateSessionId();
      setSessionId(newSid);
      sessionIdRef.current = newSid;
      setMessages([]);
    }
    setShowDeleteModal(false);
    setDeleteSessionId(null);
    setDeleteSessionTitle("");

    try {
      await fetch(`${baseUrl}/api/session/delete`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ userName: userIdFromUrl ?? loggedInUser, sessionId: sid }),
      });
    } catch (err) {
      console.warn("Failed to delete session on server:", err);
    }
  };

  const handlePinSession = async (sid: string, isPinned: boolean) => {
    try {
      const res = await fetch(`${baseUrl}/api/sessions/pin`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sessionId: sid,
          userName: userIdFromUrl ?? loggedInUser,
          isPinned: isPinned
        }),
      });
      if (res.ok) {
        setChatSessions(prev => {
          const updated = prev.map(s => s.id === sid ? { ...s, isPinned } : s);
          return sortSessionsNewestFirst(updated);
        });
      }
    } catch (e) {
      console.error("Failed to pin session:", e);
    }
  };
  const handleArchiveSession = async (sid: string, isArchived: boolean) => {
    try {
      const res = await fetch(`${baseUrl}/api/sessions/archive`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sessionId: sid,
          userName: userIdFromUrl ?? loggedInUser,
          isArchived: isArchived
        }),
      });
      if (res.ok) {
        setChatSessions(prev => {
          const updated = prev.map(s => s.id === sid ? { ...s, isArchived } : s);
          return updated;
        });
      }
    } catch (e) {
      console.error("Failed to archive session:", e);
    }
  };

  /* changes done by megnathan: Instant modal opening to remove lag */
  const [isSharing, setIsSharing] = useState(false);
  const handleShareSession = async (sid: string) => {
    setSessionToShare(sid);
    setShareCode(null);
    setShareLink("");
    setShareModalOpen(true); // Open modal immediately
    setIsSharing(true);      // Show loading inside modal

    try {
      // 1. Force save the current history to DB first
      const currentMsgs = sessionMessagesRef.current.get(sid) || messages;
      if (currentMsgs.length > 0) {
        await saveChatHistory(sid, currentMsgs);
      }

      // 2. Now mark it as public
      const res = await fetch(`${baseUrl}/api/sessions/share`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sessionId: sid,
          userName: userIdFromUrl ?? loggedInUser,
          isPublic: true
        }),
      });
      if (res.ok) {
        const link = `${window.location.origin}${window.location.pathname}?sharedSessionId=${sid}&owner=${userIdFromUrl ?? loggedInUser}`;
        setShareLink(link);
      }
    } catch (e) {
      console.error("Failed to share session:", e);
    } finally {
      setIsSharing(false);
    }
  };

  /* changes done by megnathan: Added share code generation handler (fixed username mismatch) */
  /* changes done by megnathan: Use target session ID for code generation */
  const handleGenerateShareCode = async () => {
    const sid = sessionToShare || sessionId;
    if (!sid) return;
    setIsGeneratingCode(true);

    const actualUserName = userIdFromUrl ?? localStorage.getItem("userName") ?? loggedInUser;

    try {
      const res = await fetch(`${baseUrl}/api/sessions/generate-share-code`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sessionId: sid,
          userName: actualUserName
        }),
      });
      const data = await res.json();
      if (data.status === "ok") {
        setShareCode(data.shareCode);
      } else {
        console.error("Server error generating code:", data.detail);
        alert("Could not generate code: " + (data.detail || "Unknown error"));
      }
    } catch (e) {
      console.error("Failed to generate share code:", e);
    } finally {
      setIsGeneratingCode(false);
    }
  };

  /* changes done by megnathan: Added import by code handler (improved error logging) */
  const handleImportByCode = async () => {
    if (!inputShareCode || inputShareCode.length !== 5) {
      alert("Please enter a valid 5-digit code.");
      return;
    }
    setIsImporting(true);
    const actualUserName = userIdFromUrl ?? localStorage.getItem("userName") ?? loggedInUser;

    console.log(`[Import] Starting import for code: ${inputShareCode} | User: ${actualUserName}`);

    try {
      const res = await fetch(`${baseUrl}/api/sessions/import-by-code`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          shareCode: inputShareCode,
          userName: actualUserName
        }),
      });
      const data = await res.json();

      if (data.status === "ok") {
        console.log(`[Import] Success! New Session ID: ${data.newSessionId}`);
        setImportModalOpen(false);
        setInputShareCode("");

        try {
          console.log("[Import] Refreshing session list...");
          await fetchSessions();

          console.log(`[Import] Selecting new session: ${data.newSessionId}`);
          switchSession(data.newSessionId);
          console.log("[Import] Session selection triggered.");
        } catch (innerError: any) {
          console.error("[Import] Error during list refresh/selection:", innerError);
          alert("Import was successful, but failed to load the new chat automatically. Please refresh the page.");
        }
      } else {
        console.warn("[Import] Server returned error:", data.detail);
        alert(data.detail || "Invalid code or import failed.");
      }
    } catch (e: any) {
      console.error("[Import] Fatal error during fetch:", e);
      alert(`An error occurred during import: ${e.message || "Unknown error"}`);
    } finally {
      setIsImporting(false);
    }
  };

  // ── User activity detection ───────────────────────────────────────────────
  const markUserActive = () => {
    userActiveRef.current = true;

    // Reset idle timer
    if (idleTimerRef.current) clearTimeout(idleTimerRef.current);
    idleTimerRef.current = setTimeout(() => {
      userActiveRef.current = false;
      // Save current session to backend before going idle (keep WebSocket alive)
      const idleSid = sessionIdRef.current;
      const idleMsgs = sessionMessagesRef.current.get(idleSid);
      if (idleMsgs && idleMsgs.filter(m => m.role !== "error").length > 0) {
        saveChatHistoryRef.current(idleSid, idleMsgs);
      }
      console.log("💤 User idle — saved session, keeping WebSocket connection open");
    }, IDLE_TIMEOUT);
  };

  useEffect(() => {
    const events = ["mousemove", "mousedown", "keydown", "scroll", "touchstart"] as const;
    events.forEach(e => window.addEventListener(e, markUserActive));
    // Start initial idle timer
    markUserActive();
    return () => {
      events.forEach(e => window.removeEventListener(e, markUserActive));
      if (idleTimerRef.current) clearTimeout(idleTimerRef.current);
    };
  }, []);

  const WS_CONNECT_TIMEOUT_MS = 15000; // 15s: fail fast in production if proxy/backend is slow

  const connectWS = () => {
    // If there's already an open or connecting socket, reuse it
    if (wsRef.current && (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING)) {
      return;
    }

    setWsConnectionState('connecting');
    const ws = new WebSocket(getWsUrl());
    wsRef.current = ws;

    wsConnectTimeoutRef.current = setTimeout(() => {
      if (ws.readyState === WebSocket.CONNECTING) {
        ws.close();
        setWsConnectionState('failed');
        console.warn("⚠️ WebSocket connection timeout");
      }
      wsConnectTimeoutRef.current = null;
    }, WS_CONNECT_TIMEOUT_MS);

    ws.onopen = () => {
      if (wsConnectTimeoutRef.current) {
        clearTimeout(wsConnectTimeoutRef.current);
        wsConnectTimeoutRef.current = null;
      }
      reconnectDelayRef.current = 2000;
      setWsConnectionState('connected');
      console.log("✅ WebSocket connected");
      startPing();
    };

    // ── Every message from backend ────────────────────────────────────────
    ws.onmessage = (event: MessageEvent) => {
      try {
        const raw = typeof event.data === "string" ? event.data : "";

        // Ignore pong heartbeat responses
        if (raw.trim() === "pong") return;

        const jsonStr = raw.startsWith("data: ") ? raw.slice(6) : raw;

        // "[DONE]" = end of this response → finalize bubble, stay connected
        if (jsonStr.trim() === "[DONE]" || jsonStr.trim() === "__END__") {
          const finalText = accRef.current;
          let processedText = finalText;
          let isGraphResponse = false;
          let tableData: TableWithTileRow[] | undefined = undefined;
          let tableTitle: string | undefined = undefined;

          // 🔑 FIRST: Check if this is a GRAPH response (type="graph")
          const cleanedForGraph = extractResponseContent(finalText);
          const graphData = parseGraphData(cleanedForGraph);
          if (graphData) {
            console.log("📊 [DONE] Graph response detected — will render as bar chart");
            processedText = cleanedForGraph // ← Keep raw JSON for parseGraphData() in render
            isGraphResponse = true;
          } else {
            // Not a graph → continue with normal processing
            // 🔑 SECOND: Extract response content (removes session_id wrapper)
            const cleanedText = extractResponseContent(finalText);

            // 🔑 THIRD: ALWAYS TRY RENDERING AS TABLE STRUCTURE FIRST (ALL SIZES, NO LIMITS)
            const largeDatasetHTML = renderLargeDataset(cleanedText);

            if (largeDatasetHTML) {
              // Successfully rendered as unified table structure (any size)
              processedText = largeDatasetHTML;
              // Always extract table rows for TableWithTile component
              const rows = extractTableRows(largeDatasetHTML);
              if (rows.length > 0) {
                tableData = rows;
                tableTitle = "Data";
                console.log("✅ [DONE] Rendered as unified table structure (" + rows.length + " rows)");
              }
            } else {
              // Not tabular data → format as text output only
              try {
                processedText = formatOutput(cleanedText);
                console.log("📝 [DONE] Formatted as text");
              } catch (err) {
                console.log("📝 [DONE] Using raw text", err);
                processedText = finalText;
              }
            }
          }

          setMessages(prev => {
            const u = [...prev];
            const l = u.length - 1;
            if (u[l]?.role === "ai") {
              u[l] = {
                role: "ai",
                text: processedText,
                streaming: false,
                isGraphResponse: isGraphResponse,  // ← Set graph flag
                chartType: chartType,              // ← Store chart type
                originalText: finalText,           // ← Store original raw response before HTML processing
                tableData: tableData,              // ← Store table rows
                tableTitle: tableTitle              // ← Store table title
              };
            }
            // Persist to per-session store so switching sessions keeps history
            const activeSid = sessionIdRef.current;
            sessionMessagesRef.current.set(activeSid, u);
            return u;
          });
          accRef.current = "";          // reset for next message
          setIsLoading(false);
          setTimeout(() => inputRef.current?.focus(), 50);
          return;
        }

        const part = jsonStr;
        if (part) {
          accRef.current += part;
          const snap = accRef.current;


          // Extract text for display during streaming
          let displayText = snap;
          try {
            displayText = extractText(JSON.parse(snap));
          } catch {
            // If can't parse yet (incomplete JSON), show what we have
            displayText = snap;
          }


          setMessages(prev => {
            const u = [...prev];
            const l = u.length - 1;
            // If last message is already our streaming AI bubble → update it
            if (u[l]?.role === "ai" && u[l]?.streaming === true) {
              u[l] = { ...u[l], text: displayText, streaming: true };  // ← Preserve chartType
            } else {
              // First chunk → create the AI bubble now (only once) with current chartType
              u.push({ role: "ai", text: displayText, streaming: true, chartType: chartType });
            }
            return u;
          });
        }
      } catch { /* non-JSON frame — ignore */ }
    };

    ws.onclose = (event) => {
      if (wsConnectTimeoutRef.current) {
        clearTimeout(wsConnectTimeoutRef.current);
        wsConnectTimeoutRef.current = null;
      }
      // Only react if this is the active socket
      if (wsRef.current === ws) {
        wsRef.current = null;
        setWsConnectionState('failed');
        console.warn("⚠️ WebSocket closed");
        if (pingRef.current) { clearInterval(pingRef.current); pingRef.current = null; }
        setIsLoading(false);
        if (!event.wasClean && userActiveRef.current) {
          const delay = reconnectDelayRef.current;
          reconnectDelayRef.current = Math.min(15000, delay * 2);
          setTimeout(() => connectWS(), delay);
        }
      }
    };

    ws.onerror = () => {
      if (wsConnectTimeoutRef.current) {
        clearTimeout(wsConnectTimeoutRef.current);
        wsConnectTimeoutRef.current = null;
      }
      setWsConnectionState('failed');
      // Log connection error to console only — do not surface as chat bubble
      console.error("❌ WebSocket error — connection failed, will retry");
      setIsLoading(false);
    };
  };

  // Keep ref in sync so markUserActive can call connectWS
  useEffect(() => { connectWSRef.current = connectWS; });

  // Connect when component mounts (after auth is confirmed)
  useEffect(() => {
    const sharedSid = new URLSearchParams(window.location.search).get("sharedSessionId");
    if (!authChecked || (!loggedInUser && !sharedSid)) return;

    connectWS();

    return () => {
      if (pingRef.current) { clearInterval(pingRef.current); pingRef.current = null; }
      if (idleTimerRef.current) { clearTimeout(idleTimerRef.current); idleTimerRef.current = null; }
      if (wsConnectTimeoutRef.current) { clearTimeout(wsConnectTimeoutRef.current); wsConnectTimeoutRef.current = null; }
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [authChecked, loggedInUser]);

  // Helper: sort sessions newest-first (by updatedAt or createdAt)
  const sortSessionsNewestFirst = (list: ChatSession[]): ChatSession[] =>
    [...list].sort((a, b) => {
      if (a.isPinned && !b.isPinned) return -1;
      if (!a.isPinned && b.isPinned) return 1;
      return (b.updatedAt ?? b.createdAt) - (a.updatedAt ?? a.createdAt);
    });

  // Fetch chat sessions list for sidebar (new at top, old at bottom)
  /* changes done by megnathan: Moved fetchSessions outside to make it accessible */
  const fetchSessions = async () => {
    if (!authChecked || !loggedInUser) return;
    try {
      const res = await fetch(`${baseUrl}/api/session`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ userName: userIdFromUrl ?? loggedInUser, historyOnClick: false }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const fetched: ChatSession[] = (data?.sessions ?? []).map(
        (s: { session_id: string; title?: string; created_at?: string; updated_at?: string; is_pinned?: boolean; is_archived?: boolean; group_name?: string }) => ({
          id: s.session_id,
          title: s.title || "Chat",
          createdAt: s.created_at ? new Date(s.created_at).getTime() : Date.now(),
          updatedAt: s.updated_at ? new Date(s.updated_at).getTime() : undefined,
          isPinned: s.is_pinned || false,
          isArchived: s.is_archived || false,
          group_name: s.group_name,
        })
      );
      setChatSessions(sortSessionsNewestFirst(fetched));

      // Derive groups at the same time as sessions — no extra render cycle
      const uniqueGroupNames = Array.from(new Set(fetched.map(s => s.group_name).filter(Boolean))) as string[];
      if (uniqueGroupNames.length > 0) {
        setGroups(uniqueGroupNames.map(name => ({
          id: name,
          name,
          description: "Custom group",
          chatCount: fetched.filter(s => s.group_name === name).length,
          updatedAt: new Date().toLocaleDateString(),
        })));
      }
    } catch (err) {
      console.warn("Failed to fetch chat sessions:", err);
      setChatSessions([]);
    }
  };

  useEffect(() => {
    fetchSessions();
  }, [authChecked, loggedInUser]);

  const handleFeatureClick = (featureName: 'chat' | 'archived' | 'library') => {
    // Chat and Archived have real views implemented; only Library shows placeholder
    if (featureName === 'chat') {
      setShowFeaturePlaceholder(false);
      return;
    }
    setShowFeaturePlaceholder(true);
  };

  const handleNewChat = async () => {
    if (isLoading) {
      setMessages(prev => [...prev, { role: "error", text: "Please wait for the current response to finish before starting a new chat." }]);
      return;
    }
    // Persist current session messages to ref before leaving
    const previousSid = sessionId; // chat we're leaving (may have been typed in, so keep it near top after refetch)
    sessionMessagesRef.current.set(previousSid, messages);

    setShowFeaturePlaceholder(false);
    setMessages([]);
    accRef.current = "";
    setIsLoading(false);

    const newSessionId = generateSessionId();
    setSessionId(newSessionId);
    sessionIdRef.current = newSessionId;

    // Auto-close sidebar on mobile
    if (responsive.isMobile) {
      setSidebarOpen(false);
    }

    // Immediately show this new chat at the top of the history list
    setChatSessions(prev => {
      const existing = prev.filter(s => s.id !== newSessionId);
      const newCapsule: ChatSession = {
        id: newSessionId,
        title: "New Chat",
        createdAt: Date.now(),
        updatedAt: Date.now(),
      };
      return [newCapsule, ...existing];
    });

    // Refetch session list; new chat at top, previous chat (just left) second, rest by updated_at
    const refetchSessions = async () => {
      try {
        const res = await fetch(`${baseUrl}/api/session`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ userName: userIdFromUrl ?? loggedInUser, historyOnClick: false }),
        });
        if (!res.ok) return;
        const data = await res.json();
        const fetched: ChatSession[] = (data?.sessions ?? []).map(
          (s: { session_id: string; title?: string; created_at?: string; updated_at?: string; is_pinned?: boolean; is_archived?: boolean; group_name?: string }) => ({
            id: s.session_id,
            title: s.title || "Chat",
            createdAt: s.created_at ? new Date(s.created_at).getTime() : Date.now(),
            updatedAt: s.updated_at ? new Date(s.updated_at).getTime() : undefined,
            isPinned: s.is_pinned || false,
            isArchived: s.is_archived || false,
            group_name: s.group_name,
          })
        );
        setChatSessions(prev => {
          const newCapsule: ChatSession = {
            id: newSessionId,
            title: "New Chat",
            createdAt: Date.now(),
            updatedAt: Date.now(),
          };
          // Previous chat stays second (just left, not yet saved so backend may have old order)
          const previousSession = prev.find(s => s.id === previousSid) ?? fetched.find(s => s.id === previousSid);
          const rest = sortSessionsNewestFirst(
            fetched.filter(s => s.id !== newSessionId && s.id !== previousSid)
          );
          if (previousSession) {
            const fromApi = fetched.find(s => s.id === previousSid);
            const title = fromApi?.title ?? previousSession.title;
            return [newCapsule, { ...previousSession, title }, ...rest];
          }
          return [newCapsule, ...rest];
        });

        // Re-derive groups so new group chats appear immediately
        const uniqueGroupNames = Array.from(new Set(fetched.map(s => s.group_name).filter(Boolean))) as string[];
        if (uniqueGroupNames.length > 0) {
          setGroups(uniqueGroupNames.map(name => ({
            id: name,
            name,
            description: "Custom group",
            chatCount: fetched.filter(s => s.group_name === name).length,
            updatedAt: new Date().toLocaleDateString(),
          })));
        }
      } catch (err) {
        console.warn("Failed to refetch sessions:", err);
      }
    };
    setTimeout(() => refetchSessions(), 400);
  };



  // ── Process loaded messages: convert raw JSON to formatted tables ─────────
  function processLoadedMessages(msgs: Message[]): Message[] {
    return msgs.map(m => {
      if (m.role !== "ai") return m;

      const text = m.text || "";

      // 🔑 FIRST: Check if this is a GRAPH response
      const graphData = parseGraphData(text);
      if (graphData) {
        console.log("📊 [HISTORY] Graph response detected — keeping as raw JSON for chart");
        return { ...m, text, originalText: text, isGraphResponse: true };
      }

      // 🔑 Detect if the history text is a Table JSON (records/data/columns key)
      try {
        if (text.trim().startsWith('{') || text.trim().startsWith('[')) {
          const parsed = JSON.parse(text);
          if (parsed && (parsed.columns || parsed.data || parsed.records || parsed.p_list)) {
            const tableHTML = renderLargeDataset(text);
            if (tableHTML) {
              const rows = extractTableRows(tableHTML);
              // ✅ Set originalText = raw JSON so future saves preserve it
              return { ...m, text: tableHTML, originalText: text, tableData: rows, tableTitle: "Results" };
            }
          }
        }
      } catch (e) {
        /* Not JSON, ignore */
      }

      // Check if already formatted HTML (contains table tags)
      if (
        text.includes('<table') ||
        text.includes('large-dataset-wrapper') ||
        text.includes('ai-table')
      ) {
        console.log("✅ [HISTORY] Message already HTML formatted - extracting table data");
        const rows = extractTableRows(text);
        if (rows.length > 0) {
          // ✅ originalText stays as the HTML — no raw JSON available here
          return { ...m, text, originalText: text, tableData: rows, tableTitle: "Results" };
        }
        return { ...m, originalText: text };
      }

      // Extract response content (removes session_id wrapper)
      const rawJson = extractResponseContent(text);
      const cleanedText = decodeEntities(rawJson);

      // ALWAYS TRY RENDERING AS UNIFIED TABLE STRUCTURE FIRST (ALL SIZES)
      const tableHTML = renderLargeDataset(cleanedText);
      if (tableHTML) {
        console.log("✅ [HISTORY] Successfully rendered as table structure");
        const rows = extractTableRows(tableHTML);
        if (rows.length > 0) {
          // ✅ originalText = raw text from DB so future saves re-parse correctly
          return { ...m, text: tableHTML, originalText: text, tableData: rows, tableTitle: "Results" };
        }
        return { ...m, text: tableHTML, originalText: text };
      }

      // Not tabular data → try to format as text
      try {
        const formattedText = formatOutput(cleanedText);
        // Check if formatOutput produced an HTML table
        const rows = extractTableRows(formattedText);
        if (rows.length > 0) {
          return { ...m, text: formattedText, originalText: text, tableData: rows, tableTitle: "Results" };
        }
        // If the formatted text has raw HTML tags, decode them
        if (formattedText.includes('<div') || formattedText.includes('&lt;')) {
          return { ...m, text: decodeEntities(formattedText), originalText: text };
        }
        return { ...m, text: formattedText, originalText: text };
      } catch (err) {
        console.log("📝 [HISTORY] Fallback to raw text");
        return { ...m, text: decodeEntities(text), originalText: text };
      }
    });
  };

  // ── Switch to an existing session ─────────────────────────────────────────
  const switchSession = async (targetSid: string) => {
    if (targetSid === sessionId) return; // already active
    if (isLoading) {
      setMessages(prev => [...prev, { role: "error", text: "Please wait for the current response to finish before switching chats." }]);
      return;
    }

    // Auto-close sidebar on mobile
    if (responsive.isMobile) {
      setSidebarOpen(false);
    }

    // Capture the currently active session ID
    const currentSid = sessionIdRef.current;

    // Save current messages
    sessionMessagesRef.current.set(currentSid, messages);

    // Update selected group name based on the target session
    const targetSession = chatSessions.find(s => s.id === targetSid);
    if (targetSession && targetSession.group_name) {
      setSelectedGroupName(targetSession.group_name);
    } else {
      setSelectedGroupName(null);
    }

    // Refresh from backend to get latest titles; do not move clicked chat to top (just highlight)
    const refreshSessions = async () => {
      if (!loggedInUser) return;
      try {
        const res = await fetch(`${baseUrl}/api/session`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ userName: userIdFromUrl ?? loggedInUser, historyOnClick: false }),
        });
        if (!res.ok) return;
        const data = await res.json();
        const fetched: ChatSession[] = (data?.sessions ?? []).map(
          (s: { session_id: string; title?: string; created_at?: string; updated_at?: string; group_name?: string; is_pinned?: boolean; is_archived?: boolean }) => ({
            id: s.session_id,
            title: s.title || "Chat",
            createdAt: s.created_at ? new Date(s.created_at).getTime() : Date.now(),
            updatedAt: s.updated_at ? new Date(s.updated_at).getTime() : undefined,
            isPinned: s.is_pinned || false,
            isArchived: s.is_archived || false,
            group_name: s.group_name,
          })
        );
        setChatSessions(prev => {
          const merged = sortSessionsNewestFirst(fetched);
          // If current list has a session not in fetched (e.g. new unsaved), prepend it
          const onlyInPrev = prev.filter(s => !fetched.some(f => f.id === s.id));
          return sortSessionsNewestFirst([...onlyInPrev, ...merged]);
        });
      } catch (err) {
        console.warn("Failed to refresh sessions:", err);
      }
    };
    refreshSessions();

    // Switch session ID immediately
    setSessionId(targetSid);
    sessionIdRef.current = targetSid;
    accRef.current = "";
    setIsLoading(false);

    // Check local cache first
    const cached = sessionMessagesRef.current.get(targetSid);
    if (cached && cached.length > 0) {
      const processed = processLoadedMessages(cached);
      setMessages(processed);
    } else {
      // Fetch from backend
      setHistoryLoading(true);
      setMessages([]);
      try {
        const res = await fetch(`${baseUrl}/api/session`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ userName: userIdFromUrl ?? loggedInUser, sessionId: targetSid, historyOnClick: true }),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        const history: Message[] = [];
        //handles is_audio from backend
        for (const entry of (data?.chat_history ?? [])) {
          if (entry.query) {
            if (entry.is_audio) {
              // query is base64 audio string from DB
              history.push({
                role: "user",
                text: "Voice message",
                isAudio: true,
                audioUrl: entry.query,   // base64 → audio player
                audioDuration: 0         // duration not stored in DB
              });
            } else {
              history.push({ role: "user", text: entry.query });
            }
          }
          if (entry.assistant) {
            history.push({ role: "ai", text: entry.assistant });
          }
        }
        const processed = processLoadedMessages(history);
        sessionMessagesRef.current.set(targetSid, processed);
        setMessages(processed);
      } catch (err) {
        console.warn("Failed to fetch session history:", err);
        setMessages([]);
      } finally {
        setHistoryLoading(false);
      }
    }

    // Ensure WebSocket connection is available for the target session
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      connectWS();
    } else {
      startPing();
    }
  };

  const handleLogout = async () => {
    const savePromises: Promise<void>[] = [];
    sessionMessagesRef.current.forEach((msgs, sid) => {
      const valid = msgs.filter(m => m.role !== "error");
      if (valid.length > 0) {
        savePromises.push(saveChatHistoryRef.current(sid, msgs));
      }
    });

    try {
      await Promise.all(savePromises);
      console.log("✅ All sessions saved before logout");
    } catch {
      console.warn("⚠️ Some sessions failed to save on logout");
    }

    if (pingRef.current) { clearInterval(pingRef.current); pingRef.current = null; }
    if (idleTimerRef.current) { clearTimeout(idleTimerRef.current); idleTimerRef.current = null; }
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    localStorage.removeItem("loggedInUser");
    router.replace("/");
  };
  const toggleRecording = async () => {
    if (isRecording) {
      mediaRecorderRef.current?.stop();
      setIsRecording(false);
    } else {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        const rec = new MediaRecorder(stream);
        rec.start();
        mediaRecorderRef.current = rec;
        setIsRecording(true);
      } catch { alert("Please allow microphone access."); }
    }
  };

  // ── Handle Audio Playback ─────────────────────────────────────────────────
  const handleAudioPlayback = async (idx: number, audioUrl?: string, passedDuration: number = 0) => {
    if (!audioUrl) return;

    const isCurrentlyPlaying = audioPlayingIndex === idx;

    if (isCurrentlyPlaying) {
      const audio = audioPlayersRef.current[idx];
      if (audio) {
        audio.pause();
        setAudioPlayingIndex(null);
      }
      return;
    }

    // Pause any other playing audio
    if (audioPlayingIndex !== null) {
      const otherAudio = audioPlayersRef.current[audioPlayingIndex];
      if (otherAudio) otherAudio.pause();
      setAudioPlayingIndex(null);
    }

    // Create audio element if not yet created for this index
    if (!audioPlayersRef.current[idx]) {
      let playUrl = audioUrl;
      if (audioUrl.startsWith("data:")) {
        const res = await fetch(audioUrl);
        const blob = await res.blob();
        playUrl = URL.createObjectURL(blob);
      }
      const audio = new Audio(playUrl);
      let animationFrameId: number | null = null;

      // ── FIX BUG 1: load real duration from the audio element itself ──────
      audio.addEventListener("loadedmetadata", () => {
        if (isFinite(audio.duration) && audio.duration > 0) {
          audioDurationMapRef.current[idx] = audio.duration;
          setAudioDurationMap(prev => ({ ...prev, [idx]: audio.duration }));
        } else if (passedDuration > 0) {
          setAudioDurationMap(prev => ({ ...prev, [idx]: passedDuration }));
        }
      });

      // ── FIX BUG 3: rAF loop for smooth progress ──────────────────────────
      const progressLoop = () => {
        const a = audioPlayersRef.current[idx];
        if (!a || a.paused) return;
        const dur = audioDurationMapRef.current[idx] ?? passedDuration;
        if (dur > 0) {
          const pct = (a.currentTime / dur) * 100;
          setAudioProgressMap(prev => ({ ...prev, [idx]: pct }));
        }
        animationFrameId = requestAnimationFrame(progressLoop);
      };

      audio.onplay = () => {
        setAudioPlayingIndex(idx);
        if (animationFrameId !== null) cancelAnimationFrame(animationFrameId);
        animationFrameId = requestAnimationFrame(progressLoop);
      };

      audio.onpause = () => {
        if (animationFrameId !== null) {
          cancelAnimationFrame(animationFrameId);
          animationFrameId = null;
        }
        setAudioPlayingIndex(null);
      };

      audio.onended = () => {
        if (animationFrameId !== null) {
          cancelAnimationFrame(animationFrameId);
          animationFrameId = null;
        }
        setAudioPlayingIndex(null);
        setAudioProgressMap(prev => ({ ...prev, [idx]: 0 }));
      };

      audioPlayersRef.current[idx] = audio;
    }

    // Trigger load so loadedmetadata fires (needed for old-session base64 URLs)
    const audioElement = audioPlayersRef.current[idx];
    if (audioElement) {
      audioElement.play().catch(err => {
        console.error("❌ Audio play failed:", err.message);
        setAudioPlayingIndex(null);
      });
    }
  };

  // ── Send message over the persistent WebSocket ────────────────────────────
  const sendMessage = () => {
    const domVal = inputRef.current?.value ?? "";
    if (!domVal.trim() || isLoading) return;
    clearGhostCompletion();
    const userText = domVal.trim();

    const ws = wsRef.current;

    if (!ws || ws.readyState !== WebSocket.OPEN) {
      console.warn("Socket not ready for session:", sessionId);
      setMessages(prev => [...prev, { role: "error", text: "Still connecting. Please wait." }]);
      return;
    }

    recordPromptForGhostHistory(ghostPromptHistoryStorageKey(loggedInUser), userText);

    // Ensure capsule exists and move this session to top when user types (content changed)
    const now = Date.now();
    setChatSessions(prev => {
      const existing = prev.find(s => s.id === sessionId);
      const rest = prev.filter(s => s.id !== sessionId);
      if (existing) {
        return [{ ...existing, updatedAt: now }, ...rest];
      }
      const newCapsule: ChatSession = {
        id: sessionId,
        title: "New Chat",
        createdAt: now,
        updatedAt: now,
      };
      return [newCapsule, ...rest];
    });

    setShowFeaturePlaceholder(false);
    setMessages(prev => {
      const updated = [...prev, {
        role: "user" as const,
        text: userText
      }];
      // Save to per-session store
      sessionMessagesRef.current.set(sessionId, updated);
      return updated;
    });
    // Clear textarea DOM value and debounced state
    if (inputRef.current) inputRef.current.value = "";
    rawInputRef.current = "";
    setInput("");
    syncGhostUserMirror();
    setIsLoading(true);
    accRef.current = "";

    ws.send(JSON.stringify({
      type: "message",
      messageType: "text",
      isAudio: false,
      isText: true,
      isGraph: isGraphMode,
      query: userText,
      userName: loggedInUser,
      subUserName: userIdFromUrl ?? loggedInUser,
      userId: userIdInt !== null ? String(userIdInt) : undefined,
      sessionId,
      group_name: selectedGroupName,
      timestamp: Date.now()
    }));

    setIsLoading(true);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Tab" && ghostSuffixStrRef.current) {
      e.preventDefault();
      const ta = e.currentTarget;
      const ghost = ghostSuffixStrRef.current;
      ta.value = ta.value + ghost;
      rawInputRef.current = ta.value;
      ghostSuffixStrRef.current = "";
      if (ghostSuffixSpanRef.current) ghostSuffixSpanRef.current.textContent = "";
      resizeTA();
      syncGhostUserMirror();
      if (inputDebounceRef.current) {
        window.clearTimeout(inputDebounceRef.current);
        inputDebounceRef.current = null;
      }
      setInput(ta.value);
      applyGhostSuffixFromInput();
      return;
    }
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  };

  const { theme } = useTheme();
  const isLanding = messages.length === 0;

  // Mobile/tablet header is hidden while sidebar/menu is open, or when modals are active.
  const isMobileHeaderVisible = responsive.isMobile && !sidebarOpen && !showUpgradePlan && !showManageAccount;

  /** Chat input + disclaimer; `landing` = centered column on empty state before first message */
  const renderChatInputFooter = (variant: "landing" | "default") => {
    const isGuestOnShared = !loggedInUser && typeof window !== "undefined" && !!new URLSearchParams(window.location.search).get("sharedSessionId");

    return (
      <div
        className={
          variant === "landing" ? "input-footer input-footer--start" : "input-footer"
        }
      >
        {voiceRecorder.isRecording && (
          <div className={`voice-recording-overlay${voiceRecorder.closingRecording ? " closing" : ""}`}>
            <RecordingInterface
              recordingTime={voiceRecorder.recordingTime}
              onCancel={voiceRecorder.cancelRecording}
              formatTime={voiceRecorder.formatTime}
            />
          </div>
        )}

        {voiceRecorder.recordedAudioBlob ? (
          <VoicePreviewBar
            isPlaying={voiceRecorder.isPlaying}
            playbackTime={voiceRecorder.playbackTime}
            totalDuration={voiceRecorder.totalDuration}
            displayTimeText={voiceRecorder.displayTimeText}
            onTogglePlayback={voiceRecorder.togglePlayback}
            onDelete={voiceRecorder.deleteRecording}
            onSend={voiceRecorder.sendVoiceMessage}
            isLoading={isLoading}
            wsConnectionState={wsConnectionState}
          />
        ) : (
          <div className="input-wrapper" style={{ position: 'relative' }}>
            {/* changes done by megnathan: Added blur overlay and restriction message for guests on shared chats */}
            {isGuestOnShared && (
              <div style={{
                position: 'absolute',
                inset: 0,
                background: 'rgba(0, 0, 0, 0.45)',
                backdropFilter: 'blur(8px)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                zIndex: 100,
                borderRadius: 10,
                padding: '0 16px',
                textAlign: 'center'
              }}>
                <span style={{
                  color: '#fff',
                  fontSize: responsive.isMobile ? '11px' : '13px',
                  fontWeight: 500,
                  lineHeight: 1.4,
                  textShadow: '0 1px 2px rgba(0,0,0,0.5)'
                }}>
                  Please login through SmartFM to continue the chat for having the real-time data updates regarding the facility management.
                </span>
              </div>
            )}
            {/* changes done by megnathan: Used correct CSS classes for perfect Ghost Text alignment */}
            <div className="main-input-stack">
              <div className="main-input-ghost-mirror">
                <span ref={ghostUserSpanRef} className="ghost-mirror-user"></span>
                <span ref={ghostSuffixSpanRef} className="ghost-mirror-suffix"></span>
              </div>
              <textarea
                ref={inputRef}
                className="main-input"
                defaultValue={input}
                onCompositionStart={() => { isComposingRef.current = true; }}
                onCompositionEnd={(e) => {
                  isComposingRef.current = false;
                  syncGhostUserMirror();
                  applyGhostSuffixFromInput();
                }}
                onChange={(e) => {
                  // Update ref immediately (no re-render)
                  rawInputRef.current = e.target.value;
                  // Resize based on DOM measurements
                  resizeTA();
                  syncGhostUserMirror();
                  applyGhostSuffixFromInput();

                  // Debounce updating the heavier `input` state
                  if (inputDebounceRef.current) {
                    clearTimeout(inputDebounceRef.current);
                    inputDebounceRef.current = null;
                  }
                  inputDebounceRef.current = window.setTimeout(() => {
                    setInput(rawInputRef.current);
                    inputDebounceRef.current = null;
                  }, DEBOUNCE_MS);
                }}
                onKeyDown={handleKeyDown}
                disabled={isLoading || wsConnectionState !== "connected" || isGuestOnShared}
                placeholder={
                  isGuestOnShared ? "" : (wsConnectionState === "connected" ? "Ask Anything..." : "Waiting for connection…")
                }
                rows={1}
              />
            </div>
            <VoiceMicButton
              forwardedRef={voiceRecorder.micButtonRef}
              onClick={voiceRecorder.toggleRecording}
              disabled={
                isLoading ||
                wsConnectionState !== "connected" ||
                voiceRecorder.recordedAudioBlob !== null ||
                isGuestOnShared
              }
            />
            <button
              onClick={() => setIsGraphMode((p) => !p)}
              title={isGraphMode ? "Graph mode ON — click to turn off" : "Click for graph output"}
              style={{
                background: isGraphMode
                  ? "linear-gradient(135deg, #d4af37, #f5c249)"
                  : "transparent",
                border: isGraphMode
                  ? "1px solid #d4af37"
                  : "1px solid rgba(255,255,255,0.15)",
                borderRadius: 8,
                padding: "6px 8px",
                cursor: "pointer",
                color: isGraphMode ? "#000" : "#9CA3AF",
                transition: "all 0.2s ease",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <IconChartBar size={18} stroke={1.5} />
            </button>
            <button
              className="send-btn"
              onClick={sendMessage}
              disabled={isLoading || wsConnectionState !== "connected" || !(inputRef.current?.value ?? "").trim() || isGuestOnShared}
            >
              <IconArrowUp size={16} color="white" stroke={2} />
            </button>
          </div>
        )}
        {variant === "landing" && (
          <LandingSuggestedQueries
            onSelect={(q) => {
              if (inputDebounceRef.current) { clearTimeout(inputDebounceRef.current); inputDebounceRef.current = null; }
              if (inputRef.current) {
                inputRef.current.value = q;
              }
              rawInputRef.current = q;
              setInput(q);
              requestAnimationFrame(() => inputRef.current?.focus());
            }}
            disabled={
              isLoading ||
              wsConnectionState !== "connected" ||
              voiceRecorder.isRecording ||
              !!voiceRecorder.recordedAudioBlob
            }
          />
        )}
        <p className="footer-disclaimer">
        </p>
      </div>
    );
  };

  if (!authChecked) {
    return (
      <div
        style={{
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "linear-gradient(135deg, #0A0A0A 0%, #111111 50%, #0A0A0A 100%)",
        }}
      >
        <div style={{ textAlign: "center" }}>
          <svg width="120" height="60" viewBox="0 0 100 50">
            <path
              d="M 50 25 C 30 5 10 5 10 25 C 10 45 30 45 50 25 C 70 5 90 5 90 25 C 90 45 70 45 50 25 Z"
              fill="none"
              stroke="#2A2A2A"
              strokeWidth="6"
              strokeLinecap="round"
            />
            <path
              d="M 50 25 C 30 5 10 5 10 25 C 10 45 30 45 50 25 C 70 5 90 5 90 25 C 90 45 70 45 50 25 Z"
              fill="none"
              stroke="url(#infinity-gradient)"
              strokeWidth="6"
              strokeLinecap="round"
              pathLength="100"
              strokeDasharray="30 70"
              strokeDashoffset="100"
              style={{
                animation: "infinity-dash 1.5s linear infinite",
                willChange: "stroke-dashoffset",
                transform: "translateZ(0)"
              }}
            />
            <defs>
              <linearGradient id="infinity-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="#D4AF37" />
                <stop offset="100%" stopColor="#FFFF00" />
              </linearGradient>
            </defs>
          </svg>
          <style>{`
            @keyframes infinity-dash {
              from {
                stroke-dashoffset: 100;
              }
              to {
                stroke-dashoffset: 0;
              }
            }
          `}</style>
        </div>
      </div>
    );
  }

  return (
    <div className="app-container app-container-with-bg">
      <BackgroundLayer theme={theme} />
      {/* Content above background (MainLayout-style) */}
      <div
        className={
          !historyLoading && isLanding && (activeFeature === 'chat' || activeFeature === 'library')
            ? "app-content-wrapper app-content-wrapper--landing-start"
            : "app-content-wrapper"
        }
      >
        {/* ── Sidebar ─────────────────────────────────────────────────────── */}
        <div
          className="sidebar-shell"
          style={{
            display: sidebarOpen ? 'flex' : 'none',
            position: responsive.isMobile && sidebarOpen ? 'fixed' : 'relative',
            top: 0,
            left: 0,
            zIndex: responsive.isMobile && sidebarOpen ? 9999 : 2,
            filter: (importModalOpen || shareModalOpen) ? 'blur(5px)' : 'none',
          }}
        >
          <aside className="sidebar">
            {/* Sidebar Header with Logo */}
            <div className="sidebar-header">

              <div style={{ display: "flex", alignItems: "center", flex: 1 }}>
                <div
                  className="brand-box"
                  style={loginPageClientLogoPath ? { width: "100%", maxWidth: 220, height: "auto", minHeight: 56, maxHeight: 72, padding: 0, border: "none", borderRadius: 0 } : undefined}
                >
                  {loginPageClientLogoPath ? (
                    <img
                      src={loginPageClientLogoPath}
                      alt="Client logo"
                      style={{ width: "100%", maxWidth: 220, height: "auto", maxHeight: 72, objectFit: "contain", display: "block" }}
                    />
                  ) : (
                    <Image src="/icon.png" alt="Nanosoft Ask AI" width={20} height={20} style={{ borderRadius: 0 }} />
                  )}
                </div>
              </div>
              {/* Close button on mobile */}
              {responsive.isMobile && !showManageAccount && !showUpgradePlan && (
                <button
                  className="sidebar-close-btn"
                  onClick={() => setSidebarOpen(false)}
                  title="Close sidebar"
                  aria-label="Close sidebar"
                  style={{
                    background: 'transparent',
                    border: 'none',
                    color: 'var(--color-text)',
                    cursor: 'pointer',
                    padding: '8px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    transition: 'all 0.2s ease',
                  }}
                >
                  <IconX size={24} />
                </button>
              )}
              <div className="hamburger-wrapper" ref={menuRef}>
                <button
                  className="hamburger-btn"
                  onClick={() => setMenuOpen((p) => !p)}
                  title="Profile menu"
                  aria-label="Open profile menu"
                >
                  <IconHamburger />
                </button>
                <div className={`profile-dropdown ${menuOpen ? "open" : ""}`}>
                  <div className="profile-dropdown-inner">
                    <div className="profile-dropdown-item profile-user-row">
                      <div className="profile-avatar">
                        <IconUser />
                      </div>
                      <div className="profile-user-info">
                        {/* Display original userName (if available) while backend uses client_name */}
                        <span className="profile-userid">{userIdFromUrl ?? loggedInUser}</span>
                      </div>
                    </div>
                    <div className="profile-divider" />
                    <div className="profile-dropdown-item profile-action-btn">
                      <ThemeToggle />
                    </div>
                    <div className="profile-divider" />
                    <button
                      className="profile-dropdown-item profile-action-btn"
                      onClick={() => {
                        setShowUpgradePlan(true);
                        setMenuOpen(false);
                        setSidebarOpen(false);
                      }}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '10px',
                        color: '#d4af37',
                        fontWeight: 600,
                      }}
                    >
                      <IconCrown size={18} />
                      <span>Upgrade Plan</span>
                    </button>
                    <div className="profile-divider" />
                    <button
                      className="profile-dropdown-item profile-action-btn"
                      onClick={() => {
                        setShowManageAccount(true);
                        setMenuOpen(false);
                        setSidebarOpen(false);
                      }}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '10px',
                        color: 'var(--color-primary)',
                        fontWeight: 600,
                      }}
                    >
                      <IconUser size={18} />
                      <span>Manage Account</span>
                    </button>

                  </div>
                </div>
              </div>

              {/* <button className="sidebar-hamburger-btn" onClick={() => setMenuOpen(p => !p)} title="Menu" aria-label="Open menu">
            <IconHamburger/>
          </button> */}

            </div>
            {/* <div className={`sidebar-profile-card ${menuOpen ? "open" : ""}`} ref={menuRef}> */}



            {/* </div> */}

            {/* + New Chat Button */}
            <div className="new-chat-container-top" style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              <button className="new-chat-btn" onClick={handleNewChat} style={{ flex: 1 }}>
                <IconChat width={16} height={16} />
                <span>+ New Chat</span>
              </button>

              {/* changes done by megnathan: Added import via code menu button */}
              <button
                className="new-chat-btn"
                onClick={() => setImportModalOpen(true)}
                title="Import chat via code"
                style={{ width: '40px', padding: '10px 0', justifyContent: 'center' }}
              >
                <span style={{ fontSize: '18px', fontWeight: 'bold' }}>...</span>
              </button>
            </div>

            {/* FEATURES + Chat History Section */}
            <div className="sidebar-scroll">
              {/* FEATURES */}
              <div className="section-title">FEATURES</div>
              <div
                className={`feature-item ${activeFeature === 'chat' ? 'active' : ''}`}
                onClick={() => {
                  setActiveFeature('chat');
                  handleFeatureClick('chat');
                  setSelectedGroupName(null);
                  handleNewChat();
                }}
              >
                <IconChat />
                <span>Chat</span>
              </div>
              <div
                className={`feature-item ${activeFeature === 'archived' ? 'active' : ''}`}
                onClick={() => {
                  setActiveFeature('archived');
                  handleFeatureClick('archived');
                  setSelectedGroupName(null);
                  setMessages([]); // Clear messages to show landing container
                }}
              >
                <IconArchive />
                <span>Archived</span>
              </div>
              <div
                className={`feature-item ${activeFeature === 'library' ? 'active' : ''}`}
                onClick={() => {
                  setActiveFeature('library');
                  handleFeatureClick('library');
                }}
              >
                <IconLibrary />
                <span style={{ flex: 1 }}>Groups</span>
                <button
                  title="Create group"
                  onClick={(e) => { e.stopPropagation(); setCreateGroupTrigger(prev => prev + 1); }}
                  style={{
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    padding: '0 4px',
                    color: 'var(--color-text-secondary)',
                    display: 'flex',
                    alignItems: 'center',
                    borderRadius: '4px',
                    transition: 'color 0.15s',
                    fontSize: '18px',
                    lineHeight: 1,
                    fontWeight: 300,
                  }}
                  onMouseEnter={(e) => ((e.currentTarget as HTMLElement).style.color = 'var(--color-accent, #c8932a)')}
                  onMouseLeave={(e) => ((e.currentTarget as HTMLElement).style.color = 'var(--color-text-secondary)')}
                >+</button>
              </div>

              {activeFeature === 'library' && groups.map(group => (
                <div key={group.id}>
                  <div
                    className="sidebar-sub-item"
                    style={{
                      padding: '6px 12px',
                      paddingLeft: '36px',
                      fontSize: '13px',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      color: selectedGroupName === group.name && groupActiveType === 'folder' ? 'var(--color-accent, #c8932a)' : 'var(--color-text-secondary)',
                      background: selectedGroupName === group.name && groupActiveType === 'folder' ? 'rgba(218, 165, 32, 0.12)' : 'transparent',
                      borderRadius: '8px',
                      fontWeight: selectedGroupName === group.name && groupActiveType === 'folder' ? 600 : 400,
                      transition: 'background 0.15s, color 0.15s',
                    }}
                    onClick={() => {
                      // Toggle expansion
                      setExpandedGroups(prev =>
                        prev.includes(group.name)
                          ? prev.filter(g => g !== group.name)
                          : [...prev, group.name]
                      );
                      setActiveFeature('library');
                      setSelectedGroupName(group.name);
                      setGroupActiveType('folder');
                      setMessages([]); // This makes isLanding true!
                      setSessionId(generateSessionId()); // New session for the group
                    }}
                  >
                    <IconFolder width={14} height={14} />
                    <span>{group.name}</span>
                  </div>

                  {/* Render chats for this group */}
                  {expandedGroups.includes(group.name) && chatSessions.filter(s => s.group_name === group.name).map(s => (
                    <div
                      key={s.id}
                      className={`sidebar-sub-item ${s.id === sessionId && groupActiveType === 'chat' ? "active" : ""}`}
                      onClick={() => {
                        switchSession(s.id);
                        setActiveFeature('library');
                        setSelectedGroupName(group.name);
                        setGroupActiveType('chat');
                      }}
                      style={{
                        padding: '4px 12px',
                        paddingLeft: '52px',
                        fontSize: '12px',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px',
                        color: s.id === sessionId && groupActiveType === 'chat' ? 'var(--color-accent, #c8932a)' : 'var(--color-text-secondary)',
                        background: s.id === sessionId && groupActiveType === 'chat' ? 'rgba(218, 165, 32, 0.10)' : 'transparent',
                        borderRadius: '8px',
                        fontWeight: s.id === sessionId && groupActiveType === 'chat' ? 600 : 400,
                        transition: 'background 0.15s, color 0.15s',
                      }}
                    >
                      <IconChat width={12} height={12} />
                      <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{s.title}</span>
                    </div>
                  ))}
                </div>
              ))}

              {activeFeature !== 'library' && (
                <div className="search-section-sidebar" style={{ padding: '8px 12px', marginTop: 16 }}>
                  <div className="search-input-wrapper" style={{ position: 'relative' }}>
                    <IconSearch style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', opacity: 0.5 }} />
                    <input
                      type="text"
                      placeholder="Search chats..."
                      value={searchTerm}
                      onChange={(e) => setSearchTerm(e.target.value)}
                      style={{
                        width: '100%',
                        padding: '8px 10px 8px 34px',
                        borderRadius: 8,
                        border: '1px solid var(--color-border)',
                        background: 'rgba(255,255,255,0.05)',
                        fontSize: 13,
                        outline: 'none',
                        color: 'inherit'
                      }}
                    />
                  </div>
                  {searchTerm && (
                    <div className="search-results-dropdown" style={{
                      marginTop: 8,
                      maxHeight: 200,
                      overflowY: 'auto',
                      background: 'var(--color-bg-secondary)',
                      borderRadius: 8,
                      border: '1px solid var(--color-border)',
                      boxShadow: '0 4px 12px rgba(0,0,0,0.3)'
                    }}>
                      {chatSessions.filter(s => !s.group_name && s.title.toLowerCase().includes(searchTerm.toLowerCase())).length > 0 ? (
                        chatSessions
                          .filter(s => !s.group_name && s.title.toLowerCase().includes(searchTerm.toLowerCase()))
                          .map(s => (
                            <div
                              key={s.id}
                              className="search-result-item"
                              onClick={() => {
                                switchSession(s.id);
                                setSearchTerm("");
                                setActiveFeature('chat');
                              }}
                              style={{
                                padding: '8px 12px',
                                cursor: 'pointer',
                                fontSize: 12,
                                borderBottom: '1px solid rgba(255,255,255,0.05)',
                                display: 'flex',
                                alignItems: 'center',
                                gap: 8
                              }}
                            >
                              <IconChat width={14} height={14} style={{ opacity: 0.5 }} />
                              <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{s.title}</span>
                            </div>
                          ))
                      ) : (
                        <div style={{ padding: '12px', textAlign: 'center', fontSize: 12, opacity: 0.5 }}>No results found</div>
                      )}
                    </div>
                  )}
                </div>
              )}



              {/* Archived view */}
              {activeFeature === 'archived' && (
                <div className="chat-history-box" style={{ marginTop: 24, display: "flex", flexDirection: "column", minHeight: 0 }}>
                  <div className="chat-history-scroll">
                    {chatSessions.filter(s => s.isArchived && !s.group_name).map(a => (
                      <div
                        key={a.id}
                        className="sidebar-item"
                        onClick={() => {
                          void switchSession(a.id);
                        }}
                        style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}
                      >
                        <div className="content" style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 8 }}>
                          <IconArchive width={16} height={16} />
                          <span title={a.title} style={{ whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{a.title}</span>
                        </div>
                        <div>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleArchiveSession(a.id, false);
                            }}
                            title="Unarchive"
                            style={{ background: 'transparent', border: 'none', color: 'var(--color-text)', cursor: 'pointer', padding: 6, borderRadius: 6 }}
                          >Unarchive</button>
                        </div>
                      </div>
                    ))}
                    {chatSessions.filter(s => s.isArchived && !s.group_name).length === 0 && (
                      <div style={{ padding: "12px 16px", fontSize: 12, color: "#7a8f75", fontStyle: "italic" }}>
                        No archived chats
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Chat History – only visible when Chat feature is active and not searching */}
              {activeFeature === 'chat' && !searchTerm && (

                <div className="chat-history-box" style={{ marginTop: 24, display: "flex", flexDirection: "column", minHeight: 0 }}>
                  <div className="chat-history-scroll">
                    {chatSessions.filter(s => !s.isArchived && !s.group_name).map(s => (
                      <div
                        key={s.id}
                        className={`sidebar-item${s.id === sessionId ? " active" : ""}`}
                        onClick={() => switchSession(s.id)}
                        style={{ cursor: "pointer", display: 'flex', alignItems: 'center', gap: 8 }}
                      >
                        <div className="content" style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 8 }}>
                          {s.isPinned ? <IconPin size={16} style={{ color: 'var(--color-primary)' }} /> : <IconChat width={16} height={16} />}
                          {editingSessionId === s.id ? (
                            <input
                              ref={(el) => { editingInputRef.current = el; if (el) el.focus(); }}
                              value={editingTitle}
                              onChange={(e) => setEditingTitle(e.target.value)}
                              onBlur={() => commitRename(s.id)}
                              onKeyDown={(e) => {
                                if (e.key === "Enter") { e.preventDefault(); commitRename(s.id); }
                                if (e.key === "Escape") { setEditingSessionId(null); setEditingTitle(""); }
                              }}
                              onClick={(e) => e.stopPropagation()}
                              title={s.title}
                              style={{
                                whiteSpace: "nowrap",
                                overflow: "hidden",
                                textOverflow: "ellipsis",
                                borderRadius: 6,
                                padding: "6px 8px",
                                border: "1px solid var(--color-border)",
                                background: "var(--color-bg-alt)",
                                color: "var(--color-text)",
                                width: '100%'
                              }}
                            />
                          ) : (
                            <span
                              title={s.title}
                              style={{ whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}
                            >
                              {previewTitle(s.title, 2)}
                            </span>
                          )}
                        </div>

                        <div style={{ display: 'flex', alignItems: 'center' }}>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              const btn = e.currentTarget as HTMLElement;
                              const pos = computeSessionMenuPos(btn, 140);
                              const willOpen = sessionMenuOpen !== s.id;
                              setSessionMenuOpen(willOpen ? s.id : null);
                              setSessionMenuPos(willOpen ? pos : null);
                              setSessionMenuVisible(false);
                            }}
                            aria-label="Session options"
                            title="Options"
                            style={{
                              background: 'transparent',
                              border: 'none',
                              color: 'var(--color-text)',
                              cursor: 'pointer',
                              padding: '6px',
                              borderRadius: 6,
                            }}
                          >
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="5" r="1" /><circle cx="12" cy="12" r="1" /><circle cx="12" cy="19" r="1" /></svg>
                          </button>

                          {sessionMenuOpen === s.id && sessionMenuPos && (
                            <div
                              ref={(el) => { sessionMenuRef.current = el; }}
                              onClick={(e) => e.stopPropagation()}
                              className="session-menu"
                              style={{
                                position: 'fixed',
                                top: `${sessionMenuPos.top}px`,
                                transform: sessionMenuPos.placement === 'above' ? 'translate(calc(-100% + 24px), -100%)' : 'translateX(calc(-100% + 24px))',
                                left: `${sessionMenuPos.left}px`,
                                background: 'var(--color-bg-alt)',
                                border: '1px solid var(--color-border)',
                                borderRadius: 8,
                                padding: '6px 8px',
                                boxShadow: '0 6px 18px rgba(0,0,0,0.4)',
                                zIndex: 20000,
                                minWidth: 140,
                                whiteSpace: 'nowrap',
                                visibility: sessionMenuVisible ? 'visible' : 'hidden',
                                pointerEvents: sessionMenuVisible ? 'auto' : 'none',
                              }}>
                              <button
                                onClick={() => { setSessionMenuOpen(null); setSessionMenuPos(null); handleRenameSession(s.id); }}
                                style={{ display: 'block', width: '100%', textAlign: 'left', padding: '6px 8px', background: 'transparent', border: 'none', color: 'var(--color-text)', cursor: 'pointer' }}
                              >Rename</button>
                              <button
                                onClick={() => { setSessionMenuOpen(null); setSessionMenuPos(null); handlePinSession(s.id, !s.isPinned); }}
                                style={{ display: 'block', width: '100%', textAlign: 'left', padding: '6px 8px', background: 'transparent', border: 'none', color: 'var(--color-text)', cursor: 'pointer' }}
                              >{s.isPinned ? 'Unpin' : 'Pin'}</button>
                              <button
                                onClick={() => { setSessionMenuOpen(null); setSessionMenuPos(null); handleArchiveSession(s.id, !s.isArchived); }}
                                style={{ display: 'block', width: '100%', textAlign: 'left', padding: '6px 8px', background: 'transparent', border: 'none', color: 'var(--color-text)', cursor: 'pointer' }}
                              >{s.isArchived ? 'Unarchive' : 'Archive'}</button>
                              <button
                                onClick={() => { setSessionMenuOpen(null); setSessionMenuPos(null); handleDeleteSession(s.id); }}
                                style={{ display: 'block', width: '100%', textAlign: 'left', padding: '6px 8px', background: 'transparent', border: 'none', color: 'var(--color-text)', cursor: 'pointer' }}
                              >Delete</button>
                              <button
                                onClick={() => { setSessionMenuOpen(null); setSessionMenuPos(null); handleShareSession(s.id); }}
                                style={{ display: 'block', width: '100%', textAlign: 'left', padding: '6px 8px', background: 'transparent', border: 'none', color: 'var(--color-primary)', cursor: 'pointer', borderTop: '1px solid rgba(255,255,255,0.05)', fontWeight: 600 }}
                              >Share Chat</button>
                            </div>
                          )}
                        </div>
                      </div>
                    ))}

                    {chatSessions.length === 0 && (
                      <div style={{ padding: "12px 16px", fontSize: 12, color: "#7a8f75", fontStyle: "italic" }}>
                        No chats yet — click New Chat to start
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>

          </aside>
        </div>

        {/* ── Main Content ─────────────────────────────────────────────────── */}
        <div
          className={
            !historyLoading && isLanding
              ? "main-content main-content--landing-start"
              : "main-content"
          }
        >

          {/* Mobile Header with Menu Button - sticky at top (hidden while sidebar is open) */}
          {isMobileHeaderVisible && (
            <div
              style={{
                position: 'fixed',
                top: 0,
                left: 0,
                right: 0,
                height: '36px',
                background: 'var(--color-bg-alt)',
                borderBottom: '1px solid var(--color-border)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                paddingLeft: '12px',
                paddingRight: '12px',
                zIndex: 10000,
                backdropFilter: 'blur(10px)',
              }}
            >
              <button
                onClick={() => setSidebarOpen(true)}
                title="Open sidebar"
                aria-label="Open sidebar"
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: 'var(--color-text)',
                  cursor: 'pointer',
                  padding: '8px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  transition: 'all 0.2s ease',
                }}
              >
                <IconMenu2 size={24} />
              </button>
              <div style={{ fontSize: '14px', fontWeight: '500', flex: 1, textAlign: 'center' }}>
                Ask AI
              </div>
              <div style={{ width: '40px' }} />
            </div>
          )}

          {/* Mobile Menu Button - legacy, disabled when header is shown */}
          {false && responsive.isMobile && (
            <button
              className="mobile-menu-btn"
              onClick={() => setSidebarOpen(true)}
              title="Open sidebar"
              aria-label="Open sidebar"
              style={{
                position: 'fixed',
                top: 16,
                left: 16,
                zIndex: 1000,
                background: 'transparent',
                border: 'none',
                color: 'var(--color-text)',
                cursor: 'pointer',
                padding: '8px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                transition: 'all 0.2s ease',
                opacity: sidebarOpen ? 0 : 1,
                pointerEvents: sidebarOpen ? 'none' : 'auto',
              }}
            >
              <IconMenu2 size={24} />
            </button>
          )}

          {/* Overlay when sidebar is open on mobile */}
          {(responsive.isMobile || responsive.isTablet) && sidebarOpen && (
            <div
              style={{
                position: 'fixed',
                inset: 0,
                zIndex: 9997,
                // Blur the background behind the sidebar (mobile/tablet "max blur")
                backgroundColor: 'rgba(0, 0, 0, 0.35)',
                backdropFilter: 'blur(30px) saturate(130%)',
                WebkitBackdropFilter: 'blur(30px) saturate(130%)',
              }}
              onClick={() => setSidebarOpen(false)}
            />
          )}

          {/* History loading spinner */}
          {historyLoading && (
            <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
              <div style={{ textAlign: "center" }}>
                <div style={{ display: "flex", gap: 6, justifyContent: "center", marginBottom: 8 }}>
                  {[0, 1, 2].map(i => (
                    <span key={i} style={{
                      display: "inline-block", width: 8, height: 8,
                      borderRadius: "50%", background: "#d4af37",
                      animation: `bounce 1.2s ease-in-out ${i * 0.2}s infinite`,
                    }} />
                  ))}
                </div>
                <span style={{ fontSize: 13, color: "#A0AEC0" }}>Loading chat history…</span>
              </div>
            </div>
          )}

          {/* Landing — welcome shifted up; input vertically centered (only before first message) */}
          {!historyLoading && isLanding && (activeFeature === 'chat' || activeFeature === 'library' || activeFeature === 'archived') && (
            <div className="landing-start-column">
              <div className="landing-start-spacer-top" aria-hidden />
              <div className="landing-container landing-container--start">
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
                    {selectedGroupName ? `📁 ${selectedGroupName}` : "Welcome to Ask AI"}
                  </h1>
                  <p className="landing-subtitle">{selectedGroupName ? `Start a new chat in ${selectedGroupName}` : "Let's work together buddy"}</p>
                </div>
              </div>
              {renderChatInputFooter("landing")}
              <div className="landing-start-spacer-bottom" aria-hidden />
            </div>
          )}

          {/* Chat area */}
          {!historyLoading && !isLanding && (activeFeature === 'chat' || activeFeature === 'library') && (
            <div className="chat-scroll-area">
              {selectedGroupName && (
                <div style={{ padding: '12px 24px', borderBottom: '1px solid rgba(255,255,255,0.05)', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <IconFolder size={14} style={{ color: 'var(--color-primary)' }} />
                  <span style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--color-text)' }}>{selectedGroupName}</span>
                </div>
              )}
              <div className="messages-container">
                {messages.map((msg, idx) => {
                  const isUser = msg.role === "user";
                  const isError = msg.role === "error";
                  const isStreaming = msg.streaming === true;
                  const isAudio = msg.isAudio === true;
                  const isGraphMsg = msg.isGraphResponse === true;  // ← Use explicit flag

                  // ✅ Parse graph data ONLY if message is marked as graph response
                  const graphData = isGraphMsg
                    ? parseGraphData(msg.text)
                    : null;

                  // DEBUG: Log rendering decision
                  if (isGraphMsg) {
                    console.log("✅ [RENDER] Marked as graph message → will render BarChartRenderer", {
                      parsed: graphData !== null,
                      type: graphData?.type,
                    });
                  } else if (!isUser && !isError && !isStreaming) {
                    console.log("📨 [RENDER] Regular message → will render as HTML", {
                      textLength: msg.text?.length || 0,
                    });
                  }

                  // Format duration as MM:SS
                  const formatDuration = (seconds: number): string => {
                    const mins = Math.floor(seconds / 60);
                    const secs = seconds % 60;
                    return `${mins}:${secs.toString().padStart(2, "0")}`;
                  };

                  return (
                    <div key={idx} className={`message-row ${msg.role}`}>
                      {!isUser && !isError && (
                        <div className="avatar-box"><IconAI /></div>
                      )}

                      <div
                        className={`message-bubble ${msg.role}${isGraphMsg ? ' graph-message' : ''}${msg.tableData && msg.tableData.length > 0 ? ' table-message' : ''}`}
                        style={{ position: 'relative' }}
                      >

                        {isAudio ? (
                          /* ── Audio Message: Show player UI ── */
                          (() => {
                            // BUG 1 FIX: prefer real loaded duration, fall back to stored, then 0
                            const realDur = audioDurationMap[idx] ?? msg.audioDuration ?? 0;
                            const progress = audioProgressMap[idx] ?? 0;
                            // currentTime = progress% of realDur
                            const currentSec = realDur > 0 ? (progress / 100) * realDur : 0;

                            const fmtSec = (s: number) => {
                              const m = Math.floor(s / 60);
                              const sec = Math.floor(s % 60);
                              return `${m}:${sec.toString().padStart(2, "0")}`;
                            };

                            return (
                              <div className="voice-message-container" style={{
                                fontSize: responsive.isMobile ? '12px' : responsive.isTablet ? '13px' : '14px',
                                display: 'flex',
                                gap: responsive.isMobile ? '8px' : '12px',
                                alignItems: 'center',
                                width: '100%',
                              }}>
                                <button
                                  className="voice-message-play-btn"
                                  onClick={() => handleAudioPlayback(idx, msg.audioUrl, msg.audioDuration || 0)}
                                  disabled={!isUser}
                                >
                                  {audioPlayingIndex === idx ? <IconPlayerPause size={20} /> : <IconPlayerPlay size={20} />}
                                </button>
                                <div style={{ display: "flex", flexDirection: "column", flex: 1, gap: "6px" }}>
                                  <div className="voice-message-progress-wrapper">
                                    <div
                                      className="voice-message-progress-bar"
                                      style={{
                                        width: `${progress}%`,
                                        transition: "width 0.1s linear",   // smooth CSS transition
                                      }}
                                    />
                                  </div>
                                  {/* BUG 1 FIX: show real duration; if playing show currentTime / total */}
                                  <div className="voice-message-duration" style={{
                                    fontSize: responsive.isMobile ? '11px' : responsive.isTablet ? '12px' : '13px',
                                  }}>
                                    {audioPlayingIndex === idx
                                      ? `${fmtSec(currentSec)} / ${fmtSec(realDur)}`
                                      : fmtSec(realDur)
                                    }
                                  </div>
                                </div>
                              </div>
                            );
                          })()
                        ) : isUser || isError ? (
                          /* ── User / Error: plain text ── */
                          <>{msg.text}</>

                        ) : isStreaming ? (
                          /* ── Streaming: pre-wrap plain text + blinking cursor ── */
                          <div className="ai-bubble streaming-text">
                            {msg.text}
                            <span className="stream-cursor" />
                          </div>

                        ) : isGraphMsg && graphData ? (
                          /* ── Graph: Render chart with per-message type switcher ── */
                          (() => {
                            const chartSize = getResponsivePieChartSize(responsive.screen);
                            return (
                              <div style={{
                                display: 'flex',
                                justifyContent: 'center',
                                alignItems: 'center',
                                width: '100%',
                                maxWidth: chartSize.containerMaxWidth,
                                marginTop: responsive.isMobile ? '8px' : responsive.isTablet ? '12px' : '16px',
                                marginBottom: responsive.isMobile ? '8px' : responsive.isTablet ? '12px' : '16px',
                                marginLeft: 'auto',
                                marginRight: 'auto',
                                overflow: responsive.isMobile ? 'visible' : 'visible',
                                paddingLeft: responsive.isMobile ? '8px' : responsive.isTablet ? '12px' : '16px',
                                paddingRight: responsive.isMobile ? '8px' : responsive.isTablet ? '12px' : '16px',
                                paddingTop: responsive.isMobile ? '8px' : responsive.isTablet ? '12px' : '16px',
                                paddingBottom: responsive.isMobile ? '8px' : responsive.isTablet ? '12px' : '16px',
                              }}>
                                {(() => {
                                  const msgChartType = msg.chartType || 'vertical-bar';

                                  const handleChartTypeChange = (newType: ChartType) => {
                                    setChartType(newType);
                                    setMessages(prev => {
                                      const updated = [...prev];
                                      updated[idx] = { ...updated[idx], chartType: newType };
                                      return updated;
                                    });
                                  };

                                  if (msgChartType === 'horizontal-bar') {
                                    return <HorizontalBarChartRenderer key={`hbar-${idx}`} graphData={graphData} currentChartType={msgChartType} onChartTypeChange={handleChartTypeChange} />;
                                  } else if (msgChartType === 'pie') {
                                    return <PieChartRenderer key={`pie-${idx}`} graphData={graphData} currentChartType={msgChartType} onChartTypeChange={handleChartTypeChange} />;
                                  } else if (msgChartType === 'line') {
                                    return <LineChartRenderer key={`line-${idx}`} graphData={graphData} currentChartType={msgChartType} onChartTypeChange={handleChartTypeChange} />;
                                  } else {
                                    return <BarChartRenderer key={`bar-${idx}`} graphData={graphData} currentChartType={msgChartType} onChartTypeChange={handleChartTypeChange} />;
                                  }
                                })()}
                              </div>
                            );
                          })()

                        ) : msg.tableData && msg.tableData.length > 0 ? (
                          /* ── Table: Render with TableWithTile component with toggle buttons for table/tile views ── */
                          <TableWithTile
                            rows={msg.tableData}
                            title={msg.tableTitle || "Data"}
                            htmlTableContent={msg.text}
                          />

                        ) : (
                          /* ── Complete: already formatted at [DONE] time ── */
                          <div className="ai-bubble" style={{
                            fontSize: responsive.isMobile ? '13px' : responsive.isTablet ? '14px' : '15px',
                            lineHeight: 1.5,
                            maxWidth: responsive.isMobile ? '90%' : responsive.isTablet ? '85%' : '75%',
                            display: 'flex',
                            justifyContent: 'center',
                            alignItems: 'flex-start',
                          }}>
                            <div dangerouslySetInnerHTML={{ __html: msg.text }} style={{
                              width: '100%',
                              textAlign: 'left',
                            }} />
                          </div>
                        )}

                        {/* Copy button for text bubbles only */}
                        {!isAudio && !isGraphMsg && !(msg.tableData && msg.tableData.length > 0) && (
                          <>
                            <button
                              className="copy-bubble-btn"
                              onClick={(e) => {
                                // Extract plain text if it's HTML
                                const textToCopy = msg.text.replace(/<[^>]*>?/gm, '');
                                navigator.clipboard.writeText(textToCopy);

                                // Change icon to tick
                                const btn = e.currentTarget;
                                const originalHTML = btn.innerHTML;
                                btn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>`;

                                setTimeout(() => {
                                  btn.innerHTML = originalHTML;
                                }, 2000);
                              }}
                              style={{
                                position: 'absolute',
                                bottom: '4px',
                                right: '4px',
                                opacity: 0, // hidden by default on desktop
                                transition: 'opacity 0.2s',
                                background: (typeof window !== 'undefined' ? document.documentElement.getAttribute('data-theme') === 'dark' : (theme === 'dark')) ? 'rgba(255,255,255,0.15)' : 'rgba(0,0,0,0.05)',
                                border: 'none',
                                borderRadius: '4px',
                                color: (typeof window !== 'undefined' ? document.documentElement.getAttribute('data-theme') === 'dark' : (theme === 'dark')) ? '#d4af37' : '#5c4033',
                                padding: '4px',
                                cursor: 'pointer',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                zIndex: 10
                              }}
                              title="Copy text"
                            >
                              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                                <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                              </svg>
                            </button>
                            <style>{`
                              @media (hover: hover) {
                                .message-bubble:hover .copy-bubble-btn {
                                  opacity: 1 !important;
                                }
                              }
                              @media (max-width: 1024px) {
                                .copy-bubble-btn {
                                  opacity: 1 !important;
                                  padding: 2px !important;
                                }
                                .copy-bubble-btn svg {
                                  width: 12px !important;
                                  height: 12px !important;
                                }
                              }
                            `}</style>
                          </>
                        )}

                      </div>
                    </div>
                  );
                })}

                {isLoading && (() => {
                  const isDarkTheme = typeof window !== 'undefined' ? document.documentElement.getAttribute('data-theme') === 'dark' : (theme === 'dark');
                  return (
                    <div className="loading-indicator" style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
                      <div className="avatar-box"><IconAI /></div>
                      {/* Bubble with cycling sliding workflow text */}
                      <div className="ai-bubble" style={{
                        background: isDarkTheme ? '#111111' : '#ffffff',
                        color: isDarkTheme ? '#d4af37' : '#5c4033',
                        border: '1px solid #d4af37',
                        borderRadius: '16px 16px 16px 4px',
                        padding: '10px 16px',
                        display: 'flex',
                        alignItems: 'center',
                        fontSize: '13px',
                        position: 'relative',
                        overflow: 'hidden',
                        width: 'max-content'
                      }}>
                        {/* Invisible element to size the container to the longest text naturally */}
                        <span style={{ opacity: 0, visibility: 'hidden', whiteSpace: 'nowrap' }}>Rendering Output...</span>

                        {/* Absolute container for the centered animated text */}
                        <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', paddingLeft: '16px' }}>
                          {["AI Recognized", "Passed Payload", "Fetching DB", "Returning Data", "Rendering Output"].map((text, textIdx) => (
                            <div key={textIdx} style={{
                              position: 'absolute',
                              opacity: 0,
                              animation: 'cycle-text-5 10s infinite',
                              animationDelay: `${textIdx * 2}s`,
                              whiteSpace: 'nowrap',
                              display: 'flex',
                              alignItems: 'center',
                              gap: '2px'
                            }}>
                              <span>{text}</span>
                              {/* Animated dots attached to the text */}
                              <div style={{ display: 'flex', gap: '2px', alignItems: 'flex-end', height: '10px', paddingBottom: '2px' }}>
                                {[0, 1, 2].map(i => (
                                  <span key={i} style={{
                                    display: "inline-block", width: 3, height: 3,
                                    borderRadius: "50%", background: "currentColor",
                                    animation: `bounce 1.2s ease-in-out ${i * 0.2}s infinite`,
                                  }} />
                                ))}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                      <style>{`
                        @keyframes cycle-text-5 {
                          0% { opacity: 0; transform: translateY(10px); }
                          5%, 15% { opacity: 1; transform: translateY(0); }
                          20%, 100% { opacity: 0; transform: translateY(-10px); }
                        }
                        @keyframes bounce {
                          0%, 100% { transform: translateY(0); }
                          50% { transform: translateY(-3px); }
                        }
                      `}</style>
                    </div>
                  );
                })()}
                <div ref={messagesEndRef} />
              </div>
            </div>
          )}

          {/* Groups view */}
          {!historyLoading && activeFeature === 'library' && (
            <GroupsChat createGroupTrigger={createGroupTrigger} groups={groups} onCreateGroup={handleCreateGroup} />
          )}

          {/* Input footer — bottom bar after chat starts or while history loads (not duplicated on landing) */}
          {(historyLoading || (!isLanding && (activeFeature === 'chat' || activeFeature === 'library'))) && renderChatInputFooter("default")}

          {/* Upgrade Plan Modal */}
          {showUpgradePlan && (
            <div
              className="upgrade-plan-backdrop"
              style={{
                position: 'fixed',
                inset: 0,
                background: 'rgba(0, 0, 0, 0.60)',
                backdropFilter: 'blur(12px) saturate(120%)',
                WebkitBackdropFilter: 'blur(12px) saturate(120%)',
                zIndex: 10010,
                display: 'flex',
                justifyContent: 'center',
                alignItems: 'center',
              }}
              onClick={() => setShowUpgradePlan(false)}
            >
              <div
                className="upgrade-plan-modal"
                onClick={(e) => e.stopPropagation()}
              >
                <button
                  onClick={() => setShowUpgradePlan(false)}
                  className="upgrade-plan-close-btn"
                >
                  ×
                </button>
                <UpgradePlan
                  onManageAccountClick={() => {
                    setShowUpgradePlan(false);
                    setShowManageAccount(true);
                  }}
                  onPlanChange={(planName) => {
                    setCurrentPlan(planName);
                  }}
                />
              </div>
            </div>
          )}

          {/* Delete Confirmation Modal (rendered via portal to avoid being blurred) */}
          {typeof document !== 'undefined' && showDeleteModal && createPortal(
            <div
              className="modal-backdrop"
              onClick={() => { setShowDeleteModal(false); setDeleteSessionId(null); setDeleteSessionTitle(""); }}
            >
              <div className="confirm-delete-modal" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
                <h3>Delete chat?</h3>
                <p>This will delete <strong>{deleteSessionTitle}</strong>.</p>
                <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end', marginTop: 12 }}>
                  <button className="btn btn-secondary" onClick={() => { setShowDeleteModal(false); setDeleteSessionId(null); setDeleteSessionTitle(""); }}>Cancel</button>
                  <button className="btn btn-danger" onClick={() => performDeleteSession()}>Delete</button>
                </div>
              </div>
            </div>,
            document.body
          )}

          {/* Manage Account Full-Screen Page */}
          {showManageAccount && (
            <div
              style={{
                position: "fixed",
                top: 0,
                left: 0,
                right: 0,
                bottom: 0,
                width: "100vw",
                height: "100vh",
                background: "var(--color-bg)",
                zIndex: 10000,
                display: "flex",
                flexDirection: "column",
              }}
            >
              {!isManageAccountMenuOpen && (
                <div style={{
                  position: "absolute",
                  top: "20px",
                  right: "20px",
                  zIndex: 10001,
                }}>
                  <button
                    onClick={() => {
                      setShowManageAccount(false);
                      setIsManageAccountMenuOpen(false);
                    }}
                    style={{
                      width: "40px",
                      height: "40px",
                      borderRadius: "6px",
                      border: "1.5px solid var(--color-primary)",
                      background: "transparent",
                      color: "var(--color-primary)",
                      cursor: "pointer",
                      fontSize: "24px",
                      fontWeight: 600,
                      transition: "all 0.3s ease",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                    }}
                    onMouseEnter={(e) => {
                      const btn = e.currentTarget as HTMLElement;
                      btn.style.background = "var(--color-primary)";
                      btn.style.color = "var(--color-text)";
                    }}
                    onMouseLeave={(e) => {
                      const btn = e.currentTarget as HTMLElement;
                      btn.style.background = "transparent";
                      btn.style.color = "var(--color-primary)";
                    }}
                  >
                    ×
                  </button>
                </div>
              )}
              <div style={{
                flex: 1,
                width: "100%",
                height: "100%",
              }}>
                <ManageAccount
                  currentPlan={currentPlan}
                  profileName={loggedInUser || "My Account"}
                  subUserName={userIdFromUrl ?? loggedInUser ?? ""}
                  externalUserId={loggedInUser ?? ""}
                  onMobileSidebarOpenChange={(open) => setIsManageAccountMenuOpen(open)}
                />
              </div>
            </div>
          )}

          {/* Walkthrough Popup */}
          <WalkthroughPopup />

          {/* Share Modal */}
          {shareModalOpen && (
            <div style={{
              position: 'fixed', inset: 0, zIndex: 9999,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              backgroundColor: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(8px)'
            }}>
              <div style={{
                background: (typeof window !== 'undefined' && document.documentElement.getAttribute('data-theme') === 'dark') ? 'var(--color-bg-sidebar)' : '#ffffff',
                padding: '24px', borderRadius: '16px',
                width: '90%', maxWidth: '400px',
                border: (typeof window !== 'undefined' && document.documentElement.getAttribute('data-theme') === 'dark') ? '1px solid rgba(255,255,255,0.1)' : '1px solid rgba(0,0,0,0.1)',
                boxShadow: '0 20px 25px -5px rgba(0,0,0,0.5)', textAlign: 'center'
              }}>
                <h3 style={{ margin: '0 0 8px 0', fontSize: '1.25rem', fontWeight: 600 }}>Share Chat</h3>
                <p style={{ margin: '0 0 20px 0', fontSize: '0.875rem', color: 'var(--color-text-dim)' }}>
                  Anyone with this link or code can view this conversation.
                </p>

                {/* Share Link Section */}
                <div style={{ textAlign: 'left', marginBottom: '8px', fontSize: '0.75rem', fontWeight: 600, color: 'var(--color-primary)' }}>SHARE LINK</div>
                <div style={{
                  display: 'flex', alignItems: 'center', gap: '8px',
                  background: (typeof window !== 'undefined' && document.documentElement.getAttribute('data-theme') === 'dark') ? 'rgba(0,0,0,0.2)' : 'rgba(0,0,0,0.05)',
                  padding: '12px', borderRadius: '8px',
                  border: (typeof window !== 'undefined' && document.documentElement.getAttribute('data-theme') === 'dark') ? '1px solid rgba(255,255,255,0.05)' : '1px solid rgba(0,0,0,0.1)',
                  marginBottom: '24px'
                }}>
                  <input
                    readOnly
                    value={isSharing ? "Generating link..." : shareLink}
                    style={{
                      flex: 1, background: 'transparent', border: 'none', color: isSharing ? 'var(--color-text-dim)' : 'var(--color-text)',
                      fontSize: '0.875rem', outline: 'none', cursor: 'default',
                      fontStyle: isSharing ? 'italic' : 'normal'
                    }}
                  />
                  <button
                    onClick={() => {
                      if (!isSharing && shareLink) {
                        navigator.clipboard.writeText(shareLink);
                        setShareLinkCopied(true);
                        setTimeout(() => setShareLinkCopied(false), 2000);
                      }
                    }}
                    disabled={isSharing || !shareLink}
                    style={{
                      background: 'var(--color-primary)', border: 'none', borderRadius: '6px',
                      padding: '6px 12px', color: '#000', fontWeight: 600, cursor: 'pointer', fontSize: '0.75rem',
                      opacity: (isSharing || !shareLink) ? 0.5 : 1,
                      display: 'flex', alignItems: 'center', gap: '4px'
                    }}
                  >
                    {shareLinkCopied ? (
                      <>
                        <IconCheck size={14} />
                        Copied
                      </>
                    ) : (
                      "Copy"
                    )}
                  </button>
                </div>

                {/* changes done by megnathan: Added Share via Code section with copy icon */}
                <div style={{ textAlign: 'left', marginBottom: '8px', fontSize: '0.75rem', fontWeight: 600, color: 'var(--color-primary)' }}>SHARE VIA CODE</div>
                <div style={{
                  background: (typeof window !== 'undefined' && document.documentElement.getAttribute('data-theme') === 'dark') ? 'rgba(0,0,0,0.2)' : 'rgba(0,0,0,0.05)',
                  padding: '16px', borderRadius: '8px',
                  border: (typeof window !== 'undefined' && document.documentElement.getAttribute('data-theme') === 'dark') ? '1px solid rgba(255,255,255,0.05)' : '1px solid rgba(0,0,0,0.1)',
                  marginBottom: '24px',
                  display: 'flex', flexDirection: 'column', gap: '12px', alignItems: 'center'
                }}>
                  {shareCode ? (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', alignItems: 'flex-start' }}>
                        <div style={{ fontSize: '24px', fontWeight: 800, letterSpacing: '4px', color: 'var(--color-primary)' }}>{shareCode}</div>
                        <div style={{ fontSize: '10px', opacity: 0.6 }}>Give this 5-digit code to another user</div>
                      </div>
                      <button
                        onClick={() => {
                          navigator.clipboard.writeText(shareCode);
                          setShareCodeCopied(true);
                          setTimeout(() => setShareCodeCopied(false), 2000);
                        }}
                        style={{
                          background: (typeof window !== 'undefined' && document.documentElement.getAttribute('data-theme') === 'dark') ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)',
                          border: (typeof window !== 'undefined' && document.documentElement.getAttribute('data-theme') === 'dark') ? '1px solid rgba(255,255,255,0.1)' : '1px solid rgba(0,0,0,0.1)',
                          borderRadius: '8px', padding: '8px', color: 'var(--color-primary)', cursor: 'pointer',
                          display: 'flex', alignItems: 'center', justifyContent: 'center'
                        }}
                        title="Copy Code"
                      >
                        {shareCodeCopied ? <IconCheck size={20} /> : <IconCopy size={20} />}
                      </button>
                    </div>
                  ) : (
                    <button
                      onClick={handleGenerateShareCode}
                      disabled={isGeneratingCode}
                      style={{
                        background: 'transparent', border: '1px solid var(--color-primary)', borderRadius: '6px',
                        padding: '8px 16px', color: 'var(--color-primary)', fontWeight: 600, cursor: 'pointer', fontSize: '0.875rem'
                      }}
                    >
                      {isGeneratingCode ? "Generating..." : "Generate Share Code"}
                    </button>
                  )}
                </div>

                <button
                  onClick={() => setShareModalOpen(false)}
                  style={{
                    width: '100%', padding: '10px', borderRadius: '8px', background: 'rgba(255,255,255,0.05)',
                    border: 'none', color: 'var(--color-text)', cursor: 'pointer', fontWeight: 500
                  }}
                >Close</button>
              </div>
            </div>
          )}

          {/* changes done by megnathan: Added Import Modal */}
          {importModalOpen && (
            <div style={{
              position: 'fixed', inset: 0, zIndex: 9999,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              backgroundColor: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(8px)'
            }}>
              <div style={{
                background: (typeof window !== 'undefined' && document.documentElement.getAttribute('data-theme') === 'dark') ? 'var(--color-bg-sidebar)' : '#ffffff',
                padding: '24px', borderRadius: '16px',
                width: '90%', maxWidth: '400px',
                border: (typeof window !== 'undefined' && document.documentElement.getAttribute('data-theme') === 'dark') ? '1px solid rgba(255,255,255,0.1)' : '1px solid rgba(0,0,0,0.1)',
                boxShadow: '0 20px 25px -5px rgba(0,0,0,0.5)', textAlign: 'center'
              }}>
                <h3 style={{ margin: '0 0 8px 0', fontSize: '1.25rem', fontWeight: 600 }}>Import Chat via Code</h3>
                <p style={{ margin: '0 0 20px 0', fontSize: '0.875rem', color: 'var(--color-text-dim)' }}>
                  Enter the 5-digit code to add a shared chat to your history.
                </p>

                {/* changes done by megnathan: Refined import placeholder and font size */}
                <div style={{ marginBottom: '24px' }}>
                  <input
                    type="text"
                    maxLength={5}
                    placeholder="Enter the code"
                    className="import-code-input"
                    value={inputShareCode}
                    onChange={(e) => setInputShareCode(e.target.value.replace(/[^0-9]/g, ""))}
                    style={{
                      width: '100%',
                      background: (typeof window !== 'undefined' && document.documentElement.getAttribute('data-theme') === 'dark') ? 'rgba(0,0,0,0.2)' : 'rgba(0,0,0,0.05)',
                      border: (typeof window !== 'undefined' && document.documentElement.getAttribute('data-theme') === 'dark') ? '1px solid rgba(255,255,255,0.1)' : '1px solid rgba(0,0,0,0.1)',
                      borderRadius: '8px', padding: '16px', color: 'var(--color-text)',
                      fontSize: '24px', textAlign: 'center', fontWeight: 800, letterSpacing: '8px',
                      outline: 'none'
                    }}
                  />
                  <style jsx>{`
                    .import-code-input::placeholder {
                      font-size: 16px;
                      letter-spacing: normal;
                      font-weight: 500;
                      opacity: 0.5;
                    }
                  `}</style>
                </div>

                <div style={{ display: 'flex', gap: '12px' }}>
                  <button
                    onClick={() => setImportModalOpen(false)}
                    style={{
                      flex: 1, padding: '12px', borderRadius: '8px', background: 'rgba(255,255,255,0.05)',
                      border: 'none', color: 'var(--color-text)', cursor: 'pointer', fontWeight: 500
                    }}
                  >Cancel</button>
                  <button
                    onClick={handleImportByCode}
                    disabled={isImporting || inputShareCode.length !== 5}
                    style={{
                      flex: 1, padding: '12px', borderRadius: '8px', background: 'var(--color-primary)',
                      border: 'none', color: '#000', cursor: 'pointer', fontWeight: 700,
                      opacity: (isImporting || inputShareCode.length !== 5) ? 0.5 : 1
                    }}
                  >
                    {isImporting ? "Importing..." : "Add to My Chats"}
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// Return the first `n` words of a title, adding an ellipsis if truncated
function previewTitle(title: string | undefined | null, n = 2): string {
  if (!title) return "Chat";
  const words = title.trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return "Chat";

  // If there's only one word, return it (or 'Chat' fallback)
  if (words.length === 1) return words[0];

  const first = words[0];
  const second = words[1] ?? "";

  // Preferred: show two words only when they fit a reasonable length
  const combinedLen = first.length + 1 + second.length;
  const MAX_COMBINED = 20;   // max characters for two-word preview
  const MAX_SECOND = 12;     // max chars allowed for second word

  if (combinedLen <= MAX_COMBINED && second.length <= MAX_SECOND) {
    return first + " " + second + (words.length > 2 ? "…" : "");
  }

  return first + (words.length > 1 ? "…" : "");
}