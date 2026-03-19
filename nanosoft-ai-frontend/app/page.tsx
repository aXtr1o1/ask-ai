"use client";

import { useState, useRef, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Image from "next/image";
import { ThemeToggle } from "./components/ThemeToggle";
import { useResponsive, getResponsivePieChartSize } from "./hooks/useResponsive";
import BackgroundLayer from "./components/BackgroundLayer";
import { useTheme } from "./components/useTheme";

import { useVoiceRecorder, RecordingInterface, VoicePreviewBar, VoiceMicButton } from "./components/VoiceRecorder";
import { parseGraphData, BarChartRenderer, HorizontalBarChartRenderer, LineChartRenderer, PieChartRenderer, ChartType } from "./components/GraphRenderer";
import TableWithTile, { TableWithTileRow } from "./components/TableWithTile";
import UpgradePlan from "./components/UpgradePlan";
import WalkthroughPopup from "./components/WalkthroughPopup";
import { IconUser, IconMicrophone, IconPlayerPlay, IconPlayerPause, IconTrash, IconArrowUp, IconChartBar, IconList, IconLayoutGrid, IconMenu2, IconX, IconCrown } from "@tabler/icons-react";
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
interface FolderItem { id: string; name: string; }
interface ChatSession { id: string; title: string; createdAt: number; updatedAt?: number; }

// ─── Extract text from any backend response shape ─────────────────────────────
// Improved: handles JSON strings without spaces, array join, and reply/content/text fields
function extractText(raw: any, depth = 0): string {
  if (depth > 10 || raw == null) return "";
  if (typeof raw === "string") {
    const trimmed = raw.trim();
    // Only try JSON parse if it looks like JSON AND has no spaces (avoids parsing prose)
    if ((trimmed.startsWith("{") || trimmed.startsWith("[")) && !trimmed.includes(" ")) {
      try { return extractText(JSON.parse(trimmed), depth + 1); } catch { return raw; }
    }
    return raw;
  }
  if (Array.isArray(raw))
    return raw.map(item => extractText(item, depth + 1)).filter(t => t.trim()).join("");
  if (typeof raw === "object") {
    // Priority order: response → content → text → reply
    if (raw.response) return extractText(raw.response, depth + 1);
    if (raw.content)  return extractText(raw.content,  depth + 1);
    if (raw.text)     return extractText(raw.text,     depth + 1);
    if (raw.reply)    return extractText(raw.reply,    depth + 1);
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
  text = text.replace(/\*(.+?)\*/g,     "<em>$1</em>");
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
const KV_LINE_RE   = /^\*{0,2}([A-Za-z][A-Za-z ]{1,28})\*{0,2}:[ \t]+(.+)$/;
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
  const v   = val.toLowerCase();
  const cls = ["online","open","good","active","operational","serviceable","completed"].includes(v)
            ? "status-online"
            : ["offline","closed","inactive","fault","immobilized","cancelled"].includes(v)
            ? "status-offline"
            : "status-neutral";
  return `<span class="status-badge ${cls}">${esc(val)}</span>`;
}

const BADGE_COLS = new Set(["status","condition","state","wostatus","ppstatus","ppmstatus"]);
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
      const val  = row[col] ?? "—";
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
  const re   = new RegExp(KV_BOUND_SRC, "g");
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
  const m    = KV_LINE_RE.exec(line);
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

  const split  = (l: string) =>
    l.split("|").map(c => c.trim()).filter((_, i, a) => i > 0 && i < a.length - 1);
  const isSep  = (l: string) =>
    /^\|[\s\-:|]+\|$/.test(l.trim()) && split(l).every(c => /^[\-:\s]+$/.test(c));

  const hasSep   = tl.length > 1 && isSep(tl[1]);
  const cols     = split(tl[0]);
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
  let   html     = "";

  let   i        = 0;

  while (i < allLines.length) {
    const line    = allLines[i];
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
      const sz = ["20px","17px","15px"][headM[1].length - 1];
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
  return `${h.slice(0,8)}-${h.slice(8,12)}-${h.slice(12,16)}-${h.slice(16,20)}-${h.slice(20)}`;
}

// ─── Static Data ─────────────────────────────────────────────────────────────
// Chat history will be implemented later

// ─── Icons ────────────────────────────────────────────────────────────────────
const IconFolder = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z"/>
  </svg>
);
const IconPlus = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
    <path d="M12 5v14M5 12h14"/>
  </svg>
);
const IconSearch = () => (
  <svg
    width="14"
    height="14"
    viewBox="0 0 24 24"
    fill="none"
    stroke="#9CA3AF"
    strokeWidth="1.7"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <circle cx="11" cy="11" r="5.5" />
    <line x1="15" y1="15" x2="20" y2="20" />
  </svg>
);
const IconHamburger = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
    <line x1="3" y1="6"  x2="21" y2="6"/>
    <line x1="3" y1="12" x2="21" y2="12"/>
    <line x1="3" y1="18" x2="21" y2="18"/>
  </svg>
);
const IconLogout = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
    <polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/>
  </svg>
);
const IconUser1 = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>
  </svg>
);
const IconChat = ({ width = 16, height = 16, style }: { width?: number; height?: number; style?: React.CSSProperties }) => (
  <svg width={width} height={height} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={style}>
    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
  </svg>
);
const IconArchive = ({ width = 16, height = 16, style }: { width?: number; height?: number; style?: React.CSSProperties }) => (
  <svg width={width} height={height} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={style}>
    <rect x="3" y="4" width="18" height="4" rx="1"/><path d="M5 8v10a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8"/><line x1="10" y1="12" x2="14" y2="12"/>
  </svg>
);
const IconLibrary = ({ width = 16, height = 16, style }: { width?: number; height?: number; style?: React.CSSProperties }) => (
  <svg width={width} height={height} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={style}>
    <line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/>
  </svg>
);
const IconCheckbox = ({ width = 16, height = 16, style }: { width?: number; height?: number; style?: React.CSSProperties }) => (
  <svg width={width} height={height} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={style}>
    <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
  </svg>
);
const IconWarning = ({ width = 14, height = 14, style }: { width?: number; height?: number; style?: React.CSSProperties }) => (
  <svg width={width} height={height} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={style}>
    <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
  </svg>
);
const IconTheme = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 3v2M12 19v2M5.64 5.64l1.41 1.41M16.95 16.95l1.41 1.41M3 12h2M19 12h2M5.64 18.36l1.41-1.41M16.95 7.05l1.41-1.41"/>
    <circle cx="12" cy="12" r="4"/>
  </svg>
);
const IconAI = () => (
  <svg width="22" height="22" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <linearGradient id="aiGrad" x1="0" y1="0" x2="32" y2="32" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#f5c249"/>
        <stop offset="50%" stopColor="#d4af37"/>
        <stop offset="100%" stopColor="#b8941f"/>
      </linearGradient>
      <radialGradient id="goldGlow" cx="50%" cy="50%">
        <stop offset="0%" stopColor="#f5c249" stopOpacity="0.8"/>
        <stop offset="100%" stopColor="#d4af37" stopOpacity="0.3"/>
      </radialGradient>
      <filter id="glow">
        <feGaussianBlur stdDeviation="2.5" result="coloredBlur"/>
        <feMerge>
          <feMergeNode in="coloredBlur"/>
          <feMergeNode in="SourceGraphic"/>
        </feMerge>
      </filter>
    </defs>
    {/* Premium golden circle with glow */}
    <circle cx="16" cy="16" r="15" fill="url(#goldGlow)" opacity="0.4"/>
    <circle cx="16" cy="16" r="14" fill="url(#aiGrad)" filter="url(#glow)"/>
    {/* Plus icon filling the circle */}
    <line x1="16" y1="6" x2="16" y2="26" stroke="#FFFFFF" strokeWidth="3" strokeLinecap="round"/>
    <line x1="6" y1="16" x2="26" y2="16" stroke="#FFFFFF" strokeWidth="3" strokeLinecap="round"/>
  </svg>
);

// ─── Main Component ───────────────────────────────────────────────────────────
export const dynamic = "force-dynamic";

export default function Home() {
  const router        = useRouter();
  // const searchParams  = useSearchParams();
  const responsive    = useResponsive();  // Auto-detect screen size
  const [userIdFromUrl, setUserIdFromUrl] = useState<string | null>(null); // display name
  const [clientNameFromUrl, setClientNameFromUrl] = useState<string | null>(null); // backend username
  const [input,        setInput]        = useState<string>("");
  const [messages,     setMessages]     = useState<Message[]>([]);
  const [isLoading,    setIsLoading]    = useState<boolean>(false);
  const [sessionId,    setSessionId]    = useState<string>(() => generateSessionId());
  const [searchVal,    setSearchVal]    = useState("");
  const [isRecording,  setIsRecording]  = useState<boolean>(false);
  const [recordingTime, setRecordingTime] = useState(0);
  const [isLocked, setIsLocked] = useState(false);
  const [recordedAudioBlob, setRecordedAudioBlob] = useState<Blob | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackTime, setPlaybackTime] = useState(0);
  const [slideGestureActive, setSlideGestureActive] = useState(false);
  const [loggedInUser, setLoggedInUser] = useState<string | null>(null); // backend username (client_name)
  const [authChecked,  setAuthChecked]  = useState<boolean>(false);
  const [menuOpen,     setMenuOpen]     = useState(false);
  const [showUpgradePlan, setShowUpgradePlan] = useState(false);
  const [sidebarOpen,  setSidebarOpen]  = useState(true);  // Will be auto-closed by useEffect if mobile is detected
  const [wsConnectionState, setWsConnectionState] = useState<'connecting'|'connected'|'failed'>('connecting');
  const [isGraphMode, setIsGraphMode] = useState<boolean>(false);
  const [chartType, setChartType] = useState<ChartType>('vertical-bar');
  const [activeFeature, setActiveFeature] = useState<'chat' | 'archived' | 'library'>('chat');
  const [showFeaturePlaceholder, setShowFeaturePlaceholder] = useState<boolean>(false);
  const [chatSessions, setChatSessions] = useState<ChatSession[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [audioPlayingIndex, setAudioPlayingIndex] = useState<number | null>(null);
  const [audioProgressMap,  setAudioProgressMap]  = useState<Record<number, number>>({});
  const [audioDurationMap,  setAudioDurationMap]  = useState<Record<number, number>>({});
  const audioDurationMapRef = useRef<Record<number, number>>({});
  const [loginPageClientLogoPath, setLoginPageClientLogoPath] = useState<string | null>(null);
  const [loginFooterLogoPath, setLoginFooterLogoPath] = useState<string | null>(null);

  // ─── Refs (declare early for use in hooks) ────────────────────────────────
  const messagesEndRef   = useRef<HTMLDivElement | null>(null);
  const inputRef         = useRef<HTMLTextAreaElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const menuRef          = useRef<HTMLDivElement>(null);
  const wsRef            = useRef<WebSocket | null>(null);
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
      const userName = params.get("userName") ?? params.get("userId"); // display only
      const clientName = params.get("clientName"); // backend username
      const clientLogo = params.get("loginPageClientLogoPath");
      const footerLogo = params.get("loginFooterLogoPath");
      setUserIdFromUrl(userName);
      if (clientName) {
        setClientNameFromUrl(clientName);
      }
      if (clientLogo) {
        setLoginPageClientLogoPath(clientLogo);
        localStorage.setItem("loginPageClientLogoPath", clientLogo);
      } else {
        setLoginPageClientLogoPath(localStorage.getItem("loginPageClientLogoPath"));
      }
      if (footerLogo) {
        setLoginFooterLogoPath(footerLogo);
        localStorage.setItem("loginFooterLogoPath", footerLogo);
      } else {
        setLoginFooterLogoPath(localStorage.getItem("loginFooterLogoPath"));
      }
    }
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
    if (responsive.isDesktop) {
      // Always show sidebar on desktop
      setSidebarOpen(true);
    } else if (responsive.isMobile) {
      // Close sidebar on mobile (user can open with menu button)
      setSidebarOpen(false);
    }
  }, [responsive.isDesktop, responsive.isMobile]);

  // Auth guard
  useEffect(() => {
    if (typeof window === "undefined") return;
    // Prefer clientNameFromUrl as backend username; fall back to userIdFromUrl
    const backendUserName = clientNameFromUrl;
    if (backendUserName) {
      localStorage.setItem("loggedInUser", backendUserName);
      setLoggedInUser(backendUserName);
      setAuthChecked(true);
      router.replace("/");
      return;
    }
    const stored = localStorage.getItem("loggedInUser");
    if (!stored) { router.replace("/login"); return; }
    // stored value is backend username (client_name)
    setLoggedInUser(stored);
    setAuthChecked(true);
  }, [router, userIdFromUrl]);

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

  // Auto-resize textarea
  const resizeTA = () => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "0px";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
    el.style.overflowY = el.scrollHeight > 160 ? "auto" : "hidden";
  };
  useEffect(() => { resizeTA(); }, [input]);

  // ── Persistent WebSocket: connect once on mount, stay open all session ───────
  const IDLE_TIMEOUT = 2 * 60 * 1000;  // 2 minutes
  const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;

  if (!baseUrl) {
    throw new Error("NEXT_PUBLIC_API_BASE_URL is not defined");
  }

  const getWsUrl = () =>
    baseUrl
      .replace(/^http:/, "ws:")
      .replace(/^https:/, "wss:") + "/api/chat";
  // const getWsUrl = () =>
  //   process.env.NEXT_PUBLIC_API_BASE_URL
  //     .replace(/^http:/,  "ws:")
  //     .replace(/^https:/, "wss:") + "/api/chat";

  // ── Start pinging only the ACTIVE session socket ──────────────────────────
  const connectWSRef = useRef<() => void>(() => {});  // forward ref for connectWS

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
        userName: loggedInUser,
        sessionId: sid,
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
        const raw     = typeof event.data === "string" ? event.data : "";

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
      console.error("❌ WebSocket error");
      setMessages(prev => [...prev, { role: "error", text: "❌ Connection failed. Retrying…" }]);
      setIsLoading(false);
    };
  };

  // Keep ref in sync so markUserActive can call connectWS
  useEffect(() => { connectWSRef.current = connectWS; });

  // Connect when component mounts (after auth is confirmed)
  useEffect(() => {
    if (!authChecked || !loggedInUser) return;

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
    [...list].sort((a, b) => (b.updatedAt ?? b.createdAt) - (a.updatedAt ?? a.createdAt));

  // Fetch chat sessions list for sidebar (new at top, old at bottom)
  useEffect(() => {
    if (!authChecked || !loggedInUser) return;

    const fetchSessions = async () => {
      try {
        const res = await fetch(`${baseUrl}/api/session`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ userName: loggedInUser, historyOnClick: false }),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        const fetched: ChatSession[] = (data?.sessions ?? []).map(
          (s: { session_id: string; title?: string; created_at?: string; updated_at?: string }) => ({
            id: s.session_id,
            title: s.title || "Chat",
            createdAt: s.created_at ? new Date(s.created_at).getTime() : Date.now(),
            updatedAt: s.updated_at ? new Date(s.updated_at).getTime() : undefined,
          })
        );
        setChatSessions(sortSessionsNewestFirst(fetched));
      } catch (err) {
        console.warn("Failed to fetch chat sessions:", err);
        setChatSessions([]);
      }
    };

    fetchSessions();
  }, [authChecked, loggedInUser]);

  const handleFeatureClick = (featureName: 'chat' | 'archived' | 'library') => {
    // Chat is the primary active feature, so don't show the "yet to be implemented" placeholder
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
          body: JSON.stringify({ userName: loggedInUser, historyOnClick: false }),
        });
        if (!res.ok) return;
        const data = await res.json();
        const fetched: ChatSession[] = (data?.sessions ?? []).map(
          (s: { session_id: string; title?: string; created_at?: string; updated_at?: string }) => ({
            id: s.session_id,
            title: s.title || "Chat",
            createdAt: s.created_at ? new Date(s.created_at).getTime() : Date.now(),
            updatedAt: s.updated_at ? new Date(s.updated_at).getTime() : undefined,
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
      } catch (err) {
        console.warn("Failed to refetch sessions:", err);
      }
    };
    setTimeout(() => refetchSessions(), 400);
  };

  // ── Process loaded messages: convert raw JSON to formatted tables ─────────
  const processLoadedMessages = (msgs: Message[]): Message[] => {
    return msgs.map(m => {
      if (m.role !== "ai") return m;
      
      const text = m.text || "";
     
      // 🔑 FIRST: Check if this is a GRAPH response
      const graphData = parseGraphData(text);
      if (graphData) {
        console.log("📊 [HISTORY] Graph response detected — keeping as raw JSON for chart");
        return { ...m, text, isGraphResponse: true };  // ← Mark as graph
      }
     
      // Check if already formatted (contains HTML tags)
        if (
      text.includes('<table') || 
      text.includes('<div class=') || 
      text.includes('<div style=') ||
      text.includes('large-dataset-wrapper')
    ) {
      console.log("✅ [HISTORY] Message already HTML formatted (from cache) - skipping");
      // Try to extract table data from HTML
      const rows = extractTableRows(text);
      if (rows.length > 0) {
        return { ...m, text, tableData: rows, tableTitle: "Data Results" };
      }
      return m;
    }
          
      // Extract response content (removes session_id wrapper)
      const cleanedText = decodeEntities(extractResponseContent(text));
     
      // ALWAYS TRY RENDERING AS UNIFIED TABLE STRUCTURE FIRST (ALL SIZES)
      const largeDatasetHTML = renderLargeDataset(cleanedText);
      if (largeDatasetHTML) {
        console.log("✅ [HISTORY] Rendered as unified table structure");
        // Always extract table rows for TableWithTile
        const rows = extractTableRows(largeDatasetHTML);
        if (rows.length > 0) {
          return { ...m, text: largeDatasetHTML, tableData: rows, tableTitle: "Data" };
        }
        return { ...m, text: largeDatasetHTML };
      }
      
      // Not tabular data → try to format as text
      try {
        const formattedText = formatOutput(cleanedText);
        console.log("✅ [HISTORY] Formatted as text output");
        return { ...m, text: formattedText };
      } catch (err) {
        // Not JSON → treat as already formatted or plain text
        console.log("📝 [HISTORY] Not JSON - keeping as is");
        return m;
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

    // Refresh from backend to get latest titles; do not move clicked chat to top (just highlight)
    const refreshSessions = async () => {
      if (!loggedInUser) return;
      try {
        const res = await fetch(`${baseUrl}/api/session`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ userName: loggedInUser, historyOnClick: false }),
        });
        if (!res.ok) return;
        const data = await res.json();
        const fetched: ChatSession[] = (data?.sessions ?? []).map(
          (s: { session_id: string; title?: string; created_at?: string; updated_at?: string }) => ({
            id: s.session_id,
            title: s.title || "Chat",
            createdAt: s.created_at ? new Date(s.created_at).getTime() : Date.now(),
            updatedAt: s.updated_at ? new Date(s.updated_at).getTime() : undefined,
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
          body: JSON.stringify({ userName: loggedInUser, sessionId: targetSid, historyOnClick: true }),
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
  router.replace("/login");
};
  const toggleRecording = async () => {
    if (isRecording) {
      mediaRecorderRef.current?.stop();
      setIsRecording(false);
    } else {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        const rec    = new MediaRecorder(stream);
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
  if (!input.trim() || isLoading) return;
  const userText = input.trim();

  const ws = wsRef.current;

  if (!ws || ws.readyState !== WebSocket.OPEN) {
    console.warn("Socket not ready for session:", sessionId);
    setMessages(prev => [...prev, { role: "error", text: "Still connecting. Please wait." }]);
    return;
  }

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
  setInput("");
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
    subUserName: userIdFromUrl,
    sessionId,
    timestamp: Date.now()
  }));
};
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  };

  const { theme } = useTheme();
  const isLanding = messages.length === 0;

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
        <span style={{ fontSize: 14, color: "#A0AEC0" }}>Checking authentication…</span>
      </div>
    );
  }

  return (
    <div className="app-container app-container-with-bg">
      <BackgroundLayer theme={theme} />
      {/* Content above background (MainLayout-style) */}
      <div className="app-content-wrapper">
      {/* ── Sidebar ─────────────────────────────────────────────────────── */}
      <div 
        className="sidebar-shell" 
        style={{ 
          display: sidebarOpen ? 'flex' : responsive.isMobile ? 'none' : 'flex',
          position: responsive.isMobile && sidebarOpen ? 'fixed' : 'relative',
          top: 0,
          left: 0,
          zIndex: responsive.isMobile && sidebarOpen ? 9999 : 2,
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
          {responsive.isMobile && (
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
                  <IconUser  />
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
                  className="profile-dropdown-item profile-action-btn profile-logout"
                  onClick={handleLogout}
                >
                  <IconLogout />
                  <span>Logout</span>
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
        <div className="new-chat-container-top">
          <button className="new-chat-btn" onClick={handleNewChat}>
            <IconChat width={16} height={16}/>
            <span>+ New Chat</span>
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
            }}
          >
            <IconChat/>
            <span>Chat</span>
          </div>
          <div
            className={`feature-item ${activeFeature === 'archived' ? 'active' : ''}`}
            onClick={() => {
              setActiveFeature('archived');
              handleFeatureClick('archived');
            }}
          >
            <IconArchive/>
            <span>Archived</span>
          </div>
          <div
            className={`feature-item ${activeFeature === 'library' ? 'active' : ''}`}
            onClick={() => {
              setActiveFeature('library');
              handleFeatureClick('library');
            }}
          >
            <IconLibrary/>
            <span>Library</span>
          </div>

          {showFeaturePlaceholder && (
            <div className="feature-placeholder-sidebar">
              <div className="feature-placeholder-box">
                <div className="feature-placeholder-title">
                  {activeFeature === 'archived' ? 'Archived' : 'Library'}
                </div>
                <div className="feature-placeholder-subtitle">
                  Yet to be implemented
                </div>
              </div>
            </div>
          )}

          {/* Chat History – only visible when Chat feature is active */}
          {activeFeature === 'chat' && (
            
            <div className="chat-history-box" style={{ marginTop: 24, display: "flex", flexDirection: "column", minHeight: 0 }}>
              <div className="chat-history-scroll">
                {chatSessions.map(s => (
                  <div
                    key={s.id}
                    className={`sidebar-item${s.id === sessionId ? " active" : ""}`}
                    onClick={() => switchSession(s.id)}
                    style={{ cursor: "pointer" }}
                  >
                    <div className="content">
                      <IconChat width={16} height={16}/>
                      <span style={{ whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                        {s.title}
                      </span>
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

        {/* Profile Card - Toggle on Hamburger Click */}
       
       

        {/* Beta Version Disclaimer */}
        <div className="sidebar-disclaimer">
          <IconWarning width={14} height={14}/>
          <div>
            <div style={{ fontSize: 11, fontWeight: 600, marginBottom: 2 }}>BETA VERSION</div>
            <div style={{ fontSize: 10, lineHeight: 1.4 }}>
              NanoSoft Ask AI is currently in beta. Responses may be incomplete or inaccurate and should not be treated as formal legal advice.
            </div>
          </div>
        </div>
      </aside>
      </div>

      {/* ── Main Content ─────────────────────────────────────────────────── */}
      <div className="main-content">

        {/* Mobile Header with Menu Button - sticky at top */}
        {responsive.isMobile && (
          <div
            style={{
              position: 'sticky',
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
              zIndex: 100,
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
        {responsive.isMobile && sidebarOpen && (
          <div
            style={{
              position: 'fixed',
              inset: 0,
              backgroundColor: 'rgba(0, 0, 0, 0.5)',
              zIndex: 9998,
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
                  }}/>
                ))}
              </div>
              <span style={{ fontSize: 13, color: "#A0AEC0" }}>Loading chat history…</span>
            </div>
          </div>
        )}

        {/* Landing */}
        {!historyLoading && isLanding && (
          <div className="landing-container">
            <div className="landing-card">
              <h1
                style={{
                  fontSize: 32,
                  fontWeight: 700,
                  marginBottom: 16,
                  background: "linear-gradient(180deg, #AE8625 0%, #F7EF8A 35%, #D2AC47 65%, #EDC967 100%)",
                  backgroundSize: "200% 200%",
                  WebkitBackgroundClip: "text",
                  backgroundClip: "text",
                  WebkitTextFillColor: "transparent",
                  animation: "goldShine 3s ease-in-out infinite",
                }}
              >
                Welcome to Ask AI
              </h1>
              <p className="landing-subtitle">Let's work together buddy</p>
            </div>
          </div>
        )}

        {/* Chat area */}
        {!historyLoading && !isLanding && (
          <div className="chat-scroll-area">
            <div className="messages-container">
              {messages.map((msg, idx) => {
                const isUser      = msg.role === "user";
                const isError     = msg.role === "error";
                const isStreaming = msg.streaming === true;
                const isAudio     = msg.isAudio === true;
                const isGraphMsg  = msg.isGraphResponse === true;  // ← Use explicit flag
               
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
                      <div className="avatar-box"><IconAI/></div>
                    )}

                    <div className={`message-bubble ${msg.role}${isGraphMsg ? ' graph-message' : ''}`}>

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
                          <span className="stream-cursor"/>
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

                    </div>
                  </div>
                );
              })}

              {isLoading && (
                <div className="loading-indicator">
                  <div className="avatar-box"><IconAI/></div>
                  <div className="loading-dots-box">
                    {[0, 1, 2].map(i => (
                      <span key={i} style={{
                        display: "inline-block", width: 7, height: 7,
                        borderRadius: "50%", background: "#d4af37",
                        animation: `bounce 1.2s ease-in-out ${i * 0.2}s infinite`,
                      }}/>
                    ))}
                  </div>
                </div>
              )}
              <div ref={messagesEndRef}/>
            </div>
          </div>
        )}

        {/* Input footer */}
        <div className="input-footer">
          {voiceRecorder.isRecording && (
            <div className={`voice-recording-overlay${voiceRecorder.closingRecording ? ' closing' : ''}`}>
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
            <div className="input-wrapper">
              <textarea
                ref={inputRef}
                className="main-input"
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                disabled={isLoading || wsConnectionState !== 'connected'}
                placeholder={wsConnectionState === 'connected' ? "Ask Anything..." : "Waiting for connection…"}
                rows={1}
              />
              <VoiceMicButton
                forwardedRef={voiceRecorder.micButtonRef}
                onClick={voiceRecorder.toggleRecording}
                disabled={isLoading || wsConnectionState !== 'connected' || voiceRecorder.recordedAudioBlob !== null}
              />
              <button
                onClick={() => setIsGraphMode(p => !p)}
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
              <button className="send-btn" onClick={sendMessage} disabled={isLoading || wsConnectionState !== 'connected' || !input.trim()}>
                <IconArrowUp size={16} color="white" stroke={2}/>
              </button>
            </div>
          )}
          <p className="footer-disclaimer">NanoSoft Ask AI can make mistakes. Verify important legal information.</p>
        </div>

        {/* Upgrade Plan Modal */}
        {showUpgradePlan && (
          <div 
            className="upgrade-plan-backdrop"
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
              <UpgradePlan />
            </div>
          </div>
        )}
        
        {/* Walkthrough Popup */}
        <WalkthroughPopup />
      </div>
      </div>
    </div>
  );
}