"use client";

import { useState, useRef, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Image from "next/image";

// ─── Types ───────────────────────────────────────────────────────────────────
interface Message {
  role: "user" | "ai" | "error";
  text: string;
}

interface ChatItem {
  id: string;
  title: string;
  preview: string;
}

interface FolderItem {
  id: string;
  name: string;
}

// ─── 1. Fixed Helper: Extract Text from Backend Response ─────────────────────
function extractText(raw: any, depth = 0): string {
  // Stop if too deep or null
  if (depth > 10 || raw == null) return "";

  // Handle Strings (and stringified JSON)
  if (typeof raw === "string") {
    const trimmed = raw.trim();
    // Check if it looks like JSON
    if (trimmed.startsWith("{") || trimmed.startsWith("[")) {
      try {
        return extractText(JSON.parse(trimmed), depth + 1);
      } catch {
        return raw; // If parse fails, treat as normal text
      }
    }
    return raw;
  }

  // Handle Arrays
  if (Array.isArray(raw)) {
    return raw
      .map((item) => extractText(item, depth + 1))
      .filter((text) => text.trim() !== "")
      .join(" ");
  }

  // Handle Objects - Check for specific keys from your Python backend
  if (typeof raw === "object") {
    if (raw.response) return extractText(raw.response, depth + 1); // Matches: return {"response": ...}
    if (raw.content) return extractText(raw.content, depth + 1);
    if (raw.text) return extractText(raw.text, depth + 1);
    if (raw.reply) return extractText(raw.reply, depth + 1);
    // If no specific key is found, return nothing (avoid printing raw JSON)
    return "";
  }

  return String(raw);
}

// ─── Helper: Render Markdown to HTML ─────────────────────────────────────────
function renderMarkdown(text: string, showCursor: boolean = false): string {
  if (!text) return "";

  const lines = text.split("\n");
  let html = "";
  let inList = false;
  let inOrderedList = false;

  for (let i = 0; i < lines.length; i++) {
    let line = lines[i].replace(/\s+$/, "");

    const bulletMatch = line.match(/^[\s]*(?:\*\s+|-\s+|•\s+)(.*)/);
    const orderedMatch = line.match(/^[\s]*(\d+)[.)]\s+(.*)/);

    if (bulletMatch) {
      if (inOrderedList) { html += "</ol>"; inOrderedList = false; }
      if (!inList) { html += '<ul style="margin:10px 0 10px 20px;padding:0;list-style:disc;">'; inList = true; }
      html += `<li style="margin:5px 0;line-height:1.6;color:#000000;">${applyInline(bulletMatch[1])}</li>`;
    } else if (orderedMatch) {
      if (inList) { html += "</ul>"; inList = false; }
      if (!inOrderedList) { html += '<ol style="margin:10px 0 10px 20px;padding:0;list-style:decimal;">'; inOrderedList = true; }
      html += `<li style="margin:5px 0;line-height:1.6;color:#000000;">${applyInline(orderedMatch[2])}</li>`;
    } else {
      if (inList) { html += "</ul>"; inList = false; }
      if (inOrderedList) { html += "</ol>"; inOrderedList = false; }
      if (line.trim() === "") {
        html += '<div style="height:10px;"></div>';
      } else {
        html += `<div style="line-height:1.7;margin:2px 0;color:#000000;">${applyInline(line)}</div>`;
      }
    }
  }
  if (inList) html += "</ul>";
  if (inOrderedList) html += "</ol>";

  if (showCursor) {
    const cursorHtml = '<span style="display:inline-block;width:7px;height:16px;margin-left:4px;background:#3b82f6;border-radius:2px;vertical-align:middle;animation:blink 1s step-end infinite;"></span>';
    const lastClose = html.lastIndexOf("</");
    if (lastClose !== -1) {
      html = html.substring(0, lastClose) + cursorHtml + html.substring(lastClose);
    } else {
      html += cursorHtml;
    }
  }

  return html;
}

function generateSessionId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  // Fallback: UUID v4 using getRandomValues (supported in Node and browsers)
  const bytes = new Uint8Array(16);
  if (typeof crypto !== "undefined" && crypto.getRandomValues) {
    crypto.getRandomValues(bytes);
    bytes[6] = (bytes[6]! & 0x0f) | 0x40;
    bytes[8] = (bytes[8]! & 0x3f) | 0x80;
    const hex = [...bytes].map((b) => b.toString(16).padStart(2, "0")).join("");
    return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
  }
  return "session_" + Math.random().toString(36).substr(2, 9);
}

function applyInline(text: string): string {
  text = text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  text = text.replace(/`([^`]+)`/g, '<code style="background:rgba(0,0,0,0.04);padding:2px 6px;border-radius:4px;font-family:monospace;font-size:13px;color:#000000;">$1</code>');
  text = text.replace(/\*\*(.+?)\*\*/g, '<strong style="color:#000000;font-weight:600;">$1</strong>');
  text = text.replace(/\*(.+?)\*/g, '<em style="color:#111827;font-style:italic;">$1</em>');
  return text;
}

// ─── Static Data ─────────────────────────────────────────────────────────────
const FOLDERS: FolderItem[] = [
  { id: "f1", name: "Work chats" },
  { id: "f2", name: "Life chats" },
  { id: "f3", name: "Projects chats" },
  { id: "f4", name: "Clients chats" },
];

// const CHATS: ChatItem[] = [
//   { id: "c1", title: "Plan a 3-day trip", preview: "It's a plan to the northern lights in Norway..." },
//   { id: "c2", title: "Ideas for a customer loyalty program", preview: "Here are some ideas for a customer loyalty..." },
//   { id: "c3", title: "Help me write", preview: "Here are some gift ideas for your upcoming..." },
// ];
// const CHATS: ChatItem[] = [
//   { id: "c1", title: "Plan a 3-day trip", preview: "It's a plan to the northern lights in Norway..." },
//   { id: "c2", title: "Ideas for a customer loyalty program", preview: "Here are some ideas for a customer loyalty..." },
//   { id: "c3", title: "Help me write", preview: "Here are some gift ideas for your upcoming..." },
// ];

const CATEGORIES = ["Text", "Image", "Video", "Music", "Analytics"];

// ─── Icons ───────────────────────────────────────────────────────────────────
const IconFolder = () => <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z" /></svg>;
const IconChat = () => <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" /></svg>;
const IconPlus = () => <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><path d="M12 5v14M5 12h14" /></svg>;
const IconSearch = () => <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8" /><path d="M21 21l-4.35-4.35" /></svg>;
const IconDots = () => <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="5" r="1.5" /><circle cx="12" cy="12" r="1.5" /><circle cx="12" cy="19" r="1.5" /></svg>;

const IconBot = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#3b82f6" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 8V4H8" />
    <rect width="16" height="12" x="4" y="8" rx="2" />
    <path d="M2 14h2" />
    <path d="M20 14h2" />
    <path d="M15 13v2" />
    <path d="M9 13v2" />
  </svg>
);

const IconAttach = () => <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21.44 11.05l-9.19 9.19a4.5 4.5 0 01-6.36-6.36l9.19-9.19a3 3 0 014.24 4.24l-9.2 9.19a1.5 1.5 0 01-2.12-2.12l8.49-8.48" /></svg>;
const IconSend = () => <svg width="16" height="16" viewBox="0 0 24 24" fill="white" stroke="none"><path d="M22 2L11 13" stroke="white" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round" /><path d="M22 2L15 22L11 13L2 9L22 2Z" fill="white" /></svg>;
const IconMic = ({ isActive }: { isActive: boolean }) => <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={isActive ? "#3b82f6" : "currentColor"} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" fill={isActive ? "#3b82f6" : "none"} /><path d="M19 10v2a7 7 0 0 1-14 0v-2" /><line x1="12" y1="19" x2="12" y2="23" /><line x1="8" y1="23" x2="16" y2="23" /></svg>;

// ─── Main Component ──────────────────────────────────────────────────────────
export default function Home() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const userIdFromUrl = searchParams.get("userId");

  const [input, setInput] = useState<string>("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const isTypingRef = useRef<boolean>(false);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const [sessionId, setSessionId] = useState<string>(() => {
    const id = generateSessionId();
    console.log("[Session] created:", id);
    return id;
  });
  const [searchVal, setSearchVal] = useState("");
  const [activeChatId, setActiveChatId] = useState<string | null>(null);
  const [chatName, setChatName] = useState("");
  const [activeCategory, setActiveCategory] = useState<string | null>(null);

  const [isRecording, setIsRecording] = useState<boolean>(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const [loggedInUser, setLoggedInUser] = useState<string | null>(null);
  const [authChecked, setAuthChecked] = useState<boolean>(false);

  // Client-side auth guard: redirect to login if not authenticated; don't render app until checked
  useEffect(() => {
    if (typeof window === "undefined") return;

    // If login redirected with ?userId=..., persist it and clean the URL
    if (userIdFromUrl) {
      localStorage.setItem("loggedInUser", userIdFromUrl);
      setLoggedInUser(userIdFromUrl);
      setAuthChecked(true);
      router.replace("/");
      return;
    }

    const loggedIn = localStorage.getItem("loggedInUser");
    if (!loggedIn) {
      router.replace("/login");
      return;
    }

    setLoggedInUser(loggedIn);
    setAuthChecked(true);
  }, [router, userIdFromUrl]);

  const handleNewChat = () => {
    const newSessionId = generateSessionId();
    console.log("[Session] created:", newSessionId);
    setMessages([]);       
    setChatName("New Chat"); 
    setSessionId(newSessionId); 
  };

  const handleLogout = () => {
    if (typeof window !== "undefined") {
      localStorage.removeItem("loggedInUser");
    }
    router.replace("/login");
  };

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, isLoading]);

  // Auto-resize the input textarea up to a max height
  const adjustTextareaHeight = () => {
    const el = inputRef.current;
    if (!el) return;
    const maxHeight = 160; // px, roughly several lines
    el.style.height = "0px";
    const newHeight = Math.min(el.scrollHeight, maxHeight);
    el.style.height = `${newHeight}px`;
    el.style.overflowY = el.scrollHeight > maxHeight ? "auto" : "hidden";
  };

  useEffect(() => {
    adjustTextareaHeight();
  }, [input]);

  const toggleRecording = async () => {
    if (isRecording) {
      mediaRecorderRef.current?.stop();
      setIsRecording(false);
    } else {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        const mediaRecorder = new MediaRecorder(stream);
        mediaRecorder.start();
        mediaRecorderRef.current = mediaRecorder;
        setIsRecording(true);
      } catch (error) {
        console.error("Microphone access denied:", error);
        alert("Please allow microphone access.");
      }
    }
  };

  // ─── 2. Fixed sendMessage Function ─────────────────────────────────────────
  const sendMessage = async () => {
    if (!input.trim() || isLoading) return;
    const userText = input.trim();
    
    // Add User Message
    setMessages((prev) => [...prev, { role: "user", text: userText }]);
    setInput("");
    setIsLoading(true);
    const payload = {
      query: userText,
      userId: loggedInUser,
      sessionId: sessionId,
    };
    console.log("[Chat] Request to backend:", payload);


    try {
      const response = await fetch("http://127.0.0.1:8001/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        
      });

      if (!response.ok) throw new Error(`Server error: ${response.status}`);

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      if (!reader) throw new Error("No response body");

      // Add Placeholder for AI Response
      setIsLoading(false);
      isTypingRef.current = false;
      setMessages((prev) => [...prev, { role: "ai", text: "" }]);

      let accumulatedText = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split("\n").filter(line => line.trim() !== "");

        for (const line of lines) {
          try {
            let jsonStr = line;
            if (line.startsWith("data: ")) {
              jsonStr = line.slice(6);
            }

            const textPart = extractText(JSON.parse(jsonStr));
            
            if (textPart) {
              accumulatedText += textPart;
              // Update the LAST message (which is the AI placeholder)
              setMessages((prev) => {
                const updated = [...prev];
                const lastIndex = updated.length - 1;
                if (updated[lastIndex].role === "ai") {
                    updated[lastIndex] = { role: "ai", text: accumulatedText };
                }
                return updated;
              });
              // Tiny delay to reduce render thrashing (optional)
              await new Promise(resolve => setTimeout(resolve, 10));
            }
          } catch (e) {
            // Ignore partial/invalid chunks or non-JSON strings (common in streams)
          }
        }
      }

      isTypingRef.current = false;
    } catch (error) {
      console.error("Chat Error:", error);
      setMessages((prev) => [...prev, { role: "error", text: "❌ Connection failed. Check backend." }]);
      setIsLoading(false);
      isTypingRef.current = false;
    } finally {
      setTimeout(() => {
        inputRef.current?.focus();
      }, 50);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // Enter sends, Shift+Enter makes a new line
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const isLanding = messages.length === 0;

  // Don't render main app until we've checked auth; prevents showing main page before redirect to login
  if (!authChecked) {
    return (
      <div style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "radial-gradient(circle at top, #ECFAE5 0, #DDF6D2 35%, #CAE8BD 75%)",
      }}>
        <div style={{ fontSize: 14, color: "#4b5f45" }}>Checking authentication...</div>
      </div>
    );
  }

  return (
    <div className="app-container">
      {/* Background Gradient */}
      <div className="bg-gradient" />

      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-header">
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <div className="brand-box">
              <Image
                src="/icon.png"
                alt="Nanosoft Ask AI"
                width={20}
                height={20}
                style={{ borderRadius: 6 }}
              />
            </div>
            <span style={{ fontSize: "14px", fontWeight: 600, color: "#1f2933" }}>NANOSOFT ASK AI</span>
          </div>
        </div>

        <div className="search-container">
          <div className="search-input-box">
            <IconSearch />
            <input type="text" placeholder="Search" value={searchVal} onChange={(e) => setSearchVal(e.target.value)} />
          </div>
        </div>

        <div className="sidebar-scroll">
          <div className="section-title">Folders</div>
          {FOLDERS.map((f) => (
            <div key={f.id} className="sidebar-item">
              <div className="content">
                <IconFolder />
                <span
                  style={{
                    whiteSpace: "nowrap",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                  }}
                >
                  {f.name}
                </span>
              </div>
            </div>
          ))}
        </div>
        
        <div className="new-chat-container">
          <button className="new-chat-btn" onClick={handleNewChat}>
            New chat &nbsp;<IconPlus />
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <div className="main-content">
        <header className="chat-header chat-header-transparent">
          <button
            type="button"
            onClick={handleLogout}
            className="logout-btn"
            title="Sign out"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
              <polyline points="16 17 21 12 16 7" />
              <line x1="21" y1="12" x2="9" y2="12" />
            </svg>
            Logout
          </button>
        </header>

        {/* Chat Area */}
        <div className="chat-scroll-area">
          {isLanding && (
            <div className="landing-container">
              <div style={{ marginBottom: "24px", opacity: 0.5 }}>
                <Image
                  src="/nanosoft_logo.png"
                  alt=""
                  width={560}
                  height={200}
                  style={{ width: "auto", height: "auto", maxWidth: "min(600px, 90vw)", maxHeight: "200px", objectFit: "contain" }}
                />
              </div>
              <div className="landing-card">
                <h1 style={{ fontSize: "24px", fontWeight: 700, color: "#1f2933", marginBottom: "10px" }}>How can I help you today?</h1>
                <p style={{ fontSize: "12px", color: "#3f5f3a", lineHeight: 1.6, maxWidth: "380px", margin: "0 auto 28px" }}>Start a conversation to search assets, manage complaints, or check work orders.</p>
                
                {/* <div className="feature-grid">
                  {[{ title: "Search Assets", desc: "Find equipment details." }, { title: "Work Orders", desc: "Check schedules." }, { title: "Complaints", desc: "Track issues." }].map((card, i) => (
                    <div key={i} className="feature-card">
                      <div style={{ fontSize: "12px", fontWeight: 600, color: "#3f5f3a", marginBottom: "5px" }}>{card.title}</div>
                      <div style={{ fontSize: "10px", color: "#4b5f45" }}>{card.desc}</div>
                    </div>
                  ))}
                </div> */}

                {/* <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "6px", flexWrap: "wrap" }}>
                  {CATEGORIES.map((cat) => (
                    <button 
                      key={cat} 
                      className={`cat-pill ${activeCategory === cat ? 'active' : ''}`}
                      onClick={() => setActiveCategory(activeCategory === cat ? null : cat)}
                    >
                      {cat}
                    </button>
                  ))}
                </div> */}
              </div>
            </div>
          )}

          {!isLanding && (
            <div className="messages-container">
              {messages.map((msg, index) => {
                const isUser = msg.role === "user";
                const isError = msg.role === "error";
                const isLastAi = msg.role === "ai" && index === messages.length - 1;
                const showCursor = isLastAi && isTypingRef.current;

                return (
                  <div key={index} className={`message-row ${msg.role}`}>
                    {!isUser && !isError && (
                      <div className="avatar-box">
                        <IconBot />
                      </div>
                    )}

                    <div className={`message-bubble ${msg.role}`}>
                      {(isUser || isError) ? (
                        <>{msg.text}</>
                      ) : (
                        <div className="ai-bubble">
                          <div dangerouslySetInnerHTML={{ __html: renderMarkdown(msg.text, showCursor) }} />
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}

              {isLoading && (
                <div className="loading-indicator">
                  <div className="avatar-box">
                    <IconBot />
                  </div>
                  <div className="loading-dots-box">
                    {[0, 1, 2].map((i) => <span key={i} style={{ display: "inline-block", width: "7px", height: "7px", borderRadius: "50%", background: "#4a8f3a", animation: `bounce 1.2s ease-in-out ${i * 0.2}s infinite` }} />)}
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Input Area */}
        <div className="input-footer">
          <div className="input-wrapper">
            {/* <div className="model-selector">
              <div style={{ width: "14px", height: "14px", borderRadius: "4px", background: "linear-gradient(135deg,#B0DB9C,#6fb24f)", display: "flex", alignItems: "center", justifyContent: "center" }}><svg width="8" height="8" viewBox="0 0 24 24" fill="white"><path d="M12 2L2 7l10 5 10-5-10-5z" stroke="white" strokeWidth="2" fill="none" strokeLinecap="round" /></svg></div>
              <span style={{ fontSize: "11px", color: "#3f5f3a", fontWeight: 600 }}>Bot</span>
            </div> */}

            <textarea
              ref={inputRef}
              className="main-input"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isLoading}
              placeholder="Type your prompt here..."
              rows={1}
            />
            
            {/* <div className="icon-btn"><IconAttach /></div> */}
            {/* <div className={`mic-btn ${isRecording ? "recording" : ""}`} onClick={toggleRecording}>
              <IconMic isActive={isRecording} />
              {isRecording && <span style={{ position: "absolute", top: "-2px", right: "-2px", width: "8px", height: "8px", background: "#ef4444", borderRadius: "50%", border: "1.5px solid rgba(18,30,20,0.85)", animation: "blink 1s ease-in-out infinite" }} />}
            </div> */}
            
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