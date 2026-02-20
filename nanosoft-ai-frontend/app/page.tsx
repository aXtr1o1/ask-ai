"use client";

import { useState, useRef, useEffect, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Image from "next/image";

// ─── Types ───────────────────────────────────────────────────────────────────
interface Message {
  role: "user" | "ai" | "error";
  text: string;
  streaming?: boolean;
}
interface FolderItem { id: string; name: string; }

// ─── Extract text from any backend response shape ─────────────────────────────
function extractText(raw: any, depth = 0): string {
  if (depth > 10 || raw == null) return "";
  if (typeof raw === "string") {
    const t = raw.trim();
    if (t.startsWith("{") || t.startsWith("[")) {
      try { return extractText(JSON.parse(t), depth + 1); } catch { return raw; }
    }
    return raw;
  }
  if (Array.isArray(raw))
    return raw.map(x => extractText(x, depth + 1)).filter(t => t.trim()).join(" ");
  if (typeof raw === "object") {
    for (const k of ["response", "content", "text", "reply"])
      if (raw[k]) return extractText(raw[k], depth + 1);
    return "";
  }
  return String(raw);
}

// ═══════════════════════════════════════════════════════════════════════════════
//  UNIVERSAL TABULAR FORMATTER
//
//  Converts ANY structured model output → clean HTML <table> matching the
//  "Tabular Data" image: columns auto-detected, header row, data rows.
//
//  Handles ALL formats the model may return:
//  ┌─────────────────────────────────────────────────────────────────────┐
//  │ FMT-1  Bullet KV   "• Key1: Val, Key2: Val, Key3: Val"             │
//  │ FMT-2  Numbered KV "1. Key1: Val, Key2: Val"                       │
//  │ FMT-3  Plain KV    "Key1: Val\nKey2: Val\n\nKey1: Val\n..."        │
//  │ FMT-4  Pipe table  "| Col | Col |\n|---|\n| V | V |"              │
//  └─────────────────────────────────────────────────────────────────────┘
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

// ── Build <table> from an array of row objects ────────────────────────────────
function buildTable(rows: Record<string, string>[], cols?: string[]): string {
  if (!rows.length) return "";

  // Auto-collect column order from all rows
  const allCols: string[] = cols ?? (() => {
    const seen: string[] = [];
    rows.forEach(r => Object.keys(r).forEach(k => { if (!seen.includes(k)) seen.push(k); }));
    return seen;
  })();

  // Status badge renderer
  const badge = (val: string) => {
    const v = val.toLowerCase();
    const cls = v === "online"  ? "status-online"
              : v === "offline" ? "status-offline"
              :                   "status-neutral";
    return `<span class="status-badge ${cls}">${esc(val)}</span>`;
  };

  // Header row
  const thead = `
    <thead>
      <tr>${allCols.map(c => `<th>${esc(c)}</th>`).join("")}</tr>
    </thead>`;

  // Body rows
  const tbody = `
    <tbody>
      ${rows.map(row =>
        `<tr>${allCols.map(col => {
          const val  = row[col] ?? "—";
          const cell = col.toLowerCase() === "status" ? badge(val) : esc(val);
          // Long-value columns (Location, Description, Notes etc) get wrap class
          const isLong = col.toLowerCase().includes("location") ||
                         col.toLowerCase().includes("description") ||
                         col.toLowerCase().includes("address") ||
                         col.toLowerCase().includes("notes") ||
                         val.length > 40;
          return `<td${isLong ? ' class="wrap"' : ""}>${cell}</td>`;
        }).join("")}</tr>`
      ).join("\n      ")}
    </tbody>`;

  // Row count shown as a clean tfoot row instead of a separate div
  // (separate div caused vertical character rendering bug)
  const tfoot = `<tfoot><tr><td colspan="${allCols.length}" class="table-footer">${rows.length} row${rows.length !== 1 ? "s" : ""}</td></tr></tfoot>`;

  return `<div class="table-wrapper"><table class="ai-table">${thead}${tbody}${tfoot}</table></div>`;
}

// ── REGEX constants ───────────────────────────────────────────────────────────
// Matches "Key:" boundary after start-of-string or ", "
const KV_BOUND_SRC = String.raw`(?:^|(?:,\s+))([A-Za-z][A-Za-z ]{0,25}?):\s*`;
// Matches a single plain "Key: Value" line
// Matches plain "Key: Value" OR "**Key**: Value" (bold keys)
const PLAIN_KV_RE  = /^\*{0,2}([A-Za-z][A-Za-z ]{0,28})\*{0,2}:\s*(.+)$/;

// ── FMT-1 / FMT-2: Parse one bullet/numbered line with "Key: Val, Key: Val" ──
function parseBulletKV(rawLine: string): Record<string, string> | null {
  // Strip bullet/number prefix
  // Strip bullet/number prefix
  let line = rawLine.replace(/^[\s]*(?:[-*•]|\d+[.)]) ?/, "").trim();
  if (!line) return null;

  // ⚡ Strip **bold** and *italic* markdown — model often bolds keys:
  //    "• **Asset Tag**: X, **Barcode**: Y" → "• Asset Tag: X, Barcode: Y"
  line = line.replace(/\*\*(.+?)\*\*/g, "$1").replace(/\*(.+?)\*/g, "$1");

  const re   = new RegExp(KV_BOUND_SRC, "g");
  const hits: { key: string; vs: number; rs: number }[] = [];
  let   m:   RegExpExecArray | null;

  while ((m = re.exec(line)) !== null) {
    const key = m[1].trim();
    // Reject empty keys, keys with digits, or over-long keys
    if (!key || /\d/.test(key) || key.length > 30) continue;
    hits.push({ key, vs: m.index + m[0].length, rs: m.index });
  }

  if (hits.length < 2) return null;

  const result: Record<string, string> = {};
  for (let i = 0; i < hits.length; i++) {
    // Slice from this key's value start to next key's raw start
    const end = i + 1 < hits.length ? hits[i + 1].rs : line.length;
    result[hits[i].key] = line.slice(hits[i].vs, end).replace(/,\s*$/, "").trim() || "—";
  }

  return Object.keys(result).length >= 2 ? result : null;
}

// ── FMT-3: Parse plain "Key: Value" lines separated by blank lines into rows ──
function parsePlainKVBlocks(lines: string[]): Record<string, string>[] | null {
  const blocks: Record<string, string>[] = [];
  let   cur:    Record<string, string>   = {};

  const flush = () => {
    if (Object.keys(cur).length >= 2) { blocks.push(cur); }
    cur = {};
  };

  for (const raw of lines) {
    const line = raw.trim();
    if (line === "") { flush(); continue; }
    const m = PLAIN_KV_RE.exec(line);
    if (m) {
      cur[m[1].trim()] = m[2].trim();
    } else {
      return null;  // non-KV line found — abort
    }
  }
  flush();

  return blocks.length >= 1 ? blocks : null;
}

// ── FMT-4: Parse markdown pipe-table lines ────────────────────────────────────
function parsePipeTable(lines: string[]): { cols: string[]; rows: Record<string, string>[] } | null {
  const tl = lines.filter(l => /^\|.+\|$/.test(l.trim()));
  if (tl.length < 2) return null;

  const split = (l: string) =>
    l.split("|").map(c => c.trim()).filter((_, i, a) => i > 0 && i < a.length - 1);

  const cols = split(tl[0]);
  const rows = tl.slice(2).map(l => {
    const cells = split(l);
    const row: Record<string, string> = {};
    cols.forEach((c, i) => { row[c] = cells[i] ?? "—"; });
    return row;
  });

  return { cols, rows };
}

// ══════════════════════════════════════════════════════════════════════════════
//  MASTER formatOutput()
//  Walks the raw model text line-by-line.
//  Detects structured blocks and emits <table> HTML.
//  Falls back to styled prose for non-structured content.
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
      html += '<div style="height:8px"></div>';
      i++;
      continue;
    }

    // ── FMT-4: Pipe table ──────────────────────────────────────────────────
    if (/^\|.+\|$/.test(trimmed)) {
      const block: string[] = [];
      while (i < allLines.length && /^\|.+\|$/.test(allLines[i].trim())) {
        block.push(allLines[i].trim());
        i++;
      }
      const parsed = parsePipeTable(block);
      if (parsed) {
        html += buildTable(parsed.rows, parsed.cols);
      } else {
        html += block.map(l => `<div>${md(l)}</div>`).join("");
      }
      continue;
    }

    // ── FMT-1 / FMT-2: Bullet / numbered lines ─────────────────────────────
    if (/^[\s]*(?:[-*•]|\d+[.)]) /.test(line)) {
      const block: string[] = [];
      while (
        i < allLines.length &&
        allLines[i].trim() !== "" &&
        /^[\s]*(?:[-*•]|\d+[.)]) /.test(allLines[i])
      ) {
        block.push(allLines[i]);
        i++;
      }

      const kvRows  = block.map(parseBulletKV);
      const validKV = kvRows.filter(Boolean) as Record<string, string>[];

      if (validKV.length >= Math.ceil(block.length * 0.5)) {
        // ✅ Most lines are KV pairs → render as table
        html += buildTable(validKV);
      } else {
        // Regular unordered list
        html += '<ul style="margin:8px 0 8px 20px;padding:0;list-style:disc">';
        block.forEach(bl => {
          const t = bl.replace(/^[\s]*(?:[-*•]|\d+[.)]) ?/, "").trim();
          html += `<li style="margin:4px 0;line-height:1.6">${md(t)}</li>`;
        });
        html += "</ul>";
      }
      continue;
    }

    // ── FMT-3: Plain "Key: Value" block ────────────────────────────────────
    if (PLAIN_KV_RE.test(trimmed)) {
      // Collect all consecutive KV lines (blank lines separate records)
      const block: string[] = [];
      let j = i;
      while (j < allLines.length) {
        const t = allLines[j].trim();
        if (t === "" || PLAIN_KV_RE.test(t)) {
          block.push(allLines[j]);
          j++;
        } else break;
      }
      // Remove trailing blank lines from block
      while (block.length && block[block.length - 1].trim() === "") block.pop();

      if (block.length >= 2) {
        const parsed = parsePlainKVBlocks(block);
        if (parsed) {
          html += buildTable(parsed);
          i = j;
          continue;
        }
      }
    }

    // ── Ordered list item ──────────────────────────────────────────────────
    const ordM = trimmed.match(/^(\d+)[.)]\s+(.*)/);
    if (ordM) {
      html += '<ol style="margin:8px 0 8px 20px;padding:0;list-style:decimal">';
      while (i < allLines.length) {
        const oLine = allLines[i].trim();
        const oM    = oLine.match(/^(\d+)[.)]\s+(.*)/);
        if (!oM) break;
        html += `<li style="margin:4px 0;line-height:1.6">${md(oM[2])}</li>`;
        i++;
      }
      html += "</ol>";
      continue;
    }

    // ── Heading: # ## ### ──────────────────────────────────────────────────
    const headM = trimmed.match(/^(#{1,3})\s+(.*)/);
    if (headM) {
      const sz  = ["20px", "17px", "15px"][headM[1].length - 1];
      const fw  = headM[1].length === 1 ? "700" : "600";
      html += `<div style="font-size:${sz};font-weight:${fw};margin:14px 0 6px;color:#1a2e1a;letter-spacing:-0.01em">${md(headM[2])}</div>`;
      i++;
      continue;
    }

    // ── Regular prose ──────────────────────────────────────────────────────
    html += `<div style="line-height:1.75;margin:2px 0;color:#1f2933">${md(trimmed)}</div>`;
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
const FOLDERS: FolderItem[] = [
  { id: "f1", name: "Work chats" },
  { id: "f2", name: "Life chats" },
  { id: "f3", name: "Projects chats" },
  { id: "f4", name: "Clients chats" },
];

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
  <svg width="16" height="16" viewBox="0 0 24 24" fill="white" stroke="none">
    <path d="M22 2L11 13" stroke="white" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round"/>
    <path d="M22 2L15 22L11 13L2 9L22 2Z" fill="white"/>
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
const IconUser = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>
  </svg>
);
const IconAI = () => (
  <svg width="22" height="22" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <linearGradient id="aiGrad" x1="0" y1="0" x2="32" y2="32" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#6fb24f"/>
        <stop offset="100%" stopColor="#2d6b22"/>
      </linearGradient>
    </defs>
    <path d="M16 2 L18 12 L28 16 L18 20 L16 30 L14 20 L4 16 L14 12 Z" fill="url(#aiGrad)" opacity="0.9"/>
    <circle cx="16" cy="16" r="3" fill="white" opacity="0.95"/>
  </svg>
);

// ─── Main Component (with useSearchParams wrapped in Suspense) ────────────────
function HomeContent() {
  const router        = useRouter();
  const searchParams  = useSearchParams();
  const userIdFromUrl = searchParams.get("userId");

  const [input,        setInput]        = useState<string>("");
  const [messages,     setMessages]     = useState<Message[]>([]);
  const [isLoading,    setIsLoading]    = useState<boolean>(false);
  const [sessionId,    setSessionId]    = useState<string>(() => generateSessionId());
  const [searchVal,    setSearchVal]    = useState("");
  const [isRecording,  setIsRecording]  = useState<boolean>(false);
  const [loggedInUser, setLoggedInUser] = useState<string | null>(null);
  const [authChecked,  setAuthChecked]  = useState<boolean>(false);
  const [menuOpen,     setMenuOpen]     = useState(false);

  const messagesEndRef   = useRef<HTMLDivElement | null>(null);
  const inputRef         = useRef<HTMLTextAreaElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const menuRef          = useRef<HTMLDivElement>(null);

  // Close dropdown on outside click
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

  const handleNewChat = () => { setMessages([]); setSessionId(generateSessionId()); };
  const handleLogout  = () => { localStorage.removeItem("loggedInUser"); router.replace("/login"); };

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

  // ── Send & stream ──────────────────────────────────────────────────────────
  const sendMessage = async () => {
    if (!input.trim() || isLoading) return;
    const userText = input.trim();

    setMessages(prev => [...prev, { role: "user", text: userText }]);
    setInput("");
    setIsLoading(true);

    try {
      const res = await fetch("http://127.0.0.1:8001/chat", {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({ query: userText, userId: loggedInUser, sessionId }),
      });
      if (!res.ok) throw new Error(`Server error: ${res.status}`);

      const reader  = res.body?.getReader();
      const decoder = new TextDecoder();
      if (!reader) throw new Error("No response body");

      setIsLoading(false);
      // streaming:true → renders as plain text while chunks arrive
      setMessages(prev => [...prev, { role: "ai" as const, text: "", streaming: true }]);

      let accumulated = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        for (const raw of chunk.split("\n").filter(l => l.trim())) {
          try {
            const json = raw.startsWith("data: ") ? raw.slice(6) : raw;
            const part = extractText(JSON.parse(json));
            if (part) {
              accumulated += part;
              setMessages(prev => {
                const u = [...prev];
                const l = u.length - 1;
                if (u[l]?.role === "ai") u[l] = { role: "ai", text: accumulated, streaming: true };
                return u;
              });
              await new Promise(r => setTimeout(r, 10));
            }
          } catch { /* partial chunk */ }
        }
      }

      // ✅ Stream done: flip streaming:false → formatOutput() runs → table shown
      setMessages(prev => {
        const u = [...prev];
        const l = u.length - 1;
        if (u[l]?.role === "ai") u[l] = { role: "ai", text: accumulated, streaming: false };
        return u;
      });

    } catch (err) {
      console.error("Chat Error:", err);
      setMessages(prev => [...prev, { role: "error", text: "❌ Connection failed. Check backend." }]);
      setIsLoading(false);
    } finally {
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  };

  const isLanding = messages.length === 0;

  if (!authChecked) {
    return (
      <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center",
        background: "radial-gradient(circle at top, #ECFAE5 0, #DDF6D2 35%, #CAE8BD 75%)" }}>
        <span style={{ fontSize: 14, color: "#4b5f45" }}>Checking authentication…</span>
      </div>
    );
  }

  return (
    <div className="app-container">
      <div className="bg-gradient" />

      {/* ── Sidebar ─────────────────────────────────────────────────────── */}
      <aside className="sidebar">
        <div className="sidebar-header">
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <div className="brand-box">
              <Image src="/icon.png" alt="Nanosoft Ask AI" width={20} height={20} style={{ borderRadius: 6 }}/>
            </div>
            <span style={{ fontSize: 14, fontWeight: 600, color: "#1f2933" }}>NANOSOFT ASK AI</span>
          </div>
        </div>

        <div className="search-container">
          <div className="search-input-box">
            <IconSearch/>
            <input type="text" placeholder="Search" value={searchVal} onChange={e => setSearchVal(e.target.value)}/>
          </div>
        </div>

        <div className="sidebar-scroll">
          <div className="section-title">Folders</div>
          {FOLDERS.map(f => (
            <div key={f.id} className="sidebar-item">
              <div className="content">
                <IconFolder/>
                <span style={{ whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{f.name}</span>
              </div>
            </div>
          ))}
        </div>

        <div className="new-chat-container">
          <button className="new-chat-btn" onClick={handleNewChat}>New chat &nbsp;<IconPlus/></button>
        </div>
      </aside>

      {/* ── Main Content ─────────────────────────────────────────────────── */}
      <div className="main-content">

        {/* Header */}
        <header className="chat-header chat-header-transparent">
          <div className="hamburger-wrapper" ref={menuRef}>
            <button className="hamburger-btn" onClick={() => setMenuOpen(p => !p)} title="Menu" aria-label="Open menu">
              <IconHamburger/>
            </button>

            <div className={`profile-dropdown ${menuOpen ? "open" : ""}`}>
              <div className="profile-dropdown-inner">
                <div className="profile-dropdown-item profile-user-row">
                  <div className="profile-avatar">
                    {loggedInUser ? loggedInUser.charAt(0).toUpperCase() : "U"}
                  </div>
                  <div className="profile-user-info">
                    <span className="profile-label">Logged in as</span>
                    <span className="profile-userid">{loggedInUser}</span>
                  </div>
                </div>
                <div className="profile-divider"/>
                <button className="profile-dropdown-item profile-action-btn">
                  <IconUser/><span>Profile</span>
                </button>
                <button className="profile-dropdown-item profile-action-btn profile-logout" onClick={handleLogout}>
                  <IconLogout/><span>Logout</span>
                </button>
              </div>
            </div>
          </div>
        </header>

        {/* Landing */}
        {isLanding && (
          <div className="landing-container">
            <div style={{ marginBottom: 24, opacity: 0.5 }}>
              <Image src="/nanosoft_logo.png" alt="" width={560} height={200}
                style={{ width: "auto", height: "auto", maxWidth: "min(600px,90vw)", maxHeight: 200, objectFit: "contain" }}/>
            </div>
            <div className="landing-card">
              <h1 style={{ fontSize: 24, fontWeight: 700, color: "#1f2933", marginBottom: 10 }}>
                How can I help you today?
              </h1>
              <p style={{ fontSize: 12, color: "#3f5f3a", lineHeight: 1.6, maxWidth: 380, margin: "0 auto 28px" }}>
                Start a conversation to search assets, manage complaints, or check work orders.
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
                          <div dangerouslySetInnerHTML={{ __html: formatOutput(msg.text) }}/>
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
                        borderRadius: "50%", background: "#4a8f3a",
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
          <div className="input-wrapper">
            <textarea
              ref={inputRef}
              className="main-input"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isLoading}
              placeholder="Type your prompt here…"
              rows={1}
            />
            <button className="send-btn" onClick={sendMessage} disabled={isLoading || !input.trim()}>
              <IconSend/>
            </button>
          </div>
          <p className="footer-disclaimer">AI can make mistakes. Consider checking important information.</p>
        </div>

      </div>
    </div>
  );
}

// ─── Main Export with Suspense Boundary ────────────────────────────────────────
export default function Home() {
  return (
    <Suspense fallback={
      <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: "radial-gradient(circle at top, #ECFAE5 0, #DDF6D2 35%, #CAE8BD 75%)" }}>
        <span style={{ fontSize: 14, color: "#4b5f45" }}>Loading…</span>
      </div>
    }>
      <HomeContent />
    </Suspense>
  );
}
