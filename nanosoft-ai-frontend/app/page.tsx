"use client";

import { useState, useRef, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Image from "next/image";

// ─── Types ───────────────────────────────────────────────────────────────────
interface Message {
  role: "user" | "ai" | "error";
  text: string;
  streaming?: boolean;
}

interface FolderItem {
  id: string;
  name: string;
}

// ─── Helper: Extract Text from Backend Response ───────────────────────────────
function extractText(raw: any, depth = 0): string {
  if (depth > 10 || raw == null) return "";
  if (typeof raw === "string") {
    const trimmed = raw.trim();
    if (trimmed.startsWith("{") || trimmed.startsWith("[")) {
      try { return extractText(JSON.parse(trimmed), depth + 1); } catch { return raw; }
    }
    return raw;
  }
  if (Array.isArray(raw)) {
    return raw.map((item) => extractText(item, depth + 1)).filter((t) => t.trim() !== "").join(" ");
  }
  if (typeof raw === "object") {
    if (raw.response) return extractText(raw.response, depth + 1);
    if (raw.content)  return extractText(raw.content,  depth + 1);
    if (raw.text)     return extractText(raw.text,     depth + 1);
    if (raw.reply)    return extractText(raw.reply,    depth + 1);
    return "";
  }
  return String(raw);
}

// ─── Escape HTML ─────────────────────────────────────────────────────────────
function escapeHtml(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

// ─── Inline markdown (bold, italic, code) ────────────────────────────────────
function applyInline(text: string): string {
  text = escapeHtml(text);
  text = text.replace(/`([^`]+)`/g, '<code style="background:rgba(0,0,0,0.06);padding:2px 6px;border-radius:4px;font-family:monospace;font-size:12px;">$1</code>');
  text = text.replace(/\*\*(.+?)\*\*/g, '<strong style="font-weight:600;">$1</strong>');
  text = text.replace(/\*(.+?)\*/g,     '<em style="font-style:italic;">$1</em>');
  return text;
}

// ─────────────────────────────────────────────────────────────────────────────
// CORE: Parse one bullet line into key-value pairs
//
// Works by finding every "Key:" position in the string, then slicing
// the text between consecutive key positions to get each value.
// This correctly handles values that contain commas, e.g.:
//   "Location: Building 1 - Residential High Rise, Floor 16"
// ─────────────────────────────────────────────────────────────────────────────
function parseBulletToKV(rawLine: string): Record<string, string> | null {
  // Strip leading bullet / number markers
  const line = rawLine.replace(/^[\s]*(?:[-*•]|\d+[.)]) ?/, "").trim();
  if (!line) return null;

  // Find every occurrence of "SomeKey: " preceded by start-of-string or ", "
  // Key = 1–4 words made of letters and spaces (no digits)
  const KEY_RE = /(?:^|(?:,\s+))([A-Za-z][A-Za-z ]{0,25}?):\s*/g;

  const hits: { key: string; valStart: number; matchStart: number }[] = [];
  let m: RegExpExecArray | null;

  while ((m = KEY_RE.exec(line)) !== null) {
    const key = m[1].trim();
    if (!key || /\d/.test(key)) continue;          // reject keys with digits
    hits.push({ key, valStart: m.index + m[0].length, matchStart: m.index });
  }

  if (hits.length < 2) return null;                // need at least 2 KV pairs

  const result: Record<string, string> = {};
  for (let i = 0; i < hits.length; i++) {
    const { key, valStart } = hits[i];
    const valEnd = i + 1 < hits.length ? hits[i + 1].matchStart : line.length;
    const value  = line.slice(valStart, valEnd).replace(/,\s*$/, "").trim();
    result[key]  = value || "—";
  }

  return Object.keys(result).length >= 2 ? result : null;
}

// ─── Detect whether a bullet block should become a table ─────────────────────
function isBulletTable(lines: string[]): boolean {
  if (lines.length < 1) return false;
  const parsed = lines.map(parseBulletToKV);
  const valid  = parsed.filter(Boolean).length;
  return valid >= Math.max(1, Math.ceil(lines.length * 0.5));
}

// ─── Render a status value as a coloured badge ───────────────────────────────
function renderStatusBadge(value: string): string {
  const v   = value.toLowerCase();
  const cls = v === "online"  ? "status-online"
            : v === "offline" ? "status-offline"
            : "status-neutral";
  return `<span class="status-badge ${cls}">${escapeHtml(value)}</span>`;
}

// ─── Convert detected KV bullet lines → HTML table ───────────────────────────
function bulletLinesToTable(lines: string[]): string {
  const rows = lines.map(parseBulletToKV).filter(Boolean) as Record<string, string>[];
  if (rows.length === 0) return "";

  // Gather all column keys in order of first appearance
  const cols: string[] = [];
  rows.forEach(row => {
    Object.keys(row).forEach(k => { if (!cols.includes(k)) cols.push(k); });
  });

  const thead = `<thead><tr>${cols.map(k => `<th>${escapeHtml(k)}</th>`).join("")}</tr></thead>`;

  const tbody = "<tbody>" + rows.map(row =>
    "<tr>" + cols.map(col => {
      const val = row[col] ?? "—";
      // Auto-detect Status column for badge rendering
      const cell = col.toLowerCase() === "status" ? renderStatusBadge(val) : escapeHtml(val);
      return `<td>${cell}</td>`;
    }).join("") + "</tr>"
  ).join("") + "</tbody>";

  return `<div class="table-wrapper"><table class="ai-table">${thead}${tbody}</table></div>`;
}

// ─── Render pipe-style markdown table (| col | col |) ────────────────────────
function renderPipeTable(tableLines: string[]): string {
  const rows = tableLines.map(line =>
    line.split("|").map(c => c.trim()).filter((_, i, a) => i > 0 && i < a.length - 1)
  );
  if (rows.length < 2) return tableLines.map(applyInline).join("<br/>");

  const thead = `<thead><tr>${rows[0].map(h => `<th>${applyInline(h)}</th>`).join("")}</tr></thead>`;
  const tbody = "<tbody>" + rows.slice(2).map(row =>
    `<tr>${row.map(cell => `<td>${applyInline(cell)}</td>`).join("")}</tr>`
  ).join("") + "</tbody>";

  return `<div class="table-wrapper"><table class="ai-table">${thead}${tbody}</table></div>`;
}

// ─── Master markdown renderer ─────────────────────────────────────────────────
function renderMarkdown(text: string): string {
  if (!text) return "";

  const lines = text.split("\n");
  let   html  = "";

  let inOrderedList = false;
  let pipeBuffer:   string[] = [];
  let bulletBuffer: string[] = [];

  const flushPipe = () => {
    if (pipeBuffer.length) { html += renderPipeTable(pipeBuffer); pipeBuffer = []; }
  };

  const flushBullets = () => {
    if (!bulletBuffer.length) return;
    html += isBulletTable(bulletBuffer)
      ? bulletLinesToTable(bulletBuffer)
      : '<ul style="margin:10px 0 10px 20px;padding:0;list-style:disc;">'
        + bulletBuffer.map(bl => {
            const t = bl.replace(/^[\s]*(?:[-*•]|\d+[.)]) ?/, "").trim();
            return `<li style="margin:5px 0;line-height:1.6;">${applyInline(t)}</li>`;
          }).join("")
        + "</ul>";
    bulletBuffer = [];
  };

  for (const rawLine of lines) {
    const line = rawLine.replace(/\s+$/, "");

    // ── Pipe table row ──────────────────────────────────────────────────
    if (/^\|.+\|$/.test(line.trim())) {
      flushBullets();
      if (inOrderedList) { html += "</ol>"; inOrderedList = false; }
      pipeBuffer.push(line.trim());
      continue;
    }
    flushPipe();

    // ── Bullet point ────────────────────────────────────────────────────
    if (/^[\s]*(?:[-*•]) /.test(line)) {
      if (inOrderedList) { html += "</ol>"; inOrderedList = false; }
      bulletBuffer.push(line);
      continue;
    }

    // ── Ordered list ────────────────────────────────────────────────────
    const ordM = line.match(/^[\s]*(\d+)[.)]\s+(.*)/);
    if (ordM) {
      flushBullets();
      if (!inOrderedList) { html += '<ol style="margin:10px 0 10px 20px;padding:0;list-style:decimal;">'; inOrderedList = true; }
      html += `<li style="margin:5px 0;line-height:1.6;">${applyInline(ordM[2])}</li>`;
      continue;
    }

    // ── Regular line / blank ────────────────────────────────────────────
    flushBullets();
    if (inOrderedList) { html += "</ol>"; inOrderedList = false; }
    html += line.trim() === ""
      ? '<div style="height:8px;"></div>'
      : `<div style="line-height:1.7;margin:2px 0;">${applyInline(line)}</div>`;
  }

  flushBullets();
  flushPipe();
  if (inOrderedList) html += "</ol>";

  return html;
}

// ─── Session ID ──────────────────────────────────────────────────────────────
function generateSessionId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function")
    return crypto.randomUUID();
  const b = new Uint8Array(16);
  crypto.getRandomValues(b);
  b[6] = (b[6]! & 0x0f) | 0x40;
  b[8] = (b[8]! & 0x3f) | 0x80;
  const h = [...b].map(x => x.toString(16).padStart(2,"0")).join("");
  return `${h.slice(0,8)}-${h.slice(8,12)}-${h.slice(12,16)}-${h.slice(16,20)}-${h.slice(20)}`;
}

// ─── Static sidebar data ──────────────────────────────────────────────────────
const FOLDERS: FolderItem[] = [
  { id: "f1", name: "Work chats" },
  { id: "f2", name: "Life chats" },
  { id: "f3", name: "Projects chats" },
  { id: "f4", name: "Clients chats" },
];

// ─── Icons ────────────────────────────────────────────────────────────────────
const IconFolder = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z" />
  </svg>
);
const IconPlus = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
    <path d="M12 5v14M5 12h14" />
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
    <line x1="3" y1="6"  x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/>
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
        <stop offset="0%" stopColor="#6fb24f"/><stop offset="100%" stopColor="#2d6b22"/>
      </linearGradient>
    </defs>
    <path d="M16 2 L18 12 L28 16 L18 20 L16 30 L14 20 L4 16 L14 12 Z" fill="url(#aiGrad)" opacity="0.9"/>
    <circle cx="16" cy="16" r="3" fill="white" opacity="0.95"/>
  </svg>
);

// ─── Main Component ───────────────────────────────────────────────────────────
export default function Home() {
  const router        = useRouter();
  const searchParams  = useSearchParams();
  const userIdFromUrl = searchParams.get("userId");

  const [input,        setInput]        = useState<string>("");
  const [messages,     setMessages]     = useState<Message[]>([]);
  const [isLoading,    setIsLoading]    = useState<boolean>(false);
  const [sessionId,    setSessionId]    = useState<string>(() => generateSessionId());
  const [searchVal,    setSearchVal]    = useState("");
  const [chatName,     setChatName]     = useState("");
  const [isRecording,  setIsRecording]  = useState<boolean>(false);
  const [loggedInUser, setLoggedInUser] = useState<string | null>(null);
  const [authChecked,  setAuthChecked]  = useState<boolean>(false);
  const [menuOpen,     setMenuOpen]     = useState(false);

  const messagesEndRef   = useRef<HTMLDivElement | null>(null);
  const isTypingRef      = useRef<boolean>(false);
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

  // Scroll to bottom when messages update
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, isLoading]);

  // Auto-resize textarea
  const adjustTextareaHeight = () => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "0px";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
    el.style.overflowY = el.scrollHeight > 160 ? "auto" : "hidden";
  };
  useEffect(() => { adjustTextareaHeight(); }, [input]);

  const handleNewChat = () => {
    setMessages([]);
    setChatName("New Chat");
    setSessionId(generateSessionId());
  };

  const handleLogout = () => {
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
        const rec = new MediaRecorder(stream);
        rec.start();
        mediaRecorderRef.current = rec;
        setIsRecording(true);
      } catch {
        alert("Please allow microphone access.");
      }
    }
  };

  // ── Send message & stream response ──────────────────────────────────────────
  const sendMessage = async () => {
    if (!input.trim() || isLoading) return;
    const userText = input.trim();

    setMessages(prev => [...prev, { role: "user", text: userText }]);
    setInput("");
    setIsLoading(true);

    try {
      const response = await fetch("http://127.0.0.1:8001/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: userText, userId: loggedInUser, sessionId }),
      });

      if (!response.ok) throw new Error(`Server error: ${response.status}`);

      const reader  = response.body?.getReader();
      const decoder = new TextDecoder();
      if (!reader) throw new Error("No response body");

      // Add AI placeholder with streaming: true — renders as plain text during stream
      setIsLoading(false);
      setMessages(prev => [...prev, { role: "ai" as const, text: "", streaming: true }]);

      let accumulated = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        for (const line of chunk.split("\n").filter(l => l.trim())) {
          try {
            const jsonStr  = line.startsWith("data: ") ? line.slice(6) : line;
            const textPart = extractText(JSON.parse(jsonStr));
            if (textPart) {
              accumulated += textPart;
              // Keep streaming:true → renders as plain pre-wrap text
              setMessages(prev => {
                const updated = [...prev];
                const last    = updated.length - 1;
                if (updated[last]?.role === "ai") {
                  updated[last] = { role: "ai", text: accumulated, streaming: true };
                }
                return updated;
              });
              await new Promise(r => setTimeout(r, 10));
            }
          } catch { /* partial chunk */ }
        }
      }

      // ✅ Stream done — flip streaming:false → triggers renderMarkdown → table appears
      setMessages(prev => {
        const updated = [...prev];
        const last    = updated.length - 1;
        if (updated[last]?.role === "ai") {
          updated[last] = { role: "ai", text: accumulated, streaming: false };
        }
        return updated;
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
      <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: "radial-gradient(circle at top, #ECFAE5 0, #DDF6D2 35%, #CAE8BD 75%)" }}>
        <span style={{ fontSize: 14, color: "#4b5f45" }}>Checking authentication…</span>
      </div>
    );
  }

  return (
    <div className="app-container">
      <div className="bg-gradient" />

      {/* ── Sidebar ──────────────────────────────────────────────────────── */}
      <aside className="sidebar">
        <div className="sidebar-header">
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <div className="brand-box">
              <Image src="/icon.png" alt="Nanosoft Ask AI" width={20} height={20} style={{ borderRadius: 6 }} />
            </div>
            <span style={{ fontSize: 14, fontWeight: 600, color: "#1f2933" }}>NANOSOFT ASK AI</span>
          </div>
        </div>

        <div className="search-container">
          <div className="search-input-box">
            <IconSearch />
            <input type="text" placeholder="Search" value={searchVal} onChange={e => setSearchVal(e.target.value)} />
          </div>
        </div>

        <div className="sidebar-scroll">
          <div className="section-title">Folders</div>
          {FOLDERS.map(f => (
            <div key={f.id} className="sidebar-item">
              <div className="content">
                <IconFolder />
                <span style={{ whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{f.name}</span>
              </div>
            </div>
          ))}
        </div>

        <div className="new-chat-container">
          <button className="new-chat-btn" onClick={handleNewChat}>New chat &nbsp;<IconPlus /></button>
        </div>
      </aside>

      {/* ── Main Content ─────────────────────────────────────────────────── */}
      <div className="main-content">

        {/* Header */}
        <header className="chat-header chat-header-transparent">
          <div className="hamburger-wrapper" ref={menuRef}>
            <button className="hamburger-btn" onClick={() => setMenuOpen(p => !p)} title="Menu" aria-label="Open menu">
              <IconHamburger />
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
                <div className="profile-divider" />
                <button className="profile-dropdown-item profile-action-btn"><IconUser /><span>Profile</span></button>
                <button className="profile-dropdown-item profile-action-btn profile-logout" onClick={handleLogout}>
                  <IconLogout /><span>Logout</span>
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
                style={{ width: "auto", height: "auto", maxWidth: "min(600px,90vw)", maxHeight: 200, objectFit: "contain" }} />
            </div>
            <div className="landing-card">
              <h1 style={{ fontSize: 24, fontWeight: 700, color: "#1f2933", marginBottom: 10 }}>How can I help you today?</h1>
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
                    {!isUser && !isError && <div className="avatar-box"><IconAI /></div>}

                    <div className={`message-bubble ${msg.role}`}>
                      {isUser || isError ? (
                        // User / error — plain text
                        <>{msg.text}</>

                      ) : isStreaming ? (
                        // ── STREAMING: plain pre-wrap + blinking cursor ──────
                        <div className="ai-bubble streaming-text">
                          {msg.text}
                          <span className="stream-cursor" />
                        </div>

                      ) : (
                        // ── COMPLETE: full markdown with auto-table ───────────
                        <div className="ai-bubble">
                          <div dangerouslySetInnerHTML={{ __html: renderMarkdown(msg.text) }} />
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}

              {isLoading && (
                <div className="loading-indicator">
                  <div className="avatar-box"><IconAI /></div>
                  <div className="loading-dots-box">
                    {[0,1,2].map(i => (
                      <span key={i} style={{
                        display: "inline-block", width: 7, height: 7, borderRadius: "50%", background: "#4a8f3a",
                        animation: `bounce 1.2s ease-in-out ${i*0.2}s infinite`,
                      }} />
                    ))}
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
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
              <IconSend />
            </button>
          </div>
          <p className="footer-disclaimer">AI can make mistakes. Consider checking important information.</p>
        </div>

      </div>
    </div>
  );
}
