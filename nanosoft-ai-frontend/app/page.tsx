"use client";

import { useState, useRef, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Image from "next/image";
import { ThemeToggle } from "./components/ThemeToggle";
import BackgroundLayer from "./components/BackgroundLayer";
import { useTheme } from "./components/useTheme";
import { IconUser } from "@tabler/icons-react";
// ─── Types ───────────────────────────────────────────────────────────────────
interface Message {
  role: "user" | "ai" | "error";
  text: string;
  streaming?: boolean;
}
interface FolderItem { id: string; name: string; }

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

// ── Regex: matches "Key: value" or "**Key**: value" (key 2–30 alpha chars) ────
const KV_LINE_RE   = /^\*{0,2}([A-Za-z][A-Za-z ]{1,28})\*{0,2}:[ \t]+(.+)$/;
// Multi-KV on one line: "Key: Val, Key: Val"
const KV_BOUND_SRC = String.raw`(?:^|(?:,\s+))([A-Za-z][A-Za-z ]{0,25}?):\s*`;

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

// ── Build HTML <table> from rows ──────────────────────────────────────────────
function buildTable(rows: Record<string, string>[], cols?: string[]): string {
  if (!rows.length) return "";

  // Collect column order preserving insertion order
  const allCols: string[] = cols ?? (() => {
    const seen: string[] = [];
    rows.forEach(r => Object.keys(r).forEach(k => { if (!seen.includes(k)) seen.push(k); }));
    return seen;
  })();

  const thead = `<thead><tr>${allCols.map(c => `<th>${esc(c)}</th>`).join("")}</tr></thead>`;

  const tbody = `<tbody>${rows.map((row, ri) =>
    `<tr${ri % 2 === 1 ? ' class="row-even"' : ""}>${allCols.map(col => {
      const val  = row[col] ?? "—";
      const cell = isBadgeCol(col) ? badge(val) : esc(val);
      return `<td>${cell}</td>`;
    }).join("")}</tr>`
  ).join("")}</tbody>`;

  const tfoot = `<tfoot><tr><td colspan="${allCols.length}" class="table-footer">${rows.length} row${rows.length !== 1 ? "s" : ""}</td></tr></tfoot>`;

  return `<div class="table-wrapper"><table class="ai-table">${thead}${tbody}${tfoot}</table></div>`;
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
function formatOutput(text: string): string {
  if (!text.trim()) return "";

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
    if (/^\|.+\|$/.test(trimmed)) {
      const block: string[] = [];
      while (i < allLines.length && /^\|.+\|$/.test(allLines[i].trim())) {
        block.push(allLines[i].trim()); i++;
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
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/>
  </svg>
);
const IconSend = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <line x1="12" y1="19" x2="12" y2="5"/>
    <polyline points="5 12 12 5 19 12"/>
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
  // const userIdFromUrl = searchParams.get("userId");
  const [userIdFromUrl, setUserIdFromUrl] = useState<string | null>(null);
  const [input,        setInput]        = useState<string>("");
  const [messages,     setMessages]     = useState<Message[]>([]);
  const [isLoading,    setIsLoading]    = useState<boolean>(false);
  const [sessionId,    setSessionId]    = useState<string>(() => generateSessionId());
  const [searchVal,    setSearchVal]    = useState("");
  const [isRecording,  setIsRecording]  = useState<boolean>(false);
  const [loggedInUser, setLoggedInUser] = useState<string | null>(null);
  const [authChecked,  setAuthChecked]  = useState<boolean>(false);
  const [menuOpen,     setMenuOpen]     = useState(false);
  const [wsConnectionState, setWsConnectionState] = useState<'connecting'|'connected'|'failed'>('connecting');
  const [activeFeature, setActiveFeature] = useState<'chat' | 'archived' | 'library'>('chat');
  const [showFeaturePlaceholder, setShowFeaturePlaceholder] = useState<boolean>(false);

  const messagesEndRef   = useRef<HTMLDivElement | null>(null);
  const inputRef         = useRef<HTMLTextAreaElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const menuRef          = useRef<HTMLDivElement>(null);
  const socketsRef = useRef<Map<string, WebSocket>>(new Map());
  const sessionIdRef = useRef<string>(sessionId);
  const wsConnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectDelayRef = useRef(2000);

  // Close dropdown on outside click
  useEffect(() => {
  if (typeof window !== "undefined") {
    const params = new URLSearchParams(window.location.search);
    setUserIdFromUrl(params.get("userId"));
  }
  }, []);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  // Auth guard
  useEffect(() => {
    if (typeof window === "undefined") return;
    if (userIdFromUrl) {
      localStorage.setItem("loggedInUser", userIdFromUrl);
      setLoggedInUser(userIdFromUrl);
      setAuthChecked(true);
      router.replace("/");
      return;
    }
    const stored = localStorage.getItem("loggedInUser");
    if (!stored) { router.replace("/login"); return; }
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
  const accRef = useRef<string>("");   // accumulates current response text
  const pingRef = useRef<ReturnType<typeof setInterval> | null>(null);   // ping for ACTIVE session only
  const userActiveRef = useRef<boolean>(true);  // is user actively using the page?
  const idleTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const IDLE_TIMEOUT = 2 * 60 * 1000;  // 2 minutes
  const baseUrl = "https://dev.axtr.in";

  if (!baseUrl) {
    throw new Error("NEXT_PUBLIC_API_BASE_URL is not defined");
  }

  const getWsUrl = () =>
    baseUrl
      .replace(/^http:/, "ws:")
      .replace(/^https:/, "wss:") + "/ws/chat";
  // const getWsUrl = () =>
  //   process.env.NEXT_PUBLIC_API_BASE_URL
  //     .replace(/^http:/,  "ws:")
  //     .replace(/^https:/, "wss:") + "/ws/chat";

  // ── Start pinging only the ACTIVE session socket ──────────────────────────
  const connectWSRef = useRef<() => void>(() => {});  // forward ref for connectWS

  const startPingForActiveSession = () => {
    // Clear any previous ping interval
    if (pingRef.current) { clearInterval(pingRef.current); pingRef.current = null; }

    pingRef.current = setInterval(() => {
      if (!userActiveRef.current) return; // user idle → don't ping anything
      const activeSid = sessionIdRef.current;
      const ws = socketsRef.current.get(activeSid);
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send("ping");
      }
    }, 30_000);
  };

  // ── User activity detection ───────────────────────────────────────────────
  const markUserActive = () => {
    const wasIdle = !userActiveRef.current;
    userActiveRef.current = true;

    // Reset idle timer
    if (idleTimerRef.current) clearTimeout(idleTimerRef.current);
    idleTimerRef.current = setTimeout(() => {
      userActiveRef.current = false;
      // Stop pinging — backend will close idle sockets after its timeout
      if (pingRef.current) { clearInterval(pingRef.current); pingRef.current = null; }
      console.log("💤 User idle — stopped pinging, sockets will auto-close");
    }, IDLE_TIMEOUT);

    // If user was idle and came back, reconnect the active session if needed
    if (wasIdle) {
      const activeSid = sessionIdRef.current;
      const ws = socketsRef.current.get(activeSid);
      if (!ws || ws.readyState !== WebSocket.OPEN) {
        console.log("🔄 User active again — reconnecting...");
        connectWSRef.current();
      }
      startPingForActiveSession();
    }
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
    const sid = sessionIdRef.current;
    setWsConnectionState('connecting');
    const ws = new WebSocket(getWsUrl());
    socketsRef.current.set(sid, ws);

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
      console.log("✅ WebSocket connected:", sid);
      startPingForActiveSession();
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
          setMessages(prev => {
            const u = [...prev];
            const l = u.length - 1;
            if (u[l]?.role === "ai") u[l] = { role: "ai", text: finalText, streaming: false };
            return u;
          });
          accRef.current = "";          // reset for next message
          setIsLoading(false);
          setTimeout(() => inputRef.current?.focus(), 50);
          return;
        }

        const part = extractText(JSON.parse(jsonStr));
        if (part) {
          accRef.current += part;
          const snap = accRef.current;
          setMessages(prev => {
            const u = [...prev];
            const l = u.length - 1;
            // If last message is already our streaming AI bubble → update it
            if (u[l]?.role === "ai" && u[l]?.streaming === true) {
              u[l] = { role: "ai", text: snap, streaming: true };
            } else {
              // First chunk → create the AI bubble now (only once)
              u.push({ role: "ai", text: snap, streaming: true });
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
      setWsConnectionState('failed');
      console.warn("⚠️ WebSocket closed:", sid);
      socketsRef.current.delete(sid);

      if (sid === sessionIdRef.current) {
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
  if (!authChecked) return;

  // Capture ref value for cleanup
  const sockets = socketsRef.current;
  connectWS();

  return () => {
    if (pingRef.current) { clearInterval(pingRef.current); pingRef.current = null; }
    if (idleTimerRef.current) { clearTimeout(idleTimerRef.current); idleTimerRef.current = null; }
    if (wsConnectTimeoutRef.current) { clearTimeout(wsConnectTimeoutRef.current); wsConnectTimeoutRef.current = null; }
    sockets.forEach(ws => ws.close());
    sockets.clear();
  };
},[authChecked]);

  const handleFeatureClick = (featureName: string) => {
    // For now these sections are not implemented; just show the placeholder card
    setShowFeaturePlaceholder(true);
  };

  const handleNewChat = () => {
    // Stop pinging old session (it will auto-close after backend timeout)
    if (pingRef.current) { clearInterval(pingRef.current); pingRef.current = null; }
    // DON'T close old sockets — let them live until backend times them out

    setShowFeaturePlaceholder(false);
    setMessages([]);
    accRef.current = "";
    setIsLoading(false);

    // Generate new session and update ref immediately so connectWS picks it up
    const newSessionId = generateSessionId();
    setSessionId(newSessionId);
    sessionIdRef.current = newSessionId;

    // Open a fresh socket for the new session, pings start automatically
    connectWS();
  };

const handleLogout = () => {
  if (pingRef.current) { clearInterval(pingRef.current); pingRef.current = null; }
  if (idleTimerRef.current) { clearTimeout(idleTimerRef.current); idleTimerRef.current = null; }
  socketsRef.current.forEach(ws => ws.close());
  socketsRef.current.clear();

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

  // ── Send message over the persistent WebSocket ────────────────────────────
  const sendMessage = () => {
  if (!input.trim() || isLoading) return;
  const userText = input.trim();

  const ws = socketsRef.current.get(sessionId);

  if (!ws || ws.readyState !== WebSocket.OPEN) {
    console.warn("Socket not ready for session:", sessionId);
    setMessages(prev => [...prev, { role: "error", text: "Still connecting. Please wait." }]);
    return;
  }

  setShowFeaturePlaceholder(false);
  setMessages(prev => [...prev, { role: "user", text: userText }]);
  setInput("");
  setIsLoading(true);
  accRef.current = "";

  ws.send(JSON.stringify({
    query: userText,
    userId: loggedInUser,
    sessionId
  }));
};
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  };

  const { theme } = useTheme();
  const isLanding = messages.length === 0;

  if (!authChecked) {
    return (
      <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center",
        background: ` 
            linear-gradient(135deg, #0A0A0A 0%, #111111 50%, #0A0A0A 100%)`}}>
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
      <div className="sidebar-shell">
      <aside className="sidebar">
        {/* Sidebar Header with Logo */}
        <div className="sidebar-header">
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <div className="brand-box">
              <Image src="/icon.png" alt="Nanosoft Ask AI" width={20} height={20} style={{ borderRadius: 0 }}/>
            </div>
            <span style={{ 
              fontSize: 14, 
              fontWeight: 600, 
              background: "linear-gradient(180deg, #AE8625 0%, #F7EF8A 35%, #D2AC47 65%, #EDC967 100%)",
              backgroundSize: "200% 200%",
              WebkitBackgroundClip: "text",
              backgroundClip: "text",
              WebkitTextFillColor: "transparent",
              animation: "goldShine 3s ease-in-out infinite"
            }}>ASK AI</span>
          </div>
          <div />
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
                    {/* <span className="profile-label">LOGGED IN AS</span> */}
                    <span className="profile-userid">{loggedInUser}</span>
                  </div>
                </div>
                <div className="profile-divider" />
                <div className="profile-dropdown-item profile-action-btn">
                  <ThemeToggle />
                </div>
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

        {/* FEATURES Section */}
        <div className="sidebar-scroll">
          <div className="section-title">FEATURES</div>
          <div 
            className={`feature-item ${activeFeature === 'chat' ? 'active' : ''}`}
            onClick={() => {
              setActiveFeature('chat');
              handleFeatureClick('Chat');
            }}
          >
            <IconChat/>
            <span>Chat</span>
          </div>
          <div 
            className={`feature-item ${activeFeature === 'archived' ? 'active' : ''}`}
            onClick={() => {
              setActiveFeature('archived');
              handleFeatureClick('Archived');
            }}
          >
            <IconArchive/>
            <span>Archived</span>
          </div>
          <div 
            className={`feature-item ${activeFeature === 'library' ? 'active' : ''}`}
            onClick={() => {
              setActiveFeature('library');
              handleFeatureClick('Library');
            }}
          >
            <IconLibrary/>
            <span>Library</span>
          </div>

          {showFeaturePlaceholder && (
            <div className="feature-placeholder-sidebar">
              <div className="feature-placeholder-box">
                <div className="feature-placeholder-title">
                  {activeFeature === 'chat' ? 'Chat' : activeFeature === 'archived' ? 'Archived' : 'Library'}
                </div>
                <div className="feature-placeholder-subtitle">
                  Yet to be implemented
                </div>
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

        {/* Header with profile dropdown (like DigiRett) */}
        

        {/* Landing */}
        {isLanding && (
          <div className="landing-container">
            {/* <div style={{ marginBottom: 24, opacity: 0.5 }}>
              <Image src="/nanosoft_logo.png" alt="" width={560} height={200}
                style={{ width: "auto", height: "auto", maxWidth: "min(600px,90vw)", maxHeight: 200, objectFit: "contain" }}/>
            </div> */}
            <div className="landing-card">
              <h1 style={{ 
                fontSize: 32, 
                fontWeight: 700, 
                marginBottom: 16,
                background: "linear-gradient(180deg, #AE8625 0%, #F7EF8A 35%, #D2AC47 65%, #EDC967 100%)",
                backgroundSize: "200% 200%",
                WebkitBackgroundClip: "text",
                backgroundClip: "text",
                WebkitTextFillColor: "transparent",
                animation: "goldShine 3s ease-in-out infinite"
              }}>
                Welcome to Ask AI
              </h1>
              <p className="landing-subtitle">
                Let's work together buddy
              </p>
            </div>
          </div>
        )}

        {/* Chat area */}
        {!isLanding && (
          <div className="chat-scroll-area">
            <div className="messages-container">
              {messages.map((msg, idx) => {
                const isUser      = msg.role === "user";
                const isError     = msg.role === "error";
                const isStreaming = msg.streaming === true;

                return (
                  <div key={idx} className={`message-row ${msg.role}`}>
                    {!isUser && !isError && (
                      <div className="avatar-box"><IconAI/></div>
                    )}

                    <div className={`message-bubble ${msg.role}`}>

                      {isUser || isError ? (
                        /* ── User / Error: plain text ── */
                        <>{msg.text}</>

                      ) : isStreaming ? (
                        /* ── Streaming: pre-wrap plain text + blinking cursor ── */
                        <div className="ai-bubble streaming-text">
                          {msg.text}
                          <span className="stream-cursor"/>
                        </div>

                      ) : (
                        /* ── Complete: run formatOutput() → HTML table ── */
                        <div className="ai-bubble">
                         <div dangerouslySetInnerHTML={{ __html: formatOutput(msg.text) }} />
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
          {wsConnectionState !== 'connected' && (
            <div style={{
              fontSize: 12, color: "#6b7280", marginBottom: 6, display: "flex", alignItems: "center", gap: 6,
            }}>
              <span style={{
                width: 6, height: 6, borderRadius: "50%", background: wsConnectionState === "connecting" ? "#f59e0b" : "#ef4444",
                animation: wsConnectionState === "connecting" ? "pulse 1.5s ease-in-out infinite" : undefined,
              }}/>
              {wsConnectionState === "connecting" ? "Connecting…" : "Reconnecting…"}
            </div>
          )}
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
            <button className="send-btn" onClick={sendMessage} disabled={isLoading || wsConnectionState !== 'connected' || !input.trim()}>
              <IconSend/>
            </button>
          </div>
          <p className="footer-disclaimer">NanoSoft Ask AI can make mistakes. Verify important legal information.</p>
        </div>

      </div>
      </div>
    </div>
  );
}